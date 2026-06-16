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
            "你是英语练习题解析助手，适用于英语作业、练习册、考试题和基础学习题。"
            "请根据题目图片理解题型、识别题干要求并作答。\n"
            "\n"
            "必须严格遵守：\n"
            "1) 只输出一个 JSON 对象，不要 markdown，不要代码块，不要任何额外文字。\n"
            "2) 只允许以下字段：question_meaning_zh, answer_lines, explanation_zh, "
            "key_vocabulary, speak_units, uncertainty。\n"
            "3) 字段必须齐全，不能缺失，不能新增字段；不要输出 reference_answer。\n"
            "4) key_vocabulary 是数组，元素字段：word, meaning_zh, ipa(可空)。\n"
            "5) speak_units 是数组，元素字段：unit_type(只能是word或sentence), text, "
            "meaning_zh(可空)。sentence 单元必须尽量给 meaning_zh 中文翻译。\n"
            "6) uncertainty 字段：requires_review(boolean), confidence(0到1), reason(可空字符串)。\n"
            "7) question_meaning_zh 必须分两行：第一行翻译题目要求，第二行说明孩子或学习者要做什么。\n"
            "\n"
            "证据原则：\n"
            "- 你会收到题目图片附件，必须以图片中的题干、图片、编号、空格、选项、例句为主要依据。\n"
            "- 如果视觉内容、题干文字和你的常识发生冲突，以图片和题干为准。\n"
            "- 不要补充图片中不存在的题目。\n"
            "- 看不清、被遮挡、裁切缺失时，不要强行编造答案，应降低 confidence 并说明原因。\n"
            "\n"
            "在输出 JSON 前，请在内部完成这些步骤，但不要展示过程：\n"
            "A. 判断题型：看图填空、选择、连线/匹配、排序、阅读理解、句子补全、翻译、抄写、改错等。\n"
            "B. 找出题目要求：需要写单词、短语、完整句子，还是选择编号。\n"
            "C. 识别所有编号、空格、选项和例句，确认答案数量。\n"
            "D. 按题型推导答案。\n"
            "E. 检查答案是否符合图片、题干、语法和常见英语表达。\n"
            "\n"
            "answer_lines 是参考答案区的唯一数据源。每个元素代表一行答案，字段为：\n"
            "- number: 题号，字符串或 null，支持 1、A、1a 等。\n"
            "- line_type: 只能是 fill_blank, choice, picture_word, matching, sentence_ordering, "
            "reading_qa, translation, correction, copying, other。\n"
            "- plain_text: 完整答案文本，不含题号，用于整行朗读。\n"
            "- segments: 数组，至少一个元素；元素字段 text 和 role。\n"
            "\n"
            "segments.role 只能是：\n"
            "- given: 题目原本已有的文字。\n"
            "- answer: 学生需要填写、选择或生成的答案。\n"
            "- connector: 连接符号，如箭头、短横线、冒号。\n"
            "- correction: 改错题中订正后的正确内容。\n"
            "\n"
            "题型规则：\n"
            "- 填空、补全句子、看图填空：plain_text 必须是补全后的完整句子或完整短语，不允许只输出填空词；"
            "segments 中题目已有文字标为 given，填入答案标为 answer。\n"
            "- 选择题：选项字母和选中内容标为 answer。\n"
            "- 看图写词/短语：答案整体标为 answer。\n"
            "- 连线/匹配：题目已有内容可标为 given，配对关系或选中编号标为 answer。\n"
            "- 排序/连词成句：最终正确句整体标为 answer。\n"
            "- 阅读问答/翻译：回答或译文整体标为 answer。\n"
            "- 改错题：未改部分标为 given，订正内容标为 correction。\n"
            "- 抄写题：照抄内容可标为 given，讲解中说明照抄即可。\n"
            "\n"
            "输出质量规则：\n"
            "- 若题目含编号，请按检测到的编号顺序给出 answer_lines；若无编号，请按题面阅读顺序组织。\n"
            "- key_vocabulary 优先收录答案词、题干关键词和易错词，建议 3 到 10 个。\n"
            "- speak_units 优先给 sentence 单元，并尽量让 sentence.text 等于 answer_lines[].plain_text；"
            "word 单元只保留需要单独点读的重点词。\n"
            "- 如果某个答案不确定，仍按编号保留位置，并在 uncertainty 中说明。\n"
            "\n"
            "不确定性规则：\n"
            "- 图片模糊、裁切、遮挡、编号不完整、选项看不清、答案依赖外部上下文时，requires_review=true。\n"
            "- confidence 取值：清晰可靠 0.9-1.0；轻微歧义 0.7-0.89；明显推测 0.4-0.69；无法可靠作答 0-0.39。\n"
        )

    def _normalize_candidate(self, candidate: Any) -> Any:
        if not isinstance(candidate, dict):
            return candidate

        out = dict(candidate)
        lines = out.get("answer_lines")
        if isinstance(lines, list):
            normalized_lines: list[Any] = []
            for line in lines:
                if not isinstance(line, dict):
                    normalized_lines.append(line)
                    continue
                normalized_line = dict(line)
                if normalized_line.get("number") is not None:
                    normalized_line["number"] = str(normalized_line["number"]).strip()
                segments = normalized_line.get("segments")
                if not segments and str(normalized_line.get("plain_text", "")).strip():
                    normalized_line["segments"] = [
                        {
                            "text": str(normalized_line["plain_text"]).strip(),
                            "role": "answer",
                        }
                    ]
                normalized_lines.append(normalized_line)
            out["answer_lines"] = normalized_lines
        return out

    def _fallback_output(self, reason: str | None = None) -> dict[str, Any]:
        if reason:
            logger.warning("parse_pipeline_fallback reason=%s", reason)
        return {
            "question_meaning_zh": "请根据题目完成英语作业。\n请按题目要求作答。",
            "answer_lines": [
                {
                    "number": None,
                    "line_type": "other",
                    "plain_text": "Please review the exercise.",
                    "segments": [
                        {
                            "text": "Please review the exercise.",
                            "role": "answer",
                        }
                    ],
                }
            ],
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
