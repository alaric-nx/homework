from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.services.llm_client import LLMClient
from app.services.notebook_store import NotebookStore
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


@lru_cache(maxsize=1)
def get_notebook_store() -> NotebookStore:
    settings = get_settings()
    backend_dir = Path(__file__).resolve().parents[2]
    data_dir = Path(settings.data_dir or "data")
    if not data_dir.is_absolute():
        data_dir = backend_dir / data_dir
    sqlite_path = settings.sqlite_path or f"{data_dir}/homework.sqlite3"
    return NotebookStore(
        sqlite_path=sqlite_path,
        data_dir=data_dir,
        token_ttl_sec=settings.auth_token_ttl_sec,
    )
