from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.services.llm_client import LLMClient

V4_PAYLOAD = {
    "schema_version": "4.0",
    "subject": "english",
    "question_meaning_zh": "补全句子。\n把空格补成完整句子。",
    "question_blocks": [
        {
            "block_id": "q1",
            "order": 1,
            "title": "第1题",
            "question_meaning_zh": "把空格补成完整句子。",
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
                }
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
    "student_answer_reviews": [],
    "solution_steps": [],
    "explanation_zh": "be 动词和 I 搭配用 am。",
    "learning_points": [
        {"block_id": "q1", "term": "I", "explanation_zh": "我", "pronunciation": "/aɪ/", "category": "word", "label": "vocabulary"},
        {"block_id": "q1", "term": "am", "explanation_zh": "是", "pronunciation": "/æm/", "category": "word", "label": "vocabulary"},
        {"block_id": "q1", "term": "student", "explanation_zh": "学生", "pronunciation": "/ˈstuːdnt/", "category": "word", "label": "vocabulary"},
    ],
    "uncertainty": {"requires_review": False, "confidence": 0.9, "reason": None},
}


def test_parse_json_payload_with_wrapped_text() -> None:
    client = LLMClient(Settings())
    payload_text = json.dumps(V4_PAYLOAD, ensure_ascii=False)
    raw = """some logs...
```json
%s
```
""" % payload_text
    payload = client._parse_json_payload(raw)  # noqa: SLF001
    assert payload["question_meaning_zh"] == V4_PAYLOAD["question_meaning_zh"]


def test_extract_payload_from_event_stream_lines() -> None:
    client = LLMClient(Settings())
    escaped_payload = json.dumps(V4_PAYLOAD, ensure_ascii=False)
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
    assert payload["answer_items"][0]["plain_text"] == "I am a student."


def test_parse_json_payload_rejects_step_start_only() -> None:
    client = LLMClient(Settings())
    raw = '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}'
    with pytest.raises(json.JSONDecodeError):
        client._parse_json_payload(raw)  # noqa: SLF001


def test_parse_json_payload_repairs_single_backslash_latex() -> None:
    client = LLMClient(Settings())
    raw = r'''
{
  "schema_version": "4.0",
  "subject": "science",
  "question_meaning_zh": "求圆弧长度。",
  "question_blocks": [{"block_id": "q1", "order": 1, "title": "第1题", "question_meaning_zh": "求长度。", "content_items": []}],
  "answer_items": [{
    "answer_id": "q1-a1",
    "block_id": "q1",
    "order": 1,
    "number": "1",
    "answer_type": "calculation",
    "plain_text": "44\pi",
    "speak_text": "四十四派",
    "display": {"mode": "math_block", "format": "plain_math", "latex": null, "preserve_newlines": false, "runs": [{"text": "44\pi", "role": "answer"}]}
  }],
  "student_answer_reviews": [],
  "solution_steps": [{"block_id": "q1", "number": "1", "title": "计算", "content_zh": "总弧长。", "formula": "L = (1/2)π \times 88 = 44π", "result": "44\pi"}],
  "explanation_zh": "按弧长公式计算。",
  "learning_points": [],
  "uncertainty": {"requires_review": false, "confidence": 0.9, "reason": null}
}
'''

    payload = client._parse_json_payload(raw)  # noqa: SLF001

    assert payload["answer_items"][0]["plain_text"] == r"44\pi"
    assert payload["solution_steps"][0]["formula"] == r"L = (1/2)π \times 88 = 44π"


def test_parse_json_payload_repairs_literal_newline_inside_string() -> None:
    client = LLMClient(Settings())
    raw = '''{
  "schema_version": "4.0",
  "subject": "science",
  "question_meaning_zh": "求圆弧长度。",
  "question_blocks": [{"block_id": "q1", "order": 1, "title": "第1题", "question_meaning_zh": "求长度。", "content_items": []}],
  "answer_items": [{"answer_id": "q1-a1", "block_id": "q1", "order": 1, "number": "1", "answer_type": "calculation", "plain_text": "44π", "speak_text": "四十四派", "display": {"mode": "math_block", "format": "plain_math", "latex": null, "preserve_newlines": false, "runs": [{"text": "44π", "role": "answer"}]}}],
  "student_answer_reviews": [],
  "solution_steps": [{"block_id": "q1", "number": "1", "title": "计算", "content_zh": "第一行
第二行", "formula": "44π", "result": "44π"}],
  "explanation_zh": "按弧长公式计算。",
  "learning_points": [],
  "uncertainty": {"requires_review": false, "confidence": 0.9, "reason": null}
}'''

    payload = client._parse_json_payload(raw)  # noqa: SLF001

    assert payload["solution_steps"][0]["content_zh"] == "第一行\n第二行"
