"""Incremental lift per arm (requirement 10).

Input: one dict per arm -- {"arm", "n", "retained", "spend_idr"}. Output:
retention_rate per arm, lift_vs_control (ENGINE - CONTROL, real incremental
lift), lift_vs_naive (ENGINE - NAIVE, the naive-baseline comparison demo
beat 6 needs), and incremental retained users per rupiah spent.

Below MEASUREMENT_MIN_ARM_SIZE an arm reports `None`, never a fabricated 0
-- CLAUDE.md's "never invent a number" rule applies to statistics too.

`incremental_value_per_idr` here means incrementally retained USERS per
rupiah of spend (retained-count lift / spend), not a modeled monetary value
per user -- no such per-user value figure exists at this layer yet. That is
a deliberate simplification, not a hidden assumption: label it as such
wherever it is displayed.
"""
from __future__ import annotations

CONTROL = "CONTROL"
NAIVE = "NAIVE"
ENGINE = "ENGINE"


def _retention_rate(n: int, retained: int, min_arm_size: int) -> float | None:
    if n < min_arm_size:
        return None
    return retained / n


def compute_lift(outcomes: list[dict], *, min_arm_size: int) -> dict:
    by_arm = {o["arm"]: o for o in outcomes}

    arms_out: dict[str, dict] = {}
    for arm in (CONTROL, NAIVE, ENGINE):
        row = by_arm.get(arm, {"n": 0, "retained": 0, "spend_idr": 0})
        n = int(row.get("n", 0))
        retained = int(row.get("retained", 0))
        spend_idr = int(row.get("spend_idr", 0))
        arms_out[arm] = {
            "n": n,
            "retained": retained,
            "retention_rate": _retention_rate(n, retained, min_arm_size),
            "spend_idr": spend_idr,
        }

    def _lift(a: str, b: str) -> dict | None:
        ra, rb = arms_out[a]["retention_rate"], arms_out[b]["retention_rate"]
        if ra is None or rb is None:
            return None
        absolute = ra - rb
        relative = (absolute / rb) if rb > 0 else None
        return {"absolute": absolute, "relative": relative}

    def _incremental_value_per_idr(arm: str) -> float | None:
        rate, control_rate = arms_out[arm]["retention_rate"], arms_out[CONTROL]["retention_rate"]
        n, spend = arms_out[arm]["n"], arms_out[arm]["spend_idr"]
        if rate is None or control_rate is None or spend <= 0:
            return None
        incremental_retained = (rate - control_rate) * n
        return incremental_retained / spend

    return {
        "arms": arms_out,
        "lift": {
            "engine_vs_control": _lift(ENGINE, CONTROL),
            "engine_vs_naive": _lift(ENGINE, NAIVE),
            "incremental_value_per_idr": {
                NAIVE: _incremental_value_per_idr(NAIVE),
                ENGINE: _incremental_value_per_idr(ENGINE),
            },
        },
        "synthetic_data": True,
    }
