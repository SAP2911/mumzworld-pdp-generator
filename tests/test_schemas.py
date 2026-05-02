"""
tests/test_schemas.py — unit tests for Pydantic schemas.
No API calls needed. Run: pytest tests/ -v
"""
import json
import pytest

from src.schemas import (
    CritiqueFinding,
    FieldConfidence,
    PDPContent,
    PDPResult,
    VisualAttributes,
)


class TestVisualAttributes:
    def test_defaults(self):
        attrs = VisualAttributes(product_type="stroller", image_quality="clear")
        assert attrs.product_type == "stroller"
        assert attrs.color is None
        assert attrs.brand is None
        assert attrs.material_hints == []
        assert attrs.visible_features == []
        assert attrs.accessories_visible == []

    def test_full_construction(self):
        attrs = VisualAttributes(
            product_type="car_seat",
            color="black",
            brand="Joie",
            material_hints=["fabric", "plastic"],
            visible_features=["ISOFIX", "harness"],
            age_indicators="0-12 months",
            accessories_visible=["rain cover"],
            image_quality="clear",
            extraction_notes="sharp photo",
        )
        assert attrs.brand == "Joie"
        assert len(attrs.material_hints) == 2
        assert attrs.image_quality == "clear"

    def test_non_product(self):
        attrs = VisualAttributes(product_type="unknown", image_quality="non_product")
        assert attrs.image_quality == "non_product"


class TestFieldConfidence:
    def test_construction(self):
        fc = FieldConfidence(
            field_name="title",
            confidence=0.85,
            source="visible",
            evidence="clearly visible stroller",
        )
        assert fc.field_name == "title"
        assert 0 <= fc.confidence <= 1.0

    def test_json_roundtrip(self):
        fc = FieldConfidence(
            field_name="color", confidence=0.9, source="inferred", evidence="appears blue"
        )
        data = fc.model_dump()
        loaded = FieldConfidence.model_validate(data)
        assert loaded.field_name == fc.field_name
        assert loaded.confidence == fc.confidence


class TestPDPContent:
    def test_empty_content(self):
        content = PDPContent(language="en")
        assert content.title is None
        assert content.key_features == []
        assert content.safety_warnings == []
        assert content.search_tags == []

    def test_full_content(self):
        content = PDPContent(
            title="Baby Stroller with Canopy",
            short_description="A lightweight stroller.",
            key_features=["foldable", "canopy", "harness"],
            safety_warnings=["Always use harness"],
            age_suitability="0-36 months",
            search_tags=["stroller", "baby", "pram"],
            language="en",
        )
        assert len(content.key_features) == 3
        assert content.language == "en"

    def test_arabic_content(self):
        content = PDPContent(
            title="عربة أطفال قابلة للطي",
            short_description="عربة مريحة وخفيفة الوزن",
            key_features=["طيّ بيد واحدة", "مظلة واسعة"],
            language="ar",
        )
        assert content.language == "ar"
        assert "طي" in content.key_features[0]


class TestCritiqueFinding:
    def test_construction(self):
        finding = CritiqueFinding(
            field_name="key_features",
            issue="Feature not grounded",
            severity="error",
        )
        assert finding.severity == "error"
        assert finding.revised_confidence is None

    def test_with_revised_confidence(self):
        finding = CritiqueFinding(
            field_name="title",
            issue="Slightly over-specific",
            severity="warning",
            revised_confidence=0.6,
        )
        assert finding.revised_confidence == 0.6


class TestPDPResult:
    def test_full_result(self):
        result = PDPResult(
            content_en=PDPContent(title="Test Stroller", language="en"),
            content_ar=PDPContent(title="عربة اختبار", language="ar"),
            field_confidences=[
                FieldConfidence(
                    field_name="title", confidence=0.9, source="visible", evidence="clear"
                ),
            ],
            overall_confidence=0.85,
            review_required=False,
            critique_notes=[],
            detected_category="stroller",
            processing_time_ms=1234,
            correlation_id="abc123",
            model_used="test-model",
        )
        assert result.overall_confidence == 0.85
        assert not result.review_required
        assert result.model_used == "test-model"
        assert result.product_id  # auto-generated UUID

    def test_json_roundtrip(self):
        result = PDPResult(
            content_en=PDPContent(language="en"),
            content_ar=PDPContent(language="ar"),
            field_confidences=[],
            overall_confidence=0.0,
            review_required=True,
            critique_notes=[
                CritiqueFinding(
                    field_name="image", issue="Not a product", severity="error"
                )
            ],
        )
        json_str = result.model_dump_json()
        loaded = PDPResult.model_validate_json(json_str)
        assert loaded.review_required is True
        assert len(loaded.critique_notes) == 1
        assert loaded.critique_notes[0].severity == "error"

    def test_model_dump_keys(self):
        result = PDPResult(
            content_en=PDPContent(language="en"),
            content_ar=PDPContent(language="ar"),
            field_confidences=[],
            overall_confidence=0.5,
            review_required=True,
            critique_notes=[],
        )
        data = result.model_dump()
        required_keys = {
            "product_id", "content_en", "content_ar", "field_confidences",
            "overall_confidence", "review_required", "critique_notes",
            "detected_category", "processing_time_ms", "correlation_id", "model_used",
        }
        assert required_keys.issubset(set(data.keys()))
