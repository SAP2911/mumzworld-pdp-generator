from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VisualAttributes(BaseModel):
    """Raw output of the Vision Extraction Agent."""

    product_type: str
    color: Optional[str] = None
    brand: Optional[str] = None
    material_hints: list[str] = Field(default_factory=list)
    visible_features: list[str] = Field(default_factory=list)
    age_indicators: Optional[str] = None
    accessories_visible: list[str] = Field(default_factory=list)
    image_quality: Literal["clear", "partial", "blurry", "non_product"] = "clear"
    extraction_notes: str = ""


EvidenceSource = Literal["visible", "inferred", "category_standard", "uncertain"]


class FieldConfidence(BaseModel):
    field_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: EvidenceSource = "inferred"
    evidence: str = ""

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)


class PDPContent(BaseModel):
    """PDP copy for one language. title=None means it was below confidence threshold."""

    title: Optional[str] = Field(None, max_length=70)
    short_description: Optional[str] = None
    key_features: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    age_suitability: Optional[str] = None
    search_tags: list[str] = Field(default_factory=list)
    language: Literal["en", "ar"] = "en"


class CritiqueFinding(BaseModel):
    field_name: str
    issue: str
    severity: Literal["info", "warning", "error"] = "info"
    revised_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class PDPResult(BaseModel):
    """Final output — one instance per pipeline run."""

    model_config = ConfigDict(protected_namespaces=())

    product_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    content_en: PDPContent
    content_ar: PDPContent
    field_confidences: list[FieldConfidence] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool
    critique_notes: list[CritiqueFinding] = Field(default_factory=list)
    detected_category: Optional[str] = None
    processing_time_ms: int = 0
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    model_used: str = ""

    def get_field_confidence(self, field_name: str) -> Optional[FieldConfidence]:
        return next((f for f in self.field_confidences if f.field_name == field_name), None)

    def has_errors(self) -> bool:
        return any(c.severity == "error" for c in self.critique_notes)
