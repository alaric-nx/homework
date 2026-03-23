from __future__ import annotations

import logging
import time

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

    def _attach_ocr(
        self, payload: HomeworkParseResponse, ocr_result: OCRResult
    ) -> HomeworkParseResponse:
        payload.ocr_result = ocr_result
        return payload

    async def run(
        self,
        image_bytes: bytes | None,
        image_url: str | None,
        subject_hint: str | None,
    ) -> HomeworkParseResponse:
        start_ts = time.perf_counter()
        ocr_result = OCRResult(text="", confidence=0.0)
        try:
            ocr_result = await self.ocr_skill.extract_text(
                image_bytes=image_bytes,
                image_url=image_url,
            )
            logger.info(
                "pipeline_step ocr elapsed=%.2fs confidence=%.3f text_len=%s blocks=%s",
                time.perf_counter() - start_ts,
                ocr_result.confidence,
                len(ocr_result.text),
                len(ocr_result.blocks),
            )
        except AppError as exc:
            # image-first strategy: OCR 失败不阻断后续解题
            logger.warning("pipeline_step ocr_failed detail=%s", exc.detail)
        subject = subject_hint or "english"
        logger.info(
            "pipeline_step route_subject elapsed=%.2fs", time.perf_counter() - start_ts
        )
        if subject != "english":
            raise AppError(
                "UNSUPPORTED_SUBJECT",
                f"Current MVP only supports english; got {subject}.",
            )

        model_failure_reason = ""
        try:
            candidate = await self.english_solver.solve(
                ocr_result,
                image_bytes=image_bytes,
                image_url=image_url,
                strict_mode=False,
            )
            logger.info(
                "pipeline_step opencode elapsed=%.2fs", time.perf_counter() - start_ts
            )
        except AppError as exc:
            model_failure_reason = exc.detail
            candidate = self.english_solver.fallback_output(
                ocr_result, reason=exc.detail
            )

        try:
            validated = self.schema_guard.validate_payload(candidate)
            logger.info(
                "pipeline_step schema_validate elapsed=%.2fs",
                time.perf_counter() - start_ts,
            )
            return self._attach_ocr(validated, ocr_result)
        except AppError as first_error:
            if model_failure_reason:
                # model call already failed; strict retry is unlikely to help
                fallback = self.english_solver.fallback_output(
                    ocr_result, reason=model_failure_reason
                )
                validated = self.schema_guard.validate_payload(fallback)
                logger.info(
                    "pipeline_step schema_validate_fallback elapsed=%.2fs",
                    time.perf_counter() - start_ts,
                )
                return self._attach_ocr(validated, ocr_result)
            try:
                candidate_retry = await self.english_solver.solve(
                    ocr_result,
                    image_bytes=image_bytes,
                    image_url=image_url,
                    strict_mode=True,
                )
                logger.info(
                    "pipeline_step opencode_strict elapsed=%.2fs",
                    time.perf_counter() - start_ts,
                )
            except AppError as retry_exc:
                fallback = self.english_solver.fallback_output(
                    ocr_result, reason=retry_exc.detail
                )
                validated = self.schema_guard.validate_payload(fallback)
                logger.info(
                    "pipeline_step schema_validate_retry_fallback elapsed=%.2fs",
                    time.perf_counter() - start_ts,
                )
                return self._attach_ocr(validated, ocr_result)
            try:
                validated = self.schema_guard.validate_payload(candidate_retry)
                logger.info(
                    "pipeline_step schema_validate_retry elapsed=%.2fs",
                    time.perf_counter() - start_ts,
                )
                return self._attach_ocr(validated, ocr_result)
            except AppError as second_error:
                logger.warning(
                    "schema_validation_failed first=%s second=%s",
                    first_error.detail,
                    second_error.detail,
                )
                fallback = self.english_solver.fallback_output(
                    ocr_result,
                    reason="模型输出未满足固定 JSON 结构，已自动切换兜底结果。",
                )
                validated = self.schema_guard.validate_payload(fallback)
                logger.info(
                    "pipeline_step schema_validate_final_fallback elapsed=%.2fs",
                    time.perf_counter() - start_ts,
                )
                return self._attach_ocr(validated, ocr_result)
