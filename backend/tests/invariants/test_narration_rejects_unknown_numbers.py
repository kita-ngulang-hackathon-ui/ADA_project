"""Invariant: Narration validator rejects numbers not in the fact sheet (requirement 9)."""
import pytest
from core_contracts import Arm, FactSheet, NarrationRejected
from explain import render_template, validate_narration

SHEET = FactSheet(
    subject_type="USER", subject_ref="abc", member_count=1, arm=Arm.ENGINE,
    top_pick={"candidate_id": "c", "incentive_code": "CASHBACK_10K", "display_name": "Cashback",
              "cost_idr": 10000, "priority": 1234.5, "ranking_strategy": "FALLBACK"},
    runner_up=None,
    risk={"churn_risk": 0.71, "model": "m", "external_signal_contribution": 0.0},
    circle=None, impact=None, external_signal=None,
    policy={"outcome": "ALLOW", "rules_checked": ["FREQUENCY_CAP"]},
    allocation={"strategy": "EXACT_DP", "rank": 1},
    reason_factors=[],
)


def test_narration_rejects_unknown_numbers() -> None:
    validate_narration(render_template(SHEET), SHEET)
    validate_narration("Churn risk is 71%, cost Rp 10.000.", SHEET)
    for invented in ("Churn risk is 72%.", "Costs Rp 12.000.", "Retention will rise by 15%.",
                     "Expect 3 more transactions."):
        with pytest.raises(NarrationRejected):
            validate_narration(invented, SHEET)
