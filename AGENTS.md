# AGENTS.md

## 文档导航

本项目采用分层文档：

- 根文档（本文件）：项目总览、全局边界、跨端接口决策。
- `frontend/AGENTS.md`：Android 前端约束、接口消费、展示规则。
- `frontend/PLAN.md`：前端任务计划。
- `frontend/PROGRESS.md`：前端进展记录。
- `backend/AGENTS.md`：Python 后端约束、模型编排、输出 schema。
- `backend/PLAN.md`：后端任务计划。
- `backend/PROGRESS.md`：后端进展记录。

推荐阅读顺序：

1. 先读根 `AGENTS.md`。
2. 再按任务进入 `frontend/` 或 `backend/`。
3. 实施前查看对应子项目的 `PLAN.md` 与 `PROGRESS.md`。

## 项目介绍

本项目是一个面向多学科练习题解析的 Android 应用，帮助家长或学习者处理作业、练习册、考试题和基础学习题。

核心流程：

- 家长拍照或从相册导入题图。
- 前端对题图进行裁剪、排序、合并和压缩。
- 后端接收完整题图，调用视觉大模型解析题目。
- 后端返回 JSON v4 结构化结果。
- 前端展示题目原图、批改总览、逐题答案、逐题题解、全局讲解和知识点。
- 前端支持答案高亮、英语题面点读和本地 TTS。

## 已确定技术方案

- 前端：Kotlin 原生 Android（Jetpack Compose）。
- 后端：Python。
- 模型调用：通用 OpenAI 兼容接口。
- 题图输入：前端完成裁剪与合并，后端接收完整题图。
- 学科入口：通用、英语、文科、理科。
- TTS：Android 本地 `TextToSpeech`。

## 当前阶段重点

当前阶段聚焦 JSON v4 逐题报告：

- `subject` 分为 `general`、`english`、`liberal_arts`、`science`。
- `question_blocks` 表示图片中的独立题目块。
- `question_blocks[].content_items` 表示题面可见内容，包括题目要求、例句、材料、选项等。
- `answer_items` 是参考答案区唯一数据源。
- `student_answer_reviews` 表示学生已写答案的批改结果。
- `solution_steps` 表示逐题题解，按 `block_id` 归属到题目块。
- `learning_points` 表示知识点、词汇、概念、公式、单位或方法。
- `explanation_zh` 只做全局总结、共性错因或整体提醒。
- 顶部批改总览保留，用于一眼看到错题、看不清和未作答题号。
- 前端逐题卡片内展示：答案 -> 批改短提示 -> 题解。

## 学科分类

`subject` 取值：

- `general`：通用，默认值。适合混合题或用户不确定题型时使用。
- `english`：英语。保留题目要求、例句、场景、短文、词库、选项、词义、IPA 和点读。
- `liberal_arts`：文科。覆盖语文、拼音、道法、历史、地理等文字理解类题目。
- `science`：理科。覆盖数学、科学、物理、化学等计算、推理和步骤类题目。

接口：

```text
POST /v1/homework/parse?subject=general
POST /v1/homework/parse?subject=english
POST /v1/homework/parse?subject=liberal_arts
POST /v1/homework/parse?subject=science
```

重新解题：

```text
POST /v1/homework/parse?subject=science&force=true
```

## JSON v4 正式字段

后端当前返回结构：

- `schema_version`
- `subject`
- `question_meaning_zh`
- `question_blocks`
- `answer_items`
- `student_answer_reviews`
- `solution_steps`
- `explanation_zh`
- `learning_points`
- `uncertainty`

不再作为正式接口输出：

- `question_instruction`
- `answer_lines`
- `read_units`
- `reference_answer`
- `key_vocabulary`
- `speak_units`

## 字段关系

- `question_blocks[].block_id` 是题目块主键。
- `answer_items[].block_id` 必须指向题目块。
- `student_answer_reviews[].block_id` 必须指向题目块。
- `student_answer_reviews[].answer_id` 可指向对应 `answer_items[].answer_id`。
- `solution_steps[].block_id` 必须指向题目块。
- `learning_points[].block_id` 可为空；为空表示全局知识点。

## 展示顺序

前端结果页当前顺序：

1. 题目原图。
2. 不确定性提示。
3. 批改总览。
4. 题目理解。
5. 按 `question_blocks` 展示逐题报告。
6. 全局讲解 / 总结。
7. 知识点。

逐题报告内：

1. 题块标题。
2. 必要题面辅助内容（按学科过滤）。
3. 参考答案。
4. 学生答案短批改。
5. 题解。

## 关键跨端约定

- `answer_items.plain_text` 只放最终答案或必须填写的关键结果，不放大段题解。
- 逐题推理、计算、选项排除、错因分析放到同 `block_id` 的 `solution_steps`。
- 如果同一 `question_block` 内有多条答案，前端按题号将对应 `solution_steps` 就近插到该答案后面；无法匹配题号的题解才放在题卡末尾。
- `explanation_zh` 只放全局总结，不堆逐题题解。
- `science` 和 `general` 默认不展开 `content_items`，避免题干、选项重复铺满。
- `english` 展示题目要求、例句、场景、短文、词库、选项并支持朗读。
- `liberal_arts` 展示材料、对话、图中文字等有阅读价值的题面内容。
- 数学公式优先使用 Unicode / 纯文本；前端会清洗常见 LaTeX 命令。
- 前端逐题题卡使用中性浅灰分层、左侧灰色分隔条和标题灰底，提升连续题目之间的视觉分割；不使用高饱和亮色，以免干扰答案和批改颜色。

## 后端配置文件优先级

- 通用配置：`backend/config.env`（可提交）。
- 本地覆盖：`backend/.env`（同 key 优先级高于 `config.env`，不提交 Git）。
- 进程环境变量优先级最高。
- `backend/start_backend.sh` 启动顺序：先加载 `config.env`，再加载 `.env` 覆盖。

## 本地运行产物

不提交 Git：

- `logs/`
- `backend/logs/`
- `backend/job/`
- `frontend/**/build/`
- `frontend/.gradle/`

## 远端后端部署

远端主机：

```text
root@tx
```

远端目录：

```text
/opt/homework/backend
```

服务：

```text
homework-backend.service
```

发布后需要重启服务并检查 `active (running)`。

## LLM Remote 图片触发规则

当在项目根目录通过 llm remote 交互，且用户输入包含图片文件（本地路径或上传图片）时：

1. 直接触发 skills 链路，不要求先启动本项目后端服务。
2. 优先使用已安装 OCR / 文档解析相关 skills：
   - `ocr-document-processor`
   - `paddleocr-text-recognition`
   - `paddleocr-doc-parsing`
   - `discord-homework-auto`（Discord 场景优先）
3. 解析目标按当前所选学科输出结构化结果；未指定时按通用作业解析。
4. 看图填空类题目默认按编号提取答案，并尽量生成完整答案行。
5. 仅当用户明确要求“走后端接口联调”时，才调用 `backend` API。

Discord 场景推荐命令：

```bash
python .agents/skills/discord-homework-auto/scripts/discord_homework_parse_fill.py --image "<IMAGE_PATH>"
```
