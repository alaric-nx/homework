from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LearningPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str | None = None
    term: str = Field(min_length=1)
    explanation_zh: str = Field(min_length=1)
    pronunciation: str | None = None
    category: Literal["word", "pinyin", "concept", "formula", "unit", "method", "other"] = "other"


class ReadUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str | None = None
    unit_type: Literal["word", "sentence", "paragraph", "answer", "explanation"]
    text: str = Field(min_length=1)
    meaning_zh: str | None = None


class AnswerSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    role: Literal["given", "answer", "connector", "correction"]


class AnswerLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(min_length=1)
    number: str | None = None
    line_type: Literal[
        "fill_blank",
        "choice",
        "picture_word",
        "matching",
        "sentence_ordering",
        "reading_qa",
        "translation",
        "correction",
        "copying",
        "calculation",
        "proof",
        "short_answer",
        "composition",
        "pinyin",
        "other",
    ] = "other"
    plain_text: str = Field(min_length=1)
    segments: list[AnswerSegment] = Field(min_length=1)


class QuestionInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    meaning_zh: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class QuestionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    question_instruction: QuestionInstruction = Field(
        default_factory=QuestionInstruction
    )
    question_meaning_zh: str = Field(min_length=1)


class SolutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(min_length=1)
    number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content_zh: str = Field(min_length=1)
    formula: str | None = None
    result: str | None = None


class Uncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requires_review: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    reason: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error_code: str
    message: str
    request_id: str


class HomeworkParseResult(BaseModel):
    """Fixed parse output schema v3."""

    model_config = ConfigDict(extra="forbid")
    subject: Literal["general", "english", "liberal_arts", "science"] = "general"
    question_meaning_zh: str = Field(min_length=1)
    question_instruction: QuestionInstruction = Field(
        default_factory=QuestionInstruction
    )
    question_blocks: list[QuestionBlock] = Field(min_length=1)
    answer_lines: list[AnswerLine] = Field(min_length=1)
    solution_steps: list[SolutionStep] = Field(default_factory=list)
    explanation_zh: str = Field(min_length=1)
    learning_points: list[LearningPoint] = Field(default_factory=list)
    read_units: list[ReadUnit] = Field(default_factory=list)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Internal task state for async parse workflow."""

    task_id: str
    status: TaskStatus
    image_hash: str
    model: str
    subject: str = "general"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: HomeworkParseResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class ParseSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    status: str
    image_hash: str
    subject: str = "general"
    result: HomeworkParseResult | None = None


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    status: str
    image_hash: str
    model: str
    subject: str = "general"
    result: HomeworkParseResult | None = None
    error_code: str | None = None
    error_message: str | None = None
