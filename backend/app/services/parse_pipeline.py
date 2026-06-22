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
from app.core.models import HomeworkParseResult, LearningPoint
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
CONTENT_ITEM_TYPE_ALIASES = {
    "question_instruction": "instruction",
    "sentence": "context",
    "paragraph": "material",
    "text": "context",
    "scene": "context",
    "passage": "material",
    "wordbank": "word_bank",
    "word_bank": "word_bank",
}
CONTENT_ITEM_TYPES = {
    "instruction",
    "example",
    "context",
    "material",
    "dialogue",
    "word_bank",
    "option",
    "image_text",
    "other",
}
DISPLAY_MODES_BY_ANSWER_TYPE = {
    "calculation": "math_block",
    "proof": "math_block",
    "composition": "paragraph",
    "reading_qa": "paragraph",
    "choice": "choice",
    "matching": "matching",
    "pinyin": "pinyin",
    "copying": "copying",
}
DISPLAY_FORMATS = {"plain_text", "plain_math", "latex", "vertical_calculation", "table"}
ANSWER_TYPES = {
    "fill_blank",
    "choice",
    "picture_word",
    "matching",
    "sentence_ordering",
    "reading_qa",
    "translation",
    "correction",
    "copying",
    "calculation",
    "proof",
    "short_answer",
    "composition",
    "pinyin",
    "other",
}


_SUBJECT_NOTES: dict[str, str] = {
    "general": (
        "你是通用作业解析助手。题目可能来自英语、语文、拼音、数学、科学或混合练习。"
        "先判断题目类型，再按题目块输出答案、必要步骤、中文讲解、知识点和朗读内容。"
        "不要强行套英语词汇表，也不要强行套数学公式。"
    ),
    "english": (
        "你是英语练习题解析助手，适用于英语作业、练习册、考试题和基础学习题。"
        "保持英语解析能力：完整答案项、题目要求原文、例句/场景/短文材料、词义、发音(IPA)、句义和答案词义覆盖。"
        "learning_points 重点放英文单词、短语、语法点，pronunciation 放 IPA。"
        "question_blocks[].content_items 必须放题目要求、例句、场景、短文、词库、选项等题面内容，并为可朗读内容提供 speak_text。"
        "推导答案后，必须再检查语法、拼写、时态、单复数和常见英语表达是否地道。"
    ),
    "liberal_arts": (
        "你是文科作业解析助手，覆盖语文、拼音、道法、历史、地理等。"
        "重点识别题目要求、材料、问题、选项和答题依据。"
        "阅读理解和材料题必须说明答案依据。"
        "拼音题把拼音放入 learning_points.pronunciation。"
        "古诗文、文言文要在 content_items 中放原文和现代汉语翻译(meaning_zh)。"
        "作文或开放题给出可参考答案和审题提示，不编造唯一标准答案。"
    ),
    "science": (
        "你是理科作业解析助手，覆盖数学、科学、物理、化学等。"
        "必须提取已知条件、要求的问题、关键公式或方法。"
        "solution_steps 必须清楚展示列式、推理或计算过程。"
        "answer_items 放最终答案或需要填写的关键内容，答案要带单位。"
        "单位、公式、易错概念进入 learning_points，不要给发音。复杂公式的 speak_text 要用适合朗读的自然语言。"
    ),
}

