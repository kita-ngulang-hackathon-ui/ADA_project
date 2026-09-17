"""Decision Engine types shared by policy-guard, ranker, allocator, and explain (requirement 7)."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from core_contracts.graph import PatternType
from core_contracts.scores import ImpactSegment


class Candidate(BaseModel):
    """One (user, incentive) pair. Group candidates share a group_id and are allocated as a bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    tenant_id: str
    user_pseudonym: str
    incentive_code: str
    cost_idr: int
    business_value_idr: int
    encourages_borrowing: bool = False
    changes_credit_terms: bool = False
    group_id: str | None = None
    churn_risk: float
    impact_score: float
    segment: ImpactSegment
    pattern_type: PatternType


class UserFacts(BaseModel):
    """Structural facts the hard rules need. Timestamps only, no amounts or profiles."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_pseudonym: str
    now: datetime
    late_repayment_at: tuple[datetime, ...] = ()
    contacted_at: tuple[datetime, ...] = ()


class RuleCode(str, Enum):
    RESPONSIBLE_LENDING = "RESPONSIBLE_LENDING"
    FREQUENCY_CAP = "FREQUENCY_CAP"
    NO_CREDIT_DECISION = "NO_CREDIT_DECISION"
    SEGMENT_EXCLUDED = "SEGMENT_EXCLUDED"


class RuleResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_code: RuleCode
    allowed: bool
    reason: str


class PolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    user_pseudonym: str
    outcome: str  # "ALLOW" | "DENY"
    results: tuple[RuleResult, ...]

    @property
    def allowed(self) -> bool:
        return self.outcome == "ALLOW"

    @property
    def denials(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if not r.allowed)


class RankingStrategy(str, Enum):
    TABPFN = "TABPFN"
    SKLEARN_STAND_IN = "SKLEARN_STAND_IN"  # enough context, TabPFN not installed
    FALLBACK = "FALLBACK"  # impact_score * business_value_idr
    NAIVE_RISK_ONLY = "NAIVE_RISK_ONLY"  # measurement baseline: churn risk only, no optimization


class RankedCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: Candidate
    priority: float
    ranking_strategy: RankingStrategy


class ExclusionReason(str, Enum):
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    RUNNER_UP = "RUNNER_UP"
    NO_EXPECTED_GAIN = "NO_EXPECTED_GAIN"
    POLICY_DENIED = "POLICY_DENIED"
    POLICY_RESPONSIBLE_LENDING = "POLICY_RESPONSIBLE_LENDING"
    POLICY_FREQUENCY_CAP = "POLICY_FREQUENCY_CAP"
    POLICY_NO_CREDIT_DECISION = "POLICY_NO_CREDIT_DECISION"
    SEGMENT_SURE_THING = "SEGMENT_SURE_THING"
    SEGMENT_LOST_CAUSE = "SEGMENT_LOST_CAUSE"
    SEGMENT_SLEEPING_DOG = "SEGMENT_SLEEPING_DOG"
    GROUP_MEMBER_DENIED = "GROUP_MEMBER_DENIED"
    CONTROL_HOLDOUT = "CONTROL_HOLDOUT"
    IMPACT_UNAVAILABLE = "IMPACT_UNAVAILABLE"
    NAIVE_BELOW_THRESHOLD = "NAIVE_BELOW_THRESHOLD"
    NAIVE_NOT_CHOSEN = "NAIVE_NOT_CHOSEN"


class AllocationDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    choice_key: str  # user pseudonym, or "group:<id>" for a bundle
    selected: bool
    priority: float
    cost_idr: int
    rank: int | None = None  # 1-based order among selected picks
    is_runner_up: bool = False
    exclusion_reason: ExclusionReason | None = None


class AllocationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: str  # "EXACT_DP" | "GREEDY_DENSITY"
    budget_idr: int
    spent_idr: int
    objective_value_idr: float
    decisions: tuple[AllocationDecision, ...]

    @property
    def selected(self) -> tuple[AllocationDecision, ...]:
        return tuple(d for d in self.decisions if d.selected)

    @property
    def excluded(self) -> tuple[AllocationDecision, ...]:
        return tuple(d for d in self.decisions if not d.selected)
