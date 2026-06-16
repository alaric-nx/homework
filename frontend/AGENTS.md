# AGENTS.md (frontend)

## 目录职责

本目录负责 Android 原生客户端（Kotlin + Jetpack Compose）：

- 拍照 / 相册导入
- 批量解析入口
- 题图裁剪
- 多图排序与合并
- 上传前图片压缩
- 异步提交后端
- 任务列表与历史记录
- 展示解析结果
- 参考答案分段高亮
- 点击词 / 句本地 TTS 发音

## 多学科 v3 当前实现

拍题页已新增学科选择器：

- `通用`：默认选中，对应 `general`。
- `英语`：对应 `english`，保持当前英语体验。
- `文科`：对应 `liberal_arts`。
- `理科`：对应 `science`。

交互规则：

- 用户先选择学科，再选择 `拍照解析`、`多图合并` 或 `批量解析`。
- `多图合并` 生成一个任务，任务使用当前选中学科。
- `批量解析` 生成多个任务，每个任务使用当前选中学科。
- 重新解题必须沿用任务保存的 `subject`，不能使用当前页面临时选择值。

数据规则：

- `TaskEntity` 已新增 `subject: String = "general"`。
- `HomeworkApi.submitParse()` 已新增 `subject` query 参数。
- `UploadWorker` 从任务读取 `subject` 并传给后端。

## 多学科 UI 细则

拍题页布局：

- 顶部在三个上传入口上方放学科选择器。
- 学科选择器使用单选分段按钮，顺序为：`通用`、`英语`、`文科`、`理科`。
- 默认选中 `通用`。
- 选择状态在当前 App 会话内保持；创建任务时写入任务。
- 三个入口按钮保持当前顺序：`拍照解析`、`多图合并`、`批量解析`。

任务列表：

- 每条任务显示学科标签。
- 标签文案：`通用`、`英语`、`文科`、`理科`。
- 标签颜色保持低饱和，不抢占任务状态。
- 重新解题按钮不弹出学科选择，直接使用任务原 `subject`。

结果页：

- 顶部在题目原图或题目要求附近展示学科标签。
- Section 顺序：
  1. 题目原图
  2. 不确定性提示
  3. 学科标签 + 题目要求
  4. 题目理解
  5. 参考答案
  6. 解题步骤
  7. 讲解
  8. 知识点
  9. 可朗读内容
- `solution_steps` 为空时不展示“解题步骤”区。
- `learning_points` 为空时不展示“知识点”区。
- `read_units` 为空时不展示“可朗读内容”区。

结果页文案：

- `词汇` 改为 `知识点`。
- `暂无释义，点击可发音` 改为 `暂无解释，点击可朗读`。
- 英语题中仍可展示 IPA 和单词释义。
- 理科题中公式优先用普通文本展示，不强制朗读。

## 技术约束

- 平台：Android 原生
- 语言：Kotlin
- UI：Jetpack Compose
- 语音：Android `TextToSpeech`（延迟初始化，Activity context，多引擎回退）
- 网络：OkHttp，SSL 证书忽略，readTimeout 120s
- 后端地址：`https://hs.for2.top:44443`
- 数据库：Room（任务持久化，最多 10 条，自动淘汰最早记录）
- 后台任务：WorkManager

## 拍题入口

拍题页提供三个入口：

- `拍照解析`：单张题图，进入单图解析流程。
- `多图合并`：从相册选择多张图，进入排序 / 裁剪 / 合并预览，最终合成一张题图并创建一个任务。
- `批量解析`：从相册选择多张图，不合并；每张图单独压缩、入库并创建一个解析任务。

批量解析规则：

- 不新增后端接口，前端循环使用现有单图任务链路。
- 每张图片独立生成 `TaskEntity`，独立调用 `UploadWorker.enqueue`。
- 单张失败不影响其他任务。
- 提交后跳转任务列表，用户可看到多条解析中任务。

## API 约定

异步提交：

```text
POST /v1/homework/parse?subject=<general|english|liberal_arts|science>&model=<可选模型名>
Content-Type: image/jpeg
Body: raw JPEG bytes
```

响应：

```json
{
  "task_id": "...",
  "status": "pending",
  "image_hash": "..."
}
```

轮询任务：

```text
GET /v1/homework/tasks/{task_id}
```

完成响应中的 `result` 使用 JSON v3：

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

前端不再依赖 `reference_answer` 渲染参考答案区。

展示规则：

- `learning_points` 展示标题使用 `知识点`，不再使用英语限定的 `词汇`。
- `read_units` 用于朗读入口；数学公式不强制朗读。
- `solution_steps` 在参考答案后、讲解前展示，理科题重点展示。
- 旧 v2 字段 `key_vocabulary`、`speak_units` 已在 v3 中被 `learning_points`、`read_units` 替换。

前端目标数据模型：

