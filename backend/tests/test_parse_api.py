from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_parse_invalid_request() -> None:
    client = TestClient(app)
    resp = client.post("/v1/homework/parse")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "INVALID_REQUEST"


def test_parse_fill_endpoint_removed() -> None:
    client = TestClient(app)
    resp = client.post("/v1/homework/parse-fill")
    assert resp.status_code == 404
