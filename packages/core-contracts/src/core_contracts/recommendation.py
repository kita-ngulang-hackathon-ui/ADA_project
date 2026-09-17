"""Recommendation state machine (requirement 8). FROZEN.

DRAFT -> PENDING_APPROVAL -> APPROVED -> DELIVERED
                          -> REJECTED
                          -> EXPIRED

APPROVED and DELIVERED require a human reviewer id. The database enforces
the same rule (CHECK constraints + trigger, see persistence). This module is
the in-code mirror so that bugs fail fast before reaching the DB.

TODO:
- RecommendationStatus enum.
- ALLOWED_TRANSITIONS: dict[RecommendationStatus, frozenset[RecommendationStatus]].
- Candidate, Recommendation, FactSheet models.
- assert_transition().
"""
from enum import Enum


class RecommendationStatus(str, Enum):
    """TODO."""


ALLOWED_TRANSITIONS: dict = {}  # TODO


def assert_transition(src, dst, reviewer_id: str | None) -> None:
    """Raise IllegalTransition if src->dst is not allowed or lacks a reviewer."""
    raise NotImplementedError
