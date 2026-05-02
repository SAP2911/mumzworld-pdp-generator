"""
smoke_test.py — full end-to-end pipeline smoke test.

Run real pipeline:  python smoke_test.py
Run mock (no API):  set MOCK_MODE=1 && python smoke_test.py
"""
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"

if MOCK_MODE:
    from src.mock_pipeline import run_mock as run_fn
    print("[MOCK MODE] Using synthetic data — no API calls will be made.\n")
    result = run_fn("data/sample_images/stroller_clear.jpg")
else:
    from src.pipeline import run as run_fn
    img = Path("data/sample_images/stroller_clear.jpg")
    print(f"Image exists: {img.exists()}")
    print("Running pipeline...")
    result = run_fn(str(img))

print(f"\n{'='*55}")
print(f"product_id        : {result.product_id}")
print(f"model_used        : {result.model_used}")
print(f"detected_category : {result.detected_category}")
print(f"overall_confidence: {result.overall_confidence:.2f}")
print(f"review_required   : {result.review_required}")

print(f"\n--- English ---")
print(f"title       : {result.content_en.title}")
print(f"description : {result.content_en.short_description}")
print(f"features    : {len(result.content_en.key_features)} bullets")
for f in result.content_en.key_features:
    print(f"  - {f}")
if result.content_en.search_tags:
    print(f"search_tags : {result.content_en.search_tags[:5]} ...")

print(f"\n--- Arabic ---")
print(f"title       : {result.content_ar.title}")
print(f"description : {result.content_ar.short_description}")
print(f"features    : {len(result.content_ar.key_features)} bullets")

print(f"\n--- Critique & Confidence ---")
print(f"findings    : {len(result.critique_notes)}")
for note in result.critique_notes:
    print(f"  [{note.severity}] {note.field_name}: {note.issue}")

print(f"\n{'='*55}")
passed = result.content_en.title is not None
print("SMOKE TEST:", "PASS" if passed else "FAIL (en title is None)")
sys.exit(0 if passed else 1)
