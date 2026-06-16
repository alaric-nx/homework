# PROGRESS.md (frontend)

## 最近更新

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成拍题页三入口改造，新增批量解析；`./gradlew :app:assembleDebug` 验证通过。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成 `question_blocks` 多题目块展示、`question_instruction` 题目要求卡片、强制重新解题、无释义弹窗提示和 debug APK 打包。

- 时间：2026-06-16
- 更新类型：文档规范化
- 摘要：规范化前端 PLAN / PROGRESS 状态，修正任务子项计数和计划完成时间。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成前端 JSON v2 数据模型和 `answer_lines` 分段高亮渲染；debug APK 打包通过。

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
- 明确 `question_instruction` 用于展示图片中的英文题目要求原句、中文解释和朗读。
- 明确 `question_blocks` 用于把同一图片中的多个独立题目块分开展示。
- 明确参考答案区不再依赖 `reference_answer`。
- 明确 `segments[].role` 的显示规则：
  - `given`：黑色
  - `answer`：红色
  - `connector`：灰色或黑色
  - `correction`：橙红色

当前进行中：

- 无。

新增完成内容：

- 在 `HomeworkModels.kt` 增加 `AnswerLine` / `AnswerSegment`。
- `ParseResult` 移除 `reference_answer`，新增 `question_instruction`、`question_blocks` 和 `answer_lines`。
- `ResultScreen.kt` 改为按 `question_blocks` 分组展示 `answer_lines`。
- `ResultScreen.kt` 新增“题目要求”卡片，展示英文题目要求原句、中文解释和朗读按钮。
- 参考答案左侧展示 `number` badge。
- 按 `segments[].role` 渲染颜色：`given` 黑色、`answer` 红色、`connector` 灰色、`correction` 橙红色。
- 整行朗读使用 `plain_text`，并保留单词点读和句义查看能力。
- 重新解题按钮提交 `force=true`，触发后端跳过缓存重新解析。
- 缺少释义的单词仍显示弹窗提示“暂无释义，点击可发音”。
- 已运行 `./gradlew :app:assembleDebug`，产出 debug APK。
- 拍题页入口调整为 `拍照解析`、`多图合并`、`批量解析`。
- `多图合并` 保持原排序、裁剪、合并预览和单任务提交流程。
- `批量解析` 一次选择多张图后，每张图独立压缩、创建任务并进入任务列表。
- 已再次运行 `./gradlew :app:assembleDebug` 验证通过。

阻塞项：

- 无。

下一步：

- 后续可在真机上复测题目要求朗读、答案点读和无释义弹窗体验。
