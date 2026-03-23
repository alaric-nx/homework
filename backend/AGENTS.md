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
- parse 阶段新增候选归一化：在 schema 校验前自动修正常见不规范输出（如 `reference_answer` list -> string、`font_size_ratio<=0 -> null`），降低整包 fallback 概率。

## 回写与定位（当前生效）
- 回写阶段不调用大模型；只使用 parse 结果。
- 槽位优先级：`answer_placements` 直写优先，OCR/规则映射兜底。
- 已移除 OpenCV 线检测依赖；定位基于 OCR/模型框融合与后处理。
- 新增“布局自适应校准层”：
  - 输入：最终候选框集合
  - 估计：列结构、行高中位数、行距中位数、行密度
  - 输出：按列动态 `left_ratio/top_ratio/baseline_pull/effective_h_cap`
  - 门控：候选样本不足时回退默认参数

## 环境与启动约定
- 通用配置文件：`backend/config.env`
- 本地覆盖文件：`backend/.env`（同 key 覆盖 `config.env`，不提交 Git）
- 优先级：进程环境变量 > `.env` > `config.env`
- `backend/start_backend.sh` 已按上述顺序加载配置

## 返回 JSON 目标字段
- `question_meaning_zh`
- `reference_answer`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`
