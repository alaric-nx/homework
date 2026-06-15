from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.opencode_client import OpencodeClient
from app.services.parse_pipeline import ParsePipeline
from app.services.task_store import TaskStore


@lru_cache(maxsize=1)
def get_pipeline() -> ParsePipeline:
    settings = get_settings()
    return ParsePipeline(opencode_client=OpencodeClient(settings), settings=settings)


@lru_cache(maxsize=1)
def get_task_store() -> TaskStore:
    settings = get_settings()
    return TaskStore(
        timeout_sec=settings.task_timeout_sec,
        retention_sec=settings.task_retention_sec,
    )
