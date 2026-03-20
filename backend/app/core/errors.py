from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    http_status: int
    message: str


ERROR_SPECS: dict[str, ErrorSpec] = {
    "INVALID_REQUEST": ErrorSpec("INVALID_REQUEST", HTTPStatus.BAD_REQUEST, "Invalid request payload."),
    "UNSUPPORTED_SUBJECT": ErrorSpec("UNSUPPORTED_SUBJECT", HTTPStatus.BAD_REQUEST, "Subject is not supported yet."),
    "OCR_FAILED": ErrorSpec("OCR_FAILED", HTTPStatus.BAD_GATEWAY, "OCR processing failed."),
    "MODEL_FAILED": ErrorSpec("MODEL_FAILED", HTTPStatus.BAD_GATEWAY, "Model processing failed."),
    "SCHEMA_VALIDATION_FAILED": ErrorSpec(
        "SCHEMA_VALIDATION_FAILED",
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "Structured output validation failed.",
    ),
    "TIMEOUT": ErrorSpec("TIMEOUT", HTTPStatus.GATEWAY_TIMEOUT, "Upstream timeout."),
    "INTERNAL_ERROR": ErrorSpec("INTERNAL_ERROR", HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error."),
}


class AppError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        if code not in ERROR_SPECS:
            code = "INTERNAL_ERROR"
        self.code = code
        self.spec = ERROR_SPECS[code]
        self.detail = detail or self.spec.message
        super().__init__(self.detail)

