"""
src/mock_pipeline.py — offline mock of the full pipeline for testing without API calls.

Usage:
    MOCK_MODE=1 python smoke_test.py
    # or directly:
    from src.mock_pipeline import run_mock
    result = run_mock("any_image_path.jpg")
"""
from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from src.schemas import (
    CritiqueFinding,
    FieldConfidence,
    PDPContent,
    PDPResult,
    VisualAttributes,
)

log = structlog.get_logger(__name__)

MOCK_ATTRS = VisualAttributes(
    product_type="stroller",
    color="navy blue",
    brand=None,
    material_hints=["fabric", "aluminium frame"],
    visible_features=[
        "foldable frame",
        "adjustable canopy",
        "five-point harness",
        "large storage basket",
        "swivel front wheels",
    ],
    age_indicators="0-36 months",
    accessories_visible=["rain cover"],
    image_quality="clear",
    extraction_notes="[MOCK] Synthetic attributes for offline testing",
)

MOCK_EN = PDPContent(
    title="Compact Foldable Baby Stroller with Adjustable Canopy, 0-36m",
    short_description=(
        "Designed for active families, this lightweight stroller folds flat in seconds "
        "and features a UV-protective canopy. The five-point harness keeps your baby "
        "secure from newborn through toddler stage."
    ),
    key_features=[
        "One-hand fold — collapses flat for easy storage",
        "Adjustable canopy with UV50+ sun protection",
        "Five-point safety harness, suitable 0-36 months",
        "All-terrain swivel wheels with one-click lock",
        "Extra-large storage basket fits a full diaper bag",
        "Padded seat reclines to near-flat for infant napping",
        "Rain cover included",
    ],
    safety_warnings=[
        "Always fasten the harness before use",
        "Do not use on escalators or steep inclines",
        "Maximum child weight: 15 kg",
    ],
    age_suitability="0 - 36 months",
    search_tags=[
        "baby stroller", "pram", "pushchair", "foldable stroller", "lightweight stroller",
        "travel stroller", "newborn stroller", "toddler stroller", "عربة اطفال",
        "عربة رضع", "stroller canopy", "umbrella stroller", "0-36 months",
    ],
    language="en",
)

MOCK_AR = PDPContent(
    title="عربة أطفال قابلة للطي مع مظلة قابلة للتعديل، 0-36 شهر",
    short_description=(
        "عربة مريحة وخفيفة الوزن، مصمّمة للعائلات النشطة في منطقة الخليج. "
        "تُطوى بسهولة بيد واحدة، وتوفر مظلة واسعة لحماية طفلكِ من أشعة الشمس. "
        "نظام تثبيت خماسي يمنح طفلكِ الأمان من المهد حتى سن الثلاث سنوات."
    ),
    key_features=[
        "طيّ بيد واحدة — تُخزَّن بسهولة في صندوق السيارة",
        "مظلة قابلة للتعديل بحماية من الأشعة فوق البنفسجية UV50+",
        "حزام أمان خماسي مناسب من عمر يوم واحد حتى 36 شهراً",
        "عجلات دوّارة متعددة الاستخدامات مع قفل سهل",
        "سلة تخزين واسعة تتسع لحقيبة الحفاضات كاملةً",
        "مقعد قابل للإمالة ليصبح شبه مسطح لنوم الرضيع",
        "غطاء مطر مرفق للحماية من الأمطار",
    ],
    safety_warnings=[
        "احرصي دائماً على تثبيت حزام الأمان قبل الاستخدام",
        "لا تُستخدم على السلالم المتحركة أو المنحدرات الشديدة",
        "الحد الأقصى لوزن الطفل: 15 كجم",
    ],
    age_suitability="0 - 36 شهراً",
    search_tags=[
        "عربة اطفال", "عربة رضع", "عربة قابلة للطي", "عربة خفيفة",
        "baby stroller", "pram", "pushchair", "foldable stroller",
        "travel stroller", "newborn stroller", "عربة أطفال خليجية",
        "مستلزمات الأطفال", "0-36 شهر",
    ],
    language="ar",
)

MOCK_CONFIDENCES = [
    FieldConfidence(field_name="product_type", confidence=0.97, source="visible", evidence="[MOCK]"),
    FieldConfidence(field_name="color", confidence=0.93, source="visible", evidence="[MOCK]"),
    FieldConfidence(field_name="title", confidence=0.88, source="inferred", evidence="[MOCK]"),
    FieldConfidence(field_name="key_features", confidence=0.85, source="inferred", evidence="[MOCK]"),
    FieldConfidence(field_name="safety_warnings", confidence=0.90, source="category_standard", evidence="[MOCK]"),
    FieldConfidence(field_name="short_description", confidence=0.82, source="inferred", evidence="[MOCK]"),
    FieldConfidence(field_name="age_suitability", confidence=0.91, source="visible", evidence="[MOCK]"),
]


def run_mock(image_path: str | Path = "mock_image.jpg") -> PDPResult:
    """Return a fully populated PDPResult with synthetic data. Zero API calls."""
    correlation_id = str(uuid.uuid4())[:8]
    log.info("mock_pipeline_start", correlation_id=correlation_id, image=str(image_path))

    return PDPResult(
        content_en=MOCK_EN,
        content_ar=MOCK_AR,
        field_confidences=MOCK_CONFIDENCES,
        overall_confidence=0.88,
        review_required=False,
        critique_notes=[
            CritiqueFinding(
                field_name="mock_mode",
                issue="[MOCK] This result was generated without API calls for testing.",
                severity="info",
            )
        ],
        detected_category="strollers",
        processing_time_ms=42,
        correlation_id=correlation_id,
        model_used="mock",
    )
