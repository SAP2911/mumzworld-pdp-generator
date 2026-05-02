"""
src/client.py — shared OpenAI-compatible client for all agents.

Priority order (first key found wins):
  1. GROQ_API_KEY   → api.groq.com  (fastest, free, llama-4-scout vision)
  2. NVIDIA_API_KEY → integrate.api.nvidia.com
  3. OPENROUTER_API_KEY → openrouter.ai
"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            timeout=60.0,
        )

    nvidia_key = os.getenv("NVIDIA_API_KEY")
    if nvidia_key:
        return OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_key,
            timeout=120.0,
        )

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
            default_headers={
                "HTTP-Referer": "https://github.com/mumzworld-pdp-generator",
                "X-Title": "Mumzworld PDP Generator",
            },
        )

    raise EnvironmentError(
        "No API key found. Set GROQ_API_KEY, NVIDIA_API_KEY, or OPENROUTER_API_KEY in .env"
    )


def get_model_name() -> str:
    return os.getenv("MODEL_NAME", "meta-llama/llama-4-scout-17b-16e-instruct")


def get_confidence_threshold() -> float:
    return float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))


def get_null_threshold() -> float:
    """Fields below this confidence are set to None — never a hallucinated value."""
    return float(os.getenv("FIELD_NULL_THRESHOLD", "0.40"))
