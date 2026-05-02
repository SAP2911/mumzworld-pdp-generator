"""
tests/test_knowledge_base.py — unit tests for the knowledge base loader.
No API calls needed.
"""
import pytest

from src.knowledge_base import (
    get_arabic_conventions,
    get_category_context,
    load_kb,
)


class TestLoadKB:
    def test_loads_successfully(self):
        kb = load_kb()
        assert "categories" in kb
        assert "arabic_conventions" in kb

    def test_has_categories(self):
        kb = load_kb()
        cats = kb["categories"]
        assert len(cats) >= 10, f"Expected ≥10 categories, got {len(cats)}"

    def test_category_structure(self):
        kb = load_kb()
        for name, cat in kb["categories"].items():
            assert "safety_standards" in cat or "mandatory_warnings" in cat, (
                f"Category '{name}' missing safety info"
            )


class TestGetCategoryContext:
    def test_stroller(self):
        ctx = get_category_context("stroller")
        assert ctx.get("category") in ("stroller", "strollers")
        assert "mandatory_warnings" in ctx

    def test_car_seat(self):
        ctx = get_category_context("car_seat")
        assert ctx.get("category") is not None

    def test_unknown_product_type(self):
        ctx = get_category_context("flying_carpet")
        # Should return a general/fallback context, not crash
        assert isinstance(ctx, dict)
        assert ctx.get("category") in (None, "general", "flying_carpet")

    def test_feeding_bottle(self):
        ctx = get_category_context("feeding_bottle")
        assert isinstance(ctx.get("mandatory_warnings", []), list)


class TestArabicConventions:
    def test_loads(self):
        conv = get_arabic_conventions()
        assert isinstance(conv, dict)
        assert len(conv) > 0

    def test_has_avoid_translations(self):
        conv = get_arabic_conventions()
        assert "avoid_literal_translations" in conv
        translations = conv["avoid_literal_translations"]
        assert len(translations) > 0

    def test_has_preferred_adjectives(self):
        conv = get_arabic_conventions()
        assert "preferred_adjective_patterns" in conv
