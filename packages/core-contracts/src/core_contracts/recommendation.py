"""Recommendation state machine (requirement 8). FROZEN.

DRAFT -> PENDING_APPROVAL -> APPROVED -> DELIVERED
                          -> REJECTED
                          -> EXPIRED

APPROVED and DELIVERED require a human reviewer id. The database enforces
the same rule (CHECK constraints + trigger, see persistence). This module is
the in-code mirror so that bugs fail fast before reaching the DB
(ARCHITECTURE.md §9, mechanism 1 and 2).
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from core_contracts.errors import IllegalTransition
from core_contracts.graph import PatternType
from core_contracts.scores import ImpactSegment


class RecommendationStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DELIVERED = "DELIVERED"


class SubjectType(str, Enum):
    USER = "USER"
    GROUP = "GROUP"


# Frozen transition table. No transition into APPROVED exists from any state
# other than PENDING_APPROVAL. No transition into DELIVERED exists from any
# state other than APPROVED.
ALLOWED_TRANSITIONS: dict[RecommendationStatus, frozenset[RecommendationStatus]] = {
    RecommendationStatus.DRAFT: frozenset({RecommendationStatus.PENDING_APPROVAL}),
    RecommendationStatus.PENDING_APPROVAL: frozenset(
        {
            RecommendationStatus.APPROVED,
            RecommendationStatus.REJECTED,
            RecommendationStatus.EXPIRED,
        }
    ),
    RecommendationStatus.APPROVED: frozenset({RecommendationStatus.DELIVERED}),
    RecommendationStatus.REJECTED: frozenset(),
    RecommendationStatus.EXPIRED: frozenset(),
    RecommendationStatus.DELIVERED: frozenset(),
}

# States that may only be entered with an identified human reviewer
# (mechanism 2: apply_review_decision requires reviewer_identity).
_REVIEWER_REQUIRED_STATES: frozenset[RecommendationStatus] = frozenset(
    {RecommendationStatus.APPROVED}
)


def assert_transition(
    src: RecommendationStatus, dst: RecommendationStatus, reviewer_id: str | None
) -> None:
    """Raise IllegalTransition if src->dst is not allowed, or if dst requires
    a reviewer and none was given. There is no default reviewer, no system
    reviewer, no service-account reviewer, and no LLM reviewer."""
    allowed = ALLOWED_TRANSITIONS.get(src, frozenset())
    if dst not in allowed:
        raise IllegalTransition(f"{src.value} -> {dst.value} is not a legal transition")
    if dst in _REVIEWER_REQUIRED_STATES and not reviewer_id:
        raise IllegalTransition(
            f"{dst.value} requires an identified human reviewer_id; none was given"
        )


class ReasonSource(str, Enum):
    LLM = "LLM"
    TEMPLATE = "TEMPLATE"


class RunnerUp(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    incentive_code: str
    priority_idr: int
    why_second: str


class ExternalSignalRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str
    scope_type: str
    scope_key: str
    signal_type: str
    value: float
    contribution: float | None = None


class FactSheet(BaseModel):
    """The only information the LLM narrator may use (requirement 9). Closed
    record of already-computed values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    churn_risk: float
    delta_stability: float
    pattern_type: PatternType
    external_signal: ExternalSignalRef | None = None
    impact_score: float
    segment: ImpactSegment
    tau: float
    priority: int
    rank: int
    candidate_count: int
    budget_outcome: str
    runner_up: RunnerUp | None = None
    reason_factors: tuple[dict, ...] = ()
    synthetic_data: bool = True


class Candidate(BaseModel):
    """One (user-or-group, incentive) pairing considered by the Decision Engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_type: SubjectType
    user_pseudonym: str | None = None
    circle_id: str | None = None
    incentive_code: str
    cost_idr: int
    churn_risk: float | None = None
    delta_stability: float | None = None
    pattern_type: PatternType | None = None
    impact_score: float | None = None
    segment: ImpactSegment | None = None
    priority_idr: int | None = None
    user_rank: int | None = None
    selected: bool = False
    is_runner_up: bool = False
    exclusion_reason: str | None = None


class Recommendation(BaseModel):
    """A persisted recommendation row (mirrors persistence.models.Recommendation)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    tenant_id: str
    allocation_run_id: str
    allocation_candidate_id: str | None = None
    subject_type: SubjectType
    user_pseudonym: str | None = None
    circle_id: str | None = None
    incentive_code: str
    cost_idr: int
    priority_idr: int
    user_rank: int
    is_runner_up: bool = False
    status: RecommendationStatus = RecommendationStatus.DRAFT
    reason_text: str | None = None
    reason_factors: tuple[dict, ...] = ()
    reason_source: ReasonSource | None = None
    fact_sheet_hash: str | None = None
    created_at: datetime
    submitted_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    delivered_at: datetime | None = None
    delivery_ref: str | None = None
