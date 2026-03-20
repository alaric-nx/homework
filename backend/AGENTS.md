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
- [ ] subject_router skill
- [ ] ocr skill
- [ ] english solver skill
- [ ] 固定 JSON schema
- [ ] 解析 API
- [ ] 日志与错误码

## 返回 JSON 目标字段
- `question_meaning_zh`
- `reference_answer`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`
