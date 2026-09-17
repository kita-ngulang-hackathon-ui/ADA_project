"""core-contracts (L0) — Domain types, enums, and the recommendation state machine."""
from core_contracts.decision import (
    AllocationDecision,
    AllocationResult,
    Candidate,
    ExclusionReason,
    PolicyDecision,
    RankedCandidate,
    RankingStrategy,
    RuleCode,
    RuleResult,
    UserFacts,
)
from core_contracts.errors import (
    ContextTooSmall,
    CrossTenantContext,
    DomainError,
    IllegalTransition,
    MappingError,
    NarrationRejected,
    PolicyViolation,
)
from core_contracts.events import COUNTERPARTY_EVENT_TYPES, CanonicalEvent, CanonicalEventType
from core_contracts.external import ExternalSignal, ScopeType, SignalType
from core_contracts.graph import Circle, CircleSnapshot, Edge, PatternType
from core_contracts.incentives import Incentive
from core_contracts.measurement import Arm, FeatureSnapshot, LabeledExample, OutcomeEvent
from core_contracts.recommendation import (
    ALLOWED_TRANSITIONS,
    FactSheet,
    Recommendation,
    RecommendationStatus,
    assert_transition,
)
from core_contracts.scores import ImpactScore, ImpactSegment, ReasonFactor, RiskScore

__all__ = [
    "ALLOWED_TRANSITIONS",
    "COUNTERPARTY_EVENT_TYPES",
    "AllocationDecision",
    "AllocationResult",
    "Arm",
    "Candidate",
    "CanonicalEvent",
    "CanonicalEventType",
    "Circle",
    "CircleSnapshot",
    "ContextTooSmall",
    "CrossTenantContext",
    "DomainError",
    "Edge",
    "ExclusionReason",
    "ExternalSignal",
    "FactSheet",
    "FeatureSnapshot",
    "IllegalTransition",
    "ImpactScore",
    "ImpactSegment",
    "Incentive",
    "LabeledExample",
    "MappingError",
    "NarrationRejected",
    "OutcomeEvent",
    "PatternType",
    "PolicyDecision",
    "PolicyViolation",
    "RankedCandidate",
    "RankingStrategy",
    "ReasonFactor",
    "Recommendation",
    "RecommendationStatus",
    "RiskScore",
    "RuleCode",
    "RuleResult",
    "ScopeType",
    "SignalType",
    "UserFacts",
    "assert_transition",
]
