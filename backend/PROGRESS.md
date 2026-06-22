# PROGRESS.md (backend)

## 最近更新

- 时间：2026-06-22
- 更新类型：文档收敛
- 摘要：清理当前阶段过宽项：头像资产不列入题集基础范围；现有解析缓存由 `TaskStore/job_dir` 保持兼容，notebook 落库并行存在。

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：补齐题块裁剪图资产绑定接口 `PATCH /v1/task-blocks/{id}/crop`，创建题块时校验裁剪资产归属；后端测试 25 个通过。

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：补齐本地资产上传/下载接口，解析成功后可绑定原图 `original_asset_id` 到 notebook task；后端测试 25 个通过。

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：补齐孩子更新与软删除接口，集合列表返回题块学科供前端筛选；后端测试 24 个通过。

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：账号体系收敛为用户名 + 密码，token 默认有效期改为 10 年；`create_task_block` 返回错题/关注状态，后端测试 24 个通过。

- 时间：2026-06-22
- 更新类型：阶段完成
- 摘要：完成错题集后端第一批代码：SQLite schema、账号注册登录、家庭租户、孩子创建/列表、任务占位、题块、错题/关注集合接口；题目切图仅预留 `bbox_json` 和 `crop_asset_id`，后端测试 24 个通过。

- 时间：2026-06-22
- 更新类型：开始执行
- 摘要：切换到新分支 `v4-notebook`，重写后端文档为错题集主线，移除旧的 JSON v4 / 作业解析阶段叙述，准备开始 SQLite、账户、租户和错题集实现。

## 进度记录

### 2026-06-22

完成内容：

- 创建并切换到 `v4-notebook` 分支。
- 重写根文档，改为错题集、多租户、SQLite、资产存储和迁移预留主线。
- 重写后端文档，删除旧解析阶段说明，保留错题集基础设计。
- 重建后端计划，新增 SQLite、账户租户、孩子管理、资产表、任务落库和错题集任务。
- 重建后端进度，记录当前分支切换和文档收敛。
- 新增 `NotebookStore`：
  - 初始化 SQLite schema
  - 开启 WAL、foreign keys、busy timeout
  - 使用字符串 ID，预留 PostgreSQL 迁移
- 新增账号与租户能力：
  - 用户名 + 密码注册
  - 用户名 + 密码登录
  - 当前用户
  - 注册时自动创建家庭租户和 owner 成员
  - Bearer token 默认有效期 10 年
- 新增孩子能力：
  - 创建孩子
  - 当前家庭孩子列表
  - 编辑孩子
  - 软删除孩子
- 新增资产能力：
  - `POST /v1/assets` 上传本地资产
  - `GET /v1/assets/{asset_id}/content` 鉴权下载资产文件
  - 本地保存到 `data/objects/`，数据库保存相对 `storage_key`
  - notebook task 支持绑定 `original_asset_id`
  - task block 支持绑定 `crop_asset_id`
  - `PATCH /v1/task-blocks/{id}/crop` 可给已有题块补裁剪图资产
- 新增题块集合能力：
  - `task_blocks`
  - `question_collections`
  - 错题集合加入 / 移出
  - 关注集合加入 / 取消
  - 集合列表
  - 题块详情返回 `is_wrong_collected` 和 `is_watched`
  - 创建题块接口同步返回 `is_wrong_collected` 和 `is_watched`
  - 集合列表返回题块所属学科，支持客户端筛选
- 题目切图本轮只预留字段：
  - `bbox_json`
  - `crop_asset_id`
- 新增 notebook API 回归测试，后端验证通过：`pytest`，共 25 个测试。

当前进行中：

- 无。

阻塞项：

- 无。

下一步：

- 后续如要做自动切图算法，直接生成裁剪图资产并调用 `PATCH /v1/task-blocks/{id}/crop` 绑定。
