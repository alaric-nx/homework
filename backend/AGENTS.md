# AGENTS.md (backend)

## 目录职责

本目录负责 Python 后端服务与模型编排：

- 接收前端上传的完整题图
- 通过通用 OpenAI 兼容接口调用视觉大模型
- 构建多学科练习题解析提示词
- 校验并归一化固定 JSON v3 输出
- 为前端提供题目块、结构化参考答案、讲解、知识点、朗读单元、解题步骤和不确定性标记

## 技术约束

- 语言：Python
- 模型调用：大语言模型 / 视觉语言模型
- API 风格：异步提交 + 轮询
- 学科：支持通用、英语、文科、理科；英语链路保留词义补全
- 测试：模型调用在测试中 mock 或通过配置关闭外部依赖

## 当前实现状态

- [x] Python + LLM 后端路线
- [x] 固定 JSON schema 校验
- [x] 解析 API
- [x] 任务状态轮询 API
- [x] 日志与错误码
- [x] JSON v2：以 `answer_lines` 替代 `reference_answer`
- [x] JSON v2：新增 `question_instruction` 提取图片中的英文题目要求原句
- [x] JSON v2：新增 `question_blocks` 区分同一图片内多个独立题目
- [x] 新版提示词：通用英语练习题解析，不限定小学
- [x] `answer_lines` 结构校验；schema 不匹配时任务失败，不返回假答案兜底
- [x] 缺失答案词义时最多额外调用一次模型补全词义
- [x] 过期 / 旧 schema 磁盘任务缓存清理
- [x] 多学科 v3：`subject` 参数、四套提示词、`learning_points` / `read_units` / `solution_steps`

## 多学科 v3 当前实现

后端支持四类 `subject`：

- `general`：通用，默认值。
- `english`：英语，保持当前提示词、词义补全和点读规则不变。
- `liberal_arts`：文科，覆盖语文、拼音、道法、历史、地理等。
- `science`：理科，覆盖数学、科学、物理、化学等。

API 参数：

```text
POST /v1/homework/parse?subject=<general|english|liberal_arts|science>
```

约束：

- 未传 `subject` 时默认为 `general`。
- 非法 `subject` 返回 `INVALID_REQUEST`。
- 强制重解时继续使用传入 `subject` 和 `force=true`。
- 英语链路保持当前行为，不因多学科改造降低现有能力。
- 非英语链路不执行英语单词覆盖检测和英语词义补全。

## JSON v3 当前输出字段

多学科 v3 字段为：

- `subject`
- `question_meaning_zh`
- `question_instruction`
- `question_blocks`
- `answer_lines`
- `solution_steps`
- `explanation_zh`
- `learning_points`
- `read_units`
- `uncertainty`

字段说明：

- `subject`：本次解析使用的学科分类。
- `solution_steps`：结构化解题步骤。理科必填且应覆盖主要推理 / 计算过程；通用和文科按需输出，可为空数组。
- `learning_points`：通用知识点数组，替代英语专用 `key_vocabulary`。
- `read_units`：可朗读文本单元，替代偏英语命名的 `speak_units`。
- `question_instruction.text`：题目要求原文，不再限定英文。
- `answer_lines`：仍是参考答案区主数据源。

`solution_steps[]` 目标字段：

- `block_id`：所属题目块 ID。
- `number`：步骤序号。
- `title`：步骤标题。
- `content_zh`：中文步骤说明。
- `formula`：公式、列式或表达式，可为空。
- `result`：该步骤结果，可为空。

`learning_points[]` 目标字段：

- `block_id`：所属题目块 ID，可为空。
- `term`：词语、拼音、概念、公式、单位或知识点。
- `explanation_zh`：中文解释。
- `pronunciation`：拼音、读音、音标或其他读法，可为空。
- `category`：`word`、`pinyin`、`concept`、`formula`、`unit`、`method`、`other`。

