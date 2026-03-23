from __future__ import annotations

import logging
import time
from typing import Any

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
    TOTAL_BUDGET_SEC = 35.0
    MIN_RETRY_REMAINING_SEC = 8.0

    def __init__(self, opencode_client: OpencodeClient, settings: Settings) -> None:
        self.ocr_skill = OCRSkill(settings)
        self.schema_guard = ResponseSchemaGuard()
        self.english_solver = EnglishSolverSkill(opencode_client)

    def _attach_ocr(
        self, payload: HomeworkParseResponse, ocr_result: OCRResult
    ) -> HomeworkParseResponse:
        payload.ocr_result = ocr_result
        return payload

    def _normalize_candidate(self, candidate: Any) -> Any:
        if not isinstance(candidate, dict):
            return candidate

        out = dict(candidate)
        ref = out.get("reference_answer")
        if isinstance(ref, list):
            out["reference_answer"] = "\n".join(
                str(x).strip() for x in ref if str(x).strip()
            )

        placements = out.get("answer_placements")
        if isinstance(placements, list):
            normalized: list[Any] = []
            for item in placements:
                if not isinstance(item, dict):
                    normalized.append(item)
                    continue
                p = dict(item)
                text = p.get("text")
                if isinstance(text, list):
                    p["text"] = " ".join(str(x).strip() for x in text if str(x).strip())
                fsr = p.get("font_size_ratio")
                if isinstance(fsr, (int, float)) and fsr <= 0:
                    p["font_size_ratio"] = None
                normalized.append(p)
            out["answer_placements"] = normalized
        return out

    def _has_meaningful_reference_answer(self, reference_answer: Any) -> bool:
        if not isinstance(reference_answer, str):
            return False
        text = reference_answer.strip()
        if not text:
            return False
        if "后端占位答案" in text:
            return False
        return True

    def _has_valid_placements(self, placements: Any) -> bool:
        if not isinstance(placements, list):
            return False
        for item in placements:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            bbox = item.get("bbox_norm")
            if text and isinstance(bbox, list) and len(bbox) == 4:
                return True
        return False

    def _should_retry_strict(
        self,
        normalized_candidate: Any,
        first_error: AppError,
        ocr_result: OCRResult,
        elapsed_sec: float,
    ) -> bool:
        remaining = self.TOTAL_BUDGET_SEC - elapsed_sec
        if remaining < self.MIN_RETRY_REMAINING_SEC:
            return False

        if not isinstance(normalized_candidate, dict):
            return True

        required_keys = {
            "question_meaning_zh",
            "reference_answer",
            "explanation_zh",
            "key_vocabulary",
            "speak_units",
            "uncertainty",
        }
        if not required_keys.issubset(normalized_candidate.keys()):
            return True

        has_ref = self._has_meaningful_reference_answer(
            normalized_candidate.get("reference_answer")
        )
        has_placements = self._has_valid_placements(
            normalized_candidate.get("answer_placements")
        )
        if not has_ref:
            return True
        if not has_placements and len((ocr_result.text or "").strip()) < 40:
            return True

        detail = (first_error.detail or "").lower()
        hard_fail_tokens = (
            "field required",
            "missing",
            "cannot be parsed",
            "json",
        )
        if any(token in detail for token in hard_fail_tokens):
            return True
        return False

    def _salvage_candidate(
        self, normalized_candidate: Any, ocr_result: OCRResult, reason: str
    ) -> dict[str, Any]:
        base = self.english_solver.fallback_output(ocr_result, reason=reason)
        if not isinstance(normalized_candidate, dict):
            return base

        out = dict(base)
        for key in ("question_meaning_zh", "reference_answer", "explanation_zh"):
            val = normalized_candidate.get(key)
            if isinstance(val, str) and val.strip():
                out[key] = val.strip()

        kv = normalized_candidate.get("key_vocabulary")
        if isinstance(kv, list):
            out["key_vocabulary"] = kv
        su = normalized_candidate.get("speak_units")
        if isinstance(su, list):
            out["speak_units"] = su
        unc = normalized_candidate.get("uncertainty")
        if isinstance(unc, dict):
            out["uncertainty"] = unc

        placements = normalized_candidate.get("answer_placements")
        if isinstance(placements, list):
            cleaned: list[dict[str, Any]] = []
            for item in placements:
                if not isinstance(item, dict):
                    continue
                num = item.get("number")
                text = item.get("text")
                bbox = item.get("bbox_norm")
                if not isinstance(num, int):
                    continue
                if not isinstance(text, str) or not text.strip():
                    continue
                if not isinstance(bbox, list) or len(bbox) != 4:
                    continue
                fsr = item.get("font_size_ratio")
                if not isinstance(fsr, (int, float)) or fsr <= 0:
                    fsr = None
                cleaned.append(
                    {
                        "number": num,
                        "text": text.strip(),
                        "bbox_norm": bbox,
                        "font_size_ratio": fsr,
                    }
                )
            out["answer_placements"] = cleaned
        return out

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

        normalized_candidate = self._normalize_candidate(candidate)
        try:
            validated = self.schema_guard.validate_payload(normalized_candidate)
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
            elapsed = time.perf_counter() - start_ts
            if not self._should_retry_strict(
                normalized_candidate,
                first_error,
                ocr_result,
                elapsed_sec=elapsed,
            ):
                logger.warning(
                    "schema_validate_skip_strict_retry elapsed=%.2fs detail=%s",
                    elapsed,
                    first_error.detail,
                )
                salvaged = self._salvage_candidate(
                    normalized_candidate,
                    ocr_result,
                    reason="模型输出结构存在问题，已跳过严格重试并进行本地修复。",
                )
                validated = self.schema_guard.validate_payload(salvaged)
                logger.info(
                    "pipeline_step schema_validate_skip_retry_fallback elapsed=%.2fs",
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
                validated = self.schema_guard.validate_payload(
                    self._normalize_candidate(candidate_retry)
                )
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
