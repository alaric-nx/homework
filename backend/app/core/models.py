from __future__ import annotations

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


class Uncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requires_review: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    reason: str | None = None


class HomeworkParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_meaning_zh: str = Field(min_length=1)
    reference_answer: str = Field(min_length=1)
    explanation_zh: str = Field(min_length=1)
    key_vocabulary: list[VocabularyItem] = Field(default_factory=list)
    speak_units: list[SpeakUnit] = Field(default_factory=list)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)


class HomeworkParseFillResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: HomeworkParseResponse
    filled_image_base64: str
    filled_image_path: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error_code: str
    message: str
    request_id: str


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
