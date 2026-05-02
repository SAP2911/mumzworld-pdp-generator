from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import structlog
from PIL import Image

from src.client import get_client, get_model_name
from src.retry import retry_on_rate_limit
from src.schemas import EvidenceSource, FieldConfidence, VisualAttributes

_VALID_SOURCES: set[str] = {"visible", "inferred", "category_standard", "uncertain"}


def _coerce_source(s: str) -> EvidenceSource:
    return s if s in _VALID_SOURCES else "inferred"  # type: ignore[return-value]

log = structlog.get_logger(__name__)

VISION_SYSTEM_PROMPT = """You are a product catalog specialist for Mumzworld, the largest e-commerce platform for mothers in the GCC region. Extract product attributes from images ONLY based on what is visible — including any text, labels, or packaging in the image.

CRITICAL RULES — violating these is worse than leaving a field blank:
1. NEVER invent brand names, model numbers, or specifications not visible in the image.
2. If you cannot see something clearly, set it to null and mark confidence below 0.5.
3. "visible" = you can literally see it. "inferred" = reasonable educated guess. Be honest about which.
4. image_quality guide:
   - "clear" → physical product photo with good lighting and detail
   - "partial" → product partially visible, OR image shows packaging/labels/text describing the product
   - "blurry" → product present but difficult to see details
   - "non_product" → ONLY use this for images with zero product relevance: pure landscapes, food photos, abstract art, completely black/blank images, or images of people with no product present
   Text-only product spec sheets and product packaging ARE partial — not non_product.
5. Confidence 0.9+ means you would stake the catalog listing on it. 0.3 means "I think I see something but I'm not sure."

Return a JSON object with EXACTLY these fields:
{
  "product_type": "string — the product category (e.g. stroller, feeding bottle, car seat)",
  "color": "string or null",
  "brand": "string or null — ONLY if a brand name/logo is clearly readable",
  "material_hints": ["array of visible material clues"],
  "visible_features": ["array of features you can actually see or read from labels"],
  "age_indicators": "string or null — any age markings, packaging text, or size indicators",
  "accessories_visible": ["array — any accessories visible alongside the main product"],
  "image_quality": "clear | partial | blurry | non_product",
  "extraction_notes": "string — any caveats or ambiguities you want to flag",
  "field_confidences": [
    {"field_name": "product_type", "confidence": 0.95, "source": "visible", "evidence": "clearly visible stroller in frame"},
    {"field_name": "color", "confidence": 0.9, "source": "visible", "evidence": "dark navy fabric clearly visible"},
    {"field_name": "brand", "confidence": 0.0, "source": "uncertain", "evidence": "no brand markings visible in image"}
  ]
}"""


def _encode_image_b64(image_path: str | Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for the image at image_path."""
    path = Path(image_path)
    suffix = path.suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_type_map.get(suffix, "image/jpeg")
    with open(path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    return b64_data, media_type


def _parse_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def extract_visual_attributes(
    image_path: str | Path,
    correlation_id: str = "",
) -> tuple[VisualAttributes, list[FieldConfidence]]:
    """Phase 2 entry point. Image → (VisualAttributes, list[FieldConfidence])."""
    start = time.time()
    log.info("vision_extraction_start", correlation_id=correlation_id, image=str(image_path))

    try:
        Image.open(image_path).verify()
    except Exception as e:
        log.error("vision_image_open_failed", error=str(e), correlation_id=correlation_id)
        return _fallback_attrs("Could not open image file"), []

    try:
        b64_data, media_type = _encode_image_b64(image_path)
    except Exception as e:
        log.error("vision_encode_failed", error=str(e), correlation_id=correlation_id)
        return _fallback_attrs(f"Could not encode image: {e}"), []

    client = get_client()

    try:
        response = retry_on_rate_limit(
            lambda: client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64_data}"},
                            },
                            {
                                "type": "text",
                                "text": "Extract all visible product attributes from this image. Be precise and honest about what you can and cannot see.",
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            ),
            agent_name="vision",
            correlation_id=correlation_id,
        )
        raw = _parse_json_response(response.choices[0].message.content)
    except Exception as e:
        note = "Rate limit exceeded — try again after midnight UTC" if "429" in str(e) else f"Extraction failed: {e}"
        return _fallback_attrs(note), []

    elapsed_ms = int((time.time() - start) * 1000)

    field_confidences = [
        FieldConfidence(
            field_name=fc.get("field_name", "unknown"),
            confidence=float(fc.get("confidence", 0.5)),
            source=_coerce_source(fc.get("source", "uncertain")),
            evidence=fc.get("evidence", ""),
        )
        for fc in raw.get("field_confidences", [])
    ]

    product_type = raw.get("product_type") or "unknown"
    image_quality = raw.get("image_quality") or "non_product"
    # If model identified a product type but still said non_product, it likely
    # means the image contains product text/labels — treat as partial.
    if image_quality == "non_product" and product_type not in ("unknown", ""):
        image_quality = "partial"

    attrs = VisualAttributes(
        product_type=product_type,
        color=raw.get("color"),
        brand=raw.get("brand"),
        material_hints=raw.get("material_hints", []),
        visible_features=raw.get("visible_features", []),
        age_indicators=raw.get("age_indicators"),
        accessories_visible=raw.get("accessories_visible", []),
        image_quality=image_quality,
        extraction_notes=raw.get("extraction_notes", ""),
    )

    log.info(
        "vision_extraction_complete",
        correlation_id=correlation_id,
        product_type=attrs.product_type,
        image_quality=attrs.image_quality,
        features_count=len(attrs.visible_features),
        elapsed_ms=elapsed_ms,
    )
    return attrs, field_confidences


def is_valid_product_image(attrs: VisualAttributes) -> bool:
    return attrs.image_quality != "non_product"


def _fallback_attrs(note: str) -> VisualAttributes:
    return VisualAttributes(
        product_type="unknown",
        image_quality="non_product",
        extraction_notes=note,
    )
