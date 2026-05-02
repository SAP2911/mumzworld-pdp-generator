from __future__ import annotations

import structlog

from src.client import get_confidence_threshold, get_null_threshold
from src.schemas import (
    CritiqueFinding,
    FieldConfidence,
    PDPContent,
    PDPResult,
)

log = structlog.get_logger(__name__)

_FIELD_WEIGHTS = {
    "title": 0.20,
    "key_features": 0.30,
    "safety_warnings": 0.20,
    "short_description": 0.10,
    "age_suitability": 0.10,
    "arabic_content": 0.10,
}


def apply_confidence_gate(
    content_en: PDPContent,
    content_ar: PDPContent,
    all_confidences: list[FieldConfidence],
    critique_findings: list[CritiqueFinding],
    arabic_nativeness_score: float,
    overall_assessment: str,
    processing_time_ms: int,
    correlation_id: str,
    detected_category: str | None,
) -> PDPResult:
    """
    Nullifies fields below null_threshold, computes overall confidence,
    and sets review_required. Never leaves a hallucinated value in the output.
    """
    null_threshold = get_null_threshold()
    confidence_threshold = get_confidence_threshold()

    conf_map: dict[str, FieldConfidence] = {fc.field_name: fc for fc in all_confidences}
    gate_findings: list[CritiqueFinding] = []

    # ── Nullify low-confidence EN scalar fields ──────────────────────────────
    en_data = content_en.model_dump()
    for field in ("title", "short_description", "age_suitability"):
        fc = conf_map.get(field)
        if fc and fc.confidence < null_threshold:
            en_data[field] = None
            gate_findings.append(
                CritiqueFinding(
                    field_name=field,
                    issue=f"Nullified: confidence {fc.confidence:.2f} < threshold {null_threshold}",
                    severity="warning",
                )
            )

    # ── Arabic content gate ───────────────────────────────────────────────────
    ar_data = content_ar.model_dump()
    ar_confidence = arabic_nativeness_score / 5.0
    if ar_confidence < null_threshold:
        ar_data.update(
            title=None,
            short_description=None,
            key_features=[],
            safety_warnings=[],
            age_suitability=None,
        )
        gate_findings.append(
            CritiqueFinding(
                field_name="arabic_content",
                issue=f"Arabic content nullified: nativeness score {arabic_nativeness_score:.1f}/5 is below threshold",
                severity="error",
                revised_confidence=ar_confidence,
            )
        )

    # ── Weighted overall confidence ───────────────────────────────────────────
    weighted_sum = 0.0
    weight_total = 0.0
    for field, weight in _FIELD_WEIGHTS.items():
        if field == "arabic_content":
            score = ar_confidence
        else:
            fc = conf_map.get(field)
            score = fc.confidence if fc else 0.5
        weighted_sum += score * weight
        weight_total += weight

    overall_confidence = round(weighted_sum / weight_total if weight_total > 0 else 0.0, 2)

    all_findings = critique_findings + gate_findings

    review_required = (
        overall_confidence < confidence_threshold
        or any(f.severity == "error" for f in all_findings)
        or overall_assessment in ("review", "reject")
    )

    log.info(
        "confidence_gate_applied",
        correlation_id=correlation_id,
        overall_confidence=overall_confidence,
        review_required=review_required,
        nullified_fields=len(gate_findings),
        arabic_nativeness=arabic_nativeness_score,
    )

    return PDPResult(
        content_en=PDPContent(**en_data),
        content_ar=PDPContent(**ar_data),
        field_confidences=all_confidences,
        overall_confidence=overall_confidence,
        review_required=review_required,
        critique_notes=all_findings,
        detected_category=detected_category,
        processing_time_ms=processing_time_ms,
        correlation_id=correlation_id,
    )
