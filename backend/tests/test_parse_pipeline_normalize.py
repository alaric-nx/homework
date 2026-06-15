from __future__ import annotations

from app.services.parse_pipeline import ParsePipeline


def test_normalize_candidate_joins_reference_answer_list() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "reference_answer": ["1 a car", "2 a robot"],
    }
    out = pipeline._normalize_candidate(candidate)
    assert out["reference_answer"] == "1 a car\n2 a robot"


def test_normalize_candidate_passthrough_non_dict() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    assert pipeline._normalize_candidate("not-a-dict") == "not-a-dict"


def test_fallback_output_has_required_fields_without_answer_placements() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    out = pipeline._fallback_output(reason="test")
    required = {
        "question_meaning_zh",
        "reference_answer",
        "explanation_zh",
        "key_vocabulary",
        "speak_units",
        "uncertainty",
    }
    assert required.issubset(out.keys())
    assert "answer_placements" not in out
    assert "ocr_result" not in out
