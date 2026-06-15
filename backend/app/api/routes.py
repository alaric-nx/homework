from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import get_pipeline, get_task_store
from app.core.errors import AppError
from app.core.models import (
    ParseSubmitResponse,
    TaskStatus,
    TaskStatusResponse,
)
from app.services.parse_pipeline import ParsePipeline
from app.services.task_store import TaskStore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def _run_parse_task(
    task_store: TaskStore,
    pipeline: ParsePipeline,
    task_id: str,
    image_bytes: bytes,
    model: str | None,
) -> None:
    """Background coroutine that runs the parse pipeline and updates task state."""
    await task_store.update_status(task_id, TaskStatus.PROCESSING)
    try:
        result = await pipeline.run(image_bytes=image_bytes, model=model)
        await task_store.update_status(
            task_id, TaskStatus.COMPLETED, result=result
        )
    except AppError as exc:
        logger.warning(
            "parse_task_failed task_id=%s error_code=%s detail=%s",
            task_id,
            exc.code,
            exc.detail,
        )
        await task_store.update_status(
            task_id,
            TaskStatus.FAILED,
            error_code=exc.code,
            error_message=exc.detail,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("parse_task_unexpected_error task_id=%s", task_id)
        await task_store.update_status(
            task_id,
            TaskStatus.FAILED,
            error_code="INTERNAL_ERROR",
            error_message=str(exc),
        )


@router.post(
    "/v1/homework/parse",
    response_model=ParseSubmitResponse,
    status_code=202,
)
async def submit_parse(
    pipeline: Annotated[ParsePipeline, Depends(get_pipeline)],
    task_store: Annotated[TaskStore, Depends(get_task_store)],
    request: Request,
    model: str | None = Query(default=None),
) -> ParseSubmitResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    body = await request.body()

    if not body or (
        "image/" not in content_type
        and "application/octet-stream" not in content_type
    ):
        raise AppError(
            "INVALID_REQUEST",
            "Please send raw image bytes in request body "
            "(content-type: image/jpeg|image/png|application/octet-stream).",
        )

    image_hash = hashlib.md5(body).hexdigest()
    model_value = (model or "").strip()
    task = await task_store.create(image_hash=image_hash, model=model_value)

    asyncio.create_task(
        _run_parse_task(
            task_store=task_store,
            pipeline=pipeline,
            task_id=task.task_id,
            image_bytes=body,
            model=model_value or None,
        )
    )

    logger.info(
        "parse_submitted task_id=%s image_hash=%s model=%s size=%s",
        task.task_id,
        image_hash,
        model_value or "<default>",
        len(body),
    )
    return ParseSubmitResponse(
        task_id=task.task_id,
        status=task.status.value,
        image_hash=image_hash,
    )


@router.get("/v1/homework/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task(
    task_store: Annotated[TaskStore, Depends(get_task_store)],
    task_id: str,
):
    task = await task_store.get(task_id)
    if task is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "TASK_NOT_FOUND",
                "message": "Task with given ID does not exist.",
            },
        )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        image_hash=task.image_hash,
        model=task.model or "default",
        result=task.result,
        error_code=task.error_code,
        error_message=task.error_message,
    )
