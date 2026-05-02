"""
tests/test_confidence_gate.py — unit tests for the confidence gating logic.
No API calls needed.
"""
import pytest

from src.confidence_gate import apply_confidence_gate
from src.schemas import CritiqueFinding, FieldConfidence, PDPContent


class TestApplyConfidenceGate:
    def _make_content(self, lang: str, title: str = "Test Product") -> PDPContent:
        return PDPContent(
            title=title,
            short_description="A test product",
            key_features=["feature1", "feature2"],
            safety_warnings=["warning1"],
            age_suitability="0-36 months",
            search_tags=["test"],
            language=lang,
        )

    def test_high_confidence_passes(self):
        result = apply_confidence_gate(
            self._make_content("en"),
            self._make_content("ar", "منتج اختبار"),
            [
                FieldConfidence(field_name="title", confidence=0.9, source="visible", evidence="clear"),
                FieldConfidence(field_name="key_features", confidence=0.85, source="visible", evidence="clear"),
            ],
            [],   # no critique findings
            4.0,  # arabic_nativeness_score
            "pass",  # overall_assessment
            100,  # processing_time_ms
            "test1",  # correlation_id
            "stroller",  # detected_category
        )
        assert not result.review_required
        assert result.overall_confidence >= 0.70

    def test_low_confidence_triggers_review(self):
        result = apply_confidence_gate(
            self._make_content("en"),
            self._make_content("ar"),
            [
                FieldConfidence(field_name="title", confidence=0.3, source="uncertain", evidence="blurry"),
                FieldConfidence(field_name="key_features", confidence=0.2, source="uncertain", evidence="blurry"),
            ],
            [],
            2.0,
            "review",
            100,
            "test2",
            None,
        )
        assert result.review_required

    def test_error_finding_triggers_review(self):
        result = apply_confidence_gate(
            self._make_content("en"),
            self._make_content("ar"),
            [
                FieldConfidence(field_name="title", confidence=0.9, source="visible", evidence="clear"),
            ],
            [
                CritiqueFinding(
                    field_name="key_features",
                    issue="Hallucinated feature",
                    severity="error",
                ),
            ],
            4.0,
            "reject",
            100,
            "test3",
            "stroller",
        )
        assert result.review_required

    def test_result_has_all_fields(self):
        result = apply_confidence_gate(
            self._make_content("en"),
            self._make_content("ar"),
            [],
            [],
            3.5,
            "pass",
            42,
            "test4",
            "bottle",
        )
        assert result.correlation_id == "test4"
        assert result.detected_category == "bottle"
        assert result.processing_time_ms == 42
        assert result.content_en.language == "en"
        assert result.content_ar.language == "ar"
