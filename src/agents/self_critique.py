from __future__ import annotations

import json
import time

import structlog

from src.client import get_client, get_model_name
from src.retry import retry_on_rate_limit
from src.schemas import CritiqueFinding, PDPContent, VisualAttributes

log = structlog.get_logger(__name__)

CRITIQUE_SYSTEM_PROMPT = """You are a quality auditor for Mumzworld's catalog team. Review AI-generated PDP content before it reaches the catalog. Be strict — a false positive (flagging something fine) is better than missing a hallucination.

You check:
1. GROUNDING: Are English feature claims supported by the extracted attributes? Flag any claim not supported.
2. ARABIC QUALITY: Does the Arabic read like native Gulf marketing copy? Score 1-5 (5 = "could appear in a luxury Gulf baby catalog", 1 = "clearly translated English").
3. CONSISTENCY: Do EN and AR describe the same product? Flag contradictions.
4. SAFETY: Are safety warnings appropriate for the detected age group?

Return ONLY valid JSON:
{
  "findings": [
    {
      "field_name": "key_features",
      "issue": "Feature 'built-in MP3 player' not supported by extracted attributes",
      "severity": "error",
      "revised_confidence": 0.1
    }
  ],
  "arabic_nativeness_score": 4,
  "overall_assessment": "pass | review | reject",
  "critique_summary": "One sentence summary"
}

Severity levels:
- "info": minor suggestion
- "warning": quality issue but not a hallucination
- "error": hallucinated claim or critical quality failure → triggers review_required"""


def _parse_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def critique_pdp(
    attrs: VisualAttributes,
    content_en: PDPContent,
    content_ar: PDPContent,
    category_context: dict,
    correlation_id: str = "",
) -> tuple[list[CritiqueFinding], float, str]:
    """Returns (findings, arabic_nativeness_score, overall_assessment)."""
    start = time.time()
    client = get_client()

    en_features = "\n".join(f"  - {f}" for f in content_en.key_features)
    ar_features = "\n".join(f"  - {f}" for f in content_ar.key_features)

    user_message = f"""Review this PDP content for accuracy and quality.

EXTRACTED PRODUCT ATTRIBUTES (source of truth):
- Product type: {attrs.product_type}
- Color: {attrs.color or 'unknown'}
- Brand: {attrs.brand or 'not visible'}
- Visible features: {', '.join(attrs.visible_features) or 'none identified'}
- Material hints: {', '.join(attrs.material_hints) or 'none'}
- Age indicators: {attrs.age_indicators or 'none'}
- Image quality: {attrs.image_quality}
- Extraction notes: {attrs.extraction_notes}

GENERATED ENGLISH PDP:
Title: {content_en.title or '(null)'}
Description: {content_en.short_description or '(null)'}
Key features:
{en_features or '  (none)'}
Safety warnings: {'; '.join(content_en.safety_warnings) or 'none'}
Age suitability: {content_en.age_suitability or 'not set'}

GENERATED ARABIC PDP:
Title: {content_ar.title or '(null)'}
Description: {content_ar.short_description or '(null)'}
Key features:
{ar_features or '  (none)'}

Category: {category_context.get('category', 'general')}
Mandatory warnings that MUST appear: {'; '.join(category_context.get('mandatory_warnings', [])[:2])}"""

    try:
        response = retry_on_rate_limit(
            lambda: client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": CRITIQUE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            ),
            agent_name="critique",
            correlation_id=correlation_id,
        )
        raw = _parse_json(response.choices[0].message.content)
    except Exception as e:
        log.error("critique_failed", error=str(e), correlation_id=correlation_id)
        return [
            CritiqueFinding(
                field_name="critique",
                issue=f"Self-critique agent failed: {e}",
                severity="warning",
            )
        ], 3.0, "review"

    findings = [
        CritiqueFinding(
            field_name=f.get("field_name", "unknown"),
            issue=f.get("issue", ""),
            severity=f.get("severity", "info"),
            revised_confidence=f.get("revised_confidence"),
        )
        for f in raw.get("findings", [])
    ]

    nativeness_score = float(raw.get("arabic_nativeness_score", 3.0))
    overall_assessment = raw.get("overall_assessment", "review")

    log.info(
        "critique_complete",
        correlation_id=correlation_id,
        findings_count=len(findings),
        errors=sum(1 for f in findings if f.severity == "error"),
        arabic_score=nativeness_score,
        assessment=overall_assessment,
        elapsed_ms=int((time.time() - start) * 1000),
    )
    return findings, nativeness_score, overall_assessment
