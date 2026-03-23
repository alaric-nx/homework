from __future__ import annotations

from app.core.errors import AppError
from app.core.models import OCRResult
from app.services.parse_pipeline import ParsePipeline


def test_normalize_candidate_reference_answer_and_font_size_ratio() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "reference_answer": ["1 a car", "2 a robot"],
        "answer_placements": [
            {"number": 1, "text": "a car", "bbox_norm": [0.1, 0.1, 0.2, 0.2], "font_size_ratio": 0.0},
            {"number": 2, "text": ["a", "robot"], "bbox_norm": [0.2, 0.2, 0.3, 0.3], "font_size_ratio": 0.01},
        ],
    }
    out = pipeline._normalize_candidate(candidate)
    assert out["reference_answer"] == "1 a car\n2 a robot"
    assert out["answer_placements"][0]["font_size_ratio"] is None
    assert out["answer_placements"][1]["text"] == "a robot"


def test_should_retry_strict_false_when_budget_low() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {"reference_answer": "1 a car", "answer_placements": []}
    err = AppError("SCHEMA_VALIDATION_FAILED", "minor")
    out = pipeline._should_retry_strict(
        candidate, err, OCRResult(text="some text", confidence=0.8), elapsed_sec=34.0
    )
    assert out is False


def test_salvage_candidate_keeps_valid_answers() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)

    class _DummySolver:
        def fallback_output(self, ocr, reason=None):
            return {
                "question_meaning_zh": "fallback",
                "reference_answer": "fallback",
                "explanation_zh": "fallback",
                "key_vocabulary": [],
                "speak_units": [],
                "uncertainty": {"requires_review": True, "confidence": 0.5, "reason": reason},
                "answer_placements": [],
            }

    pipeline.english_solver = _DummySolver()
    candidate = {
        "question_meaning_zh": "题意\n作答",
        "reference_answer": "1 a car\n2 a robot",
        "explanation_zh": "解释",
        "answer_placements": [
            {"number": 1, "text": "a car", "bbox_norm": [0.1, 0.1, 0.2, 0.2], "font_size_ratio": 0.0},
            {"number": 2, "text": "a robot", "bbox_norm": [0.2, 0.2, 0.3, 0.3], "font_size_ratio": 0.01},
        ],
    }
    out = pipeline._salvage_candidate(candidate, OCRResult(text="x", confidence=0.9), "r")
    assert out["reference_answer"].startswith("1 a car")
    assert len(out["answer_placements"]) == 2
    assert out["answer_placements"][0]["font_size_ratio"] is None