# 各学科的内部推理步骤（不展示给用户），按学科定制思路。
_REASONING_STEPS: dict[str, str] = {
    "general": (
        "A. 判断图片里有几个独立可批改小题：优先看每个小题编号、答案空格、选项组、作答位置和学生作答痕迹。\n"
        "B. 独立可批改小题必须拆成不同 question_blocks；大题标题、题型说明、共同材料只放入 content_items，不单独决定题卡粒度。\n"
        "C. 为每个题目块判断题型：填空、选择、判断、连线、排序、阅读、计算、作文等。\n"
        "D. 找出每个题目块的作答要求。\n"
        "E. 用最稳妥的方式推导答案，必要时补充步骤或依据，不强行套某一学科套路。\n"
        "F. 检查答案是否符合图片、题干与学科常识。\n"
    ),
    "english": (
        "A. 判断独立可批改小题数量与边界：看小题编号、空格、选项组、作答位置和版面分隔。\n"
        "B. 独立可批改小题必须拆成不同 question_blocks；共同例句、词库、题目要求只放入 content_items。\n"
        "C. 判断每个题目块题型：填空、选择、连词成句、阅读、翻译、改错等。\n"
        "D. 推导答案；填空/补全必须给出补全后的完整句子。\n"
        "E. 检查语法、拼写、时态、单复数与地道表达。\n"
        "F. 识别学生手写答案；如存在，逐题判断正确、错误、部分正确、未答或看不清。\n"
        "G. 为答案中的关键英文词补充词义和 IPA，确保答案词义覆盖。\n"
    ),
    "liberal_arts": (
        "A. 判断独立可批改小题数量与边界：看小题编号、问题、作答位置、材料引用和版面分隔。\n"
        "B. 读懂材料/题干/选项，明确每个题目块的作答要求。\n"
        "C. 判断题型：阅读理解、拼音、字词、古诗文、选择、填空、作文等。\n"
        "D. 推导答案；阅读理解和材料题必须给出答题依据。\n"
        "E. 拼音题给出拼音，古诗文给出现代汉语翻译，字词给出释义。\n"
        "F. 检查答案是否扣题、是否有据、是否符合常识。\n"
    ),
    "science": (
        "A. 判断独立可批改小题数量与边界：看小题编号、选项组、计算题空、作答位置和学生作答痕迹。\n"
        "B. 提取每个题目块的已知条件、所求问题与单位。\n"
        "C. 判断题型（计算、应用、证明、选择、填空等），选择合适的公式或方法。\n"
        "D. 在 solution_steps 中分步列式、推理、计算。\n"
        "E. 得出最终答案并标注单位，answer_items 放最终答案或关键列式。\n"
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
        "- content_items 放题目要求、例句、场景、短文、词库、选项等题面内容，并为可朗读内容提供 speak_text。\n"
    ),
    "liberal_arts": (
        "文科补充规则：\n"
        "- 阅读理解/材料题：答案必须说明依据。\n"
        "- 拼音题：把拼音放入 learning_points.pronunciation。\n"
        "- 古诗文/文言文：content_items 的 text 放原文，meaning_zh 放现代汉语翻译，便于点读和对照。\n"
        "- 作文/开放题：给参考提纲或参考答案，不编造唯一标准答案。\n"
    ),
    "science": (
        "理科补充规则：\n"
        "- 计算/应用/证明题：solution_steps 至少 1 项，清楚展示列式、推理或计算过程；"
        "answer_items 只放最终答案或必须填写的关键结果，答案要带单位；逐题推理和解释放入同 block_id 的 solution_steps。\n"
        "- 公式、单位、易错概念放入 learning_points(category=formula/unit/method/concept)，不要给发音。\n"
        "- 复杂数学公式的 speak_text 使用自然语言读法；display.mode 使用 math_block。\n"
    ),
}

