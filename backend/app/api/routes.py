from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_pipeline
from app.core.errors import AppError
from app.core.models import HomeworkParseFillResponse, HomeworkParseResponse
from app.services.answer_fill_service import AnswerFillService
from app.services.parse_pipeline import ParsePipeline

logger = logging.getLogger(__name__)
router = APIRouter()
answer_fill_service = AnswerFillService()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/ocr/providers")
async def ocr_providers(
    pipeline: Annotated[ParsePipeline, Depends(get_pipeline)],
) -> dict[str, object]:
    return {"providers": pipeline.ocr_skill.list_providers()}


@router.post("/v1/homework/parse", response_model=HomeworkParseResponse)
async def parse_homework(
    pipeline: Annotated[ParsePipeline, Depends(get_pipeline)],
    request: Request,
    expected_type: str | None = Query(default=None),
    image_url: str | None = Query(default=None),
) -> HomeworkParseResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    body = await request.body()

    # Preferred mode: send raw image bytes with content-type image/* or application/octet-stream.
    if body and ("image/" in content_type or "application/octet-stream" in content_type):
        logger.info("parse_request_received mode=binary content_type=%s size=%s", content_type, len(body))
        image_bytes = body
        return await pipeline.run(image_bytes=image_bytes, image_url=image_url, subject_hint=expected_type)

    # Compatibility mode: JSON with image_url (no base64).
    if "application/json" in content_type:
        payload = await request.json()
        parsed_image_url = payload.get("image_url") if isinstance(payload, dict) else None
        parsed_expected_type = payload.get("expected_type") if isinstance(payload, dict) else None
        logger.info("parse_request_received mode=json image_url=%s", bool(parsed_image_url))
        return await pipeline.run(
            image_bytes=None,
            image_url=parsed_image_url or image_url,
            subject_hint=parsed_expected_type or expected_type,
        )

    # Fallback: if raw bytes exist but content-type is unknown, still treat as image bytes.
    if body:
        logger.info("parse_request_received mode=raw_unknown_content_type size=%s", len(body))
        return await pipeline.run(image_bytes=body, image_url=image_url, subject_hint=expected_type)

    raise AppError(
        "INVALID_REQUEST",
        "Please send raw image bytes in request body (content-type: image/jpeg|image/png|application/octet-stream).",
    )


@router.post("/v1/homework/parse-fill", response_model=HomeworkParseFillResponse)
async def parse_and_fill_homework(
    pipeline: Annotated[ParsePipeline, Depends(get_pipeline)],
    request: Request,
    expected_type: str | None = Query(default="english"),
    image_url: str | None = Query(default=None),
) -> HomeworkParseFillResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    body = await request.body()
    if not body:
        raise AppError("INVALID_REQUEST", "Please send raw image bytes in request body.")
    if "image/" not in content_type and "application/octet-stream" not in content_type:
        logger.info("parse_fill_unknown_content_type content_type=%s; still trying as binary", content_type)

    result = await pipeline.run(image_bytes=body, image_url=image_url, subject_hint=expected_type)
    filled_image_base64, filled_image_path = answer_fill_service.fill_answers_to_image_base64_and_file(body, result)
    return HomeworkParseFillResponse(
        result=result,
        filled_image_base64=filled_image_base64,
        filled_image_path=filled_image_path,
    )
