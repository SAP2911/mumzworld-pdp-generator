"""
src/retry.py — shared retry-with-backoff utility for all agents.

Usage:
    from src.retry import retry_on_rate_limit
    response = retry_on_rate_limit(
        lambda: client.chat.completions.create(...),
        agent_name="pdp_en",
        correlation_id=cid,
    )
"""
from __future__ import annotations

import os
import time

import structlog

log = structlog.get_logger(__name__)


def retry_on_rate_limit(
    call_fn,
    *,
    agent_name: str = "agent",
    correlation_id: str = "",
    max_retries: int | None = None,
    initial_delay: float = 5.0,
):
    """
    Execute ``call_fn()`` with exponential backoff on 429 rate-limit errors.

    Returns the successful response or raises the last exception.
    """
    if max_retries is None:
        max_retries = int(os.getenv("API_MAX_RETRIES", "3"))

    delay = initial_delay

    for attempt in range(max_retries):
        try:
            return call_fn()
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate limit" in err_str.lower()

            if is_rate_limit and attempt < max_retries - 1:
                log.warning(
                    f"{agent_name}_rate_limited",
                    attempt=attempt + 1,
                    retry_in=delay,
                    correlation_id=correlation_id,
                )
                time.sleep(delay)
                delay *= 2
            else:
                # Either not a rate-limit error, or we exhausted retries
                log.error(
                    f"{agent_name}_failed",
                    error=err_str[:200],
                    attempt=attempt + 1,
                    correlation_id=correlation_id,
                )
                raise
