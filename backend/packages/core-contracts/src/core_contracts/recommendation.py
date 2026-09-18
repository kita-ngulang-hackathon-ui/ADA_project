"""Recommendation state machine (requirement 8). FROZEN.

DRAFT -> PENDING_APPROVAL -> APPROVED -> DELIVERED
                          -> REJECTED
                          -> EXPIRED

APPROVED and DELIVERED require a human reviewer id. The database enforces
the same rule (CHECK constraints + trigger, see persistence). This module is
the in-code mirror so that bugs fail fast before reaching the DB.
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from core_contracts.errors import IllegalTransition
from core_contracts.measurement import Arm


class RecommendationStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DELIVERED = "DELIVERED"


_S = RecommendationStatus

ALLOWED_TRANSITIONS: dict[RecommendationStatus, frozenset[RecommendationStatus]] = {
    _S.DRAFT: frozenset({_S.PENDING_APPROVAL}),
    _S.PENDING_APPROVAL: frozenset({_S.APPROVED, _S.REJECTED, _S.EXPIRED}),
    _S.APPROVED: frozenset({_S.DELIVERED}),
    _S.REJECTED: frozenset(),
    _S.EXPIRED: frozenset(),
    _S.DELIVERED: frozenset(),
}

# States that only a human-originated transition may write.
REVIEWER_REQUIRED: frozenset[RecommendationStatus] = frozenset(
    {_S.APPROVED, _S.REJECTED, _S.DELIVERED}
)


def assert_transition(src, dst, reviewer_id: str | None) -> None:
    """Raise IllegalTransition if src->dst is not allowed or lacks a reviewer."""
    src = RecommendationStatus(src)
    dst = RecommendationStatus(dst)
    if dst not in ALLOWED_TRANSITIONS[src]:
        raise IllegalTransition(f"{src.value} -> {dst.value} is not allowed")
    if dst in REVIEWER_REQUIRED and not (reviewer_id and reviewer_id.strip()):
        raise IllegalTransition(f"{src.value} -> {dst.value} requires a human reviewer id")


class Recommendation(BaseModel):
    """A persisted recommendation. The worker only ever creates PENDING_APPROVAL rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    tenant_id: str
    run_id: str
    candidate_id: str
    arm: Arm
    status: RecommendationStatus
    incentive_code: str
    cost_idr: int
    priority: float
    user_pseudonym: str | None = None
    group_id: str | None = None
    member_pseudonyms: tuple[str, ...] = ()
    runner_up_candidate_id: str | None = None
    reason_text: str
    reason_source: str  # "LLM" | "TEMPLATE"
    fact_sheet_hash: str
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class FactSheet(BaseModel):
    """Everything the narrator may say (requirement 9). Nothing else is allowed in the text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_type: str  # "USER" | "GROUP"
    subject_ref: str  # user pseudonym or group id
    member_count: int
    arm: Arm
    top_pick: dict[str, Any]
    runner_up: dict[str, Any] | None
    risk: dict[str, Any]
    circle: dict[str, Any] | None
    impact: dict[str, Any] | None
    external_signal: dict[str, Any] | None
    policy: dict[str, Any]
    allocation: dict[str, Any]
    reason_factors: list[dict[str, Any]]
    synthetic_data: bool = True
