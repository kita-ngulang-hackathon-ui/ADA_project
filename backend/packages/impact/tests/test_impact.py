"""impact unit tests (hand-built stand-ins for planted persuadables P3 and sleeping dogs P5)."""
import pytest
from core_contracts import Arm, ContextTooSmall, ImpactScore, ImpactSegment, LabeledExample
from impact import estimate, segment


def _rows(treated: bool, n: int, retained_fn) -> list[LabeledExample]:
    rows = []
    for i in range(n):
        kind = float(i % 2)  # 0 = persuadable-like, 1 = sleeping-dog-like
        rows.append(LabeledExample(
            tenant_id="t", source_outcome_id=f"{'T' if treated else 'C'}{i:04d}",
            user_pseudonym=f"u{i}", features={"kind": kind, "noise": float(i % 7)},
            arm=Arm.ENGINE if treated else Arm.CONTROL, treated=treated,
            retained=retained_fn(kind, i),
        ))
    return rows


# Persuadables stay only when incentivized; sleeping dogs leave only when incentivized.
TREATED = _rows(True, 80, lambda kind, i: kind == 0.0)
CONTROL = _rows(False, 80, lambda kind, i: kind == 1.0)
KW = dict(impact_threshold=0.05, sure_thing_p=0.8)


def test_persuadable_gets_positive_impact() -> None:
    s = estimate(TREATED, CONTROL, {"kind": 0.0, "noise": 3.0}, seed=42, min_rows=20)
    assert s.impact_score > 0.5
    assert segment(s, **KW) == ImpactSegment.PERSUADABLE


def test_sleeping_dog_gets_negative_impact() -> None:
    s = estimate(TREATED, CONTROL, {"kind": 1.0, "noise": 3.0}, seed=42, min_rows=20)
    assert s.impact_score < -0.5
    assert segment(s, **KW) == ImpactSegment.SLEEPING_DOG


def test_too_small_arm_raises() -> None:
    with pytest.raises(ContextTooSmall):
        estimate(TREATED[:5], CONTROL, {"kind": 0.0}, seed=42, min_rows=20)


def test_sure_thing_and_lost_cause() -> None:
    assert segment(ImpactScore(p_incentivized=0.9, p_not_incentivized=0.88, model="m"), **KW) \
        == ImpactSegment.SURE_THING
    assert segment(ImpactScore(p_incentivized=0.1, p_not_incentivized=0.09, model="m"), **KW) \
        == ImpactSegment.LOST_CAUSE
