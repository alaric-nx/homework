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
- [x] 定义前端交互细节（裁剪页、合并页、结果页）
- [x] 定义异常流程（上传失败、解析失败、超时重试）

### B. 后端能力（Python + opencode + skills）
- [x] 明确后端总体方向（Python + opencode）
- [x] 明确 skills 分流口（english/chinese/math）
- [x] 实现 subject router skill
- [x] 实现 OCR skill
- [x] 实现 English semantic/solver skill
- [x] 实现固定 JSON 输出与 schema 校验
- [x] 实现 API 接口（解析入口）
- [x] 实现日志与错误码规范

### C. 前端能力（Kotlin Android）
- [x] 明确使用 Android 本地 TTS（TextToSpeech，延迟初始化 + 多引擎回退）
- [x] 相机拍照与相册导入
- [x] 题图裁剪（合并页内单张裁剪，坐标精确映射 ContentScale.Fit）
- [x] 多段图片排序与合并
- [x] 上传与结果展示（含填写后题图 base64 展示）
- [x] 词/句点击发音
- [x] 上传前图片压缩（长边 1920px + JPEG 85%）
- [x] 后端 API 对接（parse-fill 接口、SSL 忽略、ApiResponse 字段映射）
- [x] "再来一题"状态完整清理（含 ResultHolder）
- [x] 异步任务队列（WorkManager，后台上传不受息屏/切后台影响）
- [x] 任务列表页（历史记录，最多保留 10 条，单删/全删/手动重试）
- [x] 底部导航栏（拍题 / 任务列表双 Tab）
- [x] 填写后题图双指缩放拖动（clipToBounds 限制框内）
- [x] 结果数据持久化（Room 数据库，替代 ResultHolder 内存传递）

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

## 解析策略（当前生效）
- 总体策略：`image-first + OCR-assist`
- 大模型输入：必须包含原题图；OCR 结果作为辅助，不可替代图片。
- 冲突处理：OCR 与图片冲突时，以图片语义为准。
- 编号题策略：仅当识别到编号时按编号顺序组织答案；无编号题不强制排序。
- 当前 OCR 来源：PaddleCloud 文档解析返回结构，优先取 `layoutParsingResults[*].markdown.text`，并结合 `parsing_res_list` 提供块级辅助信息。

## 回写策略（当前生效）
- 回写阶段不再调用大模型；仅消费 parse 阶段返回的 `reference_answer` / `answer_placements`。
- 槽位优先级：`answer_placements` 直写优先，OCR/规则映射作为兜底。
- 文字定位采用“布局自适应校准层”：基于候选框估计列结构、行高、行距后动态计算 `x/y` 偏移与有效行高。
- 小样本门控：当候选行不足时自动回退默认参数，避免误校准。

## 配置文件优先级（backend）
- 通用配置：`backend/config.env`（可提交）
- 本地覆盖：`backend/.env`（同 key 优先级高于 `config.env`，不提交 Git）
- 进程环境变量优先级最高（高于 `.env`）
- `backend/start_backend.sh` 启动顺序：先加载 `config.env`，再加载 `.env` 覆盖

## 子目录说明
- 前端说明：`/frontend/AGENTS.md`
- 后端说明：`/backend/AGENTS.md`

## Opencode Remote 图片触发规则（新增）
当在项目根目录通过 opencode remote 进行交互时，若用户输入里包含“图片文件”（本地路径或上传图片），执行以下默认动作：

1. 直接触发 skills 链路，不要求先启动本项目后端服务。
2. 优先使用已安装 OCR 相关 skills 进行识别与解析（当前已安装）：
   - `ocr-document-processor`
   - `paddleocr-text-recognition`
   - `paddleocr-doc-parsing`
   - `discord-homework-auto`（Discord 场景优先）
3. 解析目标仍按英语作业场景输出结构化结果（题意、答案、讲解、词汇、点读单元、不确定性）。
4. 若识别到是“看图填空”类题目，默认执行“按编号提取答案”的策略，而不是只抽取图片中文字。
5. 仅当用户明确要求“走后端接口联调”时，才调用 `backend` API。

说明：
- 该规则的目标是“收到图片立即触发 skills”，避免先做服务启动步骤。
- Discord 场景推荐命令：
  - `python .agents/skills/discord-homework-auto/scripts/discord_homework_parse_fill.py --image "<IMAGE_PATH>"`
