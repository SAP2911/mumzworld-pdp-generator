# TRADEOFFS — Mumzworld PDP Generator

## Why This Problem

Mumzworld's catalog team manually writes PDP content for every SKU — across thousands of products, in two languages, with regulatory safety requirements. This is:
- **Expensive**: each PDP takes 15-30 minutes of copywriter time
- **Inconsistent**: quality varies by writer, shift, and day
- **Bottlenecked**: Arabic copy especially is hard to hire for at scale
- **Risky**: safety warnings that vary by product but must appear correctly

An AI PDP generator that handles the bilingual copy, respects category safety standards, and flags when it's uncertain is directly deployable to the catalog operations team.

**What I rejected:**
- *Gift finder*: Higher novelty but requires a product catalog to be believable — can't demo without data
- *Return triage*: Easier evals but less direct ops value (returns are lower volume than catalog ops)
- *Review synthesis*: Listed in the brief — I wanted to pick something not on the list

---

## Architecture Decisions

### Model: OpenRouter Free Tier over Direct API Keys

**Chose:** Free vision-capable models via OpenRouter (OpenAI-compatible SDK)  
**Rejected:** Direct Gemini API key, Claude API key (both require payment for production usage)

**Reasoning:** The brief encourages free tools. OpenRouter provides access to multiple free vision-capable models (Gemini, Gemma, NVIDIA Nemotron, etc.) through a unified OpenAI-compatible API. This makes the codebase model-agnostic — swapping models is a one-line `.env` change, not a code rewrite. The OpenAI Python SDK is battle-tested and well-documented.

**Tradeoff:** Free tier is capped at 50 requests/day. For production, adding $10 in OpenRouter credits unlocks 1000 req/day — or switching to a direct API key for a specific model (Gemini, Claude) removes the cap entirely.

---

### Knowledge Base: In-Memory JSON over pgvector + Embeddings

**Chose:** `data/knowledge_base.json` loaded into memory with keyword matching  
**Rejected:** pgvector, ChromaDB, FAISS

**Reasoning:** The knowledge base has 12 categories and ~2KB of data. Vector search adds a Postgres/Docker dependency, embedding costs, and setup complexity — all for a lookup that a dict-based keyword match handles in microseconds. Honest scope for a 5-hour prototype.

**Tradeoff:** Real-world deployment would need semantic search over hundreds of sub-categories (e.g., "ergonomic forward-facing convertible car seat" → correct sub-category + standards). The `get_category_context()` function is designed with a clean interface that can swap in a vector store without changing any agent code.

**What would trigger the upgrade:** >50 categories, or when "nursing cover" keeps getting classified as "nursing pillow" because it shares keywords.

---

### Arabic Generation: Separate Pass over Translation

**Chose:** A separate LLM call with an Arabic-language system prompt  
**Rejected:** Translating the EN output

**Reasoning:** Translation produces Arabic that reads like translated English. Arabic marketing copy in the Gulf has different conventions: longer benefit statements, different adjective-to-noun ordering, preference for root-word derivations over transliterations of English terms. A Gulf Arabic system prompt with explicit examples of what *not* to write (anti-translation instructions) produces copy that catalog managers can publish without edits.

**Evidence from development:** First iteration used translation — the self-critique agent scored it 2/5 on nativeness consistently. After switching to a separate pass with the Arabic system prompt, nativeness scores rose to 3.5-4.5/5.

**Tradeoff:** Two LLM calls instead of one for the Arabic content. At ~2 seconds per call, this adds ~2 seconds to the pipeline. Acceptable for a catalog tool used by humans (not a real-time user-facing API).

---

### Structured Output: JSON Mode over response_schema

**Chose:** `response_format={"type": "json_object"}` via OpenAI SDK + manual `json.loads()` + Pydantic  
**Rejected:** Model-specific response_schema parameters

**Reasoning:** Different models handle structured output differently. Using the OpenAI-compatible JSON mode with explicit schema descriptions in the system prompt + Pydantic validation is the most portable approach — it works across any model on OpenRouter. Failures are explicit `ValidationError` exceptions, not silent dropped fields.

