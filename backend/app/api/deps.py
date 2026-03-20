from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.opencode_client import OpencodeClient
from app.services.parse_pipeline import ParsePipeline


@lru_cache(maxsize=1)
def get_pipeline() -> ParsePipeline:
    settings = get_settings()
    return ParsePipeline(opencode_client=OpencodeClient(settings), settings=settings)
