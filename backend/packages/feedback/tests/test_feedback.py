"""feedback unit tests."""
from datetime import UTC, datetime

from core_contracts import Arm, FeatureSnapshot, OutcomeEvent
from feedback import summarize, to_labeled_examples

WHEN = datetime(2026, 9, 17, tzinfo=UTC)


def _outcome(oid: str, retained: bool = True) -> OutcomeEvent:
    return OutcomeEvent(outcome_event_id=oid, tenant_id="t", run_id="run-1", user_pseudonym="u",
                        arm=Arm.ENGINE, treated=True, retained=retained, spend_idr=10_000,
                        observed_at=WHEN)


SNAPSHOTS = {("run-1", "u"): FeatureSnapshot(
    tenant_id="t", run_id="run-1", user_pseudonym="u", features={"frequency_30d": 2.0},
    churn_risk=0.7, impact_score=0.3, pattern_type="CIRCLE_SPECIFIC", incentive_code="X",
    cost_idr=10_000, business_value_idr=90_000,
)}


def test_duplicate_outcome_does_not_create_second_example() -> None:
    first = to_labeled_examples([_outcome("o1"), _outcome("o1")], SNAPSHOTS)
    assert len(first) == 1
    again = to_labeled_examples([_outcome("o1")], SNAPSHOTS, existing_outcome_ids={("t", "o1")})
    assert again == []


def test_example_uses_recommendation_time_snapshot() -> None:
    [example] = to_labeled_examples([_outcome("o1")], SNAPSHOTS)
    assert example.features == {"frequency_30d": 2.0}
    assert example.churn_risk == 0.7 and example.impact_score == 0.3
    assert example.realized_value_idr == 80_000.0


def test_outcome_without_snapshot_skipped_and_counter() -> None:
    assert to_labeled_examples([_outcome("o9").model_copy(update={"run_id": "other"})], SNAPSHOTS) == []
    summary = summarize([object()] * 12, 140, min_rows_per_cycle=10)
    assert summary["new_labeled_examples"] == 12 and summary["used_in_next_context"] is True
