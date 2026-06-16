from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.skills.common.response_schema_guard import ResponseSchemaGuard


def _valid_payload() -> dict:
    return {
        "subject": "english",
        "question_meaning_zh": "补全句子。\n把空格补成完整句子。",
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
                "question_meaning_zh": "把空格补成完整句子。",
            }
        ],
        "answer_lines": [
            {
                "block_id": "q1",
                "number": "1",
                "line_type": "fill_blank",
                "plain_text": "I am a student.",
                "segments": [
                    {"text": "I ", "role": "given"},
                    {"text": "am", "role": "answer"},
                    {"text": " a student.", "role": "given"},
                ],
            }
        ],
        "solution_steps": [],
        "explanation_zh": "I 后面的 be 动词用 am。",
        "learning_points": [
            {"block_id": "q1", "term": "I", "explanation_zh": "我", "pronunciation": "/aɪ/", "category": "word", "label": "vocabulary"},
            {"block_id": "q1", "term": "am", "explanation_zh": "是", "pronunciation": "/æm/", "category": "word", "label": "vocabulary"},
            {"block_id": "q1", "term": "student", "explanation_zh": "学生", "pronunciation": "/ˈstuːdnt/", "category": "word", "label": "vocabulary"}
        ],
        "read_units": [
            {
                "block_id": None,
                "unit_type": "text", "label": "sentence",
                "text": "把空格补成完整句子。",
                "meaning_zh": "把空格补成完整句子。",
            },
            {
                "block_id": "q1",
                "unit_type": "text", "label": "sentence",
                "text": "I am a student.",
                "meaning_zh": "我是一名学生。",
            },
            {"block_id": "q1", "unit_type": "word", "label": "vocabulary", "text": "I", "meaning_zh": "我"},
            {"block_id": "q1", "unit_type": "word", "label": "vocabulary", "text": "am", "meaning_zh": "是"},
            {"block_id": "q1", "unit_type": "word", "label": "vocabulary", "text": "student", "meaning_zh": "学生"},
        ],
        "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
    }


def test_validate_payload_accepts_answer_lines_v2() -> None:
    result = ResponseSchemaGuard().validate_payload(_valid_payload())

    assert result.answer_lines[0].segments[1].role == "answer"


def test_validate_payload_rejects_missing_answer_lines() -> None:
    payload = _valid_payload()
    payload.pop("answer_lines")

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_invalid_segment_role() -> None:
    payload = _valid_payload()
    payload["answer_lines"][0]["segments"][0]["role"] = "wrong"

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_unknown_block_id() -> None:
    payload = _valid_payload()
    payload["answer_lines"][0]["block_id"] = "q9"

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_unknown_step_block_id() -> None:
    payload = _valid_payload()
    payload["solution_steps"] = [
        {
            "block_id": "q9",
            "number": "1",
            "title": "步骤",
            "content_zh": "说明",
            "formula": None,
            "result": None,
        }
    ]

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)
