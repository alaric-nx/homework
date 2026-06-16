from __future__ import annotations

import asyncio

from app.core.models import HomeworkParseResult
from app.core.config import Settings
from app.core.errors import AppError
from app.services.parse_pipeline import ParsePipeline


def test_normalize_candidate_adds_answer_segments_from_plain_text() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "question_blocks": [
            {
                "block_id": 1,
                "title": "第1题",
                "question_instruction": {
                    "text": "Complete the sentence.",
                    "meaning_zh": "补全句子。",
                    "confidence": 0.95,
                },
                "question_meaning_zh": "补全句子。",
            }
        ],
        "answer_lines": [
            {
                "block_id": "q1",
                "number": 1,
                "line_type": "fill_blank",
                "plain_text": "I am a student.",
            }
        ],
    }
    out = pipeline._normalize_candidate(candidate)
    assert out["question_blocks"][0]["block_id"] == "1"
    assert out["answer_lines"][0]["number"] == "1"
    assert out["answer_lines"][0]["segments"] == [
        {"text": "I am a student.", "role": "answer"}
    ]


def test_normalize_candidate_passthrough_non_dict() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    assert pipeline._normalize_candidate("not-a-dict") == "not-a-dict"


def test_normalize_candidate_maps_model_enum_aliases() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    candidate = {
        "question_blocks": [
            {
                "block_id": "q1",
                "title": "Practice A",
                "question_instruction": "Fill in the blanks with 'must' or 'mustn't' and the words given.",
                "question_meaning_zh": "用 must 或 mustn't 补全句子。",
            }
        ],
        "learning_points": [
            {
                "block_id": "q1",
                "term": "must",
                "explanation_zh": "情态动词，表示必须。",
                "pronunciation": None,
                "category": "grammar",
            },
            {
                "block_id": "q1",
                "term": "play football",
                "explanation_zh": "踢足球。",
                "pronunciation": None,
                "category": "phrase",
            },
        ],
        "read_units": [
            {
                "block_id": "q1",
                "unit_type": "instruction",
                "text": "Re-arrange the words into correct sentences.",
                "meaning_zh": "把单词重新排列成正确句子。",
            },
            {
                "block_id": "q1",
                "unit_type": "text",
                "text": "You must sit down.",
                "meaning_zh": "你必须坐下。",
            }
        ],
    }

    out = pipeline._normalize_candidate(candidate)

    assert out["question_blocks"][0]["question_instruction"] == {
        "text": "Fill in the blanks with 'must' or 'mustn't' and the words given.",
        "meaning_zh": "",
        "confidence": 0.0,
    }
    assert out["learning_points"][0]["category"] == "concept"
    assert out["learning_points"][0]["label"] == "grammar"
    assert out["learning_points"][1]["category"] == "word"
    assert out["learning_points"][1]["label"] == "phrase"
    assert out["read_units"][0]["unit_type"] == "text"
    assert out["read_units"][0]["label"] == "instruction"
    assert out["read_units"][1]["unit_type"] == "text"
    assert out["read_units"][1]["label"] == "text"


