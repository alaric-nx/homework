# AGENTS.md

## 文档导航

本项目采用分层文档：

- 根文档（本文件）：项目总览、全局边界、跨端接口决策
- `frontend/AGENTS.md`：Android 前端约束、接口消费、展示规则
- `frontend/PLAN.md`：前端任务计划
- `frontend/PROGRESS.md`：前端进展记录
- `backend/AGENTS.md`：Python 后端约束、模型编排、输出 schema
- `backend/PLAN.md`：后端任务计划
- `backend/PROGRESS.md`：后端进展记录

推荐阅读顺序：

1. 先读根 `AGENTS.md`
2. 再按任务进入 `frontend/` 或 `backend/`
3. 实施前查看对应子项目的 `PLAN.md` 与 `PROGRESS.md`

## 项目介绍

本项目是一个英语练习题解析 Android 应用，帮助家长或学习者处理英语作业、练习册、考试题和基础学习题。

核心流程：

- 家长拍照或从相册导入题图。
- 前端对题图进行裁剪、排序、合并和压缩。
- 后端接收完整题图，调用视觉大模型解析题目。
- 后端返回结构化结果：
  - 图片中的英文题目要求原句
  - 题目中文理解
  - 图片中的独立题目块
  - 结构化参考答案行
  - 中文讲解
  - 重点词汇
  - 可点击发音单元
  - 不确定性标记
- 前端支持答案高亮、点击词/句发音和查看词义/句义。

## 已确定技术方案

- 前端：Kotlin 原生 Android（Jetpack Compose）
- 后端：Python
- 模型调用：通用 OpenAI 兼容接口
- 题图输入：前端完成裁剪与合并，后端接收合并后的完整题图
- 当前学科：英语
- 预留方向：语文、数学分流入口后续扩展
- TTS：Android 本地 `TextToSpeech`

## 当前阶段重点

下一阶段聚焦“答题提示词与参考答案展示 v2”：

- 提示词不再限定“小学英语”，改为通用英语练习题解析。
- 参考答案区不再以 `reference_answer` 纯文本作为主数据源。
- 新增 `answer_lines` 作为参考答案区唯一渲染数据源。
- 新增 `question_instruction` 用于展示和朗读图片中的英文题目要求原句。
- 新增 `question_blocks` 用于区分同一图片中的多个独立题目。
- 填空、补全类题目必须展示补全后的完整句/完整短语。
- `answer_lines[].block_id` 必须指向对应的 `question_blocks[].block_id`。
- `answer_lines[].segments` 用于区分题目已有内容和模型填写内容：
  - `given`：题目已有内容，前端黑色显示
  - `answer`：学生应填写、选择或生成的答案，前端红色显示
  - `connector`：连接符号，前端灰色或黑色显示
  - `correction`：改错后的正确内容，前端橙红色显示

## 返回 JSON v2（目标）

后端目标返回结构：

- `question_meaning_zh`
- `question_instruction`
- `question_blocks`
- `answer_lines`
- `explanation_zh`
- `key_vocabulary`
- `speak_units`
- `uncertainty`

不再输出 `reference_answer` 作为正式接口字段。

`answer_lines` 示例：

```json
[
  {
    "block_id": "q1",
    "number": "1",
    "line_type": "fill_blank",
    "plain_text": "I am a student.",
    "segments": [
      { "text": "I ", "role": "given" },
      { "text": "am", "role": "answer" },
      { "text": " a student.", "role": "given" }
    ]
  }
]
```

`question_instruction` 示例：

```json
{
  "text": "Complete the sentence.",
  "meaning_zh": "补全句子。",
  "confidence": 0.95
}
```

`question_blocks` 示例：

```json
[
  {
    "block_id": "q1",
    "title": "第1题",
    "question_instruction": {
      "text": "Complete the words.",
      "meaning_zh": "补全单词。",
      "confidence": 0.95
    },
    "question_meaning_zh": "根据给出的部分字母补全完整单词。"
  },
  {
    "block_id": "q2",
    "title": "第2题",
    "question_instruction": {
      "text": "Write the words in the blanks.",
      "meaning_zh": "把单词写到空格中。",
      "confidence": 0.92
    },
    "question_meaning_zh": "用上一题相关单词完成句子。"
  }
]
```