`read_units[]` 目标字段：

- `block_id`：所属题目块 ID，可为空。
- `unit_type`：`word`、`sentence`、`paragraph`、`answer`、`explanation`。
- `text`：可朗读文本。
- `meaning_zh`：中文解释或翻译，可为空。

## JSON v3 Schema 细则

通用要求：

- 顶层只允许 JSON v3 正式字段，不允许额外字段。
- 所有数组字段必须存在；没有内容时使用空数组。
- `question_blocks` 和 `answer_lines` 至少 1 项。
- `subject` 必须等于请求传入的 subject。
- 后端在 schema 校验后再次检查 `result.subject == request.subject`；不匹配时任务失败，不返回错学科结果。
- `uncertainty.requires_review=true` 时必须提供 `reason`。

`answer_lines[].line_type` 目标枚举：

- `fill_blank`
- `choice`
- `picture_word`
- `matching`
- `sentence_ordering`
- `reading_qa`
- `translation`
- `correction`
- `copying`
- `calculation`
- `proof`
- `short_answer`
- `composition`
- `pinyin`
- `other`

`answer_lines[].segments[].role` 目标枚举：

- `given`
- `answer`
- `connector`
- `correction`

`solution_steps` 规则：

- `science`：必须至少 1 项，除非题目本身只是抄写 / 选择且无需步骤。
- `general`：如果识别为计算、推理或多步题，必须输出。
- `liberal_arts`：阅读理解、材料分析、作文审题可输出；普通字词题可为空数组。
- `english`：默认可为空数组；语法推理复杂时可输出。

`learning_points` 规则：

- 每项必须能帮助用户理解题目、答案或易错点。
- 英语中 `pronunciation` 放 IPA 或读音；文科拼音题中放拼音；理科通常为空。
- 不要为了填满字段而输出无意义知识点。

`read_units` 规则：

- 只收录适合 Android TTS 直接朗读的自然语言。
- 数学公式、复杂化学式不强行进入 `read_units`。
- 英语题中可放单词、答案句、题目要求。
- `unit_type=word` 可作为前端点击词释义来源；结果页“可朗读内容”默认不重复展示 word 单元。

## JSON v3 完整示例

文科 / 拼音示例：

```json
{
  "subject": "liberal_arts",
  "question_meaning_zh": "这是一道拼音题，需要给词语选择正确读音。",
  "question_instruction": {
    "text": "给加点字选择正确读音。",
    "meaning_zh": "判断加点字在词语中的正确拼音。",
    "confidence": 0.93
  },
  "question_blocks": [
    {
      "block_id": "q1",
      "title": "拼音选择",
      "question_instruction": {
        "text": "给加点字选择正确读音。",
        "meaning_zh": "选择正确拼音。",
        "confidence": 0.93
      },
      "question_meaning_zh": "判断词语中加点字的读音。"
    }
  ],
  "answer_lines": [
    {
      "block_id": "q1",
      "number": "1",
      "line_type": "pinyin",
      "plain_text": "长大：zhǎng",
      "segments": [
        { "text": "长大：", "role": "given" },
        { "text": "zhǎng", "role": "answer" }
      ]
    }
  ],
  "solution_steps": [],
  "explanation_zh": "“长大”的“长”表示生长，读 zhǎng，不读 cháng。",
  "learning_points": [
    {
      "block_id": "q1",
      "term": "长",
      "explanation_zh": "表示生长、长大时读 zhǎng。",
      "pronunciation": "zhǎng",
      "category": "pinyin"
    }
  ],
  "read_units": [
    {
      "block_id": "q1",
      "unit_type": "answer",
      "text": "长大，zhǎng。",
      "meaning_zh": "长大中的长读 zhǎng。"
    }
  ],
  "uncertainty": {
    "requires_review": false,
    "confidence": 0.93,
    "reason": null
  }
}
```

理科示例见根 `AGENTS.md`。

