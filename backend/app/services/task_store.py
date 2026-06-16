from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from app.core.models import HomeworkParseResult, Task, TaskStatus

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SEC = 30
TIMEOUT_ERROR_CODE = "TIMEOUT"
TIMEOUT_ERROR_MESSAGE = "Task timed out before completion."

_ACTIVE_STATUSES = {TaskStatus.PENDING, TaskStatus.PROCESSING}
_TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}
TASK_RESULT_SCHEMA_VERSION = 3


class TaskStore:
    """In-memory task store with coroutine-safe access, timeout, and cleanup.

    单进程 asyncio 模型下使用 asyncio.Lock 保护内部 dict，
    不需要多线程锁。后续可替换为 Redis 等外部存储。
    """

    def __init__(
        self,
        timeout_sec: int = 60,
        retention_sec: int = 600,
        job_dir: str | Path | None = None,
    ) -> None:
        self.timeout_sec = timeout_sec
        self.retention_sec = retention_sec
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        self.job_dir = Path(job_dir) if job_dir else Path(__file__).resolve().parents[2] / "job"
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def _save_task_to_disk(self, task: Task) -> None:
        try:
            data = {
                "schema_version": TASK_RESULT_SCHEMA_VERSION,
                "task_id": task.task_id,
                "status": task.status.value,
                "image_hash": task.image_hash,
                "model": task.model,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "result": task.result.model_dump() if task.result else None,
                "error_code": task.error_code,
                "error_message": task.error_message,
            }
            file_path = self.job_dir / f"{task.task_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("task_saved_to_disk task_id=%s", task.task_id)
        except Exception as e:
            logger.error("failed_to_save_task_to_disk task_id=%s: %s", task.task_id, e)

    def _load_task_from_disk(self, task_id: str) -> Task | None:
        file_path = self.job_dir / f"{task_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("schema_version") != TASK_RESULT_SCHEMA_VERSION:
                logger.info(
                    "task_disk_cache_schema_mismatch task_id=%s found=%s expected=%s",
                    task_id,
                    data.get("schema_version"),
                    TASK_RESULT_SCHEMA_VERSION,
                )
                file_path.unlink(missing_ok=True)
                return None

            status = TaskStatus(data["status"])
            updated_at = data["updated_at"]
            if (
                status in _TERMINAL_STATUSES
                and time.time() - updated_at > self.retention_sec
            ):
                logger.info("task_disk_cache_expired task_id=%s", task_id)
                file_path.unlink(missing_ok=True)
                return None
            
            result_data = data.get("result")
            result = None
            if result_data:
                result = HomeworkParseResult.model_validate(result_data)
                
            task = Task(
                task_id=data["task_id"],
                status=status,
                image_hash=data["image_hash"],
                model=data["model"],
                created_at=data["created_at"],
                updated_at=updated_at,
                result=result,
                error_code=data.get("error_code"),
                error_message=data.get("error_message"),
            )
            logger.info("task_loaded_from_disk task_id=%s", task_id)
            return task
        except Exception as e:
            logger.error("failed_to_load_task_from_disk task_id=%s: %s", task_id, e)
            return None

    async def create(self, image_hash: str, model: str, force: bool = False) -> Task:
        """Create a new pending task or reuse an existing task unless force is True."""
        now = time.time()
        task_id = image_hash
        async with self._lock:
            # 如果不是强制重试，尝试复用
            if not force:
                # 1. 尝试从内存读取
                if task_id in self._tasks:
                    existing = self._tasks[task_id]
                    if existing.status != TaskStatus.FAILED:
                        logger.info("task_reused_from_memory task_id=%s status=%s", task_id, existing.status.value)
                        return existing

                # 2. 尝试从磁盘加载
                disk_task = self._load_task_from_disk(task_id)
                if disk_task:
                    if disk_task.status != TaskStatus.FAILED:
                        self._tasks[task_id] = disk_task
                        logger.info("task_reused_from_disk task_id=%s status=%s", task_id, disk_task.status.value)
                        return disk_task

            # 3. 创建全新任务（如果是强制重试或者未找到缓存）
            task = Task(
                task_id=task_id,
                status=TaskStatus.PENDING,
                image_hash=image_hash,
                model=model,
                created_at=now,
                updated_at=now,
            )
            self._tasks[task_id] = task
            self._save_task_to_disk(task)
            if force:
                logger.info("task_force_recreated task_id=%s", task_id)

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
            # 优先从内存读取
            task = self._tasks.get(task_id)
            if task is not None:
                return task
                
            # 内存没有，从磁盘加载
            disk_task = self._load_task_from_disk(task_id)
            if disk_task is not None:
                self._tasks[task_id] = disk_task
                return disk_task
                
            return None

    async def delete(self, task_id: str) -> bool:
        """Remove the task from memory and delete its JSON config from disk."""
        async with self._lock:
            # 1. 尝试从内存中移除
            in_memory = self._tasks.pop(task_id, None) is not None
            
            # 2. 尝试从磁盘中删除
            file_path = self.job_dir / f"{task_id}.json"
            on_disk = False
            if file_path.exists():
                try:
                    file_path.unlink(missing_ok=True)
                    on_disk = True
                except Exception as e:
                    logger.error("failed_to_delete_task_from_disk task_id=%s: %s", task_id, e)
                    
            if in_memory or on_disk:
                logger.info("task_deleted task_id=%s in_memory=%s on_disk=%s", task_id, in_memory, on_disk)
                return True
            return False

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
                # 尝试从磁盘加载
                task = self._load_task_from_disk(task_id)
                if task is None:
                    logger.warning("task_update_missing task_id=%s", task_id)
                    return None
                self._tasks[task_id] = task

            task.status = status
            if result is not None:
                task.result = result
            if error_code is not None:
                task.error_code = error_code
            if error_message is not None:
                task.error_message = error_message
            task.updated_at = time.time()

            self._save_task_to_disk(task)

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
                    file_path = self.job_dir / f"{task_id}.json"
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception as e:
                        logger.error(
                            "failed_to_delete_expired_task_from_disk task_id=%s: %s",
                            task_id,
                            e,
                        )
                    removed.append(task_id)
        if timed_out:
            logger.info("task_cleanup_timed_out count=%s", len(timed_out))
        if removed:
            logger.info("task_cleanup_removed count=%s", len(removed))
