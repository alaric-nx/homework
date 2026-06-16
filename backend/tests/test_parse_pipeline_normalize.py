from __future__ import annotations

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