## API 行为细则

- `subject` query 允许省略；省略时按 `general`。
- `subject` 只允许 `general`、`english`、`liberal_arts`、`science`。
- `model` query 保持现有行为。
- `force=true` 保持现有行为。
- 缓存复用必须区分 `subject`，同一图片不同 `subject` 不应复用同一个解析结果。
- 任务响应中的 `model` 保持现有字段；v3 结果中的 `subject` 表示解析学科。

## 后处理细则

`english`：

- 保留现有英文词覆盖检测。
- 保留最多额外一次词义补全。
- 词义补全合并到 `learning_points` 和 `read_units`。

`general`、`liberal_arts`、`science`：

- 不扫描英文单词做强制词义补全。
- 不因缺少 `learning_points` 自动二次调用模型。
- 只做 schema 校验和 block 引用一致性校验。

## 提示词模板

所有模板公共约束：

```text
只输出一个 JSON 对象，不要 markdown，不要代码块，不要额外文字。
字段必须严格符合 JSON v3。
必须先识别题目块 question_blocks，再输出 answer_lines 和其他字段。
answer_lines、solution_steps、learning_points、read_units 中的 block_id 必须能对应 question_blocks。
看不清、缺页、遮挡或需要外部上下文时，设置 uncertainty.requires_review=true 并说明原因。
不要编造图片中不存在的题目。
```

`general` 模板要点：

```text
你是通用作业解析助手。题目可能来自英语、语文、拼音、数学、科学或混合练习。
先判断学科和题型，但不要输出额外字段。
按图片证据给出参考答案、必要步骤、中文讲解、知识点和朗读内容。
如果题目偏英语，不要强行输出完整英语词汇表；如果偏理科，要输出必要 solution_steps。
```

`english` 模板要点：

```text
你是英语练习题解析助手，保持现有英语解析能力。
必须输出完整答案行；填空和补全题不能只给填空词。
learning_points 重点放英文单词、短语、语法点，pronunciation 可放 IPA。
read_units 放题目要求、答案句、需要点读的单词或短句。
```

`liberal_arts` 模板要点：

```text
你是文科作业解析助手，覆盖语文、拼音、道法、历史、地理等。
重点识别题目要求、材料、问题、选项和答题依据。
阅读理解和材料题必须说明答案依据。
拼音题要把拼音放入 learning_points.pronunciation。
作文或开放题给出可参考答案和审题提示，不编造唯一标准答案。
```

`science` 模板要点：

```text
你是理科作业解析助手，覆盖数学、科学、物理、化学等。
必须提取已知条件、要求的问题、关键公式或方法。
solution_steps 必须清楚展示列式、推理或计算过程。
answer_lines 放最终答案或需要填写的关键内容。
单位、公式、易错概念进入 learning_points。
复杂公式不要强行放入 read_units。
```

## JSON v3 输出字段

后端正式输出字段为：

- `subject`
- `question_meaning_zh`
- `question_instruction`
- `question_blocks`
- `answer_lines`
- `solution_steps`
- `explanation_zh`
- `learning_points`
- `read_units`
- `uncertainty`

不再输出 `reference_answer` 作为正式接口字段。

JSON v3 是当前已实现契约；前后端已同步更新 Pydantic 模型、JSON schema、schema guard、前端模型和任务记录。

## question_instruction 结构

`question_instruction` 用于提取图片中的题目要求原句，供前端展示、朗读和解释。

字段：

- `text`：图片中可见的题目要求原句，尽量保持原文格式。
- `meaning_zh`：题目要求的中文解释。
- `confidence`：英文原句识别置信度，范围 `0.0` 到 `1.0`。

规则：

