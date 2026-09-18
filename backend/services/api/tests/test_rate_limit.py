import pytest
from api import errors
from api.rate_limit import TokenBucketLimiter


def test_allows_up_to_capacity():
    limiter = TokenBucketLimiter(capacity=3, refill_per_minute=60)
    limiter.check("key1")
    limiter.check("key1")
    limiter.check("key1")


def test_rejects_beyond_capacity():
    limiter = TokenBucketLimiter(capacity=2, refill_per_minute=60)
    limiter.check("key1")
    limiter.check("key1")
    with pytest.raises(errors.ApiError) as exc_info:
        limiter.check("key1")
    assert exc_info.value.code == "RATE_LIMITED"
    assert "retry_after_seconds" in exc_info.value.details


def test_keys_are_independent():
    limiter = TokenBucketLimiter(capacity=1, refill_per_minute=60)
    limiter.check("key1")
    limiter.check("key2")  # different key, should not be affected by key1's usage
