# PLAN.md (frontend)

## 当前阶段

阶段目标：升级前端结果模型与参考答案区渲染，支持 `answer_lines` 分段高亮。

最后更新时间：2026-06-16

## 任务列表

### F-001 数据模型升级

- 状态：已完成
- 优先级：高
- 完成比例：100%
- 已完成子项 / 总子项：4 / 4
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：待定
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：前端不再依赖 `reference_answer` 渲染参考答案区。

子项：

- [x] 在 `HomeworkModels.kt` 新增 `AnswerLine`
- [x] 在 `HomeworkModels.kt` 新增 `AnswerSegment`
- [x] 在 `ParseResult` 中新增 `answer_lines`
- [x] 从 `ParseResult` 中移除 `reference_answer`

### F-002 参考答案区渲染升级

- 状态：已完成
- 优先级：高
- 完成比例：100%
- 已完成子项 / 总子项：5 / 5
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：待定
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：目标是完整答案行展示，题目已有内容黑色，答案红色。

子项：

- [x] `ResultScreen.kt` 改为读取 `answer_lines`
- [x] 左侧展示 `number` badge
- [x] 按 `segments[].role` 渲染颜色
- [x] 整行朗读使用 `plain_text`
- [x] 删除旧的 `parseAnswerLines(reference_answer)` 主路径

### F-003 前端验证

- 状态：已完成
- 优先级：中
- 完成比例：100%
- 已完成子项 / 总子项：3 / 3
- 负责人：Codex
- 计划开始：2026-06-16
- 计划完成：待定
- 实际完成：2026-06-16
- 最后更新时间：2026-06-16
- 备注：`./gradlew :app:assembleRelease` 已通过并产出 unsigned release APK；模拟 JSON 和 TTS 行为通过代码路径检查，未做真机手测。

子项：

- [x] 运行 `./gradlew :app:compileDebugKotlin`
- [x] 使用模拟 JSON 检查填空题红黑分段
- [x] 检查 TTS 点击行为
