"""
pipeline.py — single entry point for the entire PDP generation pipeline.

Usage:
    from src.pipeline import run
    result = run("path/to/product_image.jpg")
    print(result.model_dump_json(indent=2))
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import structlog

from src.agents.pdp_generator import generate_pdp_ar, generate_pdp_en
from src.agents.self_critique import critique_pdp
from src.agents.vision_extractor import extract_visual_attributes, is_valid_product_image
from src.client import get_model_name
from src.confidence_gate import apply_confidence_gate
from src.knowledge_base import get_category_context
from src.schemas import CritiqueFinding, PDPContent, PDPResult

log = structlog.get_logger(__name__)


def run(image_path: str | Path) -> PDPResult:
    """
    Full pipeline: image path -> PDPResult.
    This is the single callable used by both app.py and evals/run_evals.py.
    """
    correlation_id = str(uuid.uuid4())[:8]
    start = time.time()
    log.info("pipeline_start", correlation_id=correlation_id, image=str(image_path))

    # Phase 2: Vision extraction
    attrs, vision_confidences = extract_visual_attributes(image_path, correlation_id)

    # Non-product short-circuit
    if not is_valid_product_image(attrs):
        elapsed = int((time.time() - start) * 1000)
        log.warning("pipeline_non_product", correlation_id=correlation_id)
        return PDPResult(
            content_en=PDPContent(language="en"),
            content_ar=PDPContent(language="ar"),
            field_confidences=[],
            overall_confidence=0.0,
            review_required=True,
            critique_notes=[
                CritiqueFinding(
                    field_name="image",
                    issue="Image does not appear to contain a product. Manual catalog entry required.",
                    severity="error",
                )
            ],
            detected_category=None,
            processing_time_ms=elapsed,
            correlation_id=correlation_id,
            model_used=get_model_name(),
        )

    # Knowledge base lookup (lightweight RAG)
    category_context = get_category_context(attrs.product_type)
    detected_category = category_context.get("category")

    # Phase 3a: English PDP
    content_en, en_confidences = generate_pdp_en(
        attrs, category_context, vision_confidences, correlation_id
    )

    # Phase 3b: Arabic PDP (separate pass -- not a translation)
    content_ar, ar_confidences, arabic_nativeness_score = generate_pdp_ar(
        attrs, category_context, vision_confidences, correlation_id
    )

    # Phase 3c: Self-critique loop
    findings, arabic_score, overall_assessment = critique_pdp(
        attrs, content_en, content_ar, category_context, correlation_id
    )

    # Confidence gate + assemble result
    all_confidences = vision_confidences + en_confidences + ar_confidences
    elapsed = int((time.time() - start) * 1000)

    result = apply_confidence_gate(
        content_en,
        content_ar,
        all_confidences,
        findings,
        arabic_score,
        overall_assessment,
        elapsed,
        correlation_id,
        detected_category,
    )
    result.model_used = get_model_name()

    log.info(
        "pipeline_complete",
        correlation_id=correlation_id,
        category=detected_category,
        overall_confidence=result.overall_confidence,
        review_required=result.review_required,
        model=result.model_used,
        elapsed_ms=elapsed,
    )
    return result
