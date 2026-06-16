from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.core.models import HomeworkParseResult

# 固定输出仅包含以下字段，answer_lines 是参考答案区唯一数据源。
ALLOWED_FIELDS = (
    "subject",
    "question_meaning_zh",
    "question_instruction",
    "question_blocks",
    "answer_lines",
    "solution_steps",
    "explanation_zh",
    "learning_points",
    "read_units",
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
        if not isinstance(payload, dict):
            raise AppError("SCHEMA_VALIDATION_FAILED", "Payload must be a JSON object.")

        actual_fields = set(payload.keys())
        expected_fields = set(ALLOWED_FIELDS)
        if actual_fields != expected_fields:
            missing = sorted(expected_fields - actual_fields)
            extra = sorted(actual_fields - expected_fields)
            parts: list[str] = []
            if missing:
                parts.append(f"missing fields: {', '.join(missing)}")
            if extra:
                parts.append(f"extra fields: {', '.join(extra)}")
            raise AppError("SCHEMA_VALIDATION_FAILED", "; ".join(parts))

        try:
            result = HomeworkParseResult.model_validate(payload)
        except ValueError as exc:
            raise AppError("SCHEMA_VALIDATION_FAILED", str(exc)) from exc

        block_ids = {block.block_id for block in result.question_blocks}
        for line in result.answer_lines:
            if line.block_id not in block_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"answer line block_id {line.block_id!r} not found in question_blocks",
                )
        for step in result.solution_steps:
            if step.block_id not in block_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"solution step block_id {step.block_id!r} not found in question_blocks",
                )
        for item in result.learning_points:
            if item.block_id is not None and item.block_id not in block_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"learning point block_id {item.block_id!r} not found in question_blocks",
                )
        for unit in result.read_units:
            if unit.block_id is not None and unit.block_id not in block_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"read unit block_id {unit.block_id!r} not found in question_blocks",
                )
        return result
