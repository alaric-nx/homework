from __future__ import annotations

import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError
from app.core.models import HomeworkParseResult, LearningPoint, ReadUnit
from app.services.llm_client import LLMClient
from app.skills.common.response_schema_guard import ResponseSchemaGuard

logger = logging.getLogger(__name__)
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
VOCAB_SKIP_WORDS = {"a", "an", "the"}


class ParsePipeline:
    """Simplified parse pipeline.

    流程：构建 prompt（含图片附件）→ 大模型视觉理解（LLM）→ schema 校验。
    不再经过 OCR 中间步骤，模型直接读取题图；也不再生成 answer_placements 坐标。
    """

    def __init__(self, llm_client: LLMClient, settings: Settings) -> None:
        self.llm_client = llm_client
        self.settings = settings
        self.schema_guard = ResponseSchemaGuard()

    def _build_prompt(self, subject: str) -> str:
        subject_notes = {
            "general": (
                "你是通用作业解析助手。题目可能来自英语、语文、拼音、数学、科学或混合练习。"
                "先判断题目类型，再按题目块输出答案、必要步骤、中文讲解、知识点和朗读内容。"
                "不要强行套英语词汇表，也不要强行套数学公式。"
            ),
            "english": (
                "你是英语练习题解析助手，适用于英语作业、练习册、考试题和基础学习题。"
                "保持当前英语解析能力：完整答案行、题目要求原文、词义、发音、句义和答案词义覆盖。"
                "learning_points 重点放英文单词、短语、语法点，pronunciation 可放 IPA。"
                "read_units 放题目要求、答案句、需要点读的单词或短句。"
            ),
            "liberal_arts": (
                "你是文科作业解析助手，覆盖语文、拼音、道法、历史、地理等。"
                "重点识别题目要求、材料、问题、选项和答题依据。"
                "阅读理解和材料题必须说明答案依据。"
                "拼音题要把拼音放入 learning_points.pronunciation。"
                "作文或开放题给出可参考答案和审题提示，不编造唯一标准答案。"
            ),
            "science": (
                "你是理科作业解析助手，覆盖数学、科学、物理、化学等。"
                "必须提取已知条件、要求的问题、关键公式或方法。"
                "solution_steps 必须清楚展示列式、推理或计算过程。"
                "answer_lines 放最终答案或需要填写的关键内容。"
                "单位、公式、易错概念进入 learning_points。复杂公式不要强行放入 read_units。"
            ),
        }
        return (
            subject_notes.get(subject, subject_notes["general"])
            + "\n"
            "\n"
            "必须严格遵守：\n"
            "1) 只输出一个 JSON 对象，不要 markdown，不要代码块，不要任何额外文字。\n"
            "2) 只允许以下字段：subject, question_meaning_zh, question_instruction, question_blocks, "
            "answer_lines, solution_steps, explanation_zh, learning_points, read_units, uncertainty。\n"
            "3) 字段必须齐全，不能缺失，不能新增字段；不要输出 reference_answer。\n"
            f"4) subject 必须固定输出为 \"{subject}\"。\n"
            "5) solution_steps 是数组，元素字段：block_id, number, title, content_zh, formula, result。\n"
            "6) learning_points 是数组，元素字段：block_id, term, explanation_zh, pronunciation, category。\n"
            "7) read_units 是数组，元素字段：block_id, unit_type, text, meaning_zh。\n"
            "8) uncertainty 字段：requires_review(boolean), confidence(0到1), reason(可空字符串)。\n"
            "9) question_meaning_zh 用中文概括整张图里的练习内容。如果有多个题目块，要说明包含几个题目块。\n"
            "10) question_instruction 字段用于提取整张图最上层或共同的题目要求原文，字段为："
            "text, meaning_zh, confidence。\n"
            "11) question_blocks 字段用于区分同一张图片里的多个独立题目块，字段为："
            "block_id, title, question_instruction, question_meaning_zh。\n"
            "\n"
            "证据原则：\n"
            "- 你会收到题目图片附件，必须以图片中的题干、图片、编号、空格、选项、例句为主要依据。\n"
            "- 如果视觉内容、题干文字和你的常识发生冲突，以图片和题干为准。\n"
            "- 不要补充图片中不存在的题目。\n"
            "- 看不清、被遮挡、裁切缺失时，不要强行编造答案，应降低 confidence 并说明原因。\n"
            "\n"
            "在输出 JSON 前，请在内部完成这些步骤，但不要展示过程：\n"
            "A. 先判断图片里有几个独立题目块：看大题编号、标题、题目要求行、分隔线、版面分区、例题和编号重启。\n"
            "B. 即使两个题目块共享图片、词库、例句或上下文，只要作答要求不同、编号体系不同、版面分区不同，"
            "也必须拆成不同 question_blocks。\n"
            "C. 为每个题目块判断题型：填空、选择、连线/匹配、排序、阅读理解、句子补全、翻译、抄写、改错、计算、证明、拼音、作文等。\n"
            "D. 为每个题目块找出题目要求：需要写单词、短语、完整句子，还是选择编号。\n"
            "E. 识别所有编号、空格、选项和例句，确认每个题目块的答案数量。\n"
            "F. 按题型推导答案。\n"
            "G. 检查答案是否符合图片、题干、语法和常见英语表达。\n"
            "\n"
            "question_blocks 是题目块列表。每个元素代表图片中的一个独立题目块，字段为：\n"
            "- block_id: 稳定 ID，只能用 q1, q2, q3...，按图片阅读顺序编号。\n"
            "- title: 题目块标题，可用图片中的大题编号/标题；没有标题时用 第1题、第2题。\n"
            "- question_instruction: 该题目块的英文题目要求原句和中文解释。\n"
            "- question_meaning_zh: 该题目块要孩子或学习者做什么。\n"
            "\n"
            "answer_lines 是参考答案区的唯一数据源。每个元素代表一行答案，字段为：\n"
            "- block_id: 所属 question_blocks[].block_id，必须能对应到某个题目块。\n"
            "- number: 题号，字符串或 null，支持 1、A、1a 等。\n"
            "- line_type: 只能是 fill_blank, choice, picture_word, matching, sentence_ordering, "
            "reading_qa, translation, correction, copying, calculation, proof, short_answer, composition, pinyin, other。\n"
            "- plain_text: 完整答案文本，不含题号，用于整行朗读。\n"
            "- segments: 数组，至少一个元素；元素字段 text 和 role。\n"
            "\n"
            "question_instruction 规则：\n"
            "- text 必须尽量提取图片中原始题目要求，保持原文格式。\n"
            "- meaning_zh 是该题目要求的中文解释。\n"
            "- confidence 表示原文识别置信度，清晰可靠 0.9-1.0；部分遮挡/模糊则降低。\n"
            "- 如果图片里没有可见题目要求，text 和 meaning_zh 用空字符串，confidence=0，"
            "并在 uncertainty 中说明。\n"
            "- 如果图片中有多个独立题目要求，顶层 question_instruction 使用最上方共同要求；"
            "各题目块自己的题目要求必须放入 question_blocks[].question_instruction。\n"
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
            "- 计算/理科题：answer_lines 放最终答案或关键列式，solution_steps 放主要步骤。\n"
            "- 拼音题：answer_lines 放完整答案，learning_points 放字词、拼音和解释。\n"
            "- 作文/开放题：answer_lines 放参考提纲或参考答案，explanation_zh 说明审题要点，不编造唯一答案。\n"
            "\n"
            "输出质量规则：\n"
            "- 若图片中有多个题目块，必须先按题目块顺序输出 question_blocks，再按题目块顺序输出 answer_lines。\n"
            "- 若题目含编号，请按检测到的编号顺序给出 answer_lines；若无编号，请按题面阅读顺序组织。\n"
            "- 同一张图中两个相关题目不能混成一个题目块；例如第一题先补全单词、第二题再用这些词补句子，"
            "必须输出 q1 和 q2 两个 question_blocks。\n"
            "- learning_points 只收录有助于理解题目、答案或易错点的知识点，不要硬凑。\n"
            "- read_units 只收录适合 Android TTS 朗读的自然语言；复杂数学公式不要强行放入。\n"
            "- read_units 应尽量包含题目要求和答案解释中适合朗读的内容。\n"
            "- subject=science 时，除非题目无需步骤，否则 solution_steps 至少 1 项。\n"
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
        blocks = out.get("question_blocks")
        if isinstance(blocks, list):
            normalized_blocks: list[Any] = []
            for index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    normalized_blocks.append(block)
                    continue
                normalized_block = dict(block)
                normalized_block["block_id"] = str(
                    normalized_block.get("block_id") or f"q{index + 1}"
                ).strip()
                normalized_blocks.append(normalized_block)
            out["question_blocks"] = normalized_blocks

        lines = out.get("answer_lines")
        if isinstance(lines, list):
            normalized_lines: list[Any] = []
            for line in lines:
                if not isinstance(line, dict):
                    normalized_lines.append(line)
                    continue
                normalized_line = dict(line)
                normalized_line["block_id"] = str(
                    normalized_line.get("block_id") or ""
                ).strip()
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

        steps = out.get("solution_steps")
        if isinstance(steps, list):
            normalized_steps: list[Any] = []
            for step in steps:
                if not isinstance(step, dict):
                    normalized_steps.append(step)
                    continue
                normalized_step = dict(step)
                normalized_step["block_id"] = str(normalized_step.get("block_id") or "").strip()
                normalized_step["number"] = str(normalized_step.get("number") or "").strip()
                normalized_steps.append(normalized_step)
            out["solution_steps"] = normalized_steps
        return out

    def _normalize_word(self, raw: str) -> str:
        return raw.strip().lower().strip(".,!?;:()[]{}\"'")

    def _coverage_candidates(self, text: str) -> list[str]:
        words: list[str] = []
        for match in ENGLISH_WORD_RE.finditer(text):
            word = self._normalize_word(match.group(0))
            if len(word) <= 1 or word in VOCAB_SKIP_WORDS:
                continue
            words.append(word)
        return list(dict.fromkeys(words))

    def _vocabulary_keys(self, result: HomeworkParseResult) -> set[str]:
        keys: set[str] = set()
        for item in result.learning_points:
            if item.category != "word":
                continue
            key = self._normalize_word(item.term)
            if key:
                keys.add(key)
        for unit in result.read_units:
            if unit.unit_type != "word" or not unit.meaning_zh:
                continue
            key = self._normalize_word(unit.text)
            if key:
                keys.add(key)
        return keys

    def _missing_vocabulary_words(self, result: HomeworkParseResult) -> list[str]:
        expected: list[str] = []
        for line in result.answer_lines:
            expected.extend(self._coverage_candidates(line.plain_text))
        expected = list(dict.fromkeys(expected))
        if not expected:
            return []

        vocabulary_keys = self._vocabulary_keys(result)
        return [word for word in expected if word not in vocabulary_keys]

    def _mark_missing_vocabulary(
        self, result: HomeworkParseResult, missing: list[str] | None = None
    ) -> HomeworkParseResult:
        missing = missing if missing is not None else self._missing_vocabulary_words(result)
        if not missing:
            return result

        missing_text = ", ".join(missing[:12])
        reason = result.uncertainty.reason or ""
        coverage_reason = f"部分答案词缺少词义：{missing_text}"
        combined_reason = (
            f"{reason}；{coverage_reason}" if reason else coverage_reason
        )
        logger.info("parse_vocabulary_coverage_missing words=%s", missing_text)
        updated = result.model_copy(deep=True)
        updated.uncertainty.requires_review = True
        updated.uncertainty.confidence = min(updated.uncertainty.confidence, 0.85)
        updated.uncertainty.reason = combined_reason
        return updated

    def _build_vocabulary_repair_prompt(self, words: list[str]) -> str:
        payload = {"words": words}
        return (
            "你是英语词汇释义助手。请只为给定英文词补充中文释义和 IPA。\n"
            "只输出一个 JSON 对象，不要 markdown，不要代码块，不要额外文字。\n"
            "输出格式：{\"items\":[{\"word\":\"...\",\"meaning_zh\":\"...\",\"ipa\":\"...\"}]}。\n"
            "要求：\n"
            "- items 数组必须覆盖输入 words 中每个词。\n"
            "- word 保持输入单词原样。\n"
            "- meaning_zh 用简短中文释义，适合小学生/家长理解。\n"
            "- ipa 不确定可用 null。\n"
            f"输入：{payload}"
        )

    def _merge_vocabulary_items(
        self, result: HomeworkParseResult, items: list[dict[str, Any]]
    ) -> HomeworkParseResult:
        if not items:
            return result

        updated = result.model_copy(deep=True)
        existing_vocab = {
            self._normalize_word(item.term)
            for item in updated.learning_points
            if item.category == "word"
        }
        existing_word_units = {
            self._normalize_word(unit.text)
            for unit in updated.read_units
            if unit.unit_type == "word"
        }

        for raw in items:
            if not isinstance(raw, dict):
                continue
            word = str(raw.get("word", "")).strip()
            meaning = str(raw.get("meaning_zh", "")).strip()
            ipa_raw = raw.get("ipa")
            ipa = str(ipa_raw).strip() if ipa_raw is not None else None
            key = self._normalize_word(word)
            if not key or not meaning:
                continue
            if key not in existing_vocab:
                updated.learning_points.append(
                    LearningPoint(
                        term=word,
                        explanation_zh=meaning,
                        pronunciation=ipa or None,
                        category="word",
                    )
                )
                existing_vocab.add(key)
            if key not in existing_word_units:
                updated.read_units.append(
                    ReadUnit(
                        unit_type="word",
                        text=word,
                        meaning_zh=meaning,
                    )
                )
                existing_word_units.add(key)
        return updated

    async def _repair_missing_vocabulary(
        self, result: HomeworkParseResult, model: str | None
    ) -> HomeworkParseResult:
        missing = self._missing_vocabulary_words(result)
        if not missing:
            return result

        logger.info("parse_vocabulary_repair_start words=%s", ", ".join(missing[:12]))
        try:
            payload = await self.llm_client.generate_any_json(
                self._build_vocabulary_repair_prompt(missing), model=model
            )
        except AppError as exc:
            logger.warning("parse_vocabulary_repair_failed detail=%s", exc.detail)
            return self._mark_missing_vocabulary(result, missing)

        items = payload.get("items")
        if not isinstance(items, list):
            logger.warning("parse_vocabulary_repair_invalid_payload payload=%s", payload)
            return self._mark_missing_vocabulary(result, missing)

        repaired = self._merge_vocabulary_items(result, items)
        still_missing = self._missing_vocabulary_words(repaired)
        if still_missing:
            logger.info(
                "parse_vocabulary_repair_incomplete words=%s",
                ", ".join(still_missing[:12]),
            )
            return self._mark_missing_vocabulary(repaired, still_missing)

        logger.info("parse_vocabulary_repair_complete count=%s", len(items))
        return repaired

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
        subject: str = "general",
    ) -> HomeworkParseResult:
        start_ts = time.perf_counter()
        prompt = self._build_prompt(subject)

        candidate = await self._call_model(prompt, image_bytes, model)
        logger.info(
            "pipeline_step llm elapsed=%.2fs model=%s",
            time.perf_counter() - start_ts,
            (model or "").strip() or "<default>",
        )

        normalized_candidate = self._normalize_candidate(candidate)
        try:
            validated = self.schema_guard.validate_payload(normalized_candidate)
            if validated.subject != subject:
                raise AppError(
                    "SCHEMA_VALIDATION_FAILED",
                    f"response subject {validated.subject!r} does not match request subject {subject!r}",
                )
            if subject == "english":
                validated = await self._repair_missing_vocabulary(validated, model)
            logger.info(
                "pipeline_step schema_validate elapsed=%.2fs",
                time.perf_counter() - start_ts,
            )
            return validated
        except AppError as first_error:
            logger.warning("schema_validation_failed detail=%s", first_error.detail)
            raise
