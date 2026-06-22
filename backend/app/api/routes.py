from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app.api.deps import get_notebook_store, get_pipeline, get_task_store
from app.core.errors import AppError
from app.core.models import (
    AuthResponse,
    CreateNotebookTaskRequest,
    CreateStudentRequest,
    CreateTaskBlockRequest,
    LoginRequest,
    MeResponse,
    ParseSubmitResponse,
    RegisterRequest,
    SetCollectionRequest,
    TaskStatus,
    TaskStatusResponse,
    UpdateStudentRequest,
    UpdateTaskBlockCropRequest,
)
from app.services.notebook_store import CollectionType, NotebookStore
from app.services.parse_pipeline import ParsePipeline
from app.services.task_store import TaskStore

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_auth(
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
    authorization: str | None = Header(default=None),
) -> dict:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise AppError("UNAUTHORIZED", "missing bearer token.")
    return notebook_store.authenticate(authorization[len(prefix):])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/auth/register", response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> AuthResponse:
    result = notebook_store.register_user(
        username=payload.username,
        password=payload.password,
    )
    return AuthResponse(**result)


@router.post("/v1/auth/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> AuthResponse:
    return AuthResponse(**notebook_store.login(account=payload.account, password=payload.password))


@router.get("/v1/auth/me", response_model=MeResponse)
async def me(auth: Annotated[dict, Depends(_require_auth)]) -> MeResponse:
    return MeResponse(user=auth["user"], tenant=auth["tenant"])


@router.get("/v1/tenants/me")
async def get_my_tenant(auth: Annotated[dict, Depends(_require_auth)]) -> dict:
    return auth["tenant"]


@router.post("/v1/students")
async def create_student(
    payload: CreateStudentRequest,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return notebook_store.create_student(
        tenant_id=auth["tenant_id"],
        name=payload.name,
        nickname=payload.nickname,
        grade=payload.grade,
        school=payload.school,
    )


@router.get("/v1/students")
async def list_students(
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return {"items": notebook_store.list_students(tenant_id=auth["tenant_id"])}


@router.post("/v1/assets")
async def create_asset(
    request: Request,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
    owner_type: str = Query(min_length=1),
    owner_id: str = Query(min_length=1),
    asset_type: str = Query(min_length=1),
) -> dict:
    body = await request.body()
    return notebook_store.create_asset(
        tenant_id=auth["tenant_id"],
        owner_type=owner_type,
        owner_id=owner_id,
        asset_type=asset_type,
        content_type=request.headers.get("content-type"),
        data=body,
    )


@router.get("/v1/assets/{asset_id}/content")
async def get_asset_content(
    asset_id: str,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> FileResponse:
    path, content_type = notebook_store.get_asset_file(
        tenant_id=auth["tenant_id"],
        asset_id=asset_id,
    )
    return FileResponse(path, media_type=content_type)


@router.patch("/v1/students/{student_id}")
async def update_student(
    student_id: str,
    payload: UpdateStudentRequest,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return notebook_store.update_student(
        tenant_id=auth["tenant_id"],
        student_id=student_id,
        name=payload.name,
        nickname=payload.nickname,
        grade=payload.grade,
        school=payload.school,
    )


@router.delete("/v1/students/{student_id}")
async def delete_student(
    student_id: str,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict[str, str]:
    notebook_store.delete_student(tenant_id=auth["tenant_id"], student_id=student_id)
    return {"status": "ok"}


@router.post("/v1/notebook/tasks")
async def create_notebook_task(
    payload: CreateNotebookTaskRequest,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return notebook_store.create_parse_task_stub(
        tenant_id=auth["tenant_id"],
        student_id=payload.student_id,
        user_id=auth["user_id"],
        subject=payload.subject,
        task_id=payload.task_id,
        status=payload.status,
        original_asset_id=payload.original_asset_id,
        result=payload.result,
    )


@router.post("/v1/task-blocks")
async def create_task_block(
    payload: CreateTaskBlockRequest,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return notebook_store.create_task_block(
        tenant_id=auth["tenant_id"],
        student_id=payload.student_id,
        task_id=payload.task_id,
        source_block_id=payload.source_block_id,
        title=payload.title,
        question_text=payload.question_text,
        answer_text=payload.answer_text,
        solution_text=payload.solution_text,
        bbox=payload.bbox,
        crop_asset_id=payload.crop_asset_id,
    )


@router.get("/v1/task-blocks/{task_block_id}")
async def get_task_block(
    task_block_id: str,
    student_id: str = Query(min_length=1),
    auth: dict = Depends(_require_auth),
    notebook_store: NotebookStore = Depends(get_notebook_store),
) -> dict:
    return notebook_store.get_task_block_detail(
        tenant_id=auth["tenant_id"],
        student_id=student_id,
        task_block_id=task_block_id,
    )


@router.patch("/v1/task-blocks/{task_block_id}/crop")
async def update_task_block_crop(
    task_block_id: str,
    payload: UpdateTaskBlockCropRequest,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return notebook_store.update_task_block_crop(
        tenant_id=auth["tenant_id"],
        student_id=payload.student_id,
        task_block_id=task_block_id,
        crop_asset_id=payload.crop_asset_id,
        bbox=payload.bbox,
    )


@router.post("/v1/task-blocks/{task_block_id}/collections/{collection_type}")
async def set_task_block_collection(
    task_block_id: str,
    collection_type: CollectionType,
    payload: SetCollectionRequest,
    auth: Annotated[dict, Depends(_require_auth)],
    notebook_store: Annotated[NotebookStore, Depends(get_notebook_store)],
) -> dict:
    return notebook_store.set_collection(
        tenant_id=auth["tenant_id"],
        student_id=payload.student_id,
        task_block_id=task_block_id,
        collection_type=collection_type,
        user_id=auth["user_id"],
        reason=payload.reason,
        note=payload.note,
    )


@router.delete("/v1/task-blocks/{task_block_id}/collections/{collection_type}")
async def unset_task_block_collection(
    task_block_id: str,
    collection_type: CollectionType,
    student_id: str = Query(min_length=1),
    auth: dict = Depends(_require_auth),
    notebook_store: NotebookStore = Depends(get_notebook_store),
) -> dict[str, str]:
    notebook_store.unset_collection(
        tenant_id=auth["tenant_id"],
        student_id=student_id,
        task_block_id=task_block_id,
        collection_type=collection_type,
    )
    return {"status": "ok"}


@router.get("/v1/question-collections")
async def list_question_collections(
    collection_type: CollectionType = Query(alias="type"),
    student_id: str = Query(min_length=1),
    auth: dict = Depends(_require_auth),
    notebook_store: NotebookStore = Depends(get_notebook_store),
) -> dict:
    return {
        "items": notebook_store.list_collections(
            tenant_id=auth["tenant_id"],
            student_id=student_id,
            collection_type=collection_type,
        )
    }


async def _run_parse_task(
    task_store: TaskStore,
    pipeline: ParsePipeline,
    task_id: str,
    image_bytes: bytes,
    model: str | None,
    subject: str,
) -> None:
    """Background coroutine that runs the parse pipeline and updates task state."""
    await task_store.update_status(task_id, TaskStatus.PROCESSING)
    try:
        result = await pipeline.run(image_bytes=image_bytes, model=model, subject=subject)
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
    force: bool = Query(default=False),
    subject: str = Query(default="general"),
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
    subject_value = (subject or "general").strip()
    if subject_value not in {"general", "english", "liberal_arts", "science"}:
        raise AppError(
            "INVALID_REQUEST",
            "subject must be one of general, english, liberal_arts, science.",
        )
    cache_hash = f"{subject_value}:{image_hash}"
    task = await task_store.create(
        image_hash=cache_hash,
        model=model_value,
        subject=subject_value,
        force=force,
    )

    # 只有当任务是新创建的 PENDING 状态时，才触发异步解析任务
    if task.status == TaskStatus.PENDING:
        asyncio.create_task(
            _run_parse_task(
                task_store=task_store,
                pipeline=pipeline,
                task_id=task.task_id,
                image_bytes=body,
                model=model_value or None,
                subject=subject_value,
            )
        )

    logger.info(
        "parse_submitted task_id=%s image_hash=%s subject=%s status=%s model=%s size=%s force=%s",
        task.task_id,
        cache_hash,
        subject_value,
        task.status.value,
        model_value or "<default>",
        len(body),
        force,
    )

    # 如果任务已完成且并非被重置，直接在响应里附带 result 答案
    response_result = task.result if task.status == TaskStatus.COMPLETED else None

    return ParseSubmitResponse(
        task_id=task.task_id,
        status=task.status.value,
        image_hash=cache_hash,
        subject=task.subject,
        result=response_result,
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
        subject=task.subject,
        result=task.result,
        error_code=task.error_code,
        error_message=task.error_message,
    )


@router.delete("/v1/homework/tasks/{task_id}")
async def delete_task(
    task_store: Annotated[TaskStore, Depends(get_task_store)],
    task_id: str,
):
    success = await task_store.delete(task_id)
    if not success:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "TASK_NOT_FOUND",
                "message": "Task with given ID does not exist.",
            },
        )
    return {"status": "ok"}
