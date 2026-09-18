"""Incremental lift per arm (requirement 10). Real outcomes, not predicted lift.

Accepts either OutcomeEvent rows (worker) or pre-aggregated per-arm dicts
{"arm", "n", "retained", "spend_idr"} (API, which aggregates in SQL).
Arms below min_arm_size report None, never a made-up number.

`incremental_value_per_idr` means incrementally retained USERS per rupiah of
spend, not a modeled monetary value per user.
"""
from core_contracts import Arm


def _aggregate(outcomes) -> dict[str, dict]:
    totals = {arm.value: {"n": 0, "retained": 0, "spend_idr": 0} for arm in Arm}
    for o in outcomes:
        if isinstance(o, dict):
            row = totals.get(Arm(o["arm"]).value)
            row["n"] += int(o.get("n", 0))
            row["retained"] += int(o.get("retained", 0))
            row["spend_idr"] += int(o.get("spend_idr", 0))
        else:
            row = totals[Arm(o.arm).value]
            row["n"] += 1
            row["retained"] += 1 if o.retained else 0
            row["spend_idr"] += o.spend_idr
    return totals


def compute_lift(outcomes, *, min_arm_size: int):
    arms: dict[str, dict] = {}
    for key, row in _aggregate(outcomes).items():
        n = row["n"]
        arms[key] = {
            "n": n,
            "retained": row["retained"],
            "retention_rate": (row["retained"] / n) if n >= min_arm_size and n > 0 else None,
            "spend_idr": row["spend_idr"],
        }

    def diff(a: str, b: str) -> float | None:
        ra, rb = arms[a]["retention_rate"], arms[b]["retention_rate"]
        return None if ra is None or rb is None else ra - rb

    def lift_block(a: str, b: str) -> dict | None:
        absolute = diff(a, b)
        if absolute is None:
            return None
        rb = arms[b]["retention_rate"]
        return {"absolute": absolute, "relative": (absolute / rb) if rb > 0 else None}

    def incremental_per_idr(arm: str) -> float | None:
        lift = diff(arm, Arm.CONTROL.value)
        if lift is None or arms[arm]["spend_idr"] <= 0:
            return None
        return lift * arms[arm]["n"] / arms[arm]["spend_idr"]

    return {
        "arms": arms,
        "lift_vs_control": diff(Arm.ENGINE.value, Arm.CONTROL.value),
        "lift_vs_naive": diff(Arm.ENGINE.value, Arm.NAIVE.value),
        "naive_lift_vs_control": diff(Arm.NAIVE.value, Arm.CONTROL.value),
        "incremental_retained_users_per_idr": incremental_per_idr(Arm.ENGINE.value),
        "lift": {
            "engine_vs_control": lift_block(Arm.ENGINE.value, Arm.CONTROL.value),
            "engine_vs_naive": lift_block(Arm.ENGINE.value, Arm.NAIVE.value),
            "incremental_value_per_idr": {
                Arm.NAIVE.value: incremental_per_idr(Arm.NAIVE.value),
                Arm.ENGINE.value: incremental_per_idr(Arm.ENGINE.value),
            },
        },
        "min_arm_size": min_arm_size,
        "synthetic_data": True,
    }
