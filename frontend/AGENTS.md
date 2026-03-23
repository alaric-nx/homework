# AGENTS.md (frontend)

## 目录职责
本目录负责 Android 原生客户端（Kotlin + Jetpack Compose）：
- 拍照/导入
- 裁剪（合并页内单张裁剪）
- 多图排序与合并
- 上传前图片压缩
- 上传后端
- 展示解析结果（含填写后题图）
- 点击词/句本地 TTS 发音

## 技术约束
- 平台：Android 原生
- 语言：Kotlin
- UI：Jetpack Compose
- 语音：Android `TextToSpeech`（延迟初始化，Activity context，多引擎回退）
- 网络：OkHttp，SSL 证书忽略，readTimeout 120s
- 后端地址：`https://hs.for2.top:44443`
- API：`POST /v1/homework/parse-fill?expected_type=english`，Content-Type: image/jpeg，raw body

## 功能状态
- [x] 前端技术路线已确定（Kotlin 原生）
- [x] 本地 TTS 方案已确定（TextToSpeech，延迟初始化 + 多引擎回退）
- [x] 相机拍照与相册导入（单选/多选）
- [x] 裁剪能力（合并页内单张裁剪，ContentScale.Fit 坐标精确映射）
- [x] 多图合并（按顺序拼接为完整题图）
- [x] 上传前图片压缩（长边 1920px + JPEG 85%）
- [x] 上传接口对接（ApiResponse 外层包装、unit_type/reason 字段映射）
- [x] 结果页（题意、答案、讲解、词汇、点读、填写后题图 base64）
- [x] "再来一题"状态完整清理（cropSegments + originalUris + ResultHolder）

## 与后端接口约定
- 入参：合并压缩后的题图（image/jpeg raw body）
- 出参：`{ result: { question_meaning_zh, reference_answer, explanation_zh, key_vocabulary, speak_units, uncertainty }, filled_image_base64, filled_image_path }`
- speak_units 字段：`unit_type`（非 type）
- uncertainty 字段：`reason`（非 warning）

## 关键文件
- `HomeworkApp.kt`：导航与状态管理
- `CaptureScreen.kt`：拍照/选图
- `CropScreen.kt`：裁剪（坐标映射 imageRect）
- `MergeScreen.kt`：排序、合并、预览、压缩上传
- `ResultScreen.kt`：结果展示 + 填写后题图 + TTS
- `HomeworkModels.kt`：数据模型（ApiResponse/ParseResponse/SpeakUnit/Uncertainty）
- `HomeworkApi.kt`：网络请求（SSL 忽略、raw body）
- `TtsManager.kt`：TTS 管理（延迟初始化、多引擎回退）
- `ImageUtils.kt`：图片工具（裁剪、合并、压缩）
- `ResultHolder.kt`：结果传递