## 题型展示策略

- 填空 / 补全句子：`plain_text` 是补全后的完整句或短语；题目已有文本标为 `given`，填入部分标为 `answer`。
- 选择题：选项字母和选中内容标为 `answer`。
- 看图写词 / 短语：答案整体标为 `answer`。
- 连线 / 匹配：题目已有左右内容可标为 `given`，配对关系或选中编号标为 `answer`。
- 排序 / 连词成句：最终正确句整体标为 `answer`。
- 阅读问答 / 翻译：回答或译文整体标为 `answer`。
- 改错题：未改部分标为 `given`，订正内容标为 `correction`。
- 抄写题：照抄内容可标为 `given`，讲解中说明“照抄即可”。

## 需求清单与状态

### A. 产品与流程

- [x] 明确主流程：拍照 -> 裁剪 -> 合并 -> 上传 -> 解析 -> 展示结果 -> 点读
- [x] 明确“多图合一题”由前端完成
- [x] 明确前端为 Kotlin 原生
- [x] 定义前端交互细节（裁剪页、合并页、结果页）
- [x] 定义异常流程（上传失败、解析失败、超时重试）
- [x] 升级参考答案区为 `answer_lines` 分段高亮展示
- [x] 提取英文题目要求原句并支持发音和中文解释
- [x] 支持同一图片内多个有关联但独立的题目块分组展示

### B. 后端能力

- [x] 实现固定 JSON 输出与 schema 校验
- [x] 实现解析 API
- [x] 实现日志与错误码规范
- [x] 将输出 schema 升级为 JSON v2
- [x] 新增 `question_blocks` 并要求 `answer_lines[].block_id` 关联题目块
- [x] 优化英语练习题解析提示词
- [x] 移除正式输出中的 `reference_answer`
- [x] 支持缺失答案词义时最多额外调用一次模型补全词义
- [x] 清理过期 / 旧 schema 磁盘任务缓存

### C. 前端能力

- [x] 相机拍照与相册导入
- [x] 题图裁剪
- [x] 多段图片排序与合并
- [x] 上传前图片压缩
- [x] 异步任务队列与任务列表
- [x] 结果数据 Room 持久化
- [x] 本地 TTS 点读
- [x] 使用 `answer_lines` 渲染参考答案区
- [x] 使用 `question_blocks` 对参考答案按题目块分组展示
- [x] 支持 `given` / `answer` / `connector` / `correction` 分段配色
- [x] 支持英文题目要求原句朗读和中文解释展示

### D. 当前不做 / 后续再做

- [x] 暂不做语文 skills
- [x] 暂不做数学 skills
- [x] 暂不做后端完整性强校验
- [ ] 云端高拟真 TTS
- [ ] 精细化题型识别与自动分题

## 后端配置文件优先级

- 通用配置：`backend/config.env`（可提交）
- 本地覆盖：`backend/.env`（同 key 优先级高于 `config.env`，不提交 Git）
- 进程环境变量优先级最高
- `backend/start_backend.sh` 启动顺序：先加载 `config.env`，再加载 `.env` 覆盖

## 本地运行产物

- 日志目录不提交 Git：`logs/`、`backend/logs/`
- 后端任务缓存不提交 Git：`backend/job/`
- Android / Gradle 构建产物不提交 Git：`frontend/**/build/`、`frontend/.gradle/`

## LLM Remote 图片触发规则

当在项目根目录通过 llm remote 交互，且用户输入包含图片文件（本地路径或上传图片）时：

1. 直接触发 skills 链路，不要求先启动本项目后端服务。
2. 优先使用已安装 OCR / 文档解析相关 skills：
   - `ocr-document-processor`
   - `paddleocr-text-recognition`
   - `paddleocr-doc-parsing`
   - `discord-homework-auto`（Discord 场景优先）
3. 解析目标按英语练习题场景输出结构化结果。
4. 看图填空类题目默认按编号提取答案，并尽量生成完整答案行。
5. 仅当用户明确要求“走后端接口联调”时，才调用 `backend` API。

Discord 场景推荐命令：

```bash
python .agents/skills/discord-homework-auto/scripts/discord_homework_parse_fill.py --image "<IMAGE_PATH>"
```
