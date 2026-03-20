# AGENTS.md (frontend)

## 目录职责
本目录负责 Android 原生客户端（Kotlin + Jetpack Compose）：
- 拍照/导入
- 裁剪
- 多图排序与合并
- 上传后端
- 展示解析结果
- 点击词/句本地 TTS 发音

## 技术约束
- 平台：Android 原生
- 语言：Kotlin
- UI：Jetpack Compose
- 语音：Android `TextToSpeech`

## 功能状态
- [x] 前端技术路线已确定（Kotlin 原生）
- [x] 本地 TTS 方案已确定（TextToSpeech）
- [x] 相机拍照与相册导入
- [x] 裁剪能力
- [x] 多图合并（按顺序拼接为完整题图）
- [x] 上传接口对接
- [x] 结果页与点读交互

## 与后端接口约定（高层）
- 入参：合并后的完整题图（单题）
- 出参：固定 JSON（题意、答案、讲解、词汇、speak_units、uncertainty）
