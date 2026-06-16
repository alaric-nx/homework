from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.services.llm_client import LLMClient

V2_PAYLOAD = {
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
    "explanation_zh": "be 动词和 I 搭配用 am。",
    "key_vocabulary": [
        {"word": "I", "meaning_zh": "我", "ipa": "/aɪ/"},
        {"word": "am", "meaning_zh": "是", "ipa": "/æm/"},
        {"word": "student", "meaning_zh": "学生", "ipa": "/ˈstuːdnt/"},
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
    "uncertainty": {"requires_review": False, "confidence": 0.9},
}


def test_parse_json_payload_with_wrapped_text() -> None:
    client = LLMClient(Settings())
    payload_text = json.dumps(V2_PAYLOAD, ensure_ascii=False)
    raw = """some logs...
```json
%s
```
""" % payload_text
    payload = client._parse_json_payload(raw)  # noqa: SLF001
    assert payload["question_meaning_zh"] == V2_PAYLOAD["question_meaning_zh"]


def test_extract_payload_from_event_stream_lines() -> None:
    client = LLMClient(Settings())
    escaped_payload = json.dumps(V2_PAYLOAD, ensure_ascii=False)
    raw = '\n'.join(
        [
            '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}',
            json.dumps(
                {"type": "message_delta", "delta": escaped_payload},
                ensure_ascii=False,
            ),
        ]
    )
    payload = client._parse_json_payload(raw)  # noqa: SLF001
    assert payload["answer_lines"][0]["plain_text"] == "I am a student."


def test_parse_json_payload_rejects_step_start_only() -> None:
    client = LLMClient(Settings())
    raw = '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}'
    with pytest.raises(json.JSONDecodeError):
        client._parse_json_payload(raw)  # noqa: SLF001
