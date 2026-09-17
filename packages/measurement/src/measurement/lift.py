"""Incremental lift per arm (requirement 10). Real outcomes, not predicted lift.

Arms below min_arm_size report None, never a made-up number.
"""
from core_contracts import Arm


def compute_lift(outcomes, *, min_arm_size: int):
    arms: dict[str, dict] = {}
    for arm in Arm:
        rows = [o for o in outcomes if o.arm == arm]
        n = len(rows)
        retained = sum(1 for o in rows if o.retained)
        spend = sum(o.spend_idr for o in rows)
        arms[arm.value] = {
            "n": n,
            "retained": retained,
            "retention_rate": (retained / n) if n >= min_arm_size else None,
            "spend_idr": spend,
        }

    def diff(a: str, b: str) -> float | None:
        ra, rb = arms[a]["retention_rate"], arms[b]["retention_rate"]
        return None if ra is None or rb is None else ra - rb

    engine = arms[Arm.ENGINE.value]
    lift_vs_control = diff(Arm.ENGINE.value, Arm.CONTROL.value)
    incremental_per_idr = None
    if lift_vs_control is not None and engine["spend_idr"] > 0:
        incremental_retained = lift_vs_control * engine["n"]
        incremental_per_idr = incremental_retained / engine["spend_idr"]

    return {
        "arms": arms,
        "lift_vs_control": lift_vs_control,
        "lift_vs_naive": diff(Arm.ENGINE.value, Arm.NAIVE.value),
        "naive_lift_vs_control": diff(Arm.NAIVE.value, Arm.CONTROL.value),
        "incremental_retained_users_per_idr": incremental_per_idr,
        "min_arm_size": min_arm_size,
        "synthetic_data": True,
    }
