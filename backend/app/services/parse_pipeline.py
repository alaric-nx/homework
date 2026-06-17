from __future__ import annotations

import logging
import json
import re
import tempfile
import time
from functools import lru_cache
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
LEARNING_POINT_CATEGORY_ALIASES = {
    "grammar": "concept",
    "phrase": "word",
    "vocabulary": "word",
    "sentence": "concept",
    "phonics": "word",
    "pinyin": "word",
}
LEARNING_POINT_CATEGORIES = {"word", "concept", "formula", "unit", "method", "other"}
READ_UNIT_TYPE_ALIASES = {
    "sentence": "text",
    "paragraph": "text",
    "answer": "text",
    "explanation": "text",
    "instruction": "text",
    "question_instruction": "text",
}
READ_UNIT_TYPES = {"word", "text"}


_SUBJECT_NOTES: dict[str, str] = {
    "general": (
        "你是通用作业解析助手。题目可能来自英语、语文、拼音、数学、科学或混合练习。"
        "先判断题目类型，再按题目块输出答案、必要步骤、中文讲解、知识点和朗读内容。"
        "不要强行套英语词汇表，也不要强行套数学公式。"
    ),
    "english": (
        "你是英语练习题解析助手，适用于英语作业、练习册、考试题和基础学习题。"
        "保持英语解析能力：完整答案行、题目要求原文、词义、发音(IPA)、句义和答案词义覆盖。"
        "learning_points 重点放英文单词、短语、语法点，pronunciation 放 IPA。"
        "read_units 放题目要求、答案句、需要点读的单词或短句。"
        "推导答案后，必须再检查语法、拼写、时态、单复数和常见英语表达是否地道。"
    ),
    "liberal_arts": (
        "你是文科作业解析助手，覆盖语文、拼音、道法、历史、地理等。"
        "重点识别题目要求、材料、问题、选项和答题依据。"
        "阅读理解和材料题必须说明答案依据。"
        "拼音题把拼音放入 learning_points.pronunciation。"
        "古诗文、文言文要在 read_units 同时给出原文和现代汉语翻译(meaning_zh)。"
        "作文或开放题给出可参考答案和审题提示，不编造唯一标准答案。"
    ),
    "science": (
        "你是理科作业解析助手，覆盖数学、科学、物理、化学等。"
        "必须提取已知条件、要求的问题、关键公式或方法。"
        "solution_steps 必须清楚展示列式、推理或计算过程。"
        "answer_lines 放最终答案或需要填写的关键内容，答案要带单位。"
        "单位、公式、易错概念进入 learning_points，不要给发音。复杂公式不要放入 read_units。"
    ),
}

# 各学科的内部推理步骤（不展示给用户），按学科定制思路。
_REASONING_STEPS: dict[str, str] = {
    "general": (
        "A. 判断图片里有几个独立题目块：看编号、标题、题目要求行、分隔线、版面分区。\n"
        "B. 作答要求/编号体系/版面分区不同的，必须拆成不同 question_blocks。\n"
        "C. 为每个题目块判断题型：填空、选择、判断、连线、排序、阅读、计算、作文等。\n"
        "D. 找出每个题目块的作答要求。\n"
        "E. 用最稳妥的方式推导答案，必要时补充步骤或依据，不强行套某一学科套路。\n"
        "F. 检查答案是否符合图片、题干与学科常识。\n"
    ),
    "english": (
        "A. 判断题目块数量与边界：看编号、标题、分隔线、版面分区。\n"
        "B. 作答要求/编号/版面不同的，拆成不同 question_blocks。\n"
        "C. 判断每个题目块题型：填空、选择、连词成句、阅读、翻译、改错等。\n"
        "D. 推导答案；填空/补全必须给出补全后的完整句子。\n"
        "E. 检查语法、拼写、时态、单复数与地道表达。\n"
        "F. 为答案中的关键英文词补充词义和 IPA，确保答案词义覆盖。\n"
    ),
    "liberal_arts": (
        "A. 判断题目块数量与边界：看编号、标题、分隔线、版面分区。\n"
        "B. 读懂材料/题干/选项，明确每个题目块的作答要求。\n"
        "C. 判断题型：阅读理解、拼音、字词、古诗文、选择、填空、作文等。\n"
        "D. 推导答案；阅读理解和材料题必须给出答题依据。\n"
        "E. 拼音题给出拼音，古诗文给出现代汉语翻译，字词给出释义。\n"
        "F. 检查答案是否扣题、是否有据、是否符合常识。\n"
    ),
    "science": (
        "A. 判断题目块数量与边界：看编号、标题、分隔线、版面分区。\n"
        "B. 提取每个题目块的已知条件、所求问题与单位。\n"
        "C. 判断题型（计算、应用、证明、选择、填空等），选择合适的公式或方法。\n"
        "D. 在 solution_steps 中分步列式、推理、计算。\n"
        "E. 得出最终答案并标注单位，answer_lines 放最终答案或关键列式。\n"
        "F. 验算并检查单位、量纲与合理性。\n"
    ),
}

