"""Recommendation state machine tests (README "Tests to write")."""
import itertools

import pytest
from core_contracts.errors import IllegalTransition
from core_contracts.recommendation import (
    ALLOWED_TRANSITIONS,
    RecommendationStatus,
    assert_transition,
)


@pytest.mark.parametrize(
    "src,dst",
    [
        (RecommendationStatus.DRAFT, RecommendationStatus.PENDING_APPROVAL),
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.EXPIRED),
    ],
)
def test_legal_transitions_without_reviewer(src, dst):
    """DRAFT->PENDING_APPROVAL is worker-originated; EXPIRED is
    scheduler-originated. Neither needs a human reviewer."""
    assert_transition(src, dst, reviewer_id=None)


@pytest.mark.parametrize(
    "src,dst",
    [
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.APPROVED),
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.REJECTED),
        (RecommendationStatus.APPROVED, RecommendationStatus.DELIVERED),
    ],
)
def test_reviewer_required_transitions_reject_missing_reviewer(src, dst):
    """APPROVED, REJECTED, and DELIVERED all require an identified human
    reviewer -- matching persistence's own CHECK constraints
    (ck_recommendations_approved_needs_reviewer,
    ck_recommendations_rejected_needs_reviewer,
    ck_recommendations_delivered_needs_review_and_delivery)."""
    with pytest.raises(IllegalTransition):
        assert_transition(src, dst, reviewer_id=None)
    with pytest.raises(IllegalTransition):
        assert_transition(src, dst, reviewer_id="   ")  # blank/whitespace-only also rejected


@pytest.mark.parametrize(
    "src,dst",
    [
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.APPROVED),
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.REJECTED),
        (RecommendationStatus.APPROVED, RecommendationStatus.DELIVERED),
    ],
)
def test_reviewer_required_transitions_succeed_with_reviewer(src, dst):
    assert_transition(src, dst, reviewer_id="ops_reviewer_1")


def test_transition_table_rejects_every_unlisted_edge():
    all_states = list(RecommendationStatus)
    for src, dst in itertools.product(all_states, all_states):
        if dst in ALLOWED_TRANSITIONS[src]:
            continue
        with pytest.raises(IllegalTransition):
            assert_transition(src, dst, reviewer_id="someone")


def test_no_transition_into_approved_except_from_pending():
    for src in RecommendationStatus:
        if src is RecommendationStatus.PENDING_APPROVAL:
            continue
        assert RecommendationStatus.APPROVED not in ALLOWED_TRANSITIONS[src]


def test_no_transition_into_delivered_except_from_approved():
    for src in RecommendationStatus:
        if src is RecommendationStatus.APPROVED:
            continue
        assert RecommendationStatus.DELIVERED not in ALLOWED_TRANSITIONS[src]
