# AGENTS.md (backend)

## 目录职责

本目录负责 Python 后端服务、数据库、资产存储和错题集业务：

- 登录注册与家庭租户。
- 孩子管理与成员权限。
- SQLite 数据库初始化与迁移预留。
- 统一资产表与文件存储抽象。
- 拍题任务落库。
- 错题集与关注集。
- 后续为 OSS 和 PostgreSQL 迁移预留结构。

## 技术约束

- 语言：Python
- 数据库：SQLite 起步
- 存储：本地文件系统起步，后续可迁移 OSS
- 访问控制：以 `tenant_id` 为边界，以 `student_id` 区分孩子
- 图片目录：不按日期分层，日期只存数据库字段

## 设计原则

- 业务表不存绝对磁盘路径，只存 `storage_key` 或资产引用。
- 图片、头像、裁剪图统一进 `assets` 表。
- 任务、错题集和关注集都必须带 `tenant_id`。
- 错题以独立小题为单位，不以整张图片为单位。
- 表结构尽量使用 PostgreSQL 兼容的通用字段与约束。

## 建议接口

```text
POST /v1/auth/register
POST /v1/auth/login
GET  /v1/auth/me

GET  /v1/tenants/me

POST /v1/students
GET  /v1/students

POST /v1/tasks
GET  /v1/tasks/{task_id}

POST /v1/task-blocks/{id}/collections/wrong
DELETE /v1/task-blocks/{id}/collections/wrong
POST /v1/task-blocks/{id}/collections/watched
DELETE /v1/task-blocks/{id}/collections/watched
GET  /v1/question-collections?type=wrong
GET  /v1/question-collections?type=watched
```

账号接口约定：

- `POST /v1/auth/register` 请求体只包含 `username` 与 `password`。
- `POST /v1/auth/login` 使用 `account` 与 `password`，其中 `account` 为用户名。
- 后端不要求手机号、邮箱、验证码或家庭名称。
- 注册成功自动创建家庭租户和 owner 成员。
- Bearer token 默认有效期为 10 年，配置项为 `HW_AUTH_TOKEN_TTL_SEC`。

## 推荐表

- `users`
- `tenants`
- `tenant_members`
- `students`
- `assets`
- `parse_tasks`
- `task_blocks`
- `question_collections`

当前只做两个集合：错题集和关注集。

## 题块集合

- `question_collections.collection_type` 只允许 `wrong`、`watched`。
- 错题集可以自动加入，也可以手动加入 / 移出。
- 关注集只手动加入 / 取消。
- 同一个 `task_block` 可以同时在两个集合里。
- 软删除使用 `deleted_at`，再次加入时恢复原记录。

## 题目切图预留

- `task_blocks` 预留 `bbox_json` 与 `crop_asset_id`。
- 当前阶段不实现裁剪算法。
- 后续裁剪图作为 `assets` 记录保存，`task_blocks.crop_asset_id` 指向该资产。

## 存储约定

- 本地目录建议：

```text
/opt/homework/data/
  homework.sqlite3
  objects/
  tmp/
  backups/
```

- `assets.storage_key` 只保存相对 key，不保存绝对路径。
- 后续迁 OSS 时只改存储适配层和 `storage_provider`。
