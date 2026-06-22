from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_notebook_store
from app.main import app
from app.services.notebook_store import NotebookStore


def _client(tmp_path):
    store = NotebookStore(
        sqlite_path=tmp_path / "homework.sqlite3",
        data_dir=tmp_path,
        token_ttl_sec=3600,
    )
    app.dependency_overrides[get_notebook_store] = lambda: store
    return TestClient(app)


def test_register_login_students_and_collections(tmp_path) -> None:
    client = _client(tmp_path)
    try:
        register_resp = client.post(
            "/v1/auth/register",
            json={
                "username": "parent",
                "password": "secret123",
            },
        )
        assert register_resp.status_code == 200
        token = register_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        me_resp = client.get("/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["tenant"]["name"] == "parent的家庭"

        login_resp = client.post(
            "/v1/auth/login",
            json={"account": "parent", "password": "secret123"},
        )
        assert login_resp.status_code == 200

        student_resp = client.post(
            "/v1/students",
            headers=headers,
            json={"name": "小明", "grade": "五年级"},
        )
        assert student_resp.status_code == 200
        student_id = student_resp.json()["id"]

        students_resp = client.get("/v1/students", headers=headers)
        assert students_resp.status_code == 200
        assert [item["id"] for item in students_resp.json()["items"]] == [student_id]

        update_student_resp = client.patch(
            f"/v1/students/{student_id}",
            headers=headers,
            json={"name": "小明明", "grade": "六年级"},
        )
        assert update_student_resp.status_code == 200
        assert update_student_resp.json()["name"] == "小明明"
        assert update_student_resp.json()["grade"] == "六年级"

        task_resp = client.post(
            "/v1/notebook/tasks",
            headers=headers,
            json={"student_id": student_id, "subject": "science", "result": {"ok": True}},
        )
        assert task_resp.status_code == 200
        task_id = task_resp.json()["id"]

        block_resp = client.post(
            "/v1/task-blocks",
            headers=headers,
            json={
                "student_id": student_id,
                "task_id": task_id,
                "source_block_id": "q1",
                "title": "第1题",
                "question_text": "1 + 1 = ?",
                "answer_text": "2",
                "solution_text": "一加一等于二。",
                "bbox": {"x": 0, "y": 0, "width": 100, "height": 80},
            },
        )
        assert block_resp.status_code == 200
        block_id = block_resp.json()["id"]
        assert block_resp.json()["bbox"]["width"] == 100

        wrong_resp = client.post(
            f"/v1/task-blocks/{block_id}/collections/wrong",
            headers=headers,
            json={"student_id": student_id, "reason": "manual"},
        )
        assert wrong_resp.status_code == 200
        assert wrong_resp.json()["collection_type"] == "wrong"

        watched_resp = client.post(
            f"/v1/task-blocks/{block_id}/collections/watched",
            headers=headers,
            json={"student_id": student_id, "note": "重点复习"},
        )
        assert watched_resp.status_code == 200
        assert watched_resp.json()["collection_type"] == "watched"

        block_detail = client.get(
            f"/v1/task-blocks/{block_id}",
            headers=headers,
            params={"student_id": student_id},
        )
        assert block_detail.status_code == 200
        assert block_detail.json()["is_wrong_collected"] is True
        assert block_detail.json()["is_watched"] is True

        wrong_list = client.get(
            "/v1/question-collections",
            headers=headers,
            params={"type": "wrong", "student_id": student_id},
        )
        assert wrong_list.status_code == 200
        assert len(wrong_list.json()["items"]) == 1
        assert wrong_list.json()["items"][0]["task_block"]["title"] == "第1题"

        delete_resp = client.delete(
            f"/v1/task-blocks/{block_id}/collections/wrong",
            headers=headers,
            params={"student_id": student_id},
        )
        assert delete_resp.status_code == 200

        wrong_list_after_delete = client.get(
            "/v1/question-collections",
            headers=headers,
            params={"type": "wrong", "student_id": student_id},
        )
        assert wrong_list_after_delete.status_code == 200
        assert wrong_list_after_delete.json()["items"] == []

        delete_student_resp = client.delete(f"/v1/students/{student_id}", headers=headers)
        assert delete_student_resp.status_code == 200

        students_after_delete = client.get("/v1/students", headers=headers)
        assert students_after_delete.status_code == 200
        assert students_after_delete.json()["items"] == []
    finally:
        app.dependency_overrides.clear()


def test_asset_upload_download_and_task_binding(tmp_path) -> None:
    client = _client(tmp_path)
    try:
        token = client.post(
            "/v1/auth/register",
            json={"username": "asset-parent", "password": "secret123"},
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        student_id = client.post(
            "/v1/students",
            headers=headers,
            json={"name": "小红"},
        ).json()["id"]

        asset_resp = client.post(
            "/v1/assets",
            headers={**headers, "Content-Type": "image/jpeg"},
            params={"owner_type": "parse_task", "owner_id": "local-task-1", "asset_type": "original_image"},
            content=b"fake-jpeg-bytes",
        )
        assert asset_resp.status_code == 200
        asset_id = asset_resp.json()["id"]
        assert asset_resp.json()["storage_key"].startswith("objects/")

        content_resp = client.get(f"/v1/assets/{asset_id}/content", headers=headers)
        assert content_resp.status_code == 200
        assert content_resp.content == b"fake-jpeg-bytes"

        task_resp = client.post(
            "/v1/notebook/tasks",
            headers=headers,
            json={
                "task_id": "local-task-1",
                "student_id": student_id,
                "subject": "english",
                "original_asset_id": asset_id,
                "result": {},
            },
        )
        assert task_resp.status_code == 200
        assert task_resp.json()["original_asset_id"] == asset_id

        block_resp = client.post(
            "/v1/task-blocks",
            headers=headers,
            json={
                "student_id": student_id,
                "task_id": "local-task-1",
                "source_block_id": "q1",
                "title": "第1题",
            },
        )
        assert block_resp.status_code == 200
        assert block_resp.json()["original_asset_id"] == asset_id
        block_id = block_resp.json()["id"]

        crop_asset_resp = client.post(
            "/v1/assets",
            headers={**headers, "Content-Type": "image/jpeg"},
            params={"owner_type": "task_block", "owner_id": block_id, "asset_type": "question_crop"},
            content=b"fake-crop-bytes",
        )
        assert crop_asset_resp.status_code == 200
        crop_asset_id = crop_asset_resp.json()["id"]

        crop_update_resp = client.patch(
            f"/v1/task-blocks/{block_id}/crop",
            headers=headers,
            json={
                "student_id": student_id,
                "crop_asset_id": crop_asset_id,
                "bbox": {"x": 1, "y": 2, "width": 30, "height": 40},
            },
        )
        assert crop_update_resp.status_code == 200
        assert crop_update_resp.json()["crop_asset_id"] == crop_asset_id
        assert crop_update_resp.json()["bbox"]["width"] == 30

        client.post(
            f"/v1/task-blocks/{block_id}/collections/watched",
            headers=headers,
            json={"student_id": student_id},
        )
        collection_resp = client.get(
            "/v1/question-collections",
            headers=headers,
            params={"type": "watched", "student_id": student_id},
        )
        assert collection_resp.status_code == 200
        task_block = collection_resp.json()["items"][0]["task_block"]
        assert task_block["subject"] == "english"
        assert task_block["original_asset_id"] == asset_id
        assert task_block["crop_asset_id"] == crop_asset_id
    finally:
        app.dependency_overrides.clear()


def test_notebook_requires_auth(tmp_path) -> None:
    client = _client(tmp_path)
    try:
        resp = client.get("/v1/students")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "UNAUTHORIZED"
    finally:
        app.dependency_overrides.clear()
