from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.core.models import HomeworkParseResult

# 简化后的固定输出仅包含以下 6 个字段，移除了 answer_placements 与 ocr_result。
ALLOWED_FIELDS = (
    "question_meaning_zh",
    "reference_answer",
    "explanation_zh",
    "key_vocabulary",
    "speak_units",
    "uncertainty",
)


class ResponseSchemaGuard:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path = schema_path or (
            Path(__file__).resolve().parents[3] / "schemas" / "homework_parse.schema.json"
        )
        with self.schema_path.open("r", encoding="utf-8") as fp:
            self.schema = json.load(fp)

    def validate_payload(self, payload: dict[str, Any]) -> HomeworkParseResult:
        # 仅保留允许的 6 个字段，忽略模型可能返回的多余字段（如已移除的
        # answer_placements / ocr_result），保证输出结构稳定且不因多余字段而校验失败。
        filtered = {
            key: value for key, value in payload.items() if key in ALLOWED_FIELDS
        }
        try:
            return HomeworkParseResult.model_validate(filtered)
        except ValueError as exc:
            raise AppError("SCHEMA_VALIDATION_FAILED", str(exc)) from exc