# 在通用题型规则之后，针对各学科追加强调（不删除通用题型，只做加法）。
_SUBJECT_TYPE_NOTES: dict[str, str] = {
    "general": "",
    "english": (
        "英语补充规则：\n"
        "- 填空/补全/连词成句：plain_text 必须是补全后的完整句子或短语。\n"
        "- 答案中的关键英文词放入 learning_points(category=word)，尽量给 IPA。\n"
        "- read_units 放题目要求、答案句、需要点读的单词或短句。\n"
    ),
    "liberal_arts": (
        "文科补充规则：\n"
        "- 阅读理解/材料题：答案必须说明依据。\n"
        "- 拼音题：把拼音放入 learning_points.pronunciation。\n"
        "- 古诗文/文言文：read_units 的 text 放原文，meaning_zh 放现代汉语翻译，便于点读和对照。\n"
        "- 作文/开放题：给参考提纲或参考答案，不编造唯一标准答案。\n"
    ),
    "science": (
        "理科补充规则：\n"
        "- 计算/应用/证明题：solution_steps 至少 1 项，清楚展示列式、推理或计算过程；"
        "answer_lines 放最终答案或关键列式，答案要带单位。\n"
        "- 公式、单位、易错概念放入 learning_points(category=formula/unit/method/concept)，不要给发音。\n"
        "- 复杂数学公式不要放入 read_units；read_units 只放自然语言（如题意、讲解）。\n"
    ),
}

