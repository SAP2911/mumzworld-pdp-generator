"""
tests/test_mock_pipeline.py — unit tests for the mock pipeline.
No API calls needed.
"""
import pytest

from src.mock_pipeline import run_mock, MOCK_ATTRS, MOCK_EN, MOCK_AR


class TestMockPipeline:
    def test_returns_pdp_result(self):
        result = run_mock()
        assert result.content_en.title is not None
        assert result.content_ar.title is not None

    def test_mock_has_features(self):
        result = run_mock()
        assert len(result.content_en.key_features) >= 5
        assert len(result.content_ar.key_features) >= 5

    def test_mock_has_safety_warnings(self):
        result = run_mock()
        assert len(result.content_en.safety_warnings) >= 2
        assert len(result.content_ar.safety_warnings) >= 2

    def test_mock_has_search_tags(self):
        result = run_mock()
        assert len(result.content_en.search_tags) >= 10
        assert len(result.content_ar.search_tags) >= 10

    def test_mock_has_confidences(self):
        result = run_mock()
        assert len(result.field_confidences) >= 5
        for fc in result.field_confidences:
            assert 0 <= fc.confidence <= 1.0

    def test_mock_model_name(self):
        result = run_mock()
        assert result.model_used == "mock"

    def test_mock_no_review_required(self):
        result = run_mock()
        assert not result.review_required

    def test_mock_category(self):
        result = run_mock()
        assert result.detected_category == "strollers"

    def test_mock_correlation_id(self):
        r1 = run_mock()
        r2 = run_mock()
        assert r1.correlation_id != r2.correlation_id  # unique per call

    def test_mock_json_serializable(self):
        result = run_mock()
        json_str = result.model_dump_json()
        assert len(json_str) > 1000  # substantial content

    def test_mock_attrs(self):
        assert MOCK_ATTRS.product_type == "stroller"
        assert MOCK_ATTRS.image_quality == "clear"
        assert len(MOCK_ATTRS.visible_features) >= 4

    def test_mock_arabic_content(self):
        assert MOCK_AR.language == "ar"
        # Arabic title should contain Arabic chars
        assert any("\u0600" <= c <= "\u06ff" for c in MOCK_AR.title)

    def test_mock_english_content(self):
        assert MOCK_EN.language == "en"
        assert len(MOCK_EN.title) <= 70  # SEO constraint
