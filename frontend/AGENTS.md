# AGENTS.md (frontend)

## 目录职责

本目录负责 Android 原生客户端（Kotlin + Jetpack Compose）：

- 拍照 / 相册导入
- 题图裁剪
- 多图排序与合并
- 上传前图片压缩
- 异步提交后端
- 任务列表与历史记录
- 展示解析结果
- 参考答案分段高亮
- 点击词 / 句本地 TTS 发音

## 技术约束

- 平台：Android 原生
- 语言：Kotlin
- UI：Jetpack Compose
- 语音：Android `TextToSpeech`（延迟初始化，Activity context，多引擎回退）
- 网络：OkHttp，SSL 证书忽略，readTimeout 120s
- 后端地址：`https://hs.for2.top:44443`
- 数据库：Room（任务持久化，最多 10 条，自动淘汰最早记录）
- 后台任务：WorkManager

## API 约定

异步提交：

```text
POST /v1/homework/parse?model=<可选模型名>
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

完成响应中的 `result` 使用 JSON v2：

- `question_meaning_zh`
- `answer_lines`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`

前端不再依赖 `reference_answer` 渲染参考答案区。

## answer_lines 渲染规则

`answer_lines` 是参考答案区唯一数据源。

每行字段：

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
- [x] 任务列表页
- [x] 底部导航栏
- [x] 结果数据持久化
- [x] 数据模型升级为 JSON v2
- [x] 参考答案区改为 `answer_lines` 渲染
- [x] 支持 `given` / `answer` / `connector` / `correction` 分段配色
- [x] 调整 TTS 逻辑，整行朗读使用 `plain_text`

## 构建与测试

在 `frontend/` 目录下使用 Gradle Wrapper：

```bash
cd frontend
./gradlew :app:compileDebugKotlin
./gradlew :app:assembleDebug
./gradlew :app:testDebugUnitTest
```

说明：

- `compileDebugKotlin` 用于最快验证 Kotlin 编译。
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
