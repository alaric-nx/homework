from __future__ import annotations

import asyncio
import logging
import time
import uuid

from app.core.models import HomeworkParseResult, Task, TaskStatus

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SEC = 30
TIMEOUT_ERROR_CODE = "TIMEOUT"
TIMEOUT_ERROR_MESSAGE = "Task timed out before completion."

_ACTIVE_STATUSES = {TaskStatus.PENDING, TaskStatus.PROCESSING}
_TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}


class TaskStore:
    """In-memory task store with coroutine-safe access, timeout, and cleanup.

    单进程 asyncio 模型下使用 asyncio.Lock 保护内部 dict，
    不需要多线程锁。后续可替换为 Redis 等外部存储。
    """

    def __init__(self, timeout_sec: int = 60, retention_sec: int = 600) -> None:
        self.timeout_sec = timeout_sec
        self.retention_sec = retention_sec
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def create(self, image_hash: str, model: str) -> Task:
        """Create a new pending task with a UUID v4 identifier."""
        now = time.time()
        task = Task(
            task_id=str(uuid.uuid4()),
            status=TaskStatus.PENDING,
            image_hash=image_hash,
            model=model,
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._tasks[task.task_id] = task
        logger.info(
            "task_created task_id=%s image_hash=%s model=%s",
            task.task_id,
            image_hash,
            model or "<default>",
        )
        return task

    async def get(self, task_id: str) -> Task | None:
        """Return the task for the given id, or None if it does not exist."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: HomeworkParseResult | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> Task | None:
        """Update a task's status and optional result/error fields.

        Returns the updated task, or None if the task no longer exists.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("task_update_missing task_id=%s", task_id)
                return None
            task.status = status
            if result is not None:
                task.result = result
            if error_code is not None:
                task.error_code = error_code
            if error_message is not None:
                task.error_message = error_message
            task.updated_at = time.time()
        logger.info("task_updated task_id=%s status=%s", task_id, status.value)
        return task

    async def start_cleanup_loop(self) -> None:
        """Start the background cleanup loop if it is not already running."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            "task_cleanup_started interval=%ss timeout=%ss retention=%ss",
            CLEANUP_INTERVAL_SEC,
            self.timeout_sec,
            self.retention_sec,
        )

    async def stop_cleanup_loop(self) -> None:
        """Stop the background cleanup loop and wait for it to finish."""
        if self._cleanup_task is None:
            return
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        finally:
            self._cleanup_task = None
        logger.info("task_cleanup_stopped")

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SEC)
                await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning("task_cleanup_error error=%s", exc)

    async def sweep(self, now: float | None = None) -> None:
        """Run a single cleanup pass.

        - pending/processing older than timeout_sec → mark failed(TIMEOUT)
        - completed/failed older than retention_sec → remove from store
        """
        current = time.time() if now is None else now
        timed_out: list[str] = []
        removed: list[str] = []
        async with self._lock:
            for task_id, task in list(self._tasks.items()):
                if (
                    task.status in _ACTIVE_STATUSES
                    and current - task.created_at > self.timeout_sec
                ):
                    task.status = TaskStatus.FAILED
                    task.error_code = TIMEOUT_ERROR_CODE
                    task.error_message = TIMEOUT_ERROR_MESSAGE
                    task.updated_at = current
                    timed_out.append(task_id)
                    continue
                if (
                    task.status in _TERMINAL_STATUSES
                    and current - task.updated_at > self.retention_sec
                ):
                    del self._tasks[task_id]
                    removed.append(task_id)
        if timed_out:
            logger.info("task_cleanup_timed_out count=%s", len(timed_out))
        if removed:
            logger.info("task_cleanup_removed count=%s", len(removed))
