from __future__ import annotations

import json
import time

import structlog

from src.client import get_client, get_model_name
from src.knowledge_base import get_arabic_conventions
from src.retry import retry_on_rate_limit
from src.schemas import FieldConfidence, PDPContent, VisualAttributes

log = structlog.get_logger(__name__)

# ── English system prompt ────────────────────────────────────────────────────

EN_SYSTEM_PROMPT = """You are a product copywriter for Mumzworld, the largest baby & mother e-commerce platform in the GCC. Write precise, benefit-led Product Detail Page content in English.

RULES:
1. Every feature bullet must be grounded in the extracted product attributes provided. Do not invent features.
2. Title must be ≤70 characters, specific, and SEO-friendly. Not "High-Quality Baby Stroller" — prefer "Compact Foldable Baby Stroller with Adjustable Canopy, 0-36m".
3. Short description is 2-3 sentences. Lead with the primary benefit. No superlatives without evidence.
4. If a spec cannot be determined from the provided attributes, omit it — do not guess.
5. Safety warnings come from two sources — include BOTH:
   (a) The mandatory_warnings listed in the category context: copy them faithfully, adapt wording only to fit the specific product.
   (b) Feature-derived warnings from the extracted attributes: if you see small parts → "Choking hazard — small parts. Not suitable for children under 3 years."; batteries visible → "Contains batteries — keep out of reach of young children"; cords/straps → "Ensure cords/straps are not accessible to unsupervised children"; sharp edges → "Check for sharp edges before use."
   Never write generic placeholders like "Check product label for safety information" unless no other warning applies.
6. Assign honest confidence scores per field.

Return ONLY valid JSON with this exact structure:
{
  "title": "string ≤70 chars or null",
  "short_description": "string or null",
  "key_features": ["max 7 bullets, each grounded in provided attributes"],
  "safety_warnings": ["from category standards"],
  "age_suitability": "string or null",
  "search_tags": ["10-15 SEO keywords"],
  "field_confidences": [
    {"field_name": "title", "confidence": 0.85, "evidence": "product type and visible features are clear"},
    {"field_name": "key_features", "confidence": 0.78, "evidence": "5 features confirmed from image extraction"}
  ]
}"""

# ── Arabic system prompt ─────────────────────────────────────────────────────

AR_SYSTEM_PROMPT = """أنت كاتب محتوى متخصص في منصة "مامز وورلد"، أكبر منصة تجارة إلكترونية للأمهات في منطقة الخليج العربي. اكتب محتوى صفحات المنتجات بالعربية الخليجية الرسمية الدافئة.

قواعد لا تُكسَر:
١. اكتب المحتوى بالعربية أولاً — لا تترجم من الإنجليزية، بل أنشئ محتوى عربياً أصيلاً من سمات المنتج.
٢. استخدم أسلوباً تسويقياً خليجياً طبيعياً: "مريح لطفلكِ"، "صُمِّم خصيصاً لـ..."، "يمنح طفلك..."
٣. تجنب الترجمة الحرفية — "ناعم وأملس" ترجمة حرفية، أما "ناعم الملمس ومريح" فهي عربية أصيلة.
٤. العنوان ≤70 حرفاً ويبدأ باسم المنتج.
٥. إذا لم تتمكن من تحديد مواصفة، اتركها فارغة — لا تخترع معلومات.
٦. حدد درجة الثقة لكل حقل.

أعِد JSON فقط بهذا الهيكل بالضبط:
{
  "title": "عنوان ≤70 حرف أو null",
  "short_description": "وصف 2-3 جمل أو null",
  "key_features": ["حتى 7 نقاط مستندة إلى سمات المنتج"],
  "safety_warnings": ["تحذيرات السلامة من المعايير المقدمة"],
  "age_suitability": "الفئة العمرية أو null",
  "search_tags": ["10-15 كلمة بحثية باللغتين العربية والإنجليزية"],
  "arabic_nativeness_self_score": 4,
  "field_confidences": [
    {"field_name": "title", "confidence": 0.85, "evidence": "نوع المنتج واضح من الصورة"}
  ]
}"""


def _parse_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def _build_attrs_summary(attrs: VisualAttributes, category_context: dict) -> str:
    return f"""Product type: {attrs.product_type}
Color: {attrs.color or 'not determined'}
Brand: {attrs.brand or 'not visible — do not invent one'}
Visible features: {', '.join(attrs.visible_features) or 'none identified'}
Material hints: {', '.join(attrs.material_hints) or 'not determined'}
Age indicators: {attrs.age_indicators or 'not visible'}
Accessories visible: {', '.join(attrs.accessories_visible) or 'none'}
Image quality: {attrs.image_quality}
Extraction notes: {attrs.extraction_notes}

Category context (from knowledge base):
- Category: {category_context.get('category', 'general')}
- Standard age range: {category_context.get('age_range', 'not specified')}
- Mandatory safety warnings: {'; '.join(category_context.get('mandatory_warnings', []))}
- Typical features for this category: {', '.join(category_context.get('common_features', [])[:6])}"""


