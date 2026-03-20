from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.services.opencode_client import OpencodeClient


def test_parse_json_payload_with_wrapped_text() -> None:
    client = OpencodeClient(Settings())
    raw = """some logs...
```json
{"question_meaning_zh":"x","reference_answer":"y","explanation_zh":"z","key_vocabulary":[],"speak_units":[],"uncertainty":{"requires_review":false,"confidence":0.9}}
```
"""
    payload = client._parse_json_payload(raw)  # noqa: SLF001
    assert payload["question_meaning_zh"] == "x"


def test_extract_payload_from_event_stream_lines() -> None:
    client = OpencodeClient(Settings())
    raw = '\n'.join(
        [
            '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}',
            '{"type":"message_delta","delta":"{\\"question_meaning_zh\\":\\"a\\",\\"reference_answer\\":\\"b\\",\\"explanation_zh\\":\\"c\\",\\"key_vocabulary\\":[],\\"speak_units\\":[],\\"uncertainty\\":{\\"requires_review\\":false,\\"confidence\\":0.9}}"}',
        ]
    )
    payload = client._parse_json_payload(raw)  # noqa: SLF001
    assert payload["reference_answer"] == "b"


def test_parse_json_payload_rejects_step_start_only() -> None:
    client = OpencodeClient(Settings())
    raw = '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}'
    with pytest.raises(json.JSONDecodeError):
        client._parse_json_payload(raw)  # noqa: SLF001
