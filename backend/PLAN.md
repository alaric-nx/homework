# PLAN.md (backend)

## 当前阶段

阶段目标：完成 JSON v3 多学科解析基础能力（通用 / 英语 / 文科 / 理科），并保持英语链路现有能力。

最后更新时间：2026-06-16

## 任务列表

### B-001 JSON v2 输出模型

- 状态：已完成
- 优先级：高
- 完成比例：100%
- 已完成子项 / 总子项：7 / 7
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：2026-06-16
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：移除正式接口中的 `reference_answer`，以 `answer_lines` 作为参考答案区唯一数据源，并新增 `question_instruction` 和 `question_blocks`。

子项：

- [x] 在 `app/core/models.py` 新增 `AnswerLine` 与 `AnswerSegment`
- [x] 在 `HomeworkParseResult` 中移除 `reference_answer`
- [x] 在 `HomeworkParseResult` 中新增 `answer_lines`
- [x] 在 `HomeworkParseResult` 中新增 `question_instruction`
- [x] 在 `HomeworkParseResult` 中新增 `question_blocks` 与 `answer_lines[].block_id`
- [x] 更新 `schemas/homework_parse.schema.json`
- [x] 更新 `ResponseSchemaGuard` 校验规则

### B-002 新版提示词

- 状态：已完成
- 优先级：高
- 完成比例：100%
- 已完成子项 / 总子项：7 / 7
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：2026-06-16
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：提示词应适配通用英语练习题，不限定小学。

子项：

- [x] 重写角色定位与证据原则
- [x] 增加内部题型判断与答案数量确认规则
- [x] 增加 `answer_lines` 输出规则
- [x] 增加英文题目要求原句 `question_instruction` 输出规则
- [x] 增加同图多题目块 `question_blocks` 输出规则
- [x] 增加填空题完整句输出规则
- [x] 增加不确定性门控规则

### B-003 后端回归测试

- 状态：已完成
- 优先级：中
- 完成比例：100%
- 已完成子项 / 总子项：5 / 5
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：2026-06-16
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：测试不依赖真实模型调用；`python -m pytest -q` 已通过。schema 不匹配时任务失败，不返回伪造答案。

子项：

- [x] 增加 `answer_lines` schema 成功用例
- [x] 增加缺字段失败用例
- [x] 增加非法 `role` 失败用例
- [x] 增加未知 `block_id` 失败用例
- [x] 更新现有解析 API 测试

### B-004 systemd 服务部署

- 状态：已完成
- 优先级：中
- 完成比例：100%
- 已完成子项 / 总子项：4 / 4
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：2026-06-16
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：将后端配置为 systemd 用户服务以支持开机自启。

子项：

- [x] 调研系统环境，启用 `loginctl enable-linger` 开启开机不登录驻留
- [x] 创建 `homework-backend.service` 系统服务模板文件
- [x] 部署服务文件到 `~/.config/systemd/user/` 目录
- [x] 启用（enable）并启动（start）该服务，验证状态和日志

### B-005 词义补全与缓存清理

- 状态：已完成
- 优先级：高
- 完成比例：100%
- 已完成子项 / 总子项：4 / 4
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：2026-06-16
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：答案词义缺失时最多额外调用一次模型补齐；任务缓存按 schema 和保留时间清理，`backend/job/` 不提交 Git。

子项：

- [x] 检测 `answer_lines[].plain_text` 中缺少词义的英文词
- [x] 缺词时最多额外调用一次模型补齐中文释义和 IPA
- [x] 合并补齐结果到 `key_vocabulary` 和 `speak_units`
- [x] 清理过期 / 旧 schema 磁盘任务缓存并忽略 `backend/job/`

### B-006 多学科 v3 后端实现

- 状态：已完成
- 优先级：高
- 完成比例：100%
- 已完成子项 / 总子项：15 / 15
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：2026-06-16
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：已完成 `subject` 参数、JSON v3 schema、四类提示词、缓存按学科区分和英语词义补全迁移；review 后收紧 `answer_lines` 正式契约、block 引用归一化和 LLM 配置路径。

子项：

- [x] 明确 `subject` 枚举：`general`、`english`、`liberal_arts`、`science`
- [x] 设计 JSON v3 目标字段：`solution_steps`、`learning_points`、`read_units`
- [x] 补全 JSON v3 schema 细则和完整示例
- [x] 补全四套提示词模板和后处理细则
- [x] API 增加 `subject` 参数和非法值校验
- [x] 拆分四套提示词模板，英语模板保持当前逻辑
- [x] 非英语链路跳过英语词义覆盖检测和补词义调用
- [x] 更新 Pydantic 模型、JSON schema 和 schema guard
- [x] 更新任务缓存 schema 版本并清理旧缓存
- [x] 缓存复用按 `subject` 区分
- [x] 更新接口文档和错误码说明
- [x] 明确 `answer_lines` 不能被 `solution_steps` 替代
- [x] 多题块未知 `block_id` 不再静默归并到第一个题目块
- [x] `plain_text` 与 `segments` 不一致时保留完整答案
- [x] LLM 配置优先读取仓库内 `backend/.config/llm.json`
