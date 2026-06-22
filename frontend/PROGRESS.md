# PROGRESS.md (frontend)

## 最近更新

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：优化逐题报告展示：同一题卡内多条答案按题号贴合对应题解；逐题题卡改为中性浅灰分层、左侧灰色分隔条和标题灰底，提升题目分割清晰度。

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：完成 JSON v4 前端结果页改造：消费 `answer_items`、保留顶部批改总览、逐题展示答案后题解、按学科过滤题面辅助内容，并清洗常见 LaTeX 公式显示。

- 时间：2026-06-17
- 更新类型：阶段完成
- 摘要：隐藏结果页独立“可朗读内容”区，保留 `read_units` 作为词义、句义和内部朗读辅助数据源；应用版本升级到 `0.1.1`。

- 时间：2026-06-17
- 更新类型：阶段完成
- 摘要：完成 review 收敛优化：前端恢复要求完成结果必须包含非空 `answer_lines`，结果页不再用 `solution_steps` 伪造参考答案行，并同步文档说明。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成 review 优化：结果页可朗读内容过滤 `word` 单元，知识点头部改为可换行布局，减少重复和小屏挤压。

- 时间：2026-06-16
- 更新类型：阶段完成
- 摘要：完成多学科 v3 前端实现：拍题页学科选择、任务 `subject` 持久化和上传、任务列表标签、结果页 `solution_steps` / `learning_points` / `read_units` 展示；debug APK 构建通过。

- 时间：2026-06-16
- 更新类型：文档规范化
- 摘要：补全多学科 v3 前端详细设计，包含学科选择器、任务列表标签、结果页展示顺序、文案规则和目标模型。

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
- 明确前端完成响应中的 `result` 使用 JSON v3。
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
- 缺少解释的可点读内容仍显示弹窗提示“暂无解释，点击可朗读”。
- 已运行 `./gradlew :app:assembleDebug`，产出 debug APK。
- 拍题页入口调整为 `拍照解析`、`多图合并`、`批量解析`。
- `多图合并` 保持原排序、裁剪、合并预览和单任务提交流程。
- `批量解析` 一次选择多张图后，每张图独立压缩、创建任务并进入任务列表。
- 已再次运行 `./gradlew :app:assembleDebug` 验证通过。
- 完成多学科 v3 前端文档设计：
  - 拍题页目标学科：通用、英语、文科、理科
  - 默认学科：通用
  - 任务需持久化 `subject`，重新解题沿用任务原学科
  - v3 结果页目标展示：`solution_steps`、`learning_points`；`read_units` 仅作内部数据源
  - 拍题页、任务列表、结果页 UI 细则
  - v3 前端目标数据模型
- 完成多学科 v3 前端实现：
  - 拍题页新增通用 / 英语 / 文科 / 理科学科选择器，默认通用
  - `TaskEntity` 保存 `subject`
  - 上传和强制重新解题均使用任务原 `subject`
  - `HomeworkApi.submitParse()` 传递 `subject` query
  - 任务列表展示学科标签
  - 结果页展示学科标签、解题步骤和知识点
  - 结果模型升级到 JSON v3：`learning_points` / `read_units` 替代旧字段
- 完成 review 优化：
  - “可朗读内容”区过滤 `word` 单元，避免和知识点、点读词重复
  - 知识点头部使用可换行布局，长公式、长概念、长拼音在小屏上更稳
  - 已运行 `./gradlew :app:assembleDebug` 验证通过

阻塞项：

- 无。

下一步：

- 真机验证多学科图片解析体验和 TTS 表现。

### 2026-06-17

完成内容：

- 明确 `answer_lines` 是参考答案区正式数据源，`solution_steps` 只用于过程展示。
- `UploadWorker` 完成结果校验恢复要求非空 `answer_lines`，避免任务成功但参考答案为空。
- 结果页移除从 `solution_steps` 生成参考答案行的兜底逻辑。
- 前端文档同步接口契约和展示规则。
- 隐藏结果页独立“可朗读内容”区，`read_units` 继续用于词义、句义和内部朗读辅助。
- 应用版本升级到 `0.1.1`，`versionCode=2`。

阻塞项：

- 无。

下一步：

- 真机验证理科题同时展示参考答案和解题步骤的体验。

### 2026-06-22

完成内容：

- 前端结果模型升级为 JSON v4：
  - `schema_version`
  - `question_blocks[].content_items`
  - `answer_items`
  - `answer_items[].display.format`
  - `answer_items[].display.latex`
  - `student_answer_reviews`
- `UploadWorker` 完成结果契约校验：任务成功必须包含非空 `subject`、`question_blocks` 和 `answer_items`。
- 结果页保留顶部“批改总览”，集中展示错题、看不清和未作答题号。
- 每个题块卡片内先展示答案，再展示该题 `solution_steps`，标题为“题解”。
- 当后端返回一个题卡内多条答案时，前端按题号把对应 `solution_steps` 插到该答案后面；未匹配题号的题解保留在题卡末尾。
- `student_answer_reviews` 的短批改说明贴近对应答案显示。
- 移除全局“解题步骤”大区块，避免答案与题解分离。
- `explanation_zh` 作为全局讲解 / 总结展示。
- 理科和通用默认不展开 `content_items`，避免题干、选项等题面辅助内容重复铺满结果页。
- 英语保留题目要求、例句、场景、短文、词库、选项展示和朗读。
- 文科保留材料、对话、图中文字等有阅读价值的题面内容。
- 数学公式显示层清洗常见 LaTeX 命令：
  - `\frac`
  - `\pi`
  - `\Rightarrow`
  - `\times`
  - `\cdot`
  - `^\circ`
- 逐题题卡视觉改为中性浅灰分层：
  - 奇偶题卡使用近白 / 冷灰底色区分
  - 左侧灰色分隔条强化题卡边界
  - 标题区域使用灰底，帮助快速识别每题起点
- 前端 debug 构建通过：`./gradlew :app:assembleDebug`。

阻塞项：

- 无。

下一步：

- 重新安装新版 debug APK 后，用真实数学题验证逐题报告、公式显示和批改总览体验。
