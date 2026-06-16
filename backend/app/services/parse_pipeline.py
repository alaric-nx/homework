from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError
from app.core.models import HomeworkParseResult
from app.services.llm_client import LLMClient
from app.skills.common.response_schema_guard import ResponseSchemaGuard

logger = logging.getLogger(__name__)


class ParsePipeline:
    """Simplified parse pipeline.

    流程：构建 prompt（含图片附件）→ 大模型视觉理解（LLM）→ schema 校验。
    不再经过 OCR 中间步骤，模型直接读取题图；也不再生成 answer_placements 坐标。
    """

    def __init__(self, llm_client: LLMClient, settings: Settings) -> None:
        self.llm_client = llm_client
        self.settings = settings
        self.schema_guard = ResponseSchemaGuard()

    def _build_prompt(self) -> str:
        return (
            "你是小学英语作业解析助手。\n"
            "必须严格遵守：\n"
            "1) 只输出一个 JSON 对象，不要 markdown，不要代码块，不要任何额外文字。\n"
            "2) 只允许以下字段：question_meaning_zh, reference_answer, explanation_zh, "
            "key_vocabulary, speak_units, uncertainty。\n"
            "3) key_vocabulary 是数组，元素字段：word, meaning_zh, ipa(可空)。\n"
            "4) speak_units 是数组，元素字段：unit_type(只能是word或sentence), text, "
            "meaning_zh(可空)。sentence 单元必须尽量给 meaning_zh 中文翻译。\n"
            "5) uncertainty 字段：requires_review(boolean), confidence(0到1), reason(可空字符串)。\n"
            "6) 字段必须齐全，不能缺失，不能新增字段。\n"
            "7) question_meaning_zh 必须分两行：第一行是题目中文翻译，第二行说明题目要做什么。\n"
            "8) 你会收到题目图片附件，必须直接根据图片内容识别题目并解答（image-first，"
            "充分利用视觉理解能力）。\n"
            "9) 若题目含编号，请按检测到的编号顺序给出答案；若无编号，请按题面阅读顺序组织答案。\n"
            "10) reference_answer 请尽量保持按行输出，适合前端逐行渲染；每行对应一个答案，"
            "必要时保留编号。\n"
            "11) key_vocabulary 尽量补全 reference_answer 和题干中的高频词，方便前端做行内长按释义。\n"
            "12) speak_units 优先给出 sentence 单元，并尽量让 sentence 与前端可见的答案行保持顺序一致；"
            "sentence.text 尽量等于 reference_answer 对应行去掉编号后的英文内容，"
            "sentence.meaning_zh 给该整句中文翻译；word 单元只保留需要单独点读的重点词。\n"
        )

    def _normalize_candidate(self, candidate: Any) -> Any:
        if not isinstance(candidate, dict):
            return candidate

        out = dict(candidate)
        ref = out.get("reference_answer")
        if isinstance(ref, list):
            out["reference_answer"] = "\n".join(
                str(x).strip() for x in ref if str(x).strip()
            )
        return out

    def _fallback_output(self, reason: str | None = None) -> dict[str, Any]:
        if reason:
            logger.warning("parse_pipeline_fallback reason=%s", reason)
        return {
            "question_meaning_zh": "请根据题目完成英语作业。\n请按题目要求作答。",
            "reference_answer": "请根据题干补全正确答案（当前为后端占位答案）。",
            "explanation_zh": "这是兜底讲解，模型未能返回有效结果，请家长人工复核。",
            "key_vocabulary": [
                {"word": "answer", "meaning_zh": "答案", "ipa": "/ˈɑːnsər/"}
            ],
            "speak_units": [
                {"unit_type": "word", "text": "answer", "meaning_zh": "答案"},
                {
                    "unit_type": "sentence",
                    "text": "Please complete the exercise.",
                    "meaning_zh": "请完成这道练习。",
                },
            ],
            "uncertainty": {
                "requires_review": True,
                "confidence": 0.3,
                "reason": reason or "使用了兜底策略，请家长人工复核。",
            },
        }

    def _write_temp_image(self, image_bytes: bytes) -> Path:
        with tempfile.NamedTemporaryFile(
            prefix="hw_parse_", suffix=".jpg", delete=False
        ) as fp:
            fp.write(image_bytes)
            return Path(fp.name)

    async def _call_model(
        self, prompt: str, image_bytes: bytes | None, model: str | None
    ) -> dict[str, Any]:
        tmp_file: Path | None = None
        try:
            files: list[str] = []
            if image_bytes:
                tmp_file = self._write_temp_image(image_bytes)
                files.append(str(tmp_file))
            return await self.llm_client.generate_json(
                prompt, file_paths=files, model=model
            )
        finally:
            if tmp_file is not None:
                tmp_file.unlink(missing_ok=True)

    async def run(
        self,
        image_bytes: bytes | None,
        model: str | None = None,
    ) -> HomeworkParseResult:
        start_ts = time.perf_counter()
        prompt = self._build_prompt()

        model_failure_reason = ""
        try:
            candidate = await self._call_model(prompt, image_bytes, model)
            logger.info(
                "pipeline_step llm elapsed=%.2fs model=%s",
                time.perf_counter() - start_ts,
                (model or "").strip() or "<default>",
            )
        except AppError as exc:
            model_failure_reason = exc.detail
            candidate = self._fallback_output(reason=exc.detail)

        normalized_candidate = self._normalize_candidate(candidate)
        try:
            validated = self.schema_guard.validate_payload(normalized_candidate)
            logger.info(
                "pipeline_step schema_validate elapsed=%.2fs",
                time.perf_counter() - start_ts,
            )
            return validated
        except AppError as first_error:
            reason = model_failure_reason or (
                "模型输出未满足固定 JSON 结构，已自动切换兜底结果。"
            )
            logger.warning(
                "schema_validation_failed detail=%s", first_error.detail
            )
            fallback = self._fallback_output(reason=reason)
            validated = self.schema_guard.validate_payload(fallback)
            logger.info(
                "pipeline_step schema_validate_fallback elapsed=%.2fs",
                time.perf_counter() - start_ts,
            )
            return validated
