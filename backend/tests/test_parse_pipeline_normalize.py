from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.core.errors import AppError
from app.core.models import HomeworkParseResult
from app.services.parse_pipeline import ParsePipeline


def _v4_payload() -> dict:
    return {
        "schema_version": "4.0",
        "subject": "english",
        "question_meaning_zh": "题目要求补全句子。",
        "question_blocks": [
            {
                "block_id": "q1",
                "order": 1,
                "title": "第1题",
                "question_meaning_zh": "补全完整句子。",
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
                    "runs": [{"text": "I am a student.", "role": "answer"}],
                },
            }
        ],
        "student_answer_reviews": [],
        "solution_steps": [],
        "explanation_zh": "I 后面用 am。",
        "learning_points": [
            {
                "block_id": "q1",
                "term": "student",
                "explanation_zh": "学生",
                "pronunciation": "/ˈstuːdnt/",
                "category": "word",
                "label": "vocabulary",
            }
        ],
        "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
    }


def test_normalize_candidate_passthrough_non_dict() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    assert pipeline._normalize_candidate("not-a-dict") == "not-a-dict"


def test_normalize_candidate_converts_legacy_answer_lines_to_v4() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "subject": "english",
        "question_meaning_zh": "补全句子。",
        "question_blocks": [
            {
                "block_id": "q1",
                "title": "第1题",
                "question_instruction": "Complete the sentence.",
                "question_meaning_zh": "补全句子。",
            }
        ],
        "answer_lines": [
            {
                "block_id": "q1",
                "number": 1,
                "line_type": "fill_blank",
                "plain_text": "I am a student.",
                "segments": [
                    {"text": "I ", "role": "given"},
                    {"text": "am", "role": "answer"},
                    {"text": " a student.", "role": "given"},
                ],
            }
        ],
    }

    out = pipeline._normalize_candidate(candidate)

    assert out["schema_version"] == "4.0"
    assert "answer_lines" not in out
    assert out["question_blocks"][0]["order"] == 1
    assert out["question_blocks"][0]["content_items"][0]["type"] == "instruction"
    assert out["answer_items"][0]["answer_id"] == "q1-a1"
    assert out["answer_items"][0]["answer_type"] == "fill_blank"
    assert out["answer_items"][0]["display"]["runs"][1]["role"] == "answer"


def test_normalize_candidate_sorts_blocks_and_answers_by_order() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "schema_version": "4.0",
        "subject": "general",
        "question_meaning_zh": "两个题块。",
        "question_blocks": [
            {"block_id": "q2", "order": 2, "title": "第二题", "question_meaning_zh": "第二题。", "content_items": []},
            {"block_id": "q1", "order": 1, "title": "第一题", "question_meaning_zh": "第一题。", "content_items": []},
        ],
        "answer_items": [
            {"answer_id": "q1-a2", "block_id": "q1", "order": 2, "number": "2", "answer_type": "short_answer", "plain_text": "B", "speak_text": "B", "display": {"mode": "plain", "format": "plain_text", "latex": None, "preserve_newlines": False, "runs": [{"text": "B", "role": "answer"}]}},
            {"answer_id": "q1-a1", "block_id": "q1", "order": 1, "number": "1", "answer_type": "short_answer", "plain_text": "A", "speak_text": "A", "display": {"mode": "plain", "format": "plain_text", "latex": None, "preserve_newlines": False, "runs": [{"text": "A", "role": "answer"}]}},
            {"answer_id": "q2-a1", "block_id": "q2", "order": 1, "number": "1", "answer_type": "short_answer", "plain_text": "C", "speak_text": "C", "display": {"mode": "plain", "format": "plain_text", "latex": None, "preserve_newlines": False, "runs": [{"text": "C", "role": "answer"}]}},
        ],
    }

    out = pipeline._normalize_candidate(candidate)

    assert [block["block_id"] for block in out["question_blocks"]] == ["q1", "q2"]
    assert [item["answer_id"] for item in out["answer_items"]] == ["q1-a1", "q1-a2", "q2-a1"]


def test_normalize_candidate_splits_multiline_content_items() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = _v4_payload()
    candidate["question_blocks"][0]["content_items"] = [
        {
            "item_id": "q1-c1",
            "order": 1,
            "group_id": "example-1",
            "type": "example",
            "text": "It is big.\nIt has a long nose.\nIt is gray.",
            "meaning_zh": "它很大。\n它有长鼻子。\n它是灰色的。",
            "language": "en",
            "speak_text": "It is big.\nIt has a long nose.\nIt is gray.",
            "speakable": True,
        }
    ]

    out = pipeline._normalize_candidate(candidate)
    items = out["question_blocks"][0]["content_items"]

    assert [item["text"] for item in items] == [
        "It is big.",
        "It has a long nose.",
        "It is gray.",
    ]
    assert [item["order"] for item in items] == [1, 2, 3]
    assert {item["group_id"] for item in items} == {"example-1"}


def test_normalize_candidate_preserves_plain_text_when_runs_disagree() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = _v4_payload()
    candidate["answer_items"][0]["display"]["runs"] = [{"text": "am", "role": "answer"}]

    out = pipeline._normalize_candidate(candidate)

    assert out["answer_items"][0]["plain_text"] == "I am a student."
    assert out["answer_items"][0]["display"]["runs"] == [
        {"text": "I am a student.", "role": "answer"}
    ]


