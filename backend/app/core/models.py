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


class AnswerPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int = Field(ge=1, le=9)
    text: str = Field(min_length=1)
    bbox_norm: list[float] = Field(min_length=4, max_length=4)
    font_size_ratio: float | None = Field(default=None, ge=0.005, le=0.2)


class HomeworkParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_meaning_zh: str = Field(min_length=1)
    reference_answer: str = Field(min_length=1)
    explanation_zh: str = Field(min_length=1)
    key_vocabulary: list[VocabularyItem] = Field(default_factory=list)
    speak_units: list[SpeakUnit] = Field(default_factory=list)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    answer_placements: list[AnswerPlacement] = Field(default_factory=list)
    ocr_result: OCRResult | None = None


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


class OCRBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    bbox: list[float] | None = None
    polygon: list[list[float]] = Field(default_factory=list)
    label: str | None = None
    order: int | None = None
    page: int | None = None


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    image_width: int | None = None
    image_height: int | None = None
    blocks: list[OCRBlock] = Field(default_factory=list)
