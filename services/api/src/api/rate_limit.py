"""In-memory token-bucket rate limiting per API key / console session.

Single-process, in-memory by design (ADR: no Redis -- see DECISIONS.md
ADR-003, same reasoning: one more service for no correctness gain at demo
scale). Resets on process restart, which is acceptable for a hackathon demo
with `api_workers` effectively 1 in the compose file.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from api import errors


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    def __init__(self, *, capacity: int, refill_per_minute: int):
        self.capacity = capacity
        self.refill_per_second = refill_per_minute / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Raise errors.rate_limited() if `key` has no tokens left."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), last_refill=now)
                self._buckets[key] = bucket

            elapsed = now - bucket.last_refill
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_per_second)
            bucket.last_refill = now

            if bucket.tokens < 1.0:
                retry_after = max(1, int((1.0 - bucket.tokens) / self.refill_per_second))
                raise errors.rate_limited(retry_after)

            bucket.tokens -= 1.0


_ingest_limiter: TokenBucketLimiter | None = None
_console_limiter: TokenBucketLimiter | None = None


def get_ingest_limiter(refill_per_minute: int) -> TokenBucketLimiter:
    global _ingest_limiter
    if _ingest_limiter is None:
        _ingest_limiter = TokenBucketLimiter(capacity=refill_per_minute, refill_per_minute=refill_per_minute)
    return _ingest_limiter


def get_console_limiter(refill_per_minute: int) -> TokenBucketLimiter:
    global _console_limiter
    if _console_limiter is None:
        _console_limiter = TokenBucketLimiter(capacity=refill_per_minute, refill_per_minute=refill_per_minute)
    return _console_limiter
