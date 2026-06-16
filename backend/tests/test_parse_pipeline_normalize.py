from __future__ import annotations

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
