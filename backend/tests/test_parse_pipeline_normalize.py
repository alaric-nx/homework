from __future__ import annotations

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

