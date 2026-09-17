"""Deterministic HMAC arm assignment (requirement 10).

bucket = int.from_bytes(HMAC_SHA256(secret, f"{tenant_id}:{experiment_id}:{user}")) % 100
bucket < control_pct                       -> CONTROL
bucket < control_pct + naive_pct           -> NAIVE
else                                       -> ENGINE

A user's arm never changes within an experiment.
"""
import hashlib
import hmac

from core_contracts import Arm


def bucket(tenant_id: str, experiment_id: str, user_pseudonym: str, *, secret: bytes) -> int:
    if not secret:
        raise ValueError("measurement secret must not be empty")
    digest = hmac.new(secret, f"{tenant_id}:{experiment_id}:{user_pseudonym}".encode(),
                      hashlib.sha256).digest()
    return int.from_bytes(digest, "big") % 100


def assign_arm(tenant_id: str, experiment_id: str, user_pseudonym: str, *,
               secret: bytes, control_pct: int, naive_pct: int):
    if control_pct < 0 or naive_pct < 0 or control_pct + naive_pct > 100:
        raise ValueError("arm percentages must be non-negative and sum to at most 100")
    b = bucket(tenant_id, experiment_id, user_pseudonym, secret=secret)
    if b < control_pct:
        return Arm.CONTROL
    if b < control_pct + naive_pct:
        return Arm.NAIVE
    return Arm.ENGINE
