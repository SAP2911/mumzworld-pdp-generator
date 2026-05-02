import json
from functools import lru_cache
from pathlib import Path

KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base.json"


@lru_cache(maxsize=1)
def load_kb() -> dict:
    with open(KB_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_category_context(product_type: str) -> dict:
    """
    Keyword-match product_type against known categories.
    Returns the full category dict + a 'category' key.
    This is the retrieval step in the lightweight RAG pipeline.
    """
    kb = load_kb()
    product_lower = product_type.lower()

    for category_key, category_data in kb["categories"].items():
        # Direct key match
        if category_key.replace("_", " ") in product_lower:
            return {"category": category_key, **category_data}
        # Keyword match
        for kw in category_data.get("keywords", []):
            if kw.lower() in product_lower:
                return {"category": category_key, **category_data}

    return {"category": "general", **kb["fallback_category"]}


def get_arabic_conventions() -> dict:
    return load_kb()["arabic_conventions"]
