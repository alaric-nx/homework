# AGENTS.md (backend)

## 目录职责

本目录负责 Python 后端服务与模型编排：

- 接收前端上传的完整题图
- 通过通用 OpenAI 兼容接口调用视觉大模型
- 构建英语练习题解析提示词
- 校验并归一化固定 JSON v2 输出
- 为前端提供题目块、结构化参考答案、讲解、词汇、点读单元和不确定性标记

## 技术约束

- 语言：Python
- 模型调用：大语言模型 / 视觉语言模型
- API 风格：异步提交 + 轮询
- 学科：当前仅英语，预留语文/数学分流口
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

## JSON v2 输出字段

后端正式输出字段为：

- `question_meaning_zh`
- `question_instruction`
- `question_blocks`
- `answer_lines`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`

不再输出 `reference_answer` 作为正式接口字段。

## question_instruction 结构

`question_instruction` 用于提取图片中的英文题目要求原句，供前端展示、朗读和解释。

字段：

- `text`：图片中可见的英文题目要求原句，尽量保持原文大小写和标点。
- `meaning_zh`：英文题目要求的中文解释。
- `confidence`：英文原句识别置信度，范围 `0.0` 到 `1.0`。

规则：

- 图片中存在英文题目要求时，必须尽量提取原句，例如 `Look, read and write.`
- 图片中没有可见英文题目要求时，`text` 和 `meaning_zh` 使用空字符串，`confidence=0`，并在 `uncertainty.reason` 中说明。
- `speak_units` 必须包含题目要求对应的 `sentence` 单元：`text` 使用 `question_instruction.text`，`meaning_zh` 使用 `question_instruction.meaning_zh`。

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
- `question_instruction`：该题目块的英文题目要求原句、中文解释和置信度。
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
- `key_vocabulary` 与 `speak_units` 需要覆盖完整答案行里的可点读英文词，避免前端出现有发音但缺少词义来源的情况。

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

## 词义补全规则

- `key_vocabulary` 和 `speak_units(unit_type=word)` 应覆盖 `answer_lines[].plain_text` 中适合点读的英文词。
- 如果主模型结果中存在答案词缺少词义，后端最多额外调用一次模型补齐缺失词的 `meaning_zh` 和 `ipa`。
- 额外调用成功后，将词义合并到 `key_vocabulary`，并补充对应 `word` 类型 `speak_units`。
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
