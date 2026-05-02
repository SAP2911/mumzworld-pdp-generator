"""
Mumzworld PDP Generator — Streamlit Demo
Run: streamlit run app.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Mumzworld PDP Generator",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Arabic RTL block */
.arabic-block {
    direction: rtl;
    text-align: right;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 1rem;
    line-height: 2;
}
.arabic-block ul { padding-right: 1.4rem; padding-left: 0; }

/* Confidence colours */
.conf-high { color: #16a34a; font-weight: 700; }
.conf-mid  { color: #d97706; font-weight: 700; }
.conf-low  { color: #dc2626; font-weight: 700; }

/* Null placeholder */
.null-field { color: #9ca3af; font-style: italic; }

/* Field label */
.field-label { font-weight: 700; margin-bottom: 2px; }

/* Tag pill */
.tag { display: inline-block; background: #1e3a5f; color: #93c5fd;
       border-radius: 999px; padding: 2px 10px; margin: 2px;
       font-size: 0.78rem; }
</style>
""", unsafe_allow_html=True)

# ── Config ────────────────────────────────────────────────────────────────────
from src.client import get_model_name as _get_model_name
_MODEL_DISPLAY = _get_model_name().split("/")[-1].replace(":free", "")
_MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛒 Mumzworld PDP Generator")
    st.caption("AI Engineering Intern Assessment · Sai Pranav H R")
    st.divider()

    st.markdown("### 📁 Sample Images")
    st.caption("Click to load a sample product")
    samples_dir = Path("data/sample_images")
    if samples_dir.exists():
        samples = sorted(samples_dir.glob("*.jpg"))
        for s in samples:
            label = s.stem.replace("_", " ").title()
            if st.button(label, key=f"s_{s.stem}", use_container_width=True):
                st.session_state["sample_path"] = str(s)
                st.session_state["sample_name"] = label
                # Clear old result when a new sample is selected
                st.session_state.pop("last_result", None)
                st.session_state.pop("last_image_id", None)
    else:
        st.warning("Run `python data/download_samples.py` to generate samples.")

    st.divider()
    mode_badge = "🔵 MOCK MODE" if _MOCK_MODE else f"🟢 {_MODEL_DISPLAY}"
    st.caption(f"Model: {mode_badge}")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🛒 Mumzworld PDP Generator")
st.caption(
    "Upload any product image → get a publish-ready **English + Arabic** Product Detail Page "
    "with confidence scoring, safety warnings, and hallucination detection."
)
st.divider()

# ── Layout: left = image panel, right = results ───────────────────────────────
col_left, col_right = st.columns([1, 2], gap="large")

