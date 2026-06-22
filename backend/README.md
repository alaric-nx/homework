# Homework Notebook Backend

## Scope

This branch focuses on:

- user login and registration
- family tenants
- children under a family
- SQLite-backed metadata storage
- local file asset storage
- parse task persistence
- wrong-question collection
- watched-question collection

## Implemented So Far

- SQLite schema initialization through `NotebookStore`
- username/password registration and login
- bearer-token session storage, default token TTL 10 years
- family tenant creation on registration
- student creation, listing, update, and soft delete
- notebook task placeholder persistence
- task block persistence
- wrong / watched question collections
- reserved crop fields: `bbox_json`, `crop_asset_id`

## Current API

```text
POST /v1/auth/register
POST /v1/auth/login
GET  /v1/auth/me

GET  /v1/tenants/me

POST /v1/students
GET  /v1/students
PATCH /v1/students/{id}
DELETE /v1/students/{id}

POST /v1/notebook/tasks
POST /v1/task-blocks
GET  /v1/task-blocks/{id}

POST   /v1/task-blocks/{id}/collections/wrong
DELETE /v1/task-blocks/{id}/collections/wrong
POST   /v1/task-blocks/{id}/collections/watched
DELETE /v1/task-blocks/{id}/collections/watched
GET    /v1/question-collections?type=wrong|watched&student_id=<id>
```

Auth payloads:

```json
{ "username": "parent", "password": "secret123" }
```

Login uses:

```json
{ "account": "parent", "password": "secret123" }
```

## Storage Policy

- Database: SQLite first
- Images: local filesystem first
- Database stores metadata only
- Paths are stored as relative `storage_key`, not absolute filesystem paths
- Directory names do not encode dates; dates live in database columns
- Storage layer must be replaceable with OSS later

## Migration Goals

- SQLite schema should stay PostgreSQL-friendly
- asset table should decouple business rows from storage backend
- all tenant-scoped tables must include `tenant_id`
- all child-scoped rows must include `student_id`

## Local Layout

```text
/opt/homework/data/
  homework.sqlite3
  objects/
  tmp/
  backups/
```
