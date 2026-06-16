# PROGRESS.md (frontend)

## 最近更新

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成前端 JSON v2 数据模型和 `answer_lines` 分段高亮渲染；Kotlin 编译通过。

- 时间：2026-06-16
- 更新类型：开始执行
- 摘要：开始实现前端 JSON v2 数据模型和参考答案分段高亮渲染。

- 时间：2026-06-16
- 更新类型：文档规范化
- 摘要：记录 JSON v2 前端升级计划，明确参考答案区由 `answer_lines` 驱动。

## 进展记录

### 2026-06-16

完成内容：

- 统一前端文档结构。
- 明确前端完成响应中的 `result` 使用 JSON v2。
- 明确参考答案区不再依赖 `reference_answer`。
- 明确 `segments[].role` 的显示规则：
  - `given`：黑色
  - `answer`：红色
  - `connector`：灰色或黑色
  - `correction`：橙红色

当前进行中：

- 模拟 JSON 视觉检查尚未执行。
- 真机 TTS 点击行为尚未执行。

新增完成内容：

- 在 `HomeworkModels.kt` 增加 `AnswerLine` / `AnswerSegment`。
- `ParseResult` 移除 `reference_answer`，新增 `answer_lines`。
- `ResultScreen.kt` 改为从 `answer_lines` 构建展示行。
- 参考答案左侧展示 `number` badge。
- 按 `segments[].role` 渲染颜色：`given` 黑色、`answer` 红色、`connector` 灰色、`correction` 橙红色。
- 整行朗读使用 `plain_text`，并保留单词点读和句义查看能力。
- 已运行 `./gradlew :app:compileDebugKotlin`，编译通过。

阻塞项：

- 无。

下一步：

- 使用模拟 JSON 做填空题红黑分段视觉检查。
- 在设备上检查 TTS 点击行为。
