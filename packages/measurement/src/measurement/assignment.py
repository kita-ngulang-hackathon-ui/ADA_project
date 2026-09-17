"""Deterministic HMAC arm assignment (requirement 10).

bucket = int.from_bytes(HMAC_SHA256(secret, f"{tenant_id}:{experiment_id}:{user}")) % 100
bucket < control_pct                       -> CONTROL
bucket < control_pct + naive_pct           -> NAIVE
else                                       -> ENGINE

TODO: implement.
"""


def assign_arm(tenant_id: str, experiment_id: str, user_pseudonym: str, *,
               secret: bytes, control_pct: int, naive_pct: int):
    raise NotImplementedError