def test_normalize_candidate_compacts_non_english_numeric_fill_blank() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = _v4_payload()
    candidate["subject"] = "science"
    candidate["answer_items"][0] = {
        "answer_id": "q1-a1",
        "block_id": "q1",
        "order": 1,
        "number": "(2)",
        "answer_type": "fill_blank",
        "plain_text": "(2) 九年级女生人数占九年级学生人数的\n45%\n；",
        "speak_text": "(2) 九年级女生人数占九年级学生人数的 45% ；",
        "display": {
            "mode": "inline_segments",
            "format": "plain_text",
            "latex": None,
            "preserve_newlines": True,
            "runs": [
                {"text": "(2) 九年级女生人数占九年级学生人数的\n", "role": "given"},
                {"text": "45%", "role": "answer"},
                {"text": "\n；", "role": "given"},
            ],
        },
    }

    out = pipeline._normalize_candidate(candidate)
    answer = out["answer_items"][0]

    assert answer["plain_text"] == "45%"
    assert answer["speak_text"] == "45%"
    assert answer["display"]["preserve_newlines"] is False
    assert answer["display"]["runs"] == [{"text": "45%", "role": "answer"}]


def test_normalize_candidate_marks_equivalent_pi_answer_correct() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = _v4_payload()
    candidate["subject"] = "science"
    candidate["question_blocks"][0]["question_meaning_zh"] = "求圆弧总长度。"
    candidate["answer_items"][0].update(
        {
            "answer_id": "q1-a1",
            "answer_type": "calculation",
            "plain_text": "44π",
            "speak_text": "四十四派",
            "display": {
                "mode": "math_block",
                "format": "plain_math",
                "latex": None,
                "preserve_newlines": False,
                "runs": [{"text": "44π", "role": "answer"}],
            },
        }
    )
    candidate["student_answer_reviews"] = [
        {
            "review_id": "q1-r1",
            "block_id": "q1",
            "answer_id": "q1-a1",
            "order": 1,
            "number": "1",
            "student_answer": "44\\pi",
            "correct_answer": "44π",
            "status": "incorrect",
            "feedback_zh": "π 写法不同。",
            "confidence": 0.8,
        }
    ]

    out = pipeline._normalize_candidate(candidate)

    review = out["student_answer_reviews"][0]
    assert review["status"] == "correct"
    assert review["feedback_zh"] == "答案正确，π 的不同写法等价。"
    assert review["confidence"] == 0.95


def test_normalize_candidate_keeps_different_pi_coefficient_incorrect() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = _v4_payload()
    candidate["subject"] = "science"
    candidate["answer_items"][0].update(
        {
            "answer_id": "q1-a1",
            "answer_type": "calculation",
            "plain_text": "44π",
            "display": {
                "mode": "math_block",
                "format": "plain_math",
                "latex": None,
                "preserve_newlines": False,
                "runs": [{"text": "44π", "role": "answer"}],
            },
        }
    )
    candidate["student_answer_reviews"] = [
        {
            "review_id": "q1-r1",
            "block_id": "q1",
            "answer_id": "q1-a1",
            "order": 1,
            "number": "1",
            "student_answer": "43.5\\pi",
            "correct_answer": "44\\pi",
            "status": "incorrect",
            "feedback_zh": "计算错误。",
            "confidence": 0.8,
        }
    ]

    out = pipeline._normalize_candidate(candidate)

    assert out["student_answer_reviews"][0]["status"] == "incorrect"


def test_mark_missing_vocabulary_updates_uncertainty() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    result = HomeworkParseResult.model_validate(_v4_payload())

    out = pipeline._mark_missing_vocabulary(result)

    assert out.uncertainty.requires_review is True
    assert out.uncertainty.confidence == 0.85
    assert "am" in (out.uncertainty.reason or "")


def test_repair_missing_vocabulary_calls_model_once() -> None:
    class FakeLLMClient:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_any_json(self, prompt: str, model: str | None = None) -> dict:
            self.calls += 1
            return {"items": [{"word": "am", "meaning_zh": "是", "ipa": "/æm/"}]}

    llm_client = FakeLLMClient()
    pipeline = ParsePipeline.__new__(ParsePipeline)
    pipeline.llm_client = llm_client
    result = HomeworkParseResult.model_validate(_v4_payload())

    out = asyncio.run(pipeline._repair_missing_vocabulary(result, model=None))

    assert llm_client.calls == 1
    assert any(item.term == "am" for item in out.learning_points)
    assert out.uncertainty.requires_review is False


def test_run_rejects_response_subject_mismatch() -> None:
    class FakeLLMClient:
        async def generate_json(
            self,
            prompt: str,
            file_paths: list[str] | None = None,
            model: str | None = None,
        ) -> dict:
            payload = _v4_payload()
            payload["subject"] = "english"
            return payload

    pipeline = ParsePipeline(FakeLLMClient(), Settings())

    try:
        asyncio.run(pipeline.run(image_bytes=None, model=None, subject="science"))
    except AppError as exc:
        assert exc.code == "SCHEMA_VALIDATION_FAILED"
        assert "does not match request subject" in exc.detail
    else:
        raise AssertionError("expected subject mismatch to fail")
