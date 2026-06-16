# AGENTS.md (backend)

## 目录职责

本目录负责 Python 后端服务与模型编排：

- 接收前端上传的完整题图
- 通过通用 OpenAI 兼容接口调用视觉大模型
- 构建英语练习题解析提示词
- 校验并归一化固定 JSON v2 输出
- 为前端提供结构化参考答案、讲解、词汇、点读单元和不确定性标记

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
- [x] 新版提示词：通用英语练习题解析，不限定小学
- [x] `answer_lines` 结构校验与 fallback

## JSON v2 输出字段

后端正式输出字段为：

- `question_meaning_zh`
- `answer_lines`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`

不再输出 `reference_answer` 作为正式接口字段。

## answer_lines 结构

`answer_lines` 是参考答案区唯一数据源。每个元素代表一行可展示、可朗读的答案。

字段：

- `number`：题号，字符串或 `null`。支持 `1`、`A`、`1a` 等格式。
- `line_type`：题型行类型，如 `fill_blank`、`choice`、`matching`、`sentence_ordering`、`reading_qa`、`translation`、`correction`、`copying`、`other`。
- `plain_text`：完整答案文本，不含题号，用于整行 TTS 和兜底展示。
- `segments`：前端彩色渲染片段，至少 1 个。

`segments[].role` 只能是：

- `given`：题目原本已有的文字
- `answer`：学生需要填写、选择或生成的答案
- `connector`：连接符号，如箭头、短横线、冒号
- `correction`：改错题中订正后的正确内容

示例：

```json
{
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
- 内部步骤：先判断题型，再确认作答要求和答案数量，最后生成 JSON。
- 输出要求：只输出一个 JSON 对象，不输出 markdown、代码块或额外文字。

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
