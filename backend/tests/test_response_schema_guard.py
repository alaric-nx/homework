from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.skills.common.response_schema_guard import ResponseSchemaGuard


def _valid_payload() -> dict:
    return {
        "question_meaning_zh": "补全句子。\n把空格补成完整句子。",
        "answer_lines": [
            {
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
        "explanation_zh": "I 后面的 be 动词用 am。",
        "key_vocabulary": [
            {"word": "I", "meaning_zh": "我", "ipa": "/aɪ/"},
            {"word": "am", "meaning_zh": "是", "ipa": "/æm/"},
            {"word": "student", "meaning_zh": "学生", "ipa": "/ˈstuːdnt/"}
        ],
        "speak_units": [
            {
                "unit_type": "sentence",
                "text": "把空格补成完整句子。",
                "meaning_zh": "把空格补成完整句子。",
            },
            {
                "unit_type": "sentence",
                "text": "I am a student.",
                "meaning_zh": "我是一名学生。",
            },
            {"unit_type": "word", "text": "I", "meaning_zh": "我"},
            {"unit_type": "word", "text": "am", "meaning_zh": "是"},
            {"unit_type": "word", "text": "student", "meaning_zh": "学生"},
        ],
        "uncertainty": {"requires_review": False, "confidence": 0.95},
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
