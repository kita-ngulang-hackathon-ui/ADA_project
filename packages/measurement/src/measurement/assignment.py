"""Deterministic HMAC arm assignment (requirement 10).

bucket = int(HMAC_SHA256(secret, f"{tenant_id}:{experiment_id}:{user}")) mod 100
bucket < control_pct                       -> CONTROL
bucket < control_pct + naive_pct           -> NAIVE
else                                       -> ENGINE

A pure hash, not a random draw -- a user's arm never changes within an
experiment and is stable across pipeline re-runs.
"""
import hashlib
import hmac

CONTROL = "CONTROL"
NAIVE = "NAIVE"
ENGINE = "ENGINE"


def assign_arm(
    tenant_id: str,
    experiment_id: str,
    user_pseudonym: str,
    *,
    secret: bytes,
    control_pct: int,
    naive_pct: int,
) -> str:
    if not (0 <= control_pct <= 100 and 0 <= naive_pct <= 100 and control_pct + naive_pct <= 100):
        raise ValueError("control_pct + naive_pct must be within [0, 100]")

    message = f"{tenant_id}:{experiment_id}:{user_pseudonym}".encode()
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    bucket = int.from_bytes(digest, "big") % 100

    if bucket < control_pct:
        return CONTROL
    if bucket < control_pct + naive_pct:
        return NAIVE
    return ENGINE
