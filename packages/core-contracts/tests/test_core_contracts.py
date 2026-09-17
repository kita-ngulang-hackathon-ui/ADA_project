"""core-contracts unit tests."""
from datetime import UTC, datetime

import pytest
from core_contracts import (
    CanonicalEvent,
    CanonicalEventType,
    ExternalSignal,
    IllegalTransition,
    ImpactScore,
    assert_transition,
)
from core_contracts import (
    RecommendationStatus as S,
)
from pydantic import ValidationError


def test_worker_path_draft_to_pending_needs_no_reviewer() -> None:
    assert_transition(S.DRAFT, S.PENDING_APPROVAL, None)


@pytest.mark.parametrize("dst", [S.APPROVED, S.REJECTED])
def test_review_states_require_reviewer(dst: S) -> None:
    with pytest.raises(IllegalTransition):
        assert_transition(S.PENDING_APPROVAL, dst, None)
    with pytest.raises(IllegalTransition):
        assert_transition(S.PENDING_APPROVAL, dst, "  ")
    assert_transition(S.PENDING_APPROVAL, dst, "ops_reviewer_1")


def test_cannot_skip_approval() -> None:
    with pytest.raises(IllegalTransition):
        assert_transition(S.DRAFT, S.APPROVED, "ops_reviewer_1")
    with pytest.raises(IllegalTransition):
        assert_transition(S.PENDING_APPROVAL, S.DELIVERED, "ops_reviewer_1")
    with pytest.raises(IllegalTransition):
        assert_transition(S.APPROVED, S.DELIVERED, None)


def test_canonical_event_requires_tz() -> None:
    with pytest.raises(ValidationError):
        CanonicalEvent(
            tenant_id="t",
            client_event_id="e",
            event_type=CanonicalEventType.PAYMENT,
            occurred_at=datetime(2026, 9, 1),
            user_pseudonym="u",
        )


def test_external_signal_rejects_user_field_and_range() -> None:
    base = dict(
        signal_id="s", source="canned", scope_type="COHORT", scope_key="c",
        signal_type="NEWS_SENTIMENT", value=-0.5, observed_at=datetime.now(UTC),
    )
    ExternalSignal(**base)
    with pytest.raises(ValidationError):
        ExternalSignal(**base, user_pseudonym="u")
    with pytest.raises(ValidationError):
        ExternalSignal(**{**base, "value": 1.5})


def test_impact_score_is_difference() -> None:
    s = ImpactScore(p_incentivized=0.7, p_not_incentivized=0.4, model="m")
    assert s.impact_score == pytest.approx(0.3)
    assert s.model_dump()["impact_score"] == pytest.approx(0.3)
