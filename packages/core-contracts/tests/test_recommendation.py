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
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.REJECTED),
        (RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.EXPIRED),
        (RecommendationStatus.APPROVED, RecommendationStatus.DELIVERED),
    ],
)
def test_legal_transitions_without_reviewer(src, dst):
    assert_transition(src, dst, reviewer_id=None)


def test_approved_requires_reviewer():
    with pytest.raises(IllegalTransition):
        assert_transition(
            RecommendationStatus.PENDING_APPROVAL, RecommendationStatus.APPROVED, reviewer_id=None
        )


def test_approved_with_reviewer_succeeds():
    assert_transition(
        RecommendationStatus.PENDING_APPROVAL,
        RecommendationStatus.APPROVED,
        reviewer_id="ops_reviewer_1",
    )


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
