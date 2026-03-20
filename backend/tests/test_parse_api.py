from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ocr_providers_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/v1/ocr/providers")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body
    assert isinstance(body["providers"], list)
    assert len(body["providers"]) >= 1


def test_parse_with_binary_image_returns_schema_fields() -> None:
    client = TestClient(app)
    resp = client.post(
        "/v1/homework/parse?expected_type=english",
        content=b"fake-jpeg-binary",
        headers={"content-type": "image/jpeg"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for field in (
        "question_meaning_zh",
        "reference_answer",
        "explanation_zh",
        "key_vocabulary",
        "speak_units",
        "uncertainty",
    ):
        assert field in data


def test_parse_invalid_request() -> None:
    client = TestClient(app)
    resp = client.post("/v1/homework/parse")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "INVALID_REQUEST"


def test_parse_fill_invalid_request() -> None:
    client = TestClient(app)
    resp = client.post("/v1/homework/parse-fill")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "INVALID_REQUEST"
