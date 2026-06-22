from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.skills.common.response_schema_guard import ResponseSchemaGuard


def _valid_payload() -> dict:
    return {
        "schema_version": "4.0",
        "subject": "english",
        "question_meaning_zh": "题目要求根据例句补全句子。",
        "question_blocks": [
            {
                "block_id": "q1",
                "order": 1,
                "title": "第1题",
                "question_meaning_zh": "读例句后补全完整句子。",
                "content_items": [
                    {
                        "item_id": "q1-c1",
                        "order": 1,
                        "group_id": None,
                        "type": "instruction",
                        "text": "Complete the sentence.",
                        "meaning_zh": "补全句子。",
                        "language": "en",
                        "speak_text": "Complete the sentence.",
                        "speakable": True,
                    },
                    {
                        "item_id": "q1-c2",
                        "order": 2,
                        "group_id": "example-1",
                        "type": "example",
                        "text": "Example: I am happy.",
                        "meaning_zh": "例句：我很开心。",
                        "language": "en",
                        "speak_text": "I am happy.",
                        "speakable": True,
                    },
                ],
            }
        ],
        "answer_items": [
            {
                "answer_id": "q1-a1",
                "block_id": "q1",
                "order": 1,
                "number": "1",
                "answer_type": "fill_blank",
                "plain_text": "I am a student.",
                "speak_text": "I am a student.",
                "display": {
                    "mode": "inline_segments",
                    "format": "plain_text",
                    "latex": None,
                    "preserve_newlines": False,
                    "runs": [
                        {"text": "I ", "role": "given"},
                        {"text": "am", "role": "answer"},
                        {"text": " a student.", "role": "given"},
                    ],
                },
            }
        ],
        "student_answer_reviews": [
            {
                "review_id": "q1-r1",
                "block_id": "q1",
                "answer_id": "q1-a1",
                "order": 1,
                "number": "1",
                "student_answer": "am",
                "correct_answer": "am",
                "status": "correct",
                "feedback_zh": "填写正确。",
                "confidence": 0.95,
            }
        ],
        "solution_steps": [],
        "explanation_zh": "I 后面的 be 动词用 am。",
        "learning_points": [
            {
                "block_id": "q1",
                "term": "am",
                "explanation_zh": "是",
                "pronunciation": "/æm/",
                "category": "word",
                "label": "vocabulary",
            }
        ],
        "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
    }


def test_validate_payload_accepts_v4() -> None:
    result = ResponseSchemaGuard().validate_payload(_valid_payload())

    assert result.schema_version == "4.0"
    assert result.question_blocks[0].content_items[1].type == "example"
    assert result.answer_items[0].display.runs[1].role == "answer"
    assert result.student_answer_reviews[0].status == "correct"


def test_validate_payload_rejects_missing_answer_items() -> None:
    payload = _valid_payload()
    payload.pop("answer_items")

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_invalid_display_role() -> None:
    payload = _valid_payload()
    payload["answer_items"][0]["display"]["runs"][0]["role"] = "wrong"

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_unknown_answer_block_id() -> None:
    payload = _valid_payload()
    payload["answer_items"][0]["block_id"] = "q9"

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_unknown_review_answer_id() -> None:
    payload = _valid_payload()
    payload["student_answer_reviews"][0]["answer_id"] = "q1-a9"

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)


def test_validate_payload_rejects_duplicate_answer_order() -> None:
    payload = _valid_payload()
    duplicate = dict(payload["answer_items"][0])
    duplicate["answer_id"] = "q1-a2"
    payload["answer_items"].append(duplicate)

    with pytest.raises(AppError):
        ResponseSchemaGuard().validate_payload(payload)