# 每个学科一个精简示例：只示意结构与字段关系，帮助模型稳定产出 v4 JSON（请勿照抄内容）。
_SUBJECT_EXAMPLES: dict[str, str] = {
    "general": (
        "结构示例（仅示意，请勿照抄）：\n"
        "{\n"
        '  "schema_version": "4.0",\n'
        '  "subject": "general",\n'
        '  "question_meaning_zh": "题目要求从选项中选择正确答案。",\n'
        '  "question_blocks": [{"block_id": "q1", "order": 1, "title": "第1题", "question_meaning_zh": "从选项中选出正确答案。", "content_items": [{"item_id": "q1-c1", "order": 1, "group_id": null, "type": "instruction", "text": "选择正确答案。", "meaning_zh": "选出正确选项。", "language": "zh", "speak_text": "选择正确答案。", "speakable": true}]}],\n'
        '  "answer_items": [{"answer_id": "q1-a1", "block_id": "q1", "order": 1, "number": "1", "answer_type": "choice", "plain_text": "B", "speak_text": "B", "display": {"mode": "choice", "format": "plain_text", "latex": null, "preserve_newlines": false, "runs": [{"text": "B", "role": "answer"}]}}],\n'
        '  "student_answer_reviews": [],\n'
        '  "solution_steps": [],\n'
        '  "explanation_zh": "根据题意，B 项符合。",\n'
        '  "learning_points": [],\n'
        '  "uncertainty": {"requires_review": false, "confidence": 0.9, "reason": null}\n'
        "}\n"
    ),
    "english": (
        "结构示例（仅示意，请勿照抄）：\n"
        "{\n"
        '  "schema_version": "4.0",\n'
        '  "subject": "english",\n'
        '  "question_meaning_zh": "题目要求根据例句补全句子。",\n'
        '  "question_blocks": [{"block_id": "q1", "order": 1, "title": "第1题", "question_meaning_zh": "读例句后把空格补成完整句子。", "content_items": [{"item_id": "q1-c1", "order": 1, "group_id": null, "type": "instruction", "text": "Complete the sentence.", "meaning_zh": "补全句子。", "language": "en", "speak_text": "Complete the sentence.", "speakable": true}, {"item_id": "q1-c2", "order": 2, "group_id": "example-1", "type": "example", "text": "Example: I am happy.", "meaning_zh": "例句：我很开心。", "language": "en", "speak_text": "I am happy.", "speakable": true}]}],\n'
        '  "answer_items": [{"answer_id": "q1-a1", "block_id": "q1", "order": 1, "number": "1", "answer_type": "fill_blank", "plain_text": "I am a student.", "speak_text": "I am a student.", "display": {"mode": "inline_segments", "format": "plain_text", "latex": null, "preserve_newlines": false, "runs": [{"text": "I ", "role": "given"}, {"text": "am", "role": "answer"}, {"text": " a student.", "role": "given"}]}}],\n'
        '  "student_answer_reviews": [{"review_id": "q1-r1", "block_id": "q1", "answer_id": "q1-a1", "order": 1, "number": "1", "student_answer": "am", "correct_answer": "am", "status": "correct", "feedback_zh": "填写正确。", "confidence": 0.95}],\n'
        '  "solution_steps": [],\n'
        '  "explanation_zh": "be 动词与 I 搭配用 am。",\n'
        '  "learning_points": [{"block_id": "q1", "term": "am", "explanation_zh": "是", "pronunciation": "/æm/", "category": "word", "label": "vocabulary"}],\n'
        '  "uncertainty": {"requires_review": false, "confidence": 0.95, "reason": null}\n'
        "}\n"
    ),
    "liberal_arts": (
        "结构示例同 general，但古诗文/阅读材料必须放入 content_items；student_answer_reviews 用于批改手写答案。\n"
    ),
    "science": (
        "结构示例同 general，但计算题 answer_items[].display.mode 使用 math_block，speak_text 用自然语言读法，solution_steps 给出列式和推理。\n"
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
        "2) 只允许以下顶层字段：schema_version, subject, question_meaning_zh, question_blocks, "
        "answer_items, student_answer_reviews, solution_steps, explanation_zh, learning_points, uncertainty。\n"
        "3) 字段必须齐全，不能缺失，不能新增字段；不要输出 question_instruction, answer_lines, read_units, reference_answer。\n"
        '4) schema_version 必须固定输出为 "4.0"。\n'
        f"5) subject 必须固定输出为 \"{subject}\"。\n"
        "6) question_blocks 是数组，元素字段：block_id, order, title, question_meaning_zh, content_items。\n"
        "7) content_items 是题面可见内容数组，元素字段：item_id, order, group_id, type, text, meaning_zh, language, speak_text, speakable。\n"
        "8) answer_items 是参考答案数组，元素字段：answer_id, block_id, order, number, answer_type, plain_text, speak_text, display。\n"
        "9) display 字段：mode, format, latex, preserve_newlines, runs；runs 元素字段 text, role。\n"
        "10) student_answer_reviews 是学生手写答案批改数组，元素字段：review_id, block_id, answer_id, order, number, student_answer, correct_answer, status, feedback_zh, confidence。无手写答案时输出空数组。\n"
        "11) solution_steps 是数组，元素字段：block_id, number, title, content_zh, formula, result。\n"
        "12) learning_points 是数组，元素字段：block_id, term, explanation_zh, pronunciation, category, label。\n"
        "category 只能是 word, concept, formula, unit, method, other；语法点用 concept，短语/拼音/自然拼读用 word，细分类写入 label。\n"
        "13) uncertainty 字段：requires_review(boolean), confidence(0到1), reason(可空字符串)。\n"
        "14) question_meaning_zh 用中文概括整张图里的练习内容。如果有多个题目块，要说明包含几个题目块。\n"
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
        "question_blocks 是题目块列表。每个元素代表图片中的一个独立可批改小题，字段为：\n"
        "- block_id: 稳定 ID，只能用 q1, q2, q3...，按图片阅读顺序编号。\n"
        "- order: 从 1 开始的题块阅读顺序，同一图片内不能重复。\n"
        "- title: 题目块标题，优先用小题编号，如 第1题、第2题；不要只用“选择题”“填空题”这类大题类型标题。\n"
        "- question_meaning_zh: 该题目块要孩子或学习者做什么。\n"
        "- content_items: 该题块内所有需要展示或朗读的题面内容，包括题目要求、例句、场景、短文、对话、词库、选项和图片旁文字。\n"
        "- 独立可批改小题 = 一个 question_block = 前端一张题卡；共同材料、例句、题型说明不是题卡，只放入相关题块的 content_items。\n"
        "- 同一大题下面有多个独立小题时，必须按小题拆分 question_blocks；多个选择小题要按实际小题数量输出多个 question_blocks，而不是 1 个“选择题”题块。\n"
        "- 每个小题的 answer_items、student_answer_reviews、solution_steps 必须使用同一个 block_id，这样前端才能把答案、批改和题解放在同一张题卡。\n"
        "\n"
        "content_items 规则：\n"
        "- type 只能是 instruction, example, context, material, dialogue, word_bank, option, image_text, other。\n"
        "- text 必须来自图片可见题面，不要编造图片中没有的题面内容。\n"
        "- 必须按最小可展示/可朗读单元拆分：可见行、例句行、对话轮次、词库单词/短语、选项都分别成为独立 content_item；不要把多行例句或短文合并成一个 text。\n"
        "- 例句、场景、短文或材料有多少个独立可见行，就输出多少个独立 content_item；不能把多行塞进同一个 text，也不能只用空格连接成一段。\n"
        "- 同一组例句或同一段材料的多行内容，用相同 group_id 归组；无归组需求时 group_id 为 null。\n"
        "- speak_text 是适合 Android TTS 直接朗读的文本；不适合朗读时可为 null 且 speakable=false。\n"
        "- 英语题中，题目要求、例句、场景、短文、对话、词库和选项都应尽量进入 content_items，避免只提取大题标题。\n"
        "\n"
        "answer_items 是参考答案区的唯一数据源。每个元素代表一条可展示答案，字段为：\n"
        "- answer_id: 稳定 ID，建议 q1-a1, q1-a2。\n"
        "- block_id: 所属 question_blocks[].block_id，必须能对应到某个题目块。\n"
        "- order: 在所属题块内的答案顺序，从 1 开始，必须与图片题号或阅读顺序一致。\n"
        "- number: 题号，字符串或 null，支持 1、A、1a 等。\n"
        "- answer_type: 只能是 fill_blank, choice, picture_word, matching, sentence_ordering, "
        "reading_qa, translation, correction, copying, calculation, proof, short_answer, composition, pinyin, other。\n"
        "- plain_text: 完整答案文本，不含题号，用于展示和复制；不要写“第X题解答”，不要放大段题解、原因分析或步骤说明。\n"
        "- speak_text: 适合 TTS 的读法；数学公式可写自然语言读法。\n"
        "- display: 前端渲染结构；mode 根据题型选择，format 表示显示格式，latex 放 LaTeX 源码或 null，runs 保留高亮角色和换行。\n"
        "- answer_items 必须至少 1 项。理科题也必须输出最终答案或关键填写内容；solution_steps 只表示过程，不能替代 answer_items。\n"
        "- 逐题题解、推理、选项排除、计算过程必须放入对应 block_id 的 solution_steps；前端会把这些步骤直接展示在该题答案后面。\n"
        "- 数学/物理/化学公式：display.mode 使用 math_block；普通 Unicode/纯文本公式用 format=plain_math；LaTeX 公式用 format=latex 且 latex 放源码，同时 plain_text 必须给可读纯文本兜底。\n"
        "- 各学段和各类题型中的常见计算、方程、函数、几何、概率统计、物理化学公式与单位换算，优先用 format=plain_math，并在 plain_text 和 runs.text 中输出 Android 可直接显示的 Unicode/纯文本公式；不要为了简单公式输出 LaTeX 源码。\n"
        "- 不要在 plain_text、display.runs[].text、solution_steps[].content_zh、formula、result 中使用 LaTeX 美元分隔符 $...$；需要公式时直接写可读公式文本。\n"
        "\n"
        "display.runs[].role 只能是：\n"
        "- given: 题目原本已有的文字。\n"
        "- answer: 学生需要填写、选择或生成的答案。\n"
        "- connector: 连接符号，如箭头、短横线、冒号。\n"
        "- correction: 改错题中订正后的正确内容。\n"
        "- student_answer: 图片中学生已经写出的答案。\n"
        "\n"
        "solution_steps 规则：\n"
        "- 每个需要解释、推理、计算或排除选项的题目，都要把逐题题解放入 solution_steps。\n"
        "- solution_steps[].block_id 必须指向对应题目块；同一题的步骤按 number 顺序排列。\n"
        "- answer_items 只回答“答案是什么”，solution_steps 回答“为什么/怎么算/错在哪里”。\n"
        "- 选择题的选项排除、概率题的判断理由、几何题的公式推导，都属于 solution_steps，不要塞进 answer_items.plain_text。\n"
        "- solution_steps[].content_zh 是给家长和学生直接阅读的中文说明，不要夹杂 `$\\frac{...}{...}$` 这类源码；公式优先放入 formula 字段并给可读纯文本。\n"
        "\n"
        "student_answer_reviews 规则：\n"
        "- 只有图片里存在学生手写/已填写答案时才输出对应批改项；没有则输出空数组。\n"
        "- 必须区分印刷题面(given)、学生答案(student_answer)和标准答案(correct_answer)。\n"
        "- status 只能是 correct, incorrect, partially_correct, unanswered, unclear, not_applicable。\n"
        "- 看不清学生答案时用 unclear，并在 feedback_zh 说明；开放题不适合判唯一对错时用 not_applicable 或 partially_correct。\n"
        "- 错题的逐题详细分析优先放入对应 block_id 的 solution_steps；student_answer_reviews.feedback_zh 只放短提示。\n"
        "- explanation_zh 只放整体总结、共性错因或全局提醒，不要堆放逐题题解；逐题内容必须回到 solution_steps。\n"
        "\n"
        "通用题型规则（所有学科通用，选择题和填空题各学科都可能出现）：\n"
        "- 填空、补全句子、看图填空：plain_text 必须是补全后的完整句子或完整短语，不允许只输出填空词；"
        "display.runs 中题目已有文字标为 given，填入答案标为 answer。\n"
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
        "- plain_text 必须严格等于 display.runs 中各 text 字段按顺序拼接的结果，只允许去除整行首尾空白；"
        "不得出现 plain_text 与 display.runs 内容不一致。这样可保证展示文本与高亮内容完全一致。\n"
        "- 每个 question_blocks[].order 在整张图内唯一；每个 answer_items[].order 在同一 block_id 内唯一。\n"
        "\n"
        "输出质量规则：\n"
        "- 若图片中有多个题目块，必须用 question_blocks[].order 表达题块顺序，再用 answer_items[].order 表达题内答案顺序。\n"
        "- answer_items、student_answer_reviews 与 solution_steps 的 block_id 必须对应 question_blocks；不确定归属时应保留独立题目块并设置 uncertainty，不要把多题内容合并到第一个题目块。\n"
        "- 若题目含编号，请按检测到的编号顺序给出 answer_items.order；若无编号，请按题面阅读顺序组织。\n"
        "- 同一张图中多个相关题目不能混成一个题目块；每个独立可批改小题必须按实际阅读顺序拆成独立 question_blocks。\n"
        "- 大题标题、题型说明、共同材料、例句、词库、阅读材料不决定题卡粒度；它们只能作为 content_items 归属到相关小题。\n"
        "- learning_points 只收录有助于理解题目、答案或易错点的知识点，不要硬凑；label 可写 grammar, phrase, pinyin, phonics 等自由标签。\n"
        "- 所有适合朗读的题面内容放在 content_items[].speak_text；答案读法放在 answer_items[].speak_text。\n"
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

    def _coerce_order(self, value: Any, fallback: int) -> int:
        try:
            order = int(value)
        except (TypeError, ValueError):
            order = fallback
        return order if order > 0 else fallback

    def _normalize_content_type(self, raw: Any) -> str:
        value = str(raw or "other").strip().lower()
        value = CONTENT_ITEM_TYPE_ALIASES.get(value, value)
        return value if value in CONTENT_ITEM_TYPES else "other"

    def _detect_language(self, text: str) -> str:
        has_ascii = bool(re.search(r"[A-Za-z]", text))
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
        if has_ascii and has_cjk:
            return "mixed"
        if has_ascii:
            return "en"
        if has_cjk:
            return "zh"
        return "unknown"

    def _display_mode_for_answer_type(self, answer_type: str) -> str:
        return DISPLAY_MODES_BY_ANSWER_TYPE.get(answer_type, "inline_segments")

    def _display_format_for_answer_type(self, answer_type: str) -> str:
        if answer_type in {"calculation", "proof"}:
            return "plain_math"
        return "plain_text"

    def _normalize_answer_type(self, raw: Any) -> str:
        value = str(raw or "other").strip().lower()
        return value if value in ANSWER_TYPES else "other"

    def _normalize_display(
        self,
        raw_display: Any,
        plain_text: str,
        answer_type: str,
        legacy_segments: Any = None,
    ) -> dict[str, Any]:
        mode = self._display_mode_for_answer_type(answer_type)
        display_format = self._display_format_for_answer_type(answer_type)
        latex: str | None = None
        preserve_newlines = "\n" in plain_text or mode in {"math_block", "paragraph", "table"}
        runs: list[dict[str, str]] = []
        allowed_modes = {
            "inline_segments",
            "math_block",
            "paragraph",
            "choice",
            "matching",
            "table",
            "pinyin",
            "copying",
            "plain",
        }
        allowed_roles = {"given", "answer", "connector", "correction", "student_answer"}

        if isinstance(raw_display, dict):
            raw_mode = str(raw_display.get("mode") or "").strip().lower()
            if raw_mode in allowed_modes:
                mode = raw_mode
            raw_format = str(raw_display.get("format") or "").strip().lower()
            if raw_format in DISPLAY_FORMATS:
                display_format = raw_format
            if raw_display.get("latex") is not None:
                latex_value = str(raw_display.get("latex")).strip()
                latex = latex_value or None
            preserve_newlines = bool(raw_display.get("preserve_newlines", preserve_newlines))
            raw_runs = raw_display.get("runs")
            if isinstance(raw_runs, list):
                for run in raw_runs:
                    if not isinstance(run, dict):
                        continue
                    text = str(run.get("text") or "")
                    if not text:
                        continue
                    role = str(run.get("role") or "answer").strip().lower()
                    runs.append({"text": text, "role": role if role in allowed_roles else "answer"})

        if not runs and isinstance(legacy_segments, list):
            for segment in legacy_segments:
                if not isinstance(segment, dict):
                    continue
                text = str(segment.get("text") or "")
                if not text:
                    continue
                role = str(segment.get("role") or "answer").strip().lower()
                runs.append({"text": text, "role": role if role in allowed_roles else "answer"})

        concat = "".join(run["text"] for run in runs).strip()
        if not runs or (concat and concat != plain_text):
            runs = [{"text": plain_text, "role": "answer"}]

        if mode == "math_block" and display_format == "plain_text":
            display_format = "plain_math"

        return {
            "mode": mode,
            "format": display_format,
            "latex": latex,
            "preserve_newlines": preserve_newlines,
            "runs": runs,
        }

    def _split_multiline_content_item(
        self,
        item: dict[str, Any],
        block_id: str,
        item_index: int,
    ) -> list[dict[str, Any]]:
        text = str(item.get("text") or "").strip()
        if not text:
            return []

        text_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not text_lines:
            return []
        meaning_raw = item.get("meaning_zh")
        meaning_lines: list[str | None]
        if meaning_raw is not None:
            raw_meaning_lines = [
                line.strip() for line in str(meaning_raw).splitlines() if line.strip()
            ]
            meaning_lines = (
                raw_meaning_lines
                if len(raw_meaning_lines) == len(text_lines)
                else [str(meaning_raw).strip() or None] + [None] * (len(text_lines) - 1)
            )
        else:
            meaning_lines = [None] * len(text_lines)

        speak_raw = item.get("speak_text")
        if speak_raw is not None:
            raw_speak_lines = [line.strip() for line in str(speak_raw).splitlines() if line.strip()]
            speak_lines = raw_speak_lines if len(raw_speak_lines) == len(text_lines) else text_lines
        else:
            speak_lines = text_lines

        base_item_id = str(item.get("item_id") or f"{block_id}-c{item_index + 1}").strip()
        base_order = self._coerce_order(item.get("order"), item_index + 1)
        raw_group_id = item.get("group_id")
        group_id = (
            str(raw_group_id).strip()
            if raw_group_id is not None and str(raw_group_id).strip()
            else (base_item_id if len(text_lines) > 1 else None)
        )
        content_type = self._normalize_content_type(item.get("type"))
        language_raw = str(item.get("language") or "").strip().lower()

        split_items: list[dict[str, Any]] = []
        for line_index, line in enumerate(text_lines):
            language = language_raw if language_raw in {"zh", "en", "mixed", "unknown"} else self._detect_language(line)
            item_id = base_item_id if len(text_lines) == 1 else f"{base_item_id}-{line_index + 1}"
            split_items.append(
                {
                    "item_id": item_id,
                    "order": base_order + line_index,
                    "group_id": group_id,
                    "type": content_type,
                    "text": line,
                    "meaning_zh": meaning_lines[line_index],
                    "language": language,
                    "speak_text": speak_lines[line_index] or line,
                    "speakable": bool(item.get("speakable", True)),
                }
            )
        return split_items

    def _normalize_candidate(self, candidate: Any) -> Any:
        if not isinstance(candidate, dict):
            return candidate

        out = dict(candidate)
        out["schema_version"] = "4.0"
        blocks = out.get("question_blocks")
        if isinstance(blocks, list):
            normalized_blocks: list[Any] = []
            for index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    normalized_blocks.append(block)
                    continue
                normalized_block = dict(block)
                block_id = str(normalized_block.get("block_id") or f"q{index + 1}").strip()
                normalized_block["block_id"] = block_id
                normalized_block["order"] = self._coerce_order(
                    normalized_block.get("order"), index + 1
                )
                normalized_block["title"] = str(
                    normalized_block.get("title") or f"第{index + 1}题"
                ).strip()
                normalized_block["question_meaning_zh"] = str(
                    normalized_block.get("question_meaning_zh") or "完成该题目块。"
                ).strip()

                normalized_items: list[dict[str, Any]] = []
                content_items = normalized_block.get("content_items")
                if isinstance(content_items, list):
                    for item_index, item in enumerate(content_items):
                        if not isinstance(item, dict):
                            continue
                        normalized_items.extend(
                            self._split_multiline_content_item(item, block_id, item_index)
                        )
                legacy_instruction = normalized_block.pop("question_instruction", None)
                if not normalized_items and legacy_instruction:
                    if isinstance(legacy_instruction, dict):
                        text = str(legacy_instruction.get("text") or "").strip()
                        meaning = str(legacy_instruction.get("meaning_zh") or "").strip() or None
                    else:
                        text = str(legacy_instruction).strip()
                        meaning = None
                    if text:
                        normalized_items.append(
                            {
                                "item_id": f"{block_id}-c1",
                                "order": 1,
                                "group_id": None,
                                "type": "instruction",
                                "text": text,
                                "meaning_zh": meaning,
                                "language": self._detect_language(text),
                                "speak_text": text,
                                "speakable": True,
                            }
                        )
                sorted_items = sorted(normalized_items, key=lambda item: item["order"])
                for item_order, item in enumerate(sorted_items, start=1):
                    item["order"] = item_order
                normalized_block["content_items"] = sorted_items
                normalized_blocks.append(normalized_block)
            out["question_blocks"] = sorted(
                normalized_blocks,
                key=lambda block: block.get("order", 10**9) if isinstance(block, dict) else 10**9,
            )

        known_block_ids: list[str] = []
        qb = out.get("question_blocks")
        if isinstance(qb, list):
            for block in qb:
                if isinstance(block, dict):
                    bid = str(block.get("block_id") or "").strip()
                    if bid:
                        known_block_ids.append(bid)
        fallback_block_id = known_block_ids[0] if len(known_block_ids) == 1 else ""

        raw_answer_items = out.get("answer_items")
        if not isinstance(raw_answer_items, list) and isinstance(out.get("answer_lines"), list):
            raw_answer_items = out.get("answer_lines")
        if isinstance(raw_answer_items, list):
            normalized_answers: list[Any] = []
            for index, item in enumerate(raw_answer_items):
                if not isinstance(item, dict):
                    normalized_answers.append(item)
                    continue
                normalized_item = dict(item)
                block_id = str(normalized_item.get("block_id") or "").strip()
                if (not block_id) and fallback_block_id:
                    block_id = fallback_block_id
                answer_type = self._normalize_answer_type(
                    normalized_item.get("answer_type") or normalized_item.get("line_type")
                )
                plain_text = str(normalized_item.get("plain_text") or "").strip()
                if not plain_text:
                    display = normalized_item.get("display")
                    runs = display.get("runs") if isinstance(display, dict) else normalized_item.get("segments")
                    if isinstance(runs, list):
                        plain_text = "".join(
                            str(run.get("text") or "")
                            for run in runs
                            if isinstance(run, dict)
                        ).strip()
                if not plain_text:
                    plain_text = "未能识别答案"

                speak_text = None
                if normalized_item.get("speak_text") is not None:
                    speak_text = str(normalized_item.get("speak_text")).strip() or None
                normalized_answers.append(
                    {
                        "answer_id": str(
                            normalized_item.get("answer_id") or f"{block_id or 'q'}-a{index + 1}"
                        ).strip(),
                        "block_id": block_id,
                        "order": self._coerce_order(normalized_item.get("order"), index + 1),
                        "number": (
                            str(normalized_item.get("number")).strip()
                            if normalized_item.get("number") is not None
                            else None
                        ),
                        "answer_type": answer_type,
                        "plain_text": plain_text,
                        "speak_text": speak_text if speak_text is not None else plain_text,
                        "display": self._normalize_display(
                            normalized_item.get("display"),
                            plain_text,
                            answer_type,
                            legacy_segments=normalized_item.get("segments"),
                        ),
                    }
                )
            block_order_index = {bid: index for index, bid in enumerate(known_block_ids)}
            out["answer_items"] = sorted(
                normalized_answers,
                key=lambda item: (
                    block_order_index.get(item.get("block_id"), 10**9)
                    if isinstance(item, dict)
                    else 10**9,
                    item.get("order", 10**9) if isinstance(item, dict) else 10**9,
                ),
            )
        out.pop("answer_lines", None)

        raw_reviews = out.get("student_answer_reviews")
        if isinstance(raw_reviews, list):
            normalized_reviews: list[Any] = []
            for index, review in enumerate(raw_reviews):
                if not isinstance(review, dict):
                    normalized_reviews.append(review)
                    continue
                normalized_review = dict(review)
                block_id = str(normalized_review.get("block_id") or "").strip()
                if (not block_id) and fallback_block_id:
                    block_id = fallback_block_id
                status = str(normalized_review.get("status") or "unclear").strip().lower()
                if status not in {
                    "correct",
                    "incorrect",
                    "partially_correct",
                    "unanswered",
                    "unclear",
                    "not_applicable",
                }:
                    status = "unclear"
                try:
                    confidence = float(normalized_review.get("confidence"))
                except (TypeError, ValueError):
                    confidence = 0.8
                normalized_reviews.append(
                    {
                        "review_id": str(
                            normalized_review.get("review_id") or f"{block_id or 'q'}-r{index + 1}"
                        ).strip(),
                        "block_id": block_id,
                        "answer_id": (
                            str(normalized_review.get("answer_id")).strip()
                            if normalized_review.get("answer_id") is not None
                            else None
                        ),
                        "order": self._coerce_order(normalized_review.get("order"), index + 1),
                        "number": (
                            str(normalized_review.get("number")).strip()
                            if normalized_review.get("number") is not None
                            else None
                        ),
                        "student_answer": (
                            str(normalized_review.get("student_answer")).strip()
                            if normalized_review.get("student_answer") is not None
                            else None
                        ),
                        "correct_answer": (
                            str(normalized_review.get("correct_answer")).strip()
                            if normalized_review.get("correct_answer") is not None
                            else None
                        ),
                        "status": status,
                        "feedback_zh": str(
                            normalized_review.get("feedback_zh") or "需要人工确认。"
                        ).strip(),
                        "confidence": max(0.0, min(1.0, confidence)),
                    }
                )
            out["student_answer_reviews"] = sorted(
                normalized_reviews,
                key=lambda item: item.get("order", 10**9) if isinstance(item, dict) else 10**9,
            )

        steps = out.get("solution_steps")
        if isinstance(steps, list):
            normalized_steps: list[Any] = []
            for step in steps:
                if not isinstance(step, dict):
                    normalized_steps.append(step)
                    continue
                normalized_step = dict(step)
                step_block_id = str(normalized_step.get("block_id") or "").strip()
                if (not step_block_id) and fallback_block_id:
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

        # 补全缺失的可选字段，使其满足 schema guard 的严格字段集校验，
        # 避免"模型只是漏了某个可选字段"也要多调一次修复模型。
        out.setdefault("solution_steps", [])
        out.setdefault("learning_points", [])
        out.setdefault("student_answer_reviews", [])
        out.setdefault(
            "uncertainty",
            {"requires_review": False, "confidence": 0.8, "reason": None},
        )
        out.pop("question_instruction", None)
        out.pop("read_units", None)
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
        return keys

    def _missing_vocabulary_words(self, result: HomeworkParseResult) -> list[str]:
        expected: list[str] = []
        for item in result.answer_items:
            expected.extend(self._coverage_candidates(item.plain_text))
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
            "- meaning_zh 用简短中文释义，适合学习者和家长理解。\n"
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
            "顶层字段只能是：schema_version, subject, question_meaning_zh, question_blocks, "
            "answer_items, student_answer_reviews, solution_steps, explanation_zh, learning_points, uncertainty。\n"
            "schema_version 必须是 \"4.0\"。\n"
            "question_blocks[].content_items 必须存在；content_items[] 必须包含 item_id, order, group_id, type, text, meaning_zh, language, speak_text, speakable；没有题面内容用空数组。\n"
            "answer_items[].display 必须包含 mode, format, latex, preserve_newlines, runs；runs[].role 只能是 given, answer, connector, correction, student_answer。\n"
            "learning_points[].category 只能是 word, concept, formula, unit, method, other；"
            "原始细分类放入 label。\n"
            "所有数组字段必须存在，没有内容用空数组。\n"
            "answer_items、student_answer_reviews、solution_steps、learning_points 中的 block_id 必须对应 question_blocks；"
            "learning_points 的 block_id 可以为 null。\n"
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
        if "runs" in detail and "role" in detail:
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
