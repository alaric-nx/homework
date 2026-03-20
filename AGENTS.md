# AGENTS.md

## 文档导航
本项目采用分层 AGENTS 文档：
- 根文档（本文件）：给出全局目标、边界、阶段状态
- `frontend/AGENTS.md`：前端 Android 端约束与任务
- `backend/AGENTS.md`：后端 Python + opencode + skills 约束与任务

推荐阅读顺序：
1. 先读根 `AGENTS.md`
2. 再按任务进入对应子目录 `AGENTS.md`

## 项目介绍
面向家长辅导低龄孩子英语作业的 Android 应用。

核心目标：
- 家长拍照并裁剪题目。
- 多张裁剪图可在前端按顺序合并为一张“完整题图”。
- 后端接收题图后，调用大模型输出结构化结果：
  - 题目中文理解
  - 参考答案
  - 讲解
  - 词汇
  - 可点击发音单元（词/句）
  - 不确定性标记
- 前端支持点击词或句直接发音（Android 本地 TTS）。

## 已确定技术方案
- 前端：Kotlin 原生 Android（Jetpack Compose）
- 后端：Python
- 模型调用：通过 opencode 调用大模型
- 编排方式：skills 分层（现阶段仅英语）
- 学科策略：预留语文/数学分流入口，当前只实现英语链路
- 题目输入策略：前端完成裁剪与合并，后端接收合并后的完整题图

## 需求清单与状态

### A. 产品与流程
- [x] 明确主流程：拍照 -> 裁剪 -> 合并 -> 上传 -> 解析 -> 展示结果 -> 点读
- [x] 明确“多图合一题”由前端完成
- [x] 明确前端为 Kotlin 原生
- [x] 明确后端暂不做完整性强校验
- [ ] 定义前端交互细节（裁剪页、合并页、结果页）
- [ ] 定义异常流程（上传失败、解析失败、超时重试）

### B. 后端能力（Python + opencode + skills）
- [x] 明确后端总体方向（Python + opencode）
- [x] 明确 skills 分流口（english/chinese/math）
- [ ] 实现 subject router skill
- [ ] 实现 OCR skill
- [ ] 实现 English semantic/solver skill
- [ ] 实现固定 JSON 输出与 schema 校验
- [ ] 实现 API 接口（解析入口）
- [ ] 实现日志与错误码规范

### C. 前端能力（Kotlin Android）
- [x] 明确使用 Android 本地 TTS（TextToSpeech）
- [x] 相机拍照与相册导入
- [x] 题图裁剪（单图多次裁）
- [x] 多段图片排序与合并
- [x] 上传与结果展示
- [x] 词/句点击发音

### D. 当前不做 / 后续再做
- [x] 暂不做语文 skills
- [x] 暂不做数学 skills
- [x] 暂不做后端完整性强校验（缺题自动拦截）
- [ ] 云端高拟真 TTS（后续可选）
- [ ] 精细化题型识别与自动分题（后续可选）

## 固定返回 JSON（目标字段）
后端目标返回结构（字段名可在 API 设计时微调）：
- `question_meaning_zh`
- `reference_answer`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`

## 子目录说明
- 前端说明：`/frontend/AGENTS.md`
- 后端说明：`/backend/AGENTS.md`

## Opencode Remote 图片触发规则（新增）
当在项目根目录通过 opencode remote 进行交互时，若用户输入里包含“图片文件”（本地路径或上传图片），执行以下默认动作：

1. 优先调用后端接口 `POST /v1/homework/parse-fill`，而不是只做文本 OCR 或只返回说明。
2. 请求方式使用二进制图片 body（`content-type: image/jpeg|image/png|application/octet-stream`），不使用 base64 作为输入。
3. 查询参数默认带 `expected_type=english`，除非用户明确要求其它学科。
4. 返回时至少包含：
   - 结构化解析结果（6 个目标字段）
   - 回填图片落地路径（`filled_image_path`）
5. 若后端服务未启动，先提示并给出最小启动命令：
   - `cd backend && ./start_backend.sh`
6. 若回填位置偏差，优先基于后端返回的最新落地图继续迭代，不改成手工口算答案。

推荐执行命令模板（供 agent 在 shell 中调用）：
```bash
curl -sS -X POST "http://127.0.0.1:8000/v1/homework/parse-fill?expected_type=english" \
  -H "content-type: image/jpeg" \
  --data-binary "@/absolute/path/to/image.jpg"
```
