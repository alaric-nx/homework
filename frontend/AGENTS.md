# AGENTS.md (frontend)

## 目录职责

本目录负责 Android 原生客户端（Kotlin + Jetpack Compose）：

- 拍照 / 相册导入。
- 题图裁剪。
- 多图排序与合并。
- 上传前图片压缩。
- 批量解析入口。
- 异步提交后端并轮询任务。
- 任务列表与历史记录。
- 展示 JSON v4 解析结果。
- 参考答案分段高亮。
- 本地 `TextToSpeech` 点读。

## 技术约束

- 平台：Android 原生
- 语言：Kotlin
- UI：Jetpack Compose
- 语音：Android `TextToSpeech`
- 网络：OkHttp，readTimeout 120s
- 后端地址：`https://hs.for2.top:44443`
- 数据库：Room，任务持久化最多 10 条
- 后台任务：WorkManager

## 学科入口

`subject` 取值：

- `general`：通用，默认值。
- `english`：英语。
- `liberal_arts`：文科。
- `science`：理科。

规则：

- 用户先选择学科，再选择 `拍照解析`、`多图合并` 或 `批量解析`。
- 创建任务时保存当前 `subject`。
- 重新解题必须沿用任务保存的 `subject`，不能使用页面当前临时选择值。
- `UploadWorker` 从任务读取 `subject` 并传给后端。

## API

异步提交：

```text
POST /v1/homework/parse?subject=<general|english|liberal_arts|science>&model=<可选模型名>&force=<可选>
Content-Type: image/jpeg
Body: raw JPEG bytes
```

轮询：

```text
GET /v1/homework/tasks/{task_id}
```

完成响应中的 `result` 使用 JSON v4。

前端任务成功的最低要求：

- `result.subject` 非空。
- `result.question_blocks` 非空。
- `result.answer_items` 非空。

缺少以上字段时，前端标记任务失败，并提示后端未部署当前 JSON v4 契约。

## JSON v4 前端模型

主要模型：

```kotlin
data class ParseResult(
    val schema_version: String = "4.0",
    val subject: String = "general",
    val question_meaning_zh: String = "",
    val question_blocks: List<QuestionBlock> = emptyList(),
    val answer_items: List<AnswerItem> = emptyList(),
    val student_answer_reviews: List<StudentAnswerReview> = emptyList(),
    val solution_steps: List<SolutionStep> = emptyList(),
    val explanation_zh: String = "",
    val learning_points: List<LearningPoint> = emptyList(),
    val uncertainty: Uncertainty = Uncertainty()
)
```

旧字段不作为正式消费来源：

- `question_instruction`
- `answer_lines`
- `read_units`
- `reference_answer`

## 结果页展示策略

结果页顺序：

1. 题目原图。
2. 不确定性提示。
3. 批改总览。
4. 题目理解。
5. 按 `question_blocks` 展示逐题报告。
6. 全局讲解 / 总结。
7. 知识点。

批改总览：

- 保留在结果页前部。
- 汇总展示错题、看不清、未作答题号。
- 只做“一眼看到问题题号”的总览，不放详细分析。

逐题报告：

- 每个 `question_blocks[]` 是一个题目卡片。
- 卡片内先展示对应 `answer_items`。
- `solution_steps` 按 `block_id` 归到对应题目卡片，直接展示在答案后面，标题为“题解”。
- 当同一题卡内有多条答案时，前端按题号把对应 `solution_steps` 插到该答案后面；无法匹配题号的题解保留在题卡末尾。
- `student_answer_reviews` 的短批改说明贴近对应答案展示。
- 全局 `explanation_zh` 只展示整体总结、共性提醒，不承担逐题题解。
- 逐题题卡使用中性浅灰分层、左侧灰色分隔条和标题灰底增强分割；避免高饱和亮色抢占答案、纠错和批改状态的视觉优先级。

题面辅助内容：

- `content_items` 是结构化题面数据，不等于所有学科都要展示。
- `science`：默认不展示题面辅助内容，只展示答案、题解、讲解和知识点。
- `general`：默认不展开题面辅助内容。
- `english`：展示题目要求、例句、场景、短文、对话、词库、选项，并支持朗读。
- `liberal_arts`：展示材料、对话、图中文字等有阅读价值的内容。

数学公式：

- `answer_items.display.mode=math_block` 时使用数学块展示。
- 前端会把常见 LaTeX 命令清洗为可读文本，如 `\frac`、`\pi`、`\Rightarrow`、`\times`、`^\circ`。
- `solution_steps[].formula` 也会做同样清洗。
- 简单公式应优先由后端返回 Unicode / 纯文本公式。

知识点：

- `learning_points` 展示标题使用 `知识点`。
- 理科不展示发音。
- 英语可展示 IPA。
- 文科可展示拼音。

## 拍题入口

- `拍照解析`：单张题图，进入单图解析流程。
- `多图合并`：多张图排序 / 裁剪 / 合并成一张题图后创建一个任务。
- `批量解析`：多张图分别创建多个任务，不合并。

批量解析规则：

- 不新增后端接口。
- 每张图片独立生成 `TaskEntity`。
- 每张图片独立调用 `UploadWorker.enqueue`。
- 单张失败不影响其他任务。
- 提交后跳转任务列表。

## 构建与测试

在 `frontend/` 目录运行：

```bash
./gradlew :app:assembleDebug
./gradlew :app:testDebugUnitTest
```

说明：

- 当前默认打 debug APK。
- 当前 `app/src` 主要使用 `main` 源集。
- JDK 25 下 Kotlin 可能回退到 JVM_24 target，该警告无害。

## 关键文件

- `HomeworkModels.kt`：接口数据模型。
- `HomeworkApi.kt`：网络请求。
- `UploadWorker.kt`：上传、轮询和结果契约校验。
- `ResultScreen.kt`：结果展示、答案高亮、逐题题解、TTS。
- `CaptureScreen.kt`：拍照 / 选图和学科选择。
- `TaskListScreen.kt`：任务列表。
- `TtsManager.kt`：TTS 管理。
- `TaskEntity.kt`：Room Entity。
