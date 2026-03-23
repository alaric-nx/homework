# AGENTS.md (backend)

## 目录职责
本目录负责 Python 后端服务与模型编排：
- 接收前端上传的完整题图
- 通过 opencode 调用大模型
- 通过 skills 组织 OCR、语义理解、解题流程
- 返回固定 JSON 结果

## 技术约束
- 语言：Python
- 模型调用：opencode（支持代理启动）
- 编排：skills 分层
- 学科：当前仅英语，预留语文/数学分流口

## Skills 规划
- `subject_router`：学科路由（english/chinese/math）
- `ocr_skill`：题图文本提取
- `english_solver_skill`：语义理解与解题
- `response_schema_guard`：固定 JSON 约束

## 功能状态
- [x] 后端路线已确定（Python + opencode + skills）
- [x] 学科分流口已确定（先英语）
- [x] subject_router skill
- [x] ocr skill
- [x] english solver skill
- [x] 固定 JSON schema
- [x] 解析 API
- [x] 日志与错误码

## 当前实现约定（2026-03-23）
- 解题策略：`image-first + OCR-assist`
- OCR 在 pipeline 中默认执行；即使 OCR 失败，也继续把图片喂给大模型解题（不中断）。
- OCR 结构来源：优先 `layoutParsingResults[*].markdown.text`，并抽取 `parsing_res_list` 的 `block_content/order/label` 作为辅助块信息。
- 英语解题 prompt：包含原图（主证据）+ OCR 全文 + OCR 编号提示（仅检测到编号时排序）+ OCR 块预览。
- 冲突原则：图片优先，OCR 仅辅助。

## 返回 JSON 目标字段
- `question_meaning_zh`
- `reference_answer`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`