def test_mark_missing_vocabulary_updates_uncertainty() -> None:
    pipeline = ParsePipeline.__new__(ParsePipeline)
    result = HomeworkParseResult.model_validate(
        {
            "subject": "english",
            "question_meaning_zh": "补全句子。\n补全完整句子。",
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
                    "question_meaning_zh": "补全完整句子。",
                }
            ],
            "answer_lines": [
                {
                    "block_id": "q1",
                    "number": "1",
                    "line_type": "fill_blank",
                    "plain_text": "I am a student.",
                    "segments": [{"text": "I am a student.", "role": "answer"}],
                }
            ],
            "solution_steps": [],
            "explanation_zh": "I 后面用 am。",
            "learning_points": [
                {
                    "block_id": "q1",
                    "term": "student",
                    "explanation_zh": "学生",
                    "pronunciation": "/ˈstuːdnt/",
                    "category": "word", "label": "vocabulary",
                }
            ],
            "read_units": [
                {
                    "block_id": "q1",
                    "unit_type": "text", "label": "sentence",
                    "text": "I am a student.",
                    "meaning_zh": "我是一名学生。",
                }
            ],
            "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
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
            "subject": "english",
            "question_meaning_zh": "补全句子。\n补全完整句子。",
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
                    "question_meaning_zh": "补全完整句子。",
                }
            ],
            "answer_lines": [
                {
                    "block_id": "q1",
                    "number": "1",
                    "line_type": "fill_blank",
                    "plain_text": "I am a student.",
                    "segments": [{"text": "I am a student.", "role": "answer"}],
                }
            ],
            "solution_steps": [],
            "explanation_zh": "I 后面用 am。",
            "learning_points": [
                {
                    "block_id": "q1",
                    "term": "student",
                    "explanation_zh": "学生",
                    "pronunciation": "/ˈstuːdnt/",
                    "category": "word", "label": "vocabulary",
                }
            ],
            "read_units": [
                {
                    "block_id": "q1",
                    "unit_type": "text", "label": "sentence",
                    "text": "I am a student.",
                    "meaning_zh": "我是一名学生。",
                }
            ],
            "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
        }
    )

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
            return {
                "subject": "english",
                "question_meaning_zh": "计算面积。",
                "question_instruction": {
                    "text": "求下面长方形的面积。",
                    "meaning_zh": "计算长方形面积。",
                    "confidence": 0.95,
                },
                "question_blocks": [
                    {
                        "block_id": "q1",
                        "title": "第1题",
                        "question_instruction": {
                            "text": "求下面长方形的面积。",
                            "meaning_zh": "计算长方形面积。",
                            "confidence": 0.95,
                        },
                        "question_meaning_zh": "根据长和宽求面积。",
                    }
                ],
                "answer_lines": [
                    {
                        "block_id": "q1",
                        "number": "1",
                        "line_type": "calculation",
                        "plain_text": "8 × 5 = 40（平方厘米）",
                        "segments": [
                            {"text": "8 × 5 = ", "role": "given"},
                            {"text": "40（平方厘米）", "role": "answer"},
                        ],
                    }
                ],
                "solution_steps": [
                    {
                        "block_id": "q1",
                        "number": "1",
                        "title": "列式",
                        "content_zh": "长方形面积等于长乘宽。",
                        "formula": "8 × 5 = 40",
                        "result": "40 平方厘米",
                    }
                ],
                "explanation_zh": "面积单位是平方厘米。",
                "learning_points": [],
                "read_units": [],
                "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
            }

    pipeline = ParsePipeline(FakeLLMClient(), Settings())

    try:
        asyncio.run(pipeline.run(image_bytes=None, model=None, subject="science"))
    except AppError as exc:
        assert exc.code == "SCHEMA_VALIDATION_FAILED"
        assert "does not match request subject" in exc.detail
    else:
        raise AssertionError("expected subject mismatch to fail")


def test_run_repairs_json_contract_once_for_low_risk_schema_error() -> None:
    class FakeLLMClient:
        def __init__(self) -> None:
            self.repair_calls = 0

        async def generate_json(
            self,
            prompt: str,
            file_paths: list[str] | None = None,
            model: str | None = None,
        ) -> dict:
            return {
                "subject": "english",
                "question_meaning_zh": "补全句子。",
                "question_instruction": "Complete the sentence.",
                "question_blocks": [
                    {
                        "block_id": "q1",
                        "title": "第1题",
                        "question_instruction": "Complete the sentence.",
                        "question_meaning_zh": "补全完整句子。",
                    }
                ],
                "answer_lines": [
                    {
                        "block_id": "q1",
                        "number": "1",
                        "line_type": "fill_blank",
                        "plain_text": "I am a student.",
                        "segments": [{"text": "I am a student.", "role": "answer"}],
                    }
                ],
                "solution_steps": [],
                "explanation_zh": "I 后面用 am。",
                "learning_points": [
                    {
                        "block_id": "q1",
                        "term": "am",
                        "explanation_zh": "是",
                        "pronunciation": "/æm/",
                        "category": "grammar",
                    }
                ],
                "read_units": [
                    {
                        "block_id": "q1",
                        "unit_type": "instruction",
                        "text": "Complete the sentence.",
                        "meaning_zh": "补全句子。",
                    }
                ],
                "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
            }

        async def generate_any_json(self, prompt: str, model: str | None = None) -> dict:
            self.repair_calls += 1
            return {
                "subject": "english",
                "question_meaning_zh": "补全句子。",
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
                        "question_meaning_zh": "补全完整句子。",
                    }
                ],
                "answer_lines": [
                    {
                        "block_id": "q1",
                        "number": "1",
                        "line_type": "fill_blank",
                        "plain_text": "I am a student.",
                        "segments": [{"text": "I am a student.", "role": "answer"}],
                    }
                ],
                "solution_steps": [],
                "explanation_zh": "I 后面用 am。",
                "learning_points": [
                    {
                        "block_id": "q1",
                        "term": "am",
                        "explanation_zh": "是",
                        "pronunciation": "/æm/",
                        "category": "concept",
                        "label": "grammar",
                    }
                ],
                "read_units": [
                    {
                        "block_id": "q1",
                        "unit_type": "text",
                        "label": "instruction",
                        "text": "Complete the sentence.",
                        "meaning_zh": "补全句子。",
                    }
                ],
                "uncertainty": {"requires_review": False, "confidence": 0.95, "reason": None},
            }

    llm_client = FakeLLMClient()
    pipeline = ParsePipeline(llm_client, Settings())

    out = asyncio.run(pipeline.run(image_bytes=None, model=None, subject="english"))

    assert llm_client.repair_calls == 1
    assert out.learning_points[0].label == "grammar"
    assert out.read_units[0].unit_type == "text"
