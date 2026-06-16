from __future__ import annotations

import json

from app.services.task_store import TASK_RESULT_SCHEMA_VERSION, TaskStore


def _task_payload(updated_at: float, schema_version: int = TASK_RESULT_SCHEMA_VERSION) -> dict:
    return {
        "schema_version": schema_version,
        "task_id": "abc",
        "status": "completed",
        "image_hash": "abc",
        "model": "test",
        "subject": "english",
        "created_at": updated_at,
        "updated_at": updated_at,
        "result": {
            "subject": "english",
            "question_meaning_zh": "补全句子。\n补全完整句子。",
            "question_instruction": {
                "text": "Complete the sentence.",
                "meaning_zh": "补全句子。",
                "confidence": 0.95,
            },
            "question_blocks": [
                {
                    "block_id": "q1",
                    "title": "第1题",
                    "question_instruction": {
                        "text": "Complete the sentence.",
                        "meaning_zh": "补全句子。",
                        "confidence": 0.95,
                    },
                    "question_meaning_zh": "补全完整句子。",
                }
            ],
            "answer_lines": [
                {
                    "block_id": "q1",
                    "number": "1",
                    "line_type": "fill_blank",
                    "plain_text": "I am a student.",
                    "segments": [{"text": "I am a student.", "role": "answer"}],
                }
            ],
            "solution_steps": [],
            "explanation_zh": "I 后面用 am。",
            "learning_points": [
                {"block_id": "q1", "term": "I", "explanation_zh": "我", "pronunciation": "/aɪ/", "category": "word"},
                {"block_id": "q1", "term": "am", "explanation_zh": "是", "pronunciation": "/æm/", "category": "word"},
                {"block_id": "q1", "term": "student", "explanation_zh": "学生", "pronunciation": "/ˈstuːdnt/", "category": "word"},
            ],
            "read_units": [
                {
                    "block_id": "q1",
                    "unit_type": "sentence",
                    "text": "I am a student.",
                    "meaning_zh": "我是一名学生。",
                }
            ],
            "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
        },
        "error_code": None,
        "error_message": None,
    }


def test_load_task_from_disk_deletes_expired_cache(tmp_path) -> None:
    store = TaskStore(timeout_sec=60, retention_sec=10, job_dir=tmp_path)
    cache_path = tmp_path / "abc.json"
    cache_path.write_text(
        json.dumps(_task_payload(updated_at=100.0), ensure_ascii=False),
        encoding="utf-8",
    )

    assert store._load_task_from_disk("abc") is None
    assert not cache_path.exists()


def test_load_task_from_disk_deletes_schema_mismatch(tmp_path) -> None:
    store = TaskStore(timeout_sec=60, retention_sec=10, job_dir=tmp_path)
    cache_path = tmp_path / "abc.json"
    cache_path.write_text(
        json.dumps(_task_payload(updated_at=100.0, schema_version=1), ensure_ascii=False),
        encoding="utf-8",
    )

    assert store._load_task_from_disk("abc") is None
    assert not cache_path.exists()