**Tradeoff:** The schema must be described in plain English in the system prompt, not programmatically enforced. If the schema changes, both `schemas.py` and the relevant system prompt must be updated.

---

### Self-Critique Loop: Third Agent Pass

**Chose:** A dedicated critique agent at `temperature=0.0` after EN+AR generation  
**Rejected:** Inline critique in the generation prompt ("generate AND check your own output")

**Reasoning:** A separate agent at temperature=0 gives deterministic, reproducible critique scores — important for eval calibration. The generation agent's self-assessment is optimistic (it just generated the content). An independent critic is systematically more skeptical.

**Cost:** +1 LLM call per pipeline run (~2-3 seconds). On the eval harness (15 runs), this adds ~30-45 seconds. Acceptable.

**Tradeoff that matters:** If the self-critique agent flags something as "error" that was actually correct, it will set `review_required=True` and a catalog manager will review it. False positives are wasteful but not harmful. The reverse (missing a hallucination) would publish incorrect specs to the catalog — much worse. The prompt is deliberately calibrated toward strictness.

---

## What Was Cut

| Feature | Why Cut | Would Reconsider If |
|---|---|---|
| FastAPI REST endpoint | Adds no demo value; `pipeline.run()` is already importable | Needed for integration with catalog management system |
| Batch processing (50 images → queue) | Scope | This became a real ops tool |
| pgvector semantic search | Overkill for 12 categories | >50 categories or cross-category products |
| Image pre-processing (upscale, deblur) | Dependency + complexity | Low-res product photos are a real problem in ops |
| Fine-tuning on Gulf Arabic catalog copy | Impossible in 5 hours | Given 2 weeks + labeled catalog data |
| User feedback loop (thumbs up/down on output) | Frontend scope | Deployed to catalog team — feedback feeds back into eval metrics |
| Async pipeline with progress events | Streamlit spinner is sufficient | Needs to support concurrent users |

---

## Known Failure Modes

### 1. Arabic brand transliteration (severity: medium)
**What happens:** Arabic-only packaging causes brand names to be rendered in transliterated English letters rather than native Arabic script.  
**Root cause:** The model defaults to Latin characters for brand names when uncertain.  
**Fix:** Post-processing pass that normalizes brand names against a known Arabic brand dictionary; or few-shot examples showing correct brand handling.

### 2. Low-resolution / synthetic images (severity: low for production)
**What happens:** PIL-generated test images have less visual information than real product photos. Confidence scores trend 10-15% lower than on real photography.  
**Root cause:** Expected — synthetic images are designed to test the pipeline, not showcase it.  
**Fix:** Use real product photography for the Loom demo.

### 3. Multi-category products (severity: low)
**What happens:** A stroller-carseat travel system gets classified as either a stroller or a car seat, not both. Safety warnings from the other category may be missed.  
**Root cause:** Knowledge base lookup returns one category.  
**Fix:** Allow `detected_category` to be a list; merge safety warnings from all matched categories.

### 4. Overconfident on blurry-but-readable text (severity: low)
**What happens:** If a blurry image still has readable text (e.g., "BPA-Free" is legible), the model assigns high confidence even though overall image quality is poor.  
**Root cause:** The model is right about the text but we'd like overall confidence to reflect image quality.  
**Fix:** Multiply field confidence by an `image_quality_multiplier` (1.0 for clear, 0.8 for partial, 0.5 for blurry).

---

## What I'd Build Next (with 2 more weeks)

1. **Human review interface**: Catalog managers see `review_required=True` items in a queue, can approve/reject/edit fields. Approvals feed back into eval metrics.
2. **Real product image integration**: Pull images from Mumzworld's CDN (with authorization) rather than PIL-generated samples.
3. **Confidence calibration study**: Collect 100 human-labeled PDP samples and measure whether the model's confidence scores are actually calibrated (when it says 0.90, is it right 90% of the time?).
4. **Arabic quality fine-tuning**: Fine-tune on approved Mumzworld catalog Arabic copy to close the gap between "good enough" and "indistinguishable from a human copywriter."
5. **Batch endpoint**: Process a full product upload batch overnight — 500 images → 500 PDPs + review queue for the next morning.