# 每个学科一个精简示例：只示意结构与字段关系，帮助模型稳定产出 v3 JSON（请勿照抄内容）。
_SUBJECT_EXAMPLES: dict[str, str] = {
    "general": (
        "结构示例（仅示意，请勿照抄）：\n"
        "{\n"
        '  "subject": "general",\n'
        '  "question_meaning_zh": "本图包含1个题目块，单项选择。",\n'
        '  "question_instruction": {"text": "选择正确答案。", "meaning_zh": "选出正确选项。", "confidence": 0.93},\n'
        '  "question_blocks": [{"block_id": "q1", "title": "第1题", "question_instruction": {"text": "选择正确答案。", "meaning_zh": "选出正确选项。", "confidence": 0.93}, "question_meaning_zh": "从选项中选出正确答案。"}],\n'
        '  "answer_lines": [{"block_id": "q1", "number": "1", "line_type": "choice", "plain_text": "B", "segments": [{"text": "B", "role": "answer"}]}],\n'
        '  "solution_steps": [],\n'
        '  "explanation_zh": "根据题意，B 项符合。",\n'
        '  "learning_points": [],\n'
        '  "read_units": [],\n'
        '  "uncertainty": {"requires_review": false, "confidence": 0.9, "reason": null}\n'
        "}\n"
    ),
    "english": (
        "结构示例（仅示意，请勿照抄）：\n"
        "{\n"
        '  "subject": "english",\n'
        '  "question_meaning_zh": "本图包含1个题目块，要求补全句子。",\n'
        '  "question_instruction": {"text": "Complete the sentence.", "meaning_zh": "补全句子。", "confidence": 0.95},\n'
        '  "question_blocks": [{"block_id": "q1", "title": "第1题", "question_instruction": {"text": "Complete the sentence.", "meaning_zh": "补全句子。", "confidence": 0.95}, "question_meaning_zh": "把空格补成完整句子。"}],\n'
        '  "answer_lines": [{"block_id": "q1", "number": "1", "line_type": "fill_blank", "plain_text": "I am a student.", "segments": [{"text": "I ", "role": "given"}, {"text": "am", "role": "answer"}, {"text": " a student.", "role": "given"}]}],\n'
        '  "solution_steps": [],\n'
        '  "explanation_zh": "be 动词与 I 搭配用 am。",\n'
        '  "learning_points": [{"block_id": "q1", "term": "am", "explanation_zh": "是", "pronunciation": "/æm/", "category": "word", "label": "vocabulary"}],\n'
        '  "read_units": [{"block_id": "q1", "unit_type": "text", "label": "answer", "text": "I am a student.", "meaning_zh": "我是一名学生。"}],\n'
        '  "uncertainty": {"requires_review": false, "confidence": 0.95, "reason": null}\n'
        "}\n"
        "注意：plain_text 必须等于 segments 各 text 顺序拼接。上例 \"I \"+\"am\"+\" a student.\" = \"I am a student.\"。\n"
    ),
    "liberal_arts": (
        "结构示例（仅示意，请勿照抄）：\n"
        "{\n"
        '  "subject": "liberal_arts",\n'
        '  "question_meaning_zh": "本图包含1个题目块，古文填空。",\n'
        '  "question_instruction": {"text": "在横线上填写原句。", "meaning_zh": "默写古文原句。", "confidence": 0.94},\n'
        '  "question_blocks": [{"block_id": "q1", "title": "第1题", "question_instruction": {"text": "在横线上填写原句。", "meaning_zh": "默写古文原句。", "confidence": 0.94}, "question_meaning_zh": "补全《论语》名句。"}],\n'
        '  "answer_lines": [{"block_id": "q1", "number": "1", "line_type": "fill_blank", "plain_text": "学而时习之，不亦说乎", "segments": [{"text": "学而时习之，", "role": "given"}, {"text": "不亦说乎", "role": "answer"}]}],\n'
        '  "solution_steps": [],\n'
        '  "explanation_zh": "出自《论语》，“说”通“悦”，意为愉快。",\n'
        '  "learning_points": [{"block_id": "q1", "term": "说", "explanation_zh": "通“悦”，愉快。", "pronunciation": "yuè", "category": "word", "label": "字词"}],\n'
        '  "read_units": [{"block_id": "q1", "unit_type": "text", "label": "answer", "text": "学而时习之，不亦说乎", "meaning_zh": "学习并经常温习，不也很愉快吗？"}],\n'
        '  "uncertainty": {"requires_review": false, "confidence": 0.94, "reason": null}\n'
        "}\n"
        "注意：古诗文/文言句子在 read_units 用 text 放原文、meaning_zh 放现代汉语翻译。\n"
    ),
    "science": (
        "结构示例（仅示意，请勿照抄）：\n"
        "{\n"
        '  "subject": "science",\n'
        '  "question_meaning_zh": "本图包含1个题目块，求长方形面积。",\n'
        '  "question_instruction": {"text": "求下面长方形的面积。", "meaning_zh": "计算长方形面积。", "confidence": 0.96},\n'
        '  "question_blocks": [{"block_id": "q1", "title": "第1题", "question_instruction": {"text": "求下面长方形的面积。", "meaning_zh": "计算面积。", "confidence": 0.96}, "question_meaning_zh": "已知长8cm、宽5cm，求面积。"}],\n'
        '  "answer_lines": [{"block_id": "q1", "number": "1", "line_type": "calculation", "plain_text": "8 × 5 = 40（平方厘米）", "segments": [{"text": "8 × 5 = ", "role": "given"}, {"text": "40（平方厘米）", "role": "answer"}]}],\n'
        '  "solution_steps": [{"block_id": "q1", "number": "1", "title": "面积公式", "content_zh": "长方形面积等于长乘宽。", "formula": "S = 长 × 宽", "result": null}, {"block_id": "q1", "number": "2", "title": "代入计算", "content_zh": "把长8、宽5代入公式。", "formula": "8 × 5 = 40", "result": "40 平方厘米"}],\n'
        '  "explanation_zh": "考查长方形面积公式，注意单位是平方厘米。",\n'
        '  "learning_points": [{"block_id": "q1", "term": "长方形面积公式", "explanation_zh": "面积 = 长 × 宽。", "pronunciation": null, "category": "formula", "label": "formula"}],\n'
        '  "read_units": [{"block_id": "q1", "unit_type": "text", "label": "explanation", "text": "长方形面积等于长乘宽。", "meaning_zh": null}],\n'
        '  "uncertainty": {"requires_review": false, "confidence": 0.96, "reason": null}\n'
        "}\n"
    ),
}


