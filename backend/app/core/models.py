from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VocabularyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str = Field(min_length=1)
    meaning_zh: str = Field(min_length=1)
    ipa: str | None = None


class SpeakUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_type: Literal["word", "sentence"]
    text: str = Field(min_length=1)
    meaning_zh: str | None = None


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
    """Simplified parse output schema.

    仅包含 6 个固定字段，不含 answer_placements 和 ocr_result。
    """

    model_config = ConfigDict(extra="forbid")
    question_meaning_zh: str = Field(min_length=1)
    reference_answer: str = Field(min_length=1)
    explanation_zh: str = Field(min_length=1)
    key_vocabulary: list[VocabularyItem] = Field(default_factory=list)
    speak_units: list[SpeakUnit] = Field(default_factory=list)
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
    result: HomeworkParseResult | None = None


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    status: str
    image_hash: str
    model: str
    result: HomeworkParseResult | None = None
    error_code: str | None = None
    error_message: str | None = None
