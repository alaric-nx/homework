from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.core.models import HomeworkParseResponse


class ResponseSchemaGuard:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path = schema_path or (Path(__file__).resolve().parents[3] / "schemas" / "homework_parse.schema.json")
        with self.schema_path.open("r", encoding="utf-8") as fp:
            self.schema = json.load(fp)

    def validate_payload(self, payload: dict[str, Any]) -> HomeworkParseResponse:
        try:
            return HomeworkParseResponse.model_validate(payload)
        except ValueError as exc:
            raise AppError("SCHEMA_VALIDATION_FAILED", str(exc)) from exc
