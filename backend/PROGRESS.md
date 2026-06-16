# PROGRESS.md (backend)

## 最近更新

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成后端 JSON v2、提示词和回归测试改造；`python -m pytest -q` 通过。

- 时间：2026-06-16
- 更新类型：开始执行
- 摘要：开始实现后端 JSON v2、提示词和测试改造。

- 时间：2026-06-16
- 更新类型：文档规范化
- 摘要：记录 JSON v2 后端升级计划，明确 `answer_lines` 替代 `reference_answer` 的目标设计。

## 进展记录

### 2026-06-16

完成内容：

- 统一后端文档结构。
- 明确后端正式输出字段：
  - `question_meaning_zh`
  - `answer_lines`
  - `explanation_zh`
  - `key_vocabulary`
  - `speak_units`
  - `uncertainty`
- 明确不再输出 `reference_answer` 作为正式接口字段。
- 明确 `answer_lines[].segments[].role` 枚举：
  - `given`
  - `answer`
  - `connector`
  - `correction`

当前进行中：

- 无。

新增完成内容：

- 在 `app/core/models.py` 增加 `AnswerLine` / `AnswerSegment`，`HomeworkParseResult` 改为使用 `answer_lines`。
- 将 `schemas/homework_parse.schema.json` 升级为 JSON v2。
- 更新 `ResponseSchemaGuard` 与 `LLMClient` 的 v2 字段识别。
- 重写 `parse_pipeline` 提示词，覆盖通用英语练习题、题型判断、完整答案行和不确定性规则。
- 增加并更新后端测试，覆盖 v2 成功、缺字段、非法 `role`、fallback 和 event stream 提取。
- 将任务持久化目录改为默认 `backend/job`，并支持 `HW_TASK_JOB_DIR` 覆盖，避免本地环境硬编码路径。

阻塞项：

- 无。

下一步：

- 后续可补充真实图片联调和更细粒度题型样例。
