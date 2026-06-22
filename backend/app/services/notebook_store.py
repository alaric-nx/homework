from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

from app.core.errors import AppError

CollectionType = Literal["wrong", "watched"]


class NotebookStore:
    def __init__(
        self,
        sqlite_path: str | Path,
        *,
        data_dir: str | Path,
        token_ttl_sec: int = 2_592_000,
    ) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.data_dir = Path(data_dir)
        self.token_ttl_sec = token_ttl_sec
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    phone TEXT UNIQUE,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_login_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tenant_type TEXT NOT NULL DEFAULT 'family',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tenant_members (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(tenant_id, user_id),
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                );

                CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    nickname TEXT,
                    grade TEXT,
                    school TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    deleted_at INTEGER,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                );
                CREATE INDEX IF NOT EXISTS idx_students_tenant
                    ON students(tenant_id, deleted_at);

                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    storage_provider TEXT NOT NULL DEFAULT 'local',
                    bucket TEXT,
                    storage_key TEXT NOT NULL,
                    content_type TEXT,
                    size_bytes INTEGER,
                    sha256 TEXT,
                    width INTEGER,
                    height INTEGER,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    deleted_at INTEGER,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                );
                CREATE INDEX IF NOT EXISTS idx_assets_tenant_owner
                    ON assets(tenant_id, owner_type, owner_id);

                CREATE TABLE IF NOT EXISTS parse_tasks (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    created_by_user_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model TEXT,
                    image_hash TEXT,
                    original_asset_id TEXT,
                    result_json TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    deleted_at INTEGER,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                    FOREIGN KEY (original_asset_id) REFERENCES assets(id)
                );
                CREATE INDEX IF NOT EXISTS idx_parse_tasks_student
                    ON parse_tasks(tenant_id, student_id, created_at);

                CREATE TABLE IF NOT EXISTS task_blocks (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    source_block_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    question_text TEXT,
                    answer_text TEXT,
                    solution_text TEXT,
                    bbox_json TEXT,
                    crop_asset_id TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    deleted_at INTEGER,
                    UNIQUE(tenant_id, student_id, task_id, source_block_id),
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (task_id) REFERENCES parse_tasks(id),
                    FOREIGN KEY (crop_asset_id) REFERENCES assets(id)
                );
                CREATE INDEX IF NOT EXISTS idx_task_blocks_student
                    ON task_blocks(tenant_id, student_id, task_id);

                CREATE TABLE IF NOT EXISTS question_collections (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    task_block_id TEXT NOT NULL,
                    collection_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    reason TEXT NOT NULL DEFAULT 'manual',
                    note TEXT,
                    created_by_user_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    deleted_at INTEGER,
                    UNIQUE(tenant_id, student_id, task_block_id, collection_type),
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (task_block_id) REFERENCES task_blocks(id),
                    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_question_collections_list
                    ON question_collections(tenant_id, student_id, collection_type, deleted_at, updated_at);
                """
            )
            user_columns = _table_columns(conn, "users")
            if "username" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
                    ON users(username)
                    WHERE username IS NOT NULL
                """
            )

    def register_user(
        self,
        *,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        username = username.strip()
        if not username:
            raise AppError("INVALID_REQUEST", "username is required.")
        if len(password) < 6:
            raise AppError("INVALID_REQUEST", "password must be at least 6 characters.")

        now = _now()
        user_id = _new_id("usr")
        tenant_id = _new_id("ten")
        member_id = _new_id("mem")
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users(id, username, password_hash, display_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, username, _hash_password(password), username, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO tenants(id, name, tenant_type, created_at, updated_at)
                    VALUES (?, ?, 'family', ?, ?)
                    """,
                    (tenant_id, f"{username}的家庭", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO tenant_members(id, tenant_id, user_id, role, created_at, updated_at)
                    VALUES (?, ?, ?, 'owner', ?, ?)
                    """,
                    (member_id, tenant_id, user_id, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise AppError("CONFLICT", "user already exists.") from exc

        token = self._create_token(user_id=user_id, tenant_id=tenant_id)
        return {"token": token, "user": self._get_user(user_id), "tenant": self._get_tenant(tenant_id)}

    def login(self, *, account: str, password: str) -> dict[str, Any]:
        account = account.strip()
        if not account:
            raise AppError("INVALID_REQUEST", "account is required.")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM users
                WHERE username = ? AND status = 'active'
                """,
                (account,),
            ).fetchone()
            if row is None or not _verify_password(password, row["password_hash"]):
                raise AppError("UNAUTHORIZED", "invalid account or password.")
            member = conn.execute(
                """
                SELECT tenant_id FROM tenant_members
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            if member is None:
                raise AppError("FORBIDDEN", "user has no tenant.")
            now = _now()
            conn.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?", (now, now, row["id"]))
            tenant_id = member["tenant_id"]
        token = self._create_token(user_id=row["id"], tenant_id=tenant_id)
        return {"token": token, "user": self._get_user(row["id"]), "tenant": self._get_tenant(tenant_id)}

    def authenticate(self, token: str) -> dict[str, Any]:
        token = token.strip()
        if not token:
            raise AppError("UNAUTHORIZED", "missing bearer token.")
        token_hash = _hash_token(token)
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM auth_tokens
                WHERE token_hash = ? AND expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
            if row is None:
                raise AppError("UNAUTHORIZED", "invalid or expired token.")
            return {
                "user_id": row["user_id"],
                "tenant_id": row["tenant_id"],
                "user": self._get_user(row["user_id"], conn=conn),
                "tenant": self._get_tenant(row["tenant_id"], conn=conn),
            }

    def create_student(
        self,
        *,
        tenant_id: str,
        name: str,
        nickname: str | None = None,
        grade: str | None = None,
        school: str | None = None,
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise AppError("INVALID_REQUEST", "name is required.")
        now = _now()
        student_id = _new_id("stu")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO students(id, tenant_id, name, nickname, grade, school, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, tenant_id, name, _clean(nickname), _clean(grade), _clean(school), now, now),
            )
            return self._get_student(student_id, conn=conn)

    def list_students(self, *, tenant_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM students
                WHERE tenant_id = ? AND deleted_at IS NULL
                ORDER BY created_at ASC
                """,
                (tenant_id,),
            ).fetchall()
            return [_row_dict(row) for row in rows]

    def update_student(
        self,
        *,
        tenant_id: str,
        student_id: str,
        name: str,
        nickname: str | None = None,
        grade: str | None = None,
        school: str | None = None,
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise AppError("INVALID_REQUEST", "name is required.")
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM students
                WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL
                """,
                (student_id, tenant_id),
            ).fetchone()
            if row is None:
                raise AppError("NOT_FOUND", "student not found.")
            conn.execute(
                """
                UPDATE students
                SET name = ?, nickname = ?, grade = ?, school = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL
                """,
                (
                    name,
                    _clean(nickname),
                    _clean(grade),
                    _clean(school),
                    now,
                    student_id,
                    tenant_id,
                ),
            )
            return self._get_student(student_id, conn=conn)

    def delete_student(self, *, tenant_id: str, student_id: str) -> None:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM students
                WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL
                """,
                (student_id, tenant_id),
            ).fetchone()
            if row is None:
                raise AppError("NOT_FOUND", "student not found.")
            conn.execute(
                """
                UPDATE students
                SET status = 'deleted', deleted_at = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL
                """,
                (now, now, student_id, tenant_id),
            )

    def create_parse_task_stub(
        self,
        *,
        tenant_id: str,
        student_id: str,
        user_id: str,
        subject: str,
        task_id: str | None = None,
        status: str = "completed",
        original_asset_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_student(tenant_id=tenant_id, student_id=student_id)
        if original_asset_id:
            self._ensure_asset(tenant_id=tenant_id, asset_id=original_asset_id)
        now = _now()
        task_id = (task_id or "").strip() or _new_id("task")
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM parse_tasks WHERE id = ? AND tenant_id = ? AND student_id = ?",
                (task_id, tenant_id, student_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE parse_tasks
                    SET subject = ?, status = ?, original_asset_id = COALESCE(?, original_asset_id),
                        result_json = ?, updated_at = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (
                        subject,
                        status,
                        _clean(original_asset_id),
                        json.dumps(result or {}, ensure_ascii=False),
                        now,
                        now if status == "completed" else None,
                        task_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO parse_tasks(
                        id, tenant_id, student_id, created_by_user_id, subject, status,
                        original_asset_id, result_json, created_at, updated_at, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        tenant_id,
                        student_id,
                        user_id,
                        subject,
                        status,
                        _clean(original_asset_id),
                        json.dumps(result or {}, ensure_ascii=False),
                        now,
                        now,
                        now if status == "completed" else None,
                    ),
                )
            return self._get_parse_task(task_id, conn=conn)

    def create_asset(
        self,
        *,
        tenant_id: str,
        owner_type: str,
        owner_id: str,
        asset_type: str,
        content_type: str | None,
        data: bytes,
    ) -> dict[str, Any]:
        owner_type = owner_type.strip()
        owner_id = owner_id.strip()
        asset_type = asset_type.strip()
        if not owner_type or not owner_id or not asset_type:
            raise AppError("INVALID_REQUEST", "owner_type, owner_id and asset_type are required.")
        if not data:
            raise AppError("INVALID_REQUEST", "asset body is empty.")
        now = _now()
        asset_id = _new_id("ast")
        extension = _asset_extension(content_type)
        storage_key = f"objects/{asset_id}{extension}"
        path = self.data_dir / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        sha256 = hashlib.sha256(data).hexdigest()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO assets(
                    id, tenant_id, owner_type, owner_id, asset_type, storage_provider,
                    storage_key, content_type, size_bytes, sha256, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'local', ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    tenant_id,
                    owner_type,
                    owner_id,
                    asset_type,
                    storage_key,
                    _clean(content_type) or "application/octet-stream",
                    len(data),
                    sha256,
                    now,
                    now,
                ),
            )
            return self._get_asset(asset_id, conn=conn)

    def get_asset_file(self, *, tenant_id: str, asset_id: str) -> tuple[Path, str]:
        with self._connect() as conn:
            asset = self._get_asset(asset_id, conn=conn)
        if asset["tenant_id"] != tenant_id:
            raise AppError("NOT_FOUND", "asset not found.")
        path = self.data_dir / asset["storage_key"]
        if not path.exists() or not path.is_file():
            raise AppError("NOT_FOUND", "asset file not found.")
        return path, asset.get("content_type") or "application/octet-stream"

    def create_task_block(
        self,
        *,
        tenant_id: str,
        student_id: str,
        task_id: str,
        source_block_id: str,
        title: str,
        question_text: str | None = None,
        answer_text: str | None = None,
        solution_text: str | None = None,
        bbox: dict[str, Any] | None = None,
        crop_asset_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_student(tenant_id=tenant_id, student_id=student_id)
        self._ensure_task(tenant_id=tenant_id, student_id=student_id, task_id=task_id)
        now = _now()
        block_id = _new_id("blk")
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO task_blocks(
                        id, tenant_id, student_id, task_id, source_block_id, title,
                        question_text, answer_text, solution_text, bbox_json, crop_asset_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        block_id,
                        tenant_id,
                        student_id,
                        task_id,
                        source_block_id.strip(),
                        title.strip(),
                        _clean(question_text),
                        _clean(answer_text),
                        _clean(solution_text),
                        json.dumps(bbox, ensure_ascii=False) if bbox else None,
                        _clean(crop_asset_id),
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                row = conn.execute(
                    """
                    SELECT id FROM task_blocks
                    WHERE tenant_id = ? AND student_id = ? AND task_id = ? AND source_block_id = ?
                    """,
                    (tenant_id, student_id, task_id, source_block_id.strip()),
                ).fetchone()
                if row is None:
                    raise
                return self._get_task_block_detail_with_conn(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    task_block_id=row["id"],
                    conn=conn,
                )
            return self._get_task_block_detail_with_conn(
                tenant_id=tenant_id,
                student_id=student_id,
                task_block_id=block_id,
                conn=conn,
            )

    def set_collection(
        self,
        *,
        tenant_id: str,
        student_id: str,
        task_block_id: str,
        collection_type: CollectionType,
        user_id: str,
        reason: str = "manual",
        note: str | None = None,
    ) -> dict[str, Any]:
        if collection_type not in {"wrong", "watched"}:
            raise AppError("INVALID_REQUEST", "collection_type must be wrong or watched.")
        block = self._ensure_task_block(tenant_id=tenant_id, student_id=student_id, task_block_id=task_block_id)
        now = _now()
        collection_id = _new_id("col")
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM question_collections
                WHERE tenant_id = ? AND student_id = ? AND task_block_id = ? AND collection_type = ?
                """,
                (tenant_id, student_id, task_block_id, collection_type),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE question_collections
                    SET status = 'active', reason = ?, note = ?, deleted_at = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (reason, _clean(note), now, existing["id"]),
                )
                return self._get_collection(existing["id"], conn=conn)
            conn.execute(
                """
                INSERT INTO question_collections(
                    id, tenant_id, student_id, task_block_id, collection_type,
                    reason, note, created_by_user_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collection_id,
                    tenant_id,
                    student_id,
                    block["id"],
                    collection_type,
                    reason,
                    _clean(note),
                    user_id,
                    now,
                    now,
                ),
            )
            return self._get_collection(collection_id, conn=conn)

    def unset_collection(
        self,
        *,
        tenant_id: str,
        student_id: str,
        task_block_id: str,
        collection_type: CollectionType,
    ) -> None:
        self._ensure_task_block(tenant_id=tenant_id, student_id=student_id, task_block_id=task_block_id)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE question_collections
                SET status = 'archived', deleted_at = ?, updated_at = ?
                WHERE tenant_id = ? AND student_id = ? AND task_block_id = ? AND collection_type = ?
                """,
                (now, now, tenant_id, student_id, task_block_id, collection_type),
            )

    def list_collections(
        self,
        *,
        tenant_id: str,
        student_id: str,
        collection_type: CollectionType,
    ) -> list[dict[str, Any]]:
        self._ensure_student(tenant_id=tenant_id, student_id=student_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    qc.*,
                    pt.subject,
                    pt.original_asset_id,
                    tb.title,
                    tb.question_text,
                    tb.answer_text,
                    tb.solution_text,
                    tb.bbox_json,
                    tb.crop_asset_id,
                    tb.task_id,
                    tb.source_block_id
                FROM question_collections qc
                JOIN task_blocks tb ON tb.id = qc.task_block_id
                LEFT JOIN parse_tasks pt ON pt.id = tb.task_id
                WHERE qc.tenant_id = ?
                  AND qc.student_id = ?
                  AND qc.collection_type = ?
                  AND qc.deleted_at IS NULL
                ORDER BY qc.updated_at DESC
                """,
                (tenant_id, student_id, collection_type),
            ).fetchall()
        return [_collection_row(row) for row in rows]

    def get_task_block_detail(
        self,
        *,
        tenant_id: str,
        student_id: str,
        task_block_id: str,
    ) -> dict[str, Any]:
        self._ensure_student(tenant_id=tenant_id, student_id=student_id)
        with self._connect() as conn:
            return self._get_task_block_detail_with_conn(
                tenant_id=tenant_id,
                student_id=student_id,
                task_block_id=task_block_id,
                conn=conn,
            )

    def _get_task_block_detail_with_conn(
        self,
        *,
        tenant_id: str,
        student_id: str,
        task_block_id: str,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        block = self._get_task_block(task_block_id, conn=conn)
        rows = conn.execute(
            """
            SELECT collection_type FROM question_collections
            WHERE tenant_id = ?
              AND student_id = ?
              AND task_block_id = ?
              AND deleted_at IS NULL
            """,
            (tenant_id, student_id, task_block_id),
        ).fetchall()
        collection_types = {row["collection_type"] for row in rows}
        block["is_wrong_collected"] = "wrong" in collection_types
        block["is_watched"] = "watched" in collection_types
        return block

    def _create_token(self, *, user_id: str, tenant_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auth_tokens(token_hash, user_id, tenant_id, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (_hash_token(token), user_id, tenant_id, now + self.token_ttl_sec, now),
            )
        return token

    def _get_user(self, user_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_conn = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute(
                "SELECT id, username, display_name, status, created_at, updated_at, last_login_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise AppError("NOT_FOUND", "user not found.")
            return _row_dict(row)
        finally:
            if owns_conn:
                conn.close()

    def _get_tenant(self, tenant_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_conn = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
            if row is None:
                raise AppError("NOT_FOUND", "tenant not found.")
            return _row_dict(row)
        finally:
            if owns_conn:
                conn.close()

    def _get_student(self, student_id: str, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_conn = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM students WHERE id = ? AND deleted_at IS NULL",
                (student_id,),
            ).fetchone()
            if row is None:
                raise AppError("NOT_FOUND", "student not found.")
            return _row_dict(row)
        finally:
            if owns_conn:
                conn.close()

    def _get_parse_task(self, task_id: str, *, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM parse_tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "task not found.")
        return _row_dict(row)

    def _get_task_block(self, task_block_id: str, *, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT tb.*, pt.subject, pt.original_asset_id
            FROM task_blocks tb
            LEFT JOIN parse_tasks pt ON pt.id = tb.task_id
            WHERE tb.id = ? AND tb.deleted_at IS NULL
            """,
            (task_block_id,),
        ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "task block not found.")
        data = _row_dict(row)
        data["bbox"] = json.loads(data["bbox_json"]) if data.get("bbox_json") else None
        return data

    def _get_asset(self, asset_id: str, *, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM assets WHERE id = ? AND deleted_at IS NULL",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "asset not found.")
        return _row_dict(row)

    def _get_collection(self, collection_id: str, *, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM question_collections WHERE id = ?", (collection_id,)).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "collection not found.")
        return _row_dict(row)

    def _ensure_student(self, *, tenant_id: str, student_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM students WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL",
                (student_id, tenant_id),
            ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "student not found.")

    def _ensure_task(self, *, tenant_id: str, student_id: str, task_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM parse_tasks WHERE id = ? AND tenant_id = ? AND student_id = ? AND deleted_at IS NULL",
                (task_id, tenant_id, student_id),
            ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "task not found.")

    def _ensure_asset(self, *, tenant_id: str, asset_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM assets WHERE id = ? AND tenant_id = ? AND deleted_at IS NULL",
                (asset_id, tenant_id),
            ).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", "asset not found.")

    def _ensure_task_block(self, *, tenant_id: str, student_id: str, task_block_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_blocks
                WHERE id = ? AND tenant_id = ? AND student_id = ? AND deleted_at IS NULL
                """,
                (task_block_id, tenant_id, student_id),
            ).fetchone()
            if row is None:
                raise AppError("NOT_FOUND", "task block not found.")
            return _row_dict(row)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def _now() -> int:
    return int(time.time())


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _asset_extension(content_type: str | None) -> str:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(normalized, ".bin")


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_raw),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _collection_row(row: sqlite3.Row) -> dict[str, Any]:
    data = _row_dict(row)
    block = {
        "id": data.pop("task_block_id"),
        "task_id": data.pop("task_id"),
        "source_block_id": data.pop("source_block_id"),
        "subject": data.pop("subject", None),
        "original_asset_id": data.pop("original_asset_id", None),
        "title": data.pop("title"),
        "question_text": data.pop("question_text"),
        "answer_text": data.pop("answer_text"),
        "solution_text": data.pop("solution_text"),
        "bbox": json.loads(data.pop("bbox_json")) if data.get("bbox_json") else None,
        "crop_asset_id": data.pop("crop_asset_id"),
    }
    data["task_block"] = block
    return data
