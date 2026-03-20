from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.errors import AppError
from app.core.models import HomeworkParseResponse, OCRResult
from app.services.opencode_client import OpencodeClient
from app.skills.common.ocr_skill import OCRSkill
from app.skills.common.response_schema_guard import ResponseSchemaGuard
from app.skills.common.subject_router import route_subject
from app.skills.english.english_solver_skill import EnglishSolverSkill

logger = logging.getLogger(__name__)


class ParsePipeline:
    def __init__(self, opencode_client: OpencodeClient, settings: Settings) -> None:
        self.ocr_skill = OCRSkill(settings)
        self.schema_guard = ResponseSchemaGuard()
        self.english_solver = EnglishSolverSkill(opencode_client)

    async def run(
        self,
        image_bytes: bytes | None,
        image_url: str | None,
        subject_hint: str | None,
    ) -> HomeworkParseResponse:
        ocr_result: OCRResult = await self.ocr_skill.extract_text(image_bytes=image_bytes, image_url=image_url)
        subject = route_subject(subject_hint, ocr_result.text)
        if subject != "english":
            raise AppError("UNSUPPORTED_SUBJECT", f"Current MVP only supports english; got {subject}.")

        model_failure_reason = ""
        try:
            candidate = await self.english_solver.solve(
                ocr_result,
                image_bytes=image_bytes,
                image_url=image_url,
                strict_mode=False,
            )
        except AppError as exc:
            model_failure_reason = exc.detail
            candidate = self.english_solver.fallback_output(ocr_result, reason=exc.detail)

        try:
            return self.schema_guard.validate_payload(candidate)
        except AppError as first_error:
            if model_failure_reason:
                # model call already failed; strict retry is unlikely to help
                fallback = self.english_solver.fallback_output(ocr_result, reason=model_failure_reason)
                return self.schema_guard.validate_payload(fallback)
            try:
                candidate_retry = await self.english_solver.solve(
                    ocr_result,
                    image_bytes=image_bytes,
                    image_url=image_url,
                    strict_mode=True,
                )
            except AppError as retry_exc:
                fallback = self.english_solver.fallback_output(ocr_result, reason=retry_exc.detail)
                return self.schema_guard.validate_payload(fallback)
            try:
                return self.schema_guard.validate_payload(candidate_retry)
            except AppError as second_error:
                logger.warning("schema_validation_failed first=%s second=%s", first_error.detail, second_error.detail)
                fallback = self.english_solver.fallback_output(
                    ocr_result,
                    reason="模型输出未满足固定 JSON 结构，已自动切换兜底结果。",
                )
                return self.schema_guard.validate_payload(fallback)
