"""measurement unit tests."""
from collections import Counter
from datetime import UTC, datetime

from core_contracts import Arm, OutcomeEvent
from measurement import assign_arm, compute_lift

SECRET = b"measurement-secret"


def test_assignment_is_stable_and_roughly_matches_percentages() -> None:
    arms = [assign_arm("t", "exp-1", f"user-{i}", secret=SECRET, control_pct=20, naive_pct=20)
            for i in range(5000)]
    again = [assign_arm("t", "exp-1", f"user-{i}", secret=SECRET, control_pct=20, naive_pct=20)
             for i in range(5000)]
    assert arms == again
    share = Counter(arms)
    assert abs(share[Arm.CONTROL] / 5000 - 0.20) < 0.03
    assert abs(share[Arm.NAIVE] / 5000 - 0.20) < 0.03
    assert abs(share[Arm.ENGINE] / 5000 - 0.60) < 0.03


def _outcomes(arm: Arm, n: int, retained: int, spend: int = 0) -> list[OutcomeEvent]:
    return [
        OutcomeEvent(outcome_event_id=f"{arm.value}-{i}", tenant_id="t", run_id="r",
                     user_pseudonym=f"{arm.value}-{i}", arm=arm, treated=arm != Arm.CONTROL,
                     retained=i < retained, spend_idr=spend,
                     observed_at=datetime(2026, 9, 17, tzinfo=UTC))
        for i in range(n)
    ]


def test_lift_computed_from_real_outcomes() -> None:
    outcomes = _outcomes(Arm.CONTROL, 40, 20) + _outcomes(Arm.NAIVE, 40, 24, 10000) \
        + _outcomes(Arm.ENGINE, 40, 32, 10000)
    lift = compute_lift(outcomes, min_arm_size=30)
    assert lift["lift_vs_control"] == 0.8 - 0.5
    assert abs(lift["lift_vs_naive"] - (0.8 - 0.6)) < 1e-9
    assert lift["synthetic_data"] is True


def test_small_arm_returns_none_not_zero() -> None:
    outcomes = _outcomes(Arm.CONTROL, 5, 2) + _outcomes(Arm.ENGINE, 40, 32)
    lift = compute_lift(outcomes, min_arm_size=30)
    assert lift["arms"]["CONTROL"]["retention_rate"] is None
    assert lift["lift_vs_control"] is None
