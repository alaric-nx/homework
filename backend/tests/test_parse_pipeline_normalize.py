from __future__ import annotations

import asyncio

from app.core.models import HomeworkParseResult
from app.services.parse_pipeline import ParsePipeline


def test_normalize_candidate_adds_answer_segments_from_plain_text() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "answer_lines": [
            {
                "number": 1,
                "line_type": "fill_blank",
                "plain_text": "I am a student.",
            }
        ],
    }
    out = pipeline._normalize_candidate(candidate)
    assert out["answer_lines"][0]["number"] == "1"
    assert out["answer_lines"][0]["segments"] == [
        {"text": "I am a student.", "role": "answer"}
    ]


def test_normalize_candidate_passthrough_non_dict() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    assert pipeline._normalize_candidate("not-a-dict") == "not-a-dict"


def test_fallback_output_has_required_fields_without_answer_placements() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    out = pipeline._fallback_output(reason="test")
    required = {
        "question_meaning_zh",
        "answer_lines",
        "explanation_zh",
        "key_vocabulary",
        "speak_units",
        "uncertainty",
    }
    assert required.issubset(out.keys())
    assert out["answer_lines"][0]["segments"][0]["role"] == "answer"
    assert "answer_placements" not in out
    assert "ocr_result" not in out


def test_mark_missing_vocabulary_updates_uncertainty() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    result = HomeworkParseResult.model_validate(
        {
            "question_meaning_zh": "补全句子。\n补全完整句子。",
            "question_instruction": {
                "text": "Complete the sentence.",
                "meaning_zh": "补全句子。",
                "confidence": 0.95,
            },
            "answer_lines": [
                {
                    "number": "1",
                    "line_type": "fill_blank",
                    "plain_text": "I am a student.",
                    "segments": [{"text": "I am a student.", "role": "answer"}],
                }
            ],
            "explanation_zh": "I 后面用 am。",
            "key_vocabulary": [
                {"word": "student", "meaning_zh": "学生", "ipa": "/ˈstuːdnt/"}
            ],
            "speak_units": [
                {
                    "unit_type": "sentence",
                    "text": "I am a student.",
                    "meaning_zh": "我是一名学生。",
                }
            ],
            "uncertainty": {"requires_review": False, "confidence": 0.95},
        }
    )

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
            return {
                "items": [
                    {"word": "am", "meaning_zh": "是", "ipa": "/æm/"},
                ]
            }

    llm_client = FakeLLMClient()
    pipeline = ParsePipeline.__new__(ParsePipeline)
    pipeline.llm_client = llm_client
    result = HomeworkParseResult.model_validate(
        {
            "question_meaning_zh": "补全句子。\n补全完整句子。",
            "question_instruction": {
                "text": "Complete the sentence.",
                "meaning_zh": "补全句子。",
                "confidence": 0.95,
            },
            "answer_lines": [
                {
                    "number": "1",
                    "line_type": "fill_blank",
                    "plain_text": "I am a student.",
                    "segments": [{"text": "I am a student.", "role": "answer"}],
                }
            ],
            "explanation_zh": "I 后面用 am。",
            "key_vocabulary": [
                {"word": "student", "meaning_zh": "学生", "ipa": "/ˈstuːdnt/"}
            ],
            "speak_units": [
                {
                    "unit_type": "sentence",
                    "text": "I am a student.",
                    "meaning_zh": "我是一名学生。",
                }
            ],
            "uncertainty": {"requires_review": False, "confidence": 0.95},
        }
    )

    out = asyncio.run(pipeline._repair_missing_vocabulary(result, model=None))

    assert llm_client.calls == 1
    assert any(item.word == "am" for item in out.key_vocabulary)
    assert out.uncertainty.requires_review is False
