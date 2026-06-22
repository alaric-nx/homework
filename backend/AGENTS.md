# AGENTS.md (backend)

## 目录职责

本目录负责 Python 后端服务与模型编排：

- 接收前端上传的完整题图。
- 通过 OpenAI 兼容接口调用视觉大模型。
- 按 `subject` 构建多学科练习题解析提示词。
- 校验并归一化固定 JSON v4 输出。
- 为前端提供题目块、题面内容、答案项、学生答案批改、逐题题解、知识点和不确定性标记。

## 技术约束

- 语言：Python
- API 风格：异步提交 + 轮询
- 模型调用：通用 OpenAI 兼容接口
- 学科：`general`、`english`、`liberal_arts`、`science`
- 测试：模型调用在测试中 mock 或通过配置关闭外部依赖

## API

异步提交：

```text
POST /v1/homework/parse?subject=<general|english|liberal_arts|science>&model=<可选模型名>&force=<可选>
Content-Type: image/jpeg
Body: raw JPEG bytes
```

轮询：

```text
GET /v1/homework/tasks/{task_id}
```

约束：

- 未传 `subject` 时默认为 `general`。
- 非法 `subject` 返回 `INVALID_REQUEST`。
- 强制重解使用 `force=true`。
- 缓存复用必须区分 `subject`，同图不同学科不复用同一结果。
- 后端必须校验 `result.subject == request.subject`。

## JSON v4 当前正式契约

顶层字段只允许：

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

不再输出以下旧字段作为正式接口：

- `question_instruction`
- `answer_lines`
- `read_units`
- `reference_answer`
- `key_vocabulary`
- `speak_units`

## 字段语义

`question_blocks[]` 表示题目块：

- `block_id`：稳定题块 ID，如 `q1`、`q2`。
- `order`：整张图内的题块阅读顺序。
- `title`：题块标题。
- `question_meaning_zh`：该题块要求做什么。
- `content_items`：题面可见内容，包括题目要求、例句、场景、短文、对话、词库、选项、图中文字。

`content_items[]` 规则：

- 按最小可展示 / 可朗读单元拆分。
- 例句、场景、短文或材料有多少个独立可见行，就输出多少个独立 `content_item`。
- 不把多行内容塞进一个 `text`，也不只用空格连接成一段。
- 同组例句或同段材料使用相同 `group_id`。
- `speak_text` 放适合 Android TTS 直接朗读的文本；不适合朗读时 `speakable=false`。

`answer_items[]` 是参考答案区唯一数据源：

- `answer_id`：稳定答案 ID。
- `block_id`：必须对应 `question_blocks[].block_id`。
- `order`：所属题块内答案顺序。
- `number`：题号，可为空。
- `answer_type`：题型。
- `plain_text`：只放最终答案或必须填写的关键结果，不放“第X题解答”、大段解析、错因或步骤。
- `speak_text`：答案 TTS 读法，数学可用自然语言读法。
- `display`：前端渲染结构，包含 `mode`、`format`、`latex`、`preserve_newlines`、`runs`。

`display.runs[].role` 只能是：

- `given`
- `answer`
- `connector`
- `correction`
- `student_answer`

`student_answer_reviews[]` 用于批改学生已写答案：

- 只有图片里存在学生手写 / 已填写答案时才输出。
- `status` 只能是 `correct`、`incorrect`、`partially_correct`、`unanswered`、`unclear`、`not_applicable`。
- `feedback_zh` 只放短提示。
- 错题详细分析优先放到对应 `block_id` 的 `solution_steps`。

`solution_steps[]` 是逐题题解：

- 每个需要解释、推理、计算或排除选项的题目，都要输出对应 `solution_steps`。
- `block_id` 必须指向对应题目块。
- 同一题步骤按 `number` 顺序排列。
- `answer_items` 回答“答案是什么”，`solution_steps` 回答“为什么 / 怎么算 / 错在哪里”。
- 选择题选项排除、概率题判断理由、几何题公式推导都属于 `solution_steps`。

`explanation_zh` 只放全局总结：

- 放整体提醒、共性错因、整体学习建议。
- 不堆放逐题题解。
- 逐题内容必须回到 `solution_steps`。

`learning_points[]` 表示知识点：

- `block_id` 可为空；为空表示全局知识点。
- `category` 只能是 `word`、`concept`、`formula`、`unit`、`method`、`other`。
- `label` 可放自由细分类，如 `grammar`、`phrase`、`pinyin`、`phonics`。

## 学科规则

`general`：

- 先识别题型，再用保守方式输出答案、题解、讲解和知识点。
- 不强行套英语词汇或理科公式。

`english`：

- 保留完整答案项、题目要求、例句 / 场景 / 短文材料、词义、IPA 和答案词义覆盖。
- `learning_points(category=word)` 覆盖答案中的关键英文词。
- 题目要求、例句、场景、短文、词库和选项尽量进入 `content_items`。

`liberal_arts`：

- 覆盖语文、拼音、道法、历史、地理等。
- 阅读理解 / 材料题必须说明答题依据。
- 古诗文 / 文言文原文放 `content_items.text`，现代汉语翻译放 `meaning_zh`。
- 作文 / 开放题给参考答案和审题提示，不编造唯一标准答案。

`science`：

- 覆盖数学、科学、物理、化学等。
- `answer_items` 只放最终答案或必须填写的关键结果，答案带单位。
- `solution_steps` 清楚展示列式、推理或计算过程。
- 常见计算、方程、单位换算优先用 `display.format=plain_math`，在 `plain_text` 和 `runs.text` 中输出 Android 可直接显示的 Unicode / 纯文本公式。
- 不为了简单公式输出 LaTeX 源码。

## 后处理与校验

- 顶层字段必须完全匹配 JSON v4 契约。
- `question_blocks`、`answer_items` 至少 1 项。
- `answer_items`、`student_answer_reviews`、`solution_steps` 的 `block_id` 必须对应 `question_blocks`。
- `learning_points.block_id` 可为空；非空时必须对应 `question_blocks`。
- 多题块未知 `block_id` 不自动归并到第一个题块。
- `plain_text` 与 `display.runs` 不一致时，归一化保留完整 `plain_text` 并重建单段 `runs`。
- 英语链路保留最多一次词义补全；非英语链路不做英语词义强制补全。

## 部署

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

发布时同步 `backend/`，排除 `.env`、`job/`、`logs/`、`output/`、缓存目录和 `__pycache__`。

## 构建与测试

在 `backend/` 目录运行：

```bash
pytest
```

当前回归测试覆盖：

- v4 schema guard。
- JSON 归一化。
- subject mismatch。
- LLM event stream JSON 提取。
- 任务缓存 schema 与持久化。
