"""ULID generation. Stdlib only (L0 rule: stdlib + pydantic only).

Time-sortable 26-character Crockford-base32 identifiers, matching the
`01J8ZQ...` style ids used throughout API_CONTRACTS.md. Not cryptographically
significant — just a compact, sortable, collision-resistant id.
"""
import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    chars = ["0"] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(chars)


def new_id() -> str:
    """Generate a new ULID: 48-bit millisecond timestamp + 80-bit randomness."""
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(ts_ms, 10) + _encode(randomness, 16)
