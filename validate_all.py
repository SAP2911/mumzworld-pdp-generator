"""
validate_all.py — comprehensive validation that every component works.
Run: python validate_all.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Test 1: All src imports
from src.schemas import PDPResult, VisualAttributes, PDPContent, FieldConfidence, CritiqueFinding
from src.client import get_client, get_model_name, get_confidence_threshold, get_null_threshold
from src.knowledge_base import get_category_context, get_arabic_conventions
from src.confidence_gate import apply_confidence_gate
from src.pipeline import run
from src.mock_pipeline import run_mock
from src.agents.vision_extractor import extract_visual_attributes, is_valid_product_image
from src.agents.pdp_generator import generate_pdp_en, generate_pdp_ar
from src.agents.self_critique import critique_pdp
print("1. All src imports:     OK")

# Test 2: Eval runner imports
sys.path.insert(0, ".")
from evals.run_evals import main, evaluate_case, compute_metrics, check_hallucination, generate_evals_md
print("2. Eval runner imports: OK")

# Test 3: Knowledge base loads
ctx = get_category_context("stroller")
cat = ctx.get("category", "MISSING")
assert cat in ("stroller", "strollers"), f"Expected stroller(s), got {cat}"
print(f"3. Knowledge base:     OK ({len(ctx)} keys for stroller)")

# Test 4: Arabic conventions
arconv = get_arabic_conventions()
assert "avoid_literal_translations" in arconv, "Arabic conventions missing expected key"
print(f"4. Arabic conventions:  OK ({len(arconv)} keys)")

# Test 5: Client config
print(f"5. Model name:         {get_model_name()}")
print(f"6. Conf threshold:     {get_confidence_threshold()}")
print(f"7. Null threshold:     {get_null_threshold()}")

# Test 6: Mock pipeline
result = run_mock()
assert result.content_en.title is not None, "EN title should not be None"
assert result.content_ar.title is not None, "AR title should not be None"
assert result.overall_confidence > 0.5, "Confidence too low"
assert not result.review_required, "Should not require review in mock"
print(f"8. Mock pipeline:      PASS (confidence={result.overall_confidence})")

# Test 7: Schema round-trip
json_str = result.model_dump_json()
loaded = PDPResult.model_validate_json(json_str)
assert loaded.content_en.title == result.content_en.title
print(f"9. JSON round-trip:    PASS ({len(json_str)} bytes)")

# Test 8: Check test cases file
import json
from pathlib import Path
with open("data/test_cases.json", encoding="utf-8") as f:
    tc = json.load(f)
cases = tc["test_cases"]
assert len(cases) == 15, f"Expected 15 test cases, got {len(cases)}"
imgs = list(Path("data/sample_images").glob("*.jpg"))
assert len(imgs) >= 15, f"Expected 15+ images, got {len(imgs)}"
print(f"10. Test data:          {len(cases)} cases, {len(imgs)} images")

print(f"\n{'='*40}")
print("ALL CHECKS PASSED")