```kotlin
data class ParseResult(
    val subject: String = "general",
    val question_meaning_zh: String = "",
    val question_instruction: QuestionInstruction = QuestionInstruction(),
    val question_blocks: List<QuestionBlock> = emptyList(),
    val answer_lines: List<AnswerLine> = emptyList(),
    val solution_steps: List<SolutionStep> = emptyList(),
    val explanation_zh: String = "",
    val learning_points: List<LearningPoint> = emptyList(),
    val read_units: List<ReadUnit> = emptyList(),
    val uncertainty: Uncertainty = Uncertainty()
)
```

新增模型：

```kotlin
data class SolutionStep(
    val block_id: String = "",
    val number: String = "",
    val title: String = "",
    val content_zh: String = "",
    val formula: String? = null,
    val result: String? = null
)

data class LearningPoint(
    val block_id: String? = null,
    val term: String = "",
    val explanation_zh: String = "",
    val pronunciation: String? = null,
    val category: String = "other"
)

data class ReadUnit(
    val block_id: String? = null,
    val unit_type: String = "sentence",
    val text: String = "",
    val meaning_zh: String? = null
)
```

## question_instruction 展示规则

`question_instruction` 用于“题目要求”区域。

字段：

- `text`：图片中的题目要求原文。
- `meaning_zh`：题目要求的中文解释。
- `confidence`：后端识别置信度。

展示：

- 当 `text` 或 `meaning_zh` 非空时，结果页展示独立的“题目要求”卡片。
- 题目要求原文可点击 / 按钮朗读，使用本地 `TextToSpeech`。
- 中文解释直接展示给家长理解题目要求。
- 若该字段为空，不影响参考答案区渲染。

## answer_lines 渲染规则

`answer_lines` 是参考答案区唯一数据源。

前端按 `question_blocks` 分组展示参考答案。每个 `question_blocks[]` 渲染为一个独立题目块卡片，卡片内展示该题目块的英文要求、中文解释、中文理解和所属答案行。

`answer_lines[].block_id` 必须对应某个 `question_blocks[].block_id`。

每行字段：

- `block_id`：所属题目块 ID
- `number`：题号，显示为左侧 badge；可为空
- `line_type`：题型，用于后续样式或行为扩展
- `plain_text`：完整答案文本，用于整行朗读
- `segments`：分段渲染文本

`segments[].role` 配色：

- `given`：黑色，表示题目已有内容
- `answer`：红色，表示学生应填写、选择或生成的答案
- `connector`：灰色或黑色，表示箭头、短横线、冒号等连接符
- `correction`：橙红色，表示改错题订正内容

填空题展示目标：

```text
I am a student.
```

其中 `I ` 与 ` a student.` 为 `given`，`am` 为 `answer`。

## 功能状态

- [x] 前端技术路线已确定（Kotlin 原生）
- [x] 本地 TTS 方案已确定
- [x] 相机拍照与相册导入
- [x] 裁剪能力
- [x] 多图合并
- [x] 上传前图片压缩
- [x] 异步任务队列
- [x] 批量解析：多张图片分别创建解析任务
- [x] 任务列表页
- [x] 底部导航栏
- [x] 结果数据持久化
- [x] 数据模型升级为 JSON v3
- [x] 展示 `question_instruction` 题目要求原句、中文解释和朗读按钮
- [x] 使用 `question_blocks` 将同一图片中的多个题目块分组展示
- [x] 参考答案区改为 `answer_lines` 渲染
- [x] 支持 `given` / `answer` / `connector` / `correction` 分段配色
- [x] 调整 TTS 逻辑，整行朗读使用 `plain_text`
- [x] 重新解题时提交 `force=true`，触发后端强制重新解析
- [x] 单词缺少释义时仍弹窗提示“暂无解释，点击可朗读”
- [x] 多学科选择：通用 / 英语 / 文科 / 理科
- [x] 任务持久化保存 `subject`
- [x] 展示 `solution_steps` / `learning_points` / `read_units`

## 构建与测试

在 `frontend/` 目录下使用 Gradle Wrapper：

```bash
cd frontend
./gradlew :app:assembleDebug
./gradlew :app:testDebugUnitTest
```

说明：

- 当前默认打 debug APK，不单独打 release 包。
- 当前 `app/src` 仅有 `main` 源集，暂无单元测试源集。
- JDK 25 下 Kotlin 可能回退到 JVM_24 target，该警告无害。

## 关键文件

- `HomeworkApp.kt`：导航与状态管理
- `CaptureScreen.kt`：拍照 / 选图
- `CropScreen.kt`：裁剪
- `MergeScreen.kt`：排序、合并、预览、提交任务
- `ResultScreen.kt`：结果展示、答案高亮、TTS
- `TaskListScreen.kt`：任务列表
- `HomeworkModels.kt`：接口数据模型
- `HomeworkApi.kt`：网络请求
- `TtsManager.kt`：TTS 管理
- `ImageUtils.kt`：图片工具
- `TaskEntity.kt`：Room Entity
- `TaskDao.kt`：Room DAO
- `AppDatabase.kt`：Room Database 单例
- `TaskRepository.kt`：任务仓库
- `UploadWorker.kt`：后台上传和轮询
- `HomeworkApplication.kt`：Application 入口
