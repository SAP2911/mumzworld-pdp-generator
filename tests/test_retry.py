"""
tests/test_retry.py — unit tests for the retry utility.
No API calls needed.
"""
import time
import pytest

from src.retry import retry_on_rate_limit


class TestRetryOnRateLimit:
    def test_succeeds_first_try(self):
        result = retry_on_rate_limit(lambda: "ok", agent_name="test")
        assert result == "ok"

    def test_non_429_error_raises_immediately(self):
        call_count = 0

        def failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Something else broke")

        with pytest.raises(ValueError, match="Something else broke"):
            retry_on_rate_limit(failing, agent_name="test", max_retries=3)

        assert call_count == 1  # didn't retry

    def test_429_retries_and_succeeds(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Error code: 429 - rate limit")
            return "success"

        result = retry_on_rate_limit(
            flaky, agent_name="test", max_retries=3, initial_delay=0.01
        )
        assert result == "success"
        assert call_count == 3

    def test_429_exhausts_retries(self):
        def always_limited():
            raise Exception("429 rate limit exceeded")

        with pytest.raises(Exception, match="429"):
            retry_on_rate_limit(
                always_limited, agent_name="test", max_retries=2, initial_delay=0.01
            )

    def test_exponential_backoff_timing(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 rate limit")
            return "done"

        start = time.time()
        result = retry_on_rate_limit(
            flaky, agent_name="test", max_retries=3, initial_delay=0.05
        )
        elapsed = time.time() - start

        assert result == "done"
        # first delay=0.05, second=0.10 → total ≥ 0.15
        assert elapsed >= 0.10  # some tolerance