def generate_pdp_en(
    attrs: VisualAttributes,
    category_context: dict,
    vision_confidences: list[FieldConfidence],
    correlation_id: str = "",
) -> tuple[PDPContent, list[FieldConfidence]]:
    start = time.time()
    client = get_client()
    attrs_summary = _build_attrs_summary(attrs, category_context)

    try:
        response = retry_on_rate_limit(
            lambda: client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": EN_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Generate English PDP content for this product:\n\n{attrs_summary}",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            ),
            agent_name="pdp_en",
            correlation_id=correlation_id,
        )
        raw = _parse_json(response.choices[0].message.content)
    except Exception as e:
        log.error("pdp_en_failed", error=str(e), correlation_id=correlation_id)
        return PDPContent(language="en"), []

    confidences = [
        FieldConfidence(
            field_name=fc.get("field_name", "unknown"),
            confidence=float(fc.get("confidence", 0.5)),
            source="inferred",
            evidence=fc.get("evidence", ""),
        )
        for fc in raw.get("field_confidences", [])
    ]

    raw_title = raw.get("title")
    content = PDPContent(
        title=raw_title[:70] if raw_title else None,
        short_description=raw.get("short_description"),
        key_features=raw.get("key_features", [])[:7],
        safety_warnings=raw.get("safety_warnings", []),
        age_suitability=raw.get("age_suitability"),
        search_tags=raw.get("search_tags", [])[:15],
        language="en",
    )

    log.info(
        "pdp_en_generated",
        correlation_id=correlation_id,
        title=content.title,
        features=len(content.key_features),
        elapsed_ms=int((time.time() - start) * 1000),
    )
    return content, confidences


def generate_pdp_ar(
    attrs: VisualAttributes,
    category_context: dict,
    vision_confidences: list[FieldConfidence],
    correlation_id: str = "",
) -> tuple[PDPContent, list[FieldConfidence], float]:
    """Returns (PDPContent, confidences, arabic_nativeness_self_score 1-5)."""
    start = time.time()
    conventions = get_arabic_conventions()
    client = get_client()

    attrs_summary = _build_attrs_summary(attrs, category_context)
    arabic_name = category_context.get("arabic_category_name", "منتج")
    adjectives = ", ".join(category_context.get("arabic_marketing_adjectives", []))
    phrases = "\n".join(f"- {p}" for p in category_context.get("arabic_feature_phrases", [])[:4])
    avoid = "\n".join(
        f"- تجنب: '{x['bad_arabic']}' → استخدم: '{x['good_arabic']}'"
        for x in conventions.get("avoid_literal_translations", [])[:3]
    )

    user_message = f"""أنشئ محتوى صفحة المنتج (PDP) بالعربية لهذا المنتج:

{attrs_summary}

السياق العربي:
- اسم الفئة: {arabic_name}
- صفات تسويقية مناسبة: {adjectives}
- جمل وصفية مقترحة:
{phrases}

أمثلة للترجمات الصحيحة:
{avoid}"""

    try:
        response = retry_on_rate_limit(
            lambda: client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": AR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            ),
            agent_name="pdp_ar",
            correlation_id=correlation_id,
        )
        raw = _parse_json(response.choices[0].message.content)
    except Exception as e:
        log.error("pdp_ar_failed", error=str(e), correlation_id=correlation_id)
        return PDPContent(language="ar"), [], 1.0

    nativeness_score = float(raw.get("arabic_nativeness_self_score", 3.0))

    confidences = [
        FieldConfidence(
            field_name=f"ar_{fc.get('field_name', 'unknown')}",
            confidence=float(fc.get("confidence", 0.5)),
            source="inferred",
            evidence=fc.get("evidence", ""),
        )
        for fc in raw.get("field_confidences", [])
    ]

    raw_title_ar = raw.get("title")
    content = PDPContent(
        title=raw_title_ar[:70] if raw_title_ar else None,
        short_description=raw.get("short_description"),
        key_features=raw.get("key_features", [])[:7],
        safety_warnings=raw.get("safety_warnings", []),
        age_suitability=raw.get("age_suitability"),
        search_tags=raw.get("search_tags", [])[:15],
        language="ar",
    )

    log.info(
        "pdp_ar_generated",
        correlation_id=correlation_id,
        nativeness_score=nativeness_score,
        features=len(content.key_features),
        elapsed_ms=int((time.time() - start) * 1000),
    )
    return content, confidences, nativeness_score