- 图片中存在题目要求时，必须尽量提取原句，例如 `Look, read and write.` 或 `求下面长方形的面积。`
- 图片中没有可见题目要求时，`text` 和 `meaning_zh` 使用空字符串，`confidence=0`，并在 `uncertainty.reason` 中说明。
- `read_units` 可包含题目要求对应的朗读单元：`text` 使用 `question_instruction.text`，`meaning_zh` 使用 `question_instruction.meaning_zh`。

示例：

```json
{
  "text": "Complete the sentence.",
  "meaning_zh": "补全句子。",
  "confidence": 0.95
}
```

## question_blocks 结构

`question_blocks` 用于区分同一张图片里的多个独立题目块。两个题目即使有关联，只要作答要求、编号体系或版面分区不同，也必须拆成不同块。

字段：

- `block_id`：稳定 ID，按图片阅读顺序使用 `q1`、`q2`、`q3`。
- `title`：题目块标题，可来自图片中的大题编号 / 标题；没有标题时使用 `第1题`、`第2题`。
- `question_instruction`：该题目块的题目要求原句、中文解释和置信度。
- `question_meaning_zh`：该题目块要孩子或学习者做什么。

规则：

- 后端必须先识别题目块，再生成答案行。
- `answer_lines[].block_id` 必须指向存在的 `question_blocks[].block_id`。
- 例如同一图片中第一题补全单词、第二题用这些词填句子，必须输出 `q1` 和 `q2` 两个题目块。

示例：

```json
{
  "block_id": "q1",
  "title": "第1题",
  "question_instruction": {
    "text": "Complete the words.",
    "meaning_zh": "补全单词。",
    "confidence": 0.95
  },
  "question_meaning_zh": "根据给出的部分字母补全完整单词。"
}
```

## answer_lines 结构

`answer_lines` 是参考答案区唯一数据源。每个元素代表一行可展示、可朗读的答案。

字段：

- `block_id`：所属题目块 ID，必须对应某个 `question_blocks[].block_id`。
- `number`：题号，字符串或 `null`。支持 `1`、`A`、`1a` 等格式。
- `line_type`：题型行类型，如 `fill_blank`、`choice`、`matching`、`sentence_ordering`、`reading_qa`、`translation`、`correction`、`copying`、`other`。
- `plain_text`：完整答案文本，不含题号，用于整行 TTS 和纯文本展示。
- `segments`：前端彩色渲染片段，至少 1 个。
- `learning_points` 与 `read_units` 需要覆盖英语完整答案行里的可点读英文词，避免前端出现有发音但缺少词义来源的情况。

`segments[].role` 只能是：

- `given`：题目原本已有的文字
- `answer`：学生需要填写、选择或生成的答案
- `connector`：连接符号，如箭头、短横线、冒号
- `correction`：改错题中订正后的正确内容

示例：

```json
{
  "block_id": "q1",
  "number": "1",
  "line_type": "fill_blank",
  "plain_text": "She is reading a book.",
  "segments": [
    { "text": "She is ", "role": "given" },
    { "text": "reading", "role": "answer" },
    { "text": " a book.", "role": "given" }
  ]
}
```

## 提示词设计原则

- 角色定位：英语练习题解析助手，适用于作业、练习册、考试题和基础学习题。
- 证据原则：以图片中的题干、图片、编号、空格、选项、例句为主。
- 冲突处理：图片与推测冲突时，以图片和题干为准。
- 不确定性：看不清、裁切、遮挡、编号缺失、选项缺失时必须降低 `confidence` 并说明原因。
- 内部步骤：先判断题目块数量，再逐块判断题型、确认作答要求和答案数量，最后生成 JSON。
- 输出要求：只输出一个 JSON 对象，不输出 markdown、代码块或额外文字。
- 严格契约：模型输出缺字段、多字段或 `answer_lines[].block_id` 无法对应题目块时，任务失败并暴露错误，不返回伪造答案。

## 多学科提示词设计

`english`：

- 保持当前英语提示词与后处理逻辑不变。
- 继续要求完整答案行、题目要求原文、词义、发音、句义和答案词义覆盖。

