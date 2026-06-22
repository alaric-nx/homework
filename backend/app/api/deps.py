from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.llm_client import LLMClient
from app.services.parse_pipeline import ParsePipeline
from app.services.task_store import TaskStore


@lru_cache(maxsize=1)
def get_pipeline() -> ParsePipeline:
    settings = get_settings()
    return ParsePipeline(llm_client=LLMClient(settings), settings=settings)


@lru_cache(maxsize=1)
def get_task_store() -> TaskStore:
    settings = get_settings()
    return TaskStore(
        timeout_sec=settings.task_timeout_sec,
        retention_sec=settings.task_retention_sec,
        job_dir=settings.task_job_dir or None,
    )
