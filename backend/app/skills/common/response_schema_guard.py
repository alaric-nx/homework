from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.core.models import HomeworkParseResult

# 固定输出仅包含以下字段，answer_items 是参考答案区唯一数据源。
ALLOWED_FIELDS = (
    "schema_version",
    "subject",
    "question_meaning_zh",
    "question_blocks",
    "answer_items",
    "student_answer_reviews",
    "solution_steps",
    "explanation_zh",
    "learning_points",
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
        block_orders: set[int] = set()
        for block in result.question_blocks:
            if block.order in block_orders:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"duplicate question block order {block.order}",
                )
            block_orders.add(block.order)
            content_orders: set[int] = set()
            for item in block.content_items:
                if item.order in content_orders:
                    raise AppError(
                        "SCHEMA_VALIDATION_FAILED",
                        f"duplicate content item order {item.order} in block {block.block_id!r}",
                    )
                content_orders.add(item.order)

        answer_ids = {item.answer_id for item in result.answer_items}
        answer_orders_by_block: dict[str, set[int]] = {}
        for item in result.answer_items:
            if item.block_id not in block_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"answer item block_id {item.block_id!r} not found in question_blocks",
                )
            block_orders_seen = answer_orders_by_block.setdefault(item.block_id, set())
            if item.order in block_orders_seen:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"duplicate answer item order {item.order} in block {item.block_id!r}",
                )
            block_orders_seen.add(item.order)

        review_orders_by_block: dict[str, set[int]] = {}
        for review in result.student_answer_reviews:
            if review.block_id not in block_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"student answer review block_id {review.block_id!r} not found in question_blocks",
                )
            if review.answer_id is not None and review.answer_id not in answer_ids:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"student answer review answer_id {review.answer_id!r} not found in answer_items",
                )
            block_orders_seen = review_orders_by_block.setdefault(review.block_id, set())
            if review.order in block_orders_seen:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"duplicate student answer review order {review.order} in block {review.block_id!r}",
                )
            block_orders_seen.add(review.order)

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
        return result