@lru_cache(maxsize=8)
def _compose_subject_prompt(subject: str) -> str:
    """构建并缓存指定学科的完整提示词。

    结构：学科角色说明 + 共享字段约束/证据原则 + 学科定制推理步骤 +
    共享字段定义 + 共享通用题型规则 + 学科追加题型强调 + 共享质量/不确定性规则 + 学科示例。
    subject 仅 4 种取值，使用 lru_cache 避免重复拼接大字符串。
    """
    notes = _SUBJECT_NOTES.get(subject, _SUBJECT_NOTES["general"])
    reasoning = _REASONING_STEPS.get(subject, _REASONING_STEPS["general"])
    type_notes = _SUBJECT_TYPE_NOTES.get(subject, "")
    example = _SUBJECT_EXAMPLES.get(subject, _SUBJECT_EXAMPLES["general"])
    type_notes_block = ("\n" + type_notes) if type_notes else ""
    return (
        notes
        + "\n"
        "\n"
        "必须严格遵守：\n"
        "1) 只输出一个 JSON 对象，不要 markdown，不要代码块，不要任何额外文字。\n"
        "2) 只允许以下字段：subject, question_meaning_zh, question_instruction, question_blocks, "
        "answer_lines, solution_steps, explanation_zh, learning_points, read_units, uncertainty。\n"
        "3) 字段必须齐全，不能缺失，不能新增字段；不要输出 reference_answer。\n"
        f"4) subject 必须固定输出为 \"{subject}\"。\n"
        "5) solution_steps 是数组，元素字段：block_id, number, title, content_zh, formula, result。\n"
        "6) learning_points 是数组，元素字段：block_id, term, explanation_zh, pronunciation, category, label。\n"
        "category 只能是 word, concept, formula, unit, method, other；语法点用 concept，短语/拼音/自然拼读用 word，细分类写入 label。\n"
        "7) read_units 是数组，元素字段：block_id, unit_type, label, text, meaning_zh。unit_type 只能是 word 或 text；"
        "题目要求、句子、段落、答案、讲解都用 text，细分类写入 label。\n"
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
        + reasoning
        + "\n"
        "question_blocks 是题目块列表。每个元素代表图片中的一个独立题目块，字段为：\n"
        "- block_id: 稳定 ID，只能用 q1, q2, q3...，按图片阅读顺序编号。\n"
        "- title: 题目块标题，可用图片中的大题编号/标题；没有标题时用 第1题、第2题。\n"
        "- question_instruction: 该题目块的题目要求原句和中文解释。\n"
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
        "通用题型规则（所有学科通用，选择题和填空题各学科都可能出现）：\n"
        "- 填空、补全句子、看图填空：plain_text 必须是补全后的完整句子或完整短语，不允许只输出填空词；"
        "segments 中题目已有文字标为 given，填入答案标为 answer。\n"
        "- 选择题：选项字母和选中内容标为 answer。\n"
        "- 看图写词/短语：答案整体标为 answer。\n"
        "- 连线/匹配：题目已有内容可标为 given，配对关系或选中编号标为 answer。\n"
        "- 排序/连词成句：最终正确句整体标为 answer。\n"
        "- 阅读问答：回答整体标为 answer。\n"
        "- 改错题：未改部分标为 given，订正内容标为 correction。\n"
        "- 抄写题：照抄内容可标为 given，讲解中说明照抄即可。\n"
        + type_notes_block
        + "\n"
        "一致性硬约束（务必遵守）：\n"
        "- plain_text 必须严格等于 segments 中各 text 字段按顺序拼接的结果，只允许去除整行首尾空白；"
        "不得出现 plain_text 与 segments 内容不一致。这样可保证朗读文本与高亮内容完全一致。\n"
        "\n"
        "输出质量规则：\n"
        "- 若图片中有多个题目块，必须先按题目块顺序输出 question_blocks，再按题目块顺序输出 answer_lines。\n"
        "- 若题目含编号，请按检测到的编号顺序给出 answer_lines；若无编号，请按题面阅读顺序组织。\n"
        "- 同一张图中两个相关题目不能混成一个题目块；例如第一题先补全单词、第二题再用这些词补句子，"
        "必须输出 q1 和 q2 两个 question_blocks。\n"
        "- learning_points 只收录有助于理解题目、答案或易错点的知识点，不要硬凑；label 可写 grammar, phrase, pinyin, phonics 等自由标签。\n"
        "- read_units 只收录适合 Android TTS 朗读的自然语言；复杂数学公式不要强行放入；label 可写 instruction, answer, explanation 等自由标签。\n"
        "- read_units 应尽量包含题目要求和答案解释中适合朗读的内容。\n"
        "- 如果某个答案不确定，仍按编号保留位置，并在 uncertainty 中说明。\n"
        "\n"
        "不确定性规则：\n"
        "- 图片模糊、裁切、遮挡、编号不完整、选项看不清、答案依赖外部上下文时，requires_review=true。\n"
        "- confidence 取值：清晰可靠 0.9-1.0；轻微歧义 0.7-0.89；明显推测 0.4-0.69；无法可靠作答 0-0.39。\n"
        "\n"
        + example
    )


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
        return _compose_subject_prompt(subject)

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
                instruction = normalized_block.get("question_instruction")
                if isinstance(instruction, str):
                    normalized_block["question_instruction"] = {
                        "text": instruction.strip(),
                        "meaning_zh": "",
                        "confidence": 0.0,
                    }
                normalized_blocks.append(normalized_block)
            out["question_blocks"] = normalized_blocks

        # 已知题目块 ID，用于 answer_lines / solution_steps 缺失 block_id 时兜底，
        # 避免本可成立的结果因引用缺失而触发额外的修复模型调用。
        known_block_ids: list[str] = []
        qb = out.get("question_blocks")
        if isinstance(qb, list):
            for block in qb:
                if isinstance(block, dict):
                    bid = str(block.get("block_id") or "").strip()
                    if bid:
                        known_block_ids.append(bid)
        fallback_block_id = known_block_ids[0] if known_block_ids else "q1"

        lines = out.get("answer_lines")
        if isinstance(lines, list):
            normalized_lines: list[Any] = []
            for line in lines:
                if not isinstance(line, dict):
                    normalized_lines.append(line)
                    continue
                normalized_line = dict(line)
                block_id = str(normalized_line.get("block_id") or "").strip()
                # block_id 缺失或无法对应已知题目块时，兜底到首个题目块。
                if not block_id or (known_block_ids and block_id not in known_block_ids):
                    block_id = fallback_block_id
                normalized_line["block_id"] = block_id
                if normalized_line.get("number") is not None:
                    normalized_line["number"] = str(normalized_line["number"]).strip()

                segments = normalized_line.get("segments")
                plain_text = str(normalized_line.get("plain_text") or "").strip()
                # segments 缺失但有 plain_text：用 plain_text 兜底成单段。
                if not segments and plain_text:
                    segments = [{"text": plain_text, "role": "answer"}]
                    normalized_line["segments"] = segments

                # 一致性：plain_text 必须等于 segments 文本顺序拼接（仅去首尾空白）。
                # segments 是前端高亮与朗读的结构来源，二者不一致时以 segments 为准，
                # 保证朗读文本与展示内容完全一致。
                if isinstance(segments, list) and segments:
                    concat = "".join(
                        str(seg.get("text", ""))
                        for seg in segments
                        if isinstance(seg, dict)
                    ).strip()
                    if concat and concat != plain_text:
                        normalized_line["plain_text"] = concat

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
                step_block_id = str(normalized_step.get("block_id") or "").strip()
                if not step_block_id or (
                    known_block_ids and step_block_id not in known_block_ids
                ):
                    step_block_id = fallback_block_id
                normalized_step["block_id"] = step_block_id
                normalized_step["number"] = str(normalized_step.get("number") or "").strip()
                normalized_steps.append(normalized_step)
            out["solution_steps"] = normalized_steps

        learning_points = out.get("learning_points")
        if isinstance(learning_points, list):
            normalized_points: list[Any] = []
            for item in learning_points:
                if not isinstance(item, dict):
                    normalized_points.append(item)
                    continue
                normalized_item = dict(item)
                category = str(normalized_item.get("category") or "").strip().lower()
                if normalized_item.get("label") is None and category:
                    normalized_item["label"] = category
                if category in LEARNING_POINT_CATEGORY_ALIASES:
                    mapped = LEARNING_POINT_CATEGORY_ALIASES[category]
                    normalized_item["category"] = mapped
                    logger.info(
                        "enum_normalized field=learning_points.category from=%s to=%s label=%s",
                        category,
                        mapped,
                        normalized_item.get("label"),
                    )
                elif category not in LEARNING_POINT_CATEGORIES:
                    normalized_item["category"] = "other"
                    logger.info(
                        "enum_defaulted field=learning_points.category from=%s to=other label=%s",
                        category,
                        normalized_item.get("label"),
                    )
                normalized_points.append(normalized_item)
            out["learning_points"] = normalized_points

        read_units = out.get("read_units")
        if isinstance(read_units, list):
            normalized_units: list[Any] = []
            for unit in read_units:
                if not isinstance(unit, dict):
                    normalized_units.append(unit)
                    continue
                normalized_unit = dict(unit)
                unit_type = str(normalized_unit.get("unit_type") or "").strip().lower()
                if normalized_unit.get("label") is None and unit_type:
                    normalized_unit["label"] = unit_type
                if unit_type in READ_UNIT_TYPE_ALIASES:
                    mapped = READ_UNIT_TYPE_ALIASES[unit_type]
                    normalized_unit["unit_type"] = mapped
                    logger.info(
                        "enum_normalized field=read_units.unit_type from=%s to=%s label=%s",
                        unit_type,
                        mapped,
                        normalized_unit.get("label"),
                    )
                elif unit_type not in READ_UNIT_TYPES:
                    normalized_unit["unit_type"] = "text"
                    logger.info(
                        "enum_defaulted field=read_units.unit_type from=%s to=text label=%s",
                        unit_type,
                        normalized_unit.get("label"),
                    )
                normalized_units.append(normalized_unit)
            out["read_units"] = normalized_units

        # 补全缺失的可选字段，使其满足 schema guard 的严格字段集校验，
        # 避免"模型只是漏了某个可选字段"也要多调一次修复模型。
        out.setdefault("solution_steps", [])
        out.setdefault("learning_points", [])
        out.setdefault("read_units", [])
        out.setdefault(
            "question_instruction",
            {"text": "", "meaning_zh": "", "confidence": 0.0},
        )
        out.setdefault(
            "uncertainty",
            {"requires_review": False, "confidence": 0.8, "reason": None},
        )
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

    def _build_json_repair_prompt(
        self, subject: str, candidate: Any, error_detail: str
    ) -> str:
        raw_json = json.dumps(candidate, ensure_ascii=False)
        return (
            "你是 JSON 契约修复助手。请只修复给定 JSON 的结构、字段名、字段类型、缺失空数组和枚举值，"
            "不得重新解题，不得改变答案内容、题号、题目块、讲解含义。\n"
            "只输出一个 JSON 对象，不要 markdown，不要代码块，不要额外文字。\n"
            f"请求 subject 固定为：{subject}。输出 subject 必须等于该值。\n"
            "顶层字段只能是：subject, question_meaning_zh, question_instruction, question_blocks, "
            "answer_lines, solution_steps, explanation_zh, learning_points, read_units, uncertainty。\n"
            "learning_points[].category 只能是 word, concept, formula, unit, method, other；"
            "原始细分类放入 label。\n"
            "read_units[].unit_type 只能是 word 或 text；原始细分类放入 label。\n"
            "answer_lines[].segments[].role 只能是 given, answer, connector, correction。\n"
            "所有数组字段必须存在，没有内容用空数组。\n"
            "question_instruction 必须是对象，字段 text, meaning_zh, confidence。\n"
            "answer_lines、solution_steps、learning_points、read_units 中的 block_id 必须对应 question_blocks，"
            "learning_points/read_units 的 block_id 可以为 null。\n"
            f"schema 错误：{error_detail}\n"
            f"待修复 JSON：{raw_json}"
        )

    async def _repair_json_contract_once(
        self,
        candidate: Any,
        subject: str,
        model: str | None,
        error: AppError,
    ) -> HomeworkParseResult:
        logger.info("parse_json_repair_start detail=%s", error.detail)
        payload = await self.llm_client.generate_any_json(
            self._build_json_repair_prompt(subject, candidate, error.detail),
            model=model,
        )
        normalized = self._normalize_candidate(payload)
        validated = self.schema_guard.validate_payload(normalized)
        if validated.subject != subject:
            raise AppError(
                "SCHEMA_VALIDATION_FAILED",
                f"response subject {validated.subject!r} does not match request subject {subject!r}",
            )
        logger.info("parse_json_repair_complete")
        return validated

    def _is_json_repair_allowed(self, error: AppError) -> bool:
        detail = error.detail.lower()
        if "does not match request subject" in detail:
            return False
        if "not found in question_blocks" in detail:
            return False
        if "segments" in detail and "role" in detail:
            return False
        return True

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
                        label="vocabulary",
                    )
                )
                existing_vocab.add(key)
            if key not in existing_word_units:
                updated.read_units.append(
                    ReadUnit(
                        unit_type="word",
                        label="vocabulary",
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
        used_json_repair = False
        try:
            validated = self._validate_subject_result(normalized_candidate, subject)
        except AppError as first_error:
            logger.warning("schema_validation_failed detail=%s", first_error.detail)
            if not self._is_json_repair_allowed(first_error):
                raise
            try:
                validated = await self._repair_json_contract_once(
                    candidate=candidate,
                    subject=subject,
                    model=model,
                    error=first_error,
                )
                used_json_repair = True
            except AppError as repair_error:
                logger.warning("schema_repair_failed detail=%s", repair_error.detail)
                raise repair_error

        if subject == "english" and not used_json_repair:
            validated = await self._repair_missing_vocabulary(validated, model)
        logger.info(
            "pipeline_step schema_validate elapsed=%.2fs json_repair=%s",
            time.perf_counter() - start_ts,
            used_json_repair,
        )
        return validated

    def _validate_subject_result(
        self, payload: dict[str, Any], subject: str
    ) -> HomeworkParseResult:
        validated = self.schema_guard.validate_payload(payload)
        if validated.subject != subject:
            raise AppError(
                "SCHEMA_VALIDATION_FAILED",
                f"response subject {validated.subject!r} does not match request subject {subject!r}",
            )
        return validated
