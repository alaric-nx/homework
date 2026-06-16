# PROGRESS.md (backend)

## 最近更新

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成 review 优化：后端强校验响应 `subject` 必须匹配请求学科，并补充 subject mismatch 回归测试。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成多学科 v3 后端实现：`subject` API 参数、四套提示词、JSON v3 schema、`learning_points` / `read_units` / `solution_steps`、缓存按学科区分和测试更新。

- 时间：2026-06-16
- 更新类型：文档规范化
- 摘要：补全多学科 v3 后端详细设计，包含 JSON v3 schema 细则、完整示例、四套提示词模板和后处理规则。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成 `question_blocks` 多题目块结构、`question_instruction` 题目要求字段、答案词义一次补全、任务缓存清理和文档同步。

- 时间：2026-06-16
- 更新类型：文档规范化
- 摘要：规范化后端 PLAN / PROGRESS 状态，修正任务子项计数、计划完成时间和旧 fallback 表述。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成后端 systemd 服务化改造，支持开机自启动，开启 linger 保证驻留运行。

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

- 完成后端 systemd 用户服务配置，编写 `homework-backend.service` 并部署至 `~/.config/systemd/user/`。
- 开启用户 linger 驻留模式 (`loginctl enable-linger`)，支持开机免登录自启动。
- 启动服务并通过了本地接口与 pytest 回归测试。
- 统一后端文档结构。
- 明确后端当前正式输出字段：
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
- 增加并更新后端测试，覆盖 v2 成功、缺字段、非法 `role`、未知 `block_id` 和 event stream 提取。
- 将任务持久化目录改为默认 `backend/job`，并支持 `HW_TASK_JOB_DIR` 覆盖，避免本地环境硬编码路径。
- 新增 `question_instruction` 字段，用于提取图片中的英文题目要求原句、中文解释和识别置信度。
- 新增 `question_blocks` 字段，用于区分同一图片中有关联但独立的多个题目块。
- `answer_lines` 新增 `block_id`，必须指向存在的 `question_blocks[].block_id`。
- 移除 schema/model 失败时的假答案兜底；契约不匹配会让任务进入 FAILED。
- 提示词要求 `read_units` 尽量包含适合朗读的题目要求和答案解释。
- 增加答案词义覆盖检测：发现 `answer_lines[].plain_text` 中有英文词缺少释义时，最多额外调用一次模型补齐。
- 词义补齐结果会合并到 `learning_points` 和 `read_units(unit_type=word)`；补齐失败不循环重试，只在 `uncertainty` 标记。
- 任务磁盘缓存增加 schema 版本检查，旧 schema 或过期终态任务会从磁盘删除。
- `backend/job/`、`backend/logs/`、根 `logs/` 已在 `.gitignore` 中忽略。
- 后端回归测试已通过：`python -m pytest -q`，共 16 个测试。
- 完成多学科 v3 后端文档设计：
  - `subject` 枚举：`general`、`english`、`liberal_arts`、`science`
  - JSON v3 目标字段：`solution_steps`、`learning_points`、`read_units`
  - 英语链路保持当前逻辑，非英语链路不执行英语词义补全
  - JSON v3 schema 细则、文科示例和理科示例
  - `general`、`english`、`liberal_arts`、`science` 四套提示词模板
- 完成多学科 v3 后端实现：
  - API 支持 `subject=general|english|liberal_arts|science`，非法值返回 `INVALID_REQUEST`
  - Pydantic 模型、JSON schema、schema guard 升级为 JSON v3
  - `key_vocabulary` / `speak_units` 替换为 `learning_points` / `read_units`
  - 新增 `solution_steps` 并校验 `block_id`
  - 非英语链路跳过英语词义覆盖检测和额外补词义调用
  - 英语链路缺词义时最多额外调用一次模型并合并到 v3 字段
  - 任务缓存 schema 版本更新，缓存复用按 `subject` 区分
  - 后端回归测试已通过：`python -m pytest -q`，共 17 个测试。
- 完成 review 优化：
  - 后端强校验模型返回的 `subject` 必须等于请求 `subject`
  - 补充 subject mismatch 回归测试
  - 后端回归测试已通过：`python -m pytest -q`，共 18 个测试。

阻塞项：

- 无。

下一步：

- 使用真实题图联调四类学科输出质量。
