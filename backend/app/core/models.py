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
    category: Literal["word", "concept", "formula", "unit", "method", "other"] = "other"
    label: str | None = None


class ContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    group_id: str | None = None
    type: Literal[
        "instruction",
        "example",
        "context",
        "material",
        "dialogue",
        "word_bank",
        "option",
        "image_text",
        "other",
    ] = "other"
    text: str = Field(min_length=1)
    meaning_zh: str | None = None
    language: Literal["zh", "en", "mixed", "unknown"] = "unknown"
    speak_text: str | None = None
    speakable: bool = True


class DisplayRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    role: Literal["given", "answer", "connector", "correction", "student_answer"]


class AnswerDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal[
        "inline_segments",
        "math_block",
        "paragraph",
        "choice",
        "matching",
        "table",
        "pinyin",
        "copying",
        "plain",
    ] = "inline_segments"
    format: Literal["plain_text", "plain_math", "latex", "vertical_calculation", "table"] = "plain_text"
    latex: str | None = None
    preserve_newlines: bool = False
    runs: list[DisplayRun] = Field(min_length=1)


class AnswerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    number: str | None = None
    answer_type: Literal[
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
    speak_text: str | None = None
    display: AnswerDisplay


class QuestionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    question_meaning_zh: str = Field(min_length=1)
    content_items: list[ContentItem] = Field(default_factory=list)


class StudentAnswerReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    answer_id: str | None = None
    order: int = Field(ge=1)
    number: str | None = None
    student_answer: str | None = None
    correct_answer: str | None = None
    status: Literal[
        "correct",
        "incorrect",
        "partially_correct",
        "unanswered",
        "unclear",
        "not_applicable",
    ]
    feedback_zh: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


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
    """Fixed parse output schema v4."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["4.0"] = "4.0"
    subject: Literal["general", "english", "liberal_arts", "science"] = "general"
    question_meaning_zh: str = Field(min_length=1)
    question_blocks: list[QuestionBlock] = Field(min_length=1)
    answer_items: list[AnswerItem] = Field(min_length=1)
    student_answer_reviews: list[StudentAnswerReview] = Field(default_factory=list)
    solution_steps: list[SolutionStep] = Field(default_factory=list)
    explanation_zh: str = Field(min_length=1)
    learning_points: list[LearningPoint] = Field(default_factory=list)
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


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1)
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    user: dict
    tenant: dict


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: dict
    tenant: dict


class CreateStudentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    nickname: str | None = None
    grade: str | None = None
    school: str | None = None


class UpdateStudentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    nickname: str | None = None
    grade: str | None = None
    school: str | None = None


class CreateNotebookTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str | None = None
    student_id: str = Field(min_length=1)
    subject: Literal["general", "english", "liberal_arts", "science"] = "general"
    status: str = "completed"
    result: dict = Field(default_factory=dict)


class CreateTaskBlockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    source_block_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    question_text: str | None = None
    answer_text: str | None = None
    solution_text: str | None = None
    bbox: dict | None = None
    crop_asset_id: str | None = None


class SetCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str = Field(min_length=1)
    reason: str = "manual"
    note: str | None = None