`general`：

- 适合混合题或用户不确定学科。
- 先判断题目类型，再按题目块输出答案、讲解、必要步骤和知识点。
- 不强行输出英语词义或数学公式。

`liberal_arts`：

- 适合语文、拼音、道法、历史、地理等。
- 重点输出题目要求、标准答案、答题依据、关键词、字词解释、拼音或概念解释。
- 阅读理解必须在讲解中说明答案依据。
- 拼音题应将汉字 / 词语作为 `learning_points[].term`，拼音放入 `pronunciation`。

`science`：

- 适合数学、科学、物理、化学等。
- 必须重视题目条件、公式 / 列式、推理步骤、单位、最终答案和易错点。
- `solution_steps` 应覆盖主要解题过程。
- `answer_lines` 放最终答案、关键列式或需要填写的内容。
- 数学公式不强制朗读；`read_units` 只放适合 TTS 的自然语言。

## 词义补全规则

- `learning_points(category=word)` 和 `read_units(unit_type=word)` 应覆盖 `answer_lines[].plain_text` 中适合点读的英文词。
- 如果英语主模型结果中存在答案词缺少词义，后端最多额外调用一次模型补齐缺失词的中文解释和发音。
- 额外调用成功后，将词义合并到 `learning_points`，并补充对应 `word` 类型 `read_units`。
- 额外调用失败或仍不完整时，不继续重试；仅在 `uncertainty` 中标记“部分答案词缺少词义”。

## 任务缓存与运行产物

- 后端任务缓存目录默认是 `backend/job/`，可通过 `HW_TASK_JOB_DIR` 覆盖。
- `backend/job/`、`backend/logs/` 和根 `logs/` 不提交 Git。
- 磁盘任务缓存写入 `schema_version`，加载时发现旧 schema 会删除缓存并重新解析。
- 已完成 / 已失败任务超过保留时间后，会从内存和磁盘清理。

## 题型策略

- 填空 / 补全句子：`plain_text` 必须是补全后的完整句子或短语；题目已有文字标为 `given`，填入答案标为 `answer`。
- 选择题：选项字母和选中内容标为 `answer`。
- 看图写词 / 短语：答案整体标为 `answer`。
- 连线 / 匹配：题目已有内容可标为 `given`，配对关系或选中编号标为 `answer`。
- 排序 / 连词成句：最终正确句整体标为 `answer`。
- 阅读问答 / 翻译：回答或译文整体标为 `answer`。
- 改错题：未改部分标为 `given`，订正内容标为 `correction`。
- 抄写题：照抄内容可标为 `given`，讲解中说明“照抄即可”。

## 环境与启动约定

- 通用配置文件：`backend/config.env`
- 本地覆盖文件：`backend/.env`（同 key 覆盖 `config.env`，不提交 Git）
- 优先级：进程环境变量 > `.env` > `config.env`
- `backend/start_backend.sh` 按上述顺序加载配置

## 构建与测试

运行环境：Python 3.12（pyenv），无 venv，直接使用系统 / pyenv 解释器。

安装依赖：

```bash
cd backend
python -m pip install -r requirements.txt
```

运行测试：

```bash
cd backend
python -m pytest -q
```

单文件测试：

```bash
cd backend
python -m pytest tests/test_parse_api.py -q
```

导入冒烟检查：

```bash
cd backend
python -c "from app.main import app"
```

启动服务：

```bash
bash backend/start_backend.sh
```

## 关键文件

- `app/services/parse_pipeline.py`：构建提示词、调用模型、schema 校验
- `app/services/llm_client.py`：模型调用适配
- `app/core/models.py`：Pydantic 数据模型
- `app/skills/common/response_schema_guard.py`：固定 JSON 校验与归一化
- `schemas/homework_parse.schema.json`：JSON schema
- `app/api/routes.py`：解析与任务查询 API