with col_left:
    st.markdown("#### 📷 Product Image")

    uploaded = st.file_uploader(
        "Drop a PNG / JPG / WebP here",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="visible",
    )

    # Detect when user clears the uploader → wipe old results
    prev_id = st.session_state.get("last_image_id")
    curr_id = uploaded.file_id if uploaded else None
    if prev_id and curr_id != prev_id:
        st.session_state.pop("last_result", None)
    st.session_state["last_image_id"] = curr_id

    # Also clear if uploader is empty and no sample selected
    if not uploaded and not st.session_state.get("sample_path"):
        st.session_state.pop("last_result", None)

    sample_path = st.session_state.get("sample_path")
    sample_name = st.session_state.get("sample_name", "")

    if uploaded:
        st.image(uploaded, use_column_width=True)
    elif sample_path and Path(sample_path).exists():
        st.image(sample_path, caption=sample_name, use_column_width=True)
    else:
        st.markdown(
            "<div style='border:2px dashed #374151; border-radius:8px; "
            "padding:40px; text-align:center; color:#6b7280;'>"
            "📦 Upload a product image<br>or select a sample →"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("")  # spacer
    run_clicked = st.button("⚡ Generate PDP", type="primary", use_container_width=True)
    st.caption("⏱ ~5–10 seconds · 4 AI passes (vision → EN → AR → critique)")

    # Clear button
    if st.session_state.get("last_result"):
        if st.button("🗑 Clear results", use_container_width=True):
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_image_id", None)
            st.session_state.pop("sample_path", None)
            st.session_state.pop("sample_name", None)
            st.rerun()

# ── Run pipeline ──────────────────────────────────────────────────────────────
result = None

with col_right:
    if run_clicked:
        image_source: str | None = None
        tmp_path: str | None = None

        if uploaded:
            suffix = Path(uploaded.name).suffix or ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(uploaded.read())
            tmp.close()
            image_source = tmp.name
            tmp_path = tmp.name
        elif sample_path:
            image_source = sample_path

        if not image_source:
            st.warning("⬅ Upload an image or pick a sample from the sidebar first.")
        else:
            steps = st.empty()
            try:
                if _MOCK_MODE:
                    steps.info("🔵 Mock mode — returning pre-built result…")
                    from src.mock_pipeline import run_mock
                    result = run_mock(image_source)
                    steps.success("✅ Done (mock mode)")
                else:
                    # Step-by-step progress
                    steps.markdown("⏳ **Step 1 / 4** — Vision extraction: reading the image…")
                    from src.agents.vision_extractor import extract_visual_attributes, is_valid_product_image
                    from src.knowledge_base import get_category_context
                    from src.agents.pdp_generator import generate_pdp_en, generate_pdp_ar
                    from src.agents.self_critique import critique_pdp
                    from src.confidence_gate import apply_confidence_gate
                    from src.client import get_model_name
                    from src.schemas import CritiqueFinding, PDPContent, PDPResult
                    import uuid, time as _time
                    correlation_id = str(uuid.uuid4())[:8]
                    t0 = _time.time()

                    attrs, vision_conf = extract_visual_attributes(image_source, correlation_id)

                    if not is_valid_product_image(attrs):
                        steps.warning("⚠️ No product detected — image flagged for review.")
                        result = PDPResult(
                            content_en=PDPContent(language="en"),
                            content_ar=PDPContent(language="ar"),
                            field_confidences=[],
                            overall_confidence=0.0,
                            review_required=True,
                            critique_notes=[CritiqueFinding(field_name="image",
                                issue="Image does not appear to contain a product.",
                                severity="error")],
                            detected_category=None,
                            processing_time_ms=int((_time.time()-t0)*1000),
                            correlation_id=correlation_id,
                            model_used=get_model_name(),
                        )
                    else:
                        steps.markdown(f"✅ **Step 1 / 4** — Vision done: `{attrs.product_type}` detected  \n"
                                       f"⏳ **Step 2 / 4** — Generating English copy…")
                        category_ctx = get_category_context(attrs.product_type)

                        content_en, en_conf = generate_pdp_en(attrs, category_ctx, vision_conf, correlation_id)

                        steps.markdown(f"✅ **Step 1 / 4** — Vision: `{attrs.product_type}`  \n"
                                       f"✅ **Step 2 / 4** — English PDP ready  \n"
                                       f"⏳ **Step 3 / 4** — Generating Arabic copy…")

                        content_ar, ar_conf, nativeness = generate_pdp_ar(attrs, category_ctx, vision_conf, correlation_id)

                        steps.markdown(f"✅ **Step 1 / 4** — Vision: `{attrs.product_type}`  \n"
                                       f"✅ **Step 2 / 4** — English PDP ready  \n"
                                       f"✅ **Step 3 / 4** — Arabic PDP ready (nativeness {nativeness:.0f}/5)  \n"
                                       f"⏳ **Step 4 / 4** — Self-critique: checking for hallucinations…")

                        findings, arabic_score, assessment = critique_pdp(
                            attrs, content_en, content_ar, category_ctx, correlation_id
                        )

                        elapsed = int((_time.time()-t0)*1000)
                        result = apply_confidence_gate(
                            content_en, content_ar,
                            vision_conf + en_conf + ar_conf,
                            findings, arabic_score, assessment,
                            elapsed, correlation_id,
                            category_ctx.get("category"),
                        )
                        result.model_used = get_model_name()
                        # Store nativeness on session for display
                        st.session_state["nativeness_score"] = nativeness

                        steps.success(
                            f"✅ All 4 passes complete — "
                            f"{elapsed}ms · confidence {result.overall_confidence:.0%}"
                        )

                st.session_state["last_result"] = result.model_dump()
            except Exception as e:
                steps.empty()
                st.error(f"Pipeline error: **{type(e).__name__}**: {e}")
                st.exception(e)
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

    elif "last_result" in st.session_state:
        from src.schemas import PDPResult
        result = PDPResult.model_validate(st.session_state["last_result"])

# ── Results ───────────────────────────────────────────────────────────────────
if result is not None:
    with col_right:
        # ── Status banner ─────────────────────────────────────────────────────
        cat  = result.detected_category or "unknown"
        conf = f"{result.overall_confidence:.0%}"
        ms   = f"{result.processing_time_ms}ms"
        cid  = result.correlation_id

        if result.review_required:
            st.warning(
                f"⚠️ **Human review required before publishing** — "
                f"Confidence: **{conf}** · Category: `{cat}` · ID: `{cid}`"
            )
        else:
            st.success(
                f"✅ **Ready for catalog** — "
                f"Confidence: **{conf}** · Category: `{cat}` · {ms}"
            )

        st.divider()

        # ── EN / AR side-by-side ──────────────────────────────────────────────
        en_col, ar_col = st.columns(2, gap="medium")

        # helpers
        def _txt(v, fallback="—") -> str:
            if v is None or v == "" or v == []:
                return f'<span class="null-field">{fallback}</span>'
            return str(v)

        with en_col:
            st.markdown("#### 🇬🇧 English PDP")
            e = result.content_en

            st.markdown(f"**Title:** {_txt(e.title)}", unsafe_allow_html=True)
            st.markdown(f"**Description:** {_txt(e.short_description)}", unsafe_allow_html=True)
            st.markdown(f"**Age:** {_txt(e.age_suitability)}", unsafe_allow_html=True)

            st.markdown("**Key Features:**")
            if e.key_features:
                for feat in e.key_features:
                    st.markdown(f"- {feat}")
            else:
                st.markdown('<span class="null-field">— not determined</span>', unsafe_allow_html=True)

            st.markdown("**Safety Warnings:**")
            if e.safety_warnings:
                for w in e.safety_warnings:
                    st.markdown(f"- ⚠️ {w}")
            else:
                st.markdown('<span class="null-field">— none</span>', unsafe_allow_html=True)

            if e.search_tags:
                st.markdown("**Search Tags:**")
                tags_html = " ".join(f'<span class="tag">{t}</span>' for t in e.search_tags[:12])
                st.markdown(tags_html, unsafe_allow_html=True)

        with ar_col:
            nativeness = st.session_state.get("nativeness_score")
            nat_label = f" · Arabic nativeness **{nativeness:.0f}/5**" if nativeness else ""
            st.markdown(f"#### 🇦🇪 Arabic PDP (RTL){nat_label}")
            a = result.content_ar

            def _ar(label: str, val) -> None:
                content = val if val else '<span class="null-field">— غير محدد</span>'
                st.markdown(
                    f'<div class="arabic-block"><span class="field-label">{label}</span> {content}</div>',
                    unsafe_allow_html=True,
                )

            _ar("العنوان:", a.title)
            _ar("الوصف:", a.short_description)
            _ar("الفئة العمرية:", a.age_suitability)

            st.markdown('<div class="arabic-block"><span class="field-label">المميزات:</span></div>', unsafe_allow_html=True)
            if a.key_features:
                items = "".join(f"<li>{f}</li>" for f in a.key_features)
                st.markdown(f'<div class="arabic-block"><ul>{items}</ul></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="arabic-block null-field">— غير محدد</div>', unsafe_allow_html=True)

            st.markdown('<div class="arabic-block"><span class="field-label">تحذيرات السلامة:</span></div>', unsafe_allow_html=True)
            if a.safety_warnings:
                warns = "".join(f"<li>⚠️ {w}</li>" for w in a.safety_warnings)
                st.markdown(f'<div class="arabic-block"><ul>{warns}</ul></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="arabic-block null-field">— لا تحذيرات</div>', unsafe_allow_html=True)

            if a.search_tags:
                st.markdown('<div class="arabic-block"><span class="field-label">كلمات البحث:</span></div>', unsafe_allow_html=True)
                tags_html = " ".join(f'<span class="tag">{t}</span>' for t in a.search_tags[:12])
                st.markdown(f'<div class="arabic-block">{tags_html}</div>', unsafe_allow_html=True)

        st.divider()

        # ── Confidence scores ─────────────────────────────────────────────────
        st.markdown("#### 📊 Field Confidence Scores")
        if result.field_confidences:
            conf_items = result.field_confidences[:8]
            cols = st.columns(4)
            for i, fc in enumerate(conf_items):
                c_cls = "conf-high" if fc.confidence >= 0.70 else ("conf-mid" if fc.confidence >= 0.40 else "conf-low")
                with cols[i % 4]:
                    st.markdown(
                        f'<span class="{c_cls}">{fc.field_name}<br>{fc.confidence:.0%}</span>',
                        unsafe_allow_html=True,
                    )
                    st.progress(fc.confidence)
                    st.caption(f"{fc.source}")
        else:
            st.caption("No field confidence data.")

        # ── Critique notes ────────────────────────────────────────────────────
        if result.critique_notes:
            st.divider()
            st.markdown("#### 🔍 Critique Notes")
            icons = {"info": "ℹ️", "warning": "⚠️", "error": "🚫"}
            for note in result.critique_notes:
                icon = icons.get(note.severity, "•")
                st.markdown(f"{icon} **[{note.severity.upper()}]** `{note.field_name}` — {note.issue}")

        # ── Raw JSON ──────────────────────────────────────────────────────────
        with st.expander("🔧 Raw PDPResult JSON"):
            st.json(result.model_dump())
