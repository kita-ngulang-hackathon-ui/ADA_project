"""core-contracts (L0) — Domain types, enums, and the recommendation state machine."""
from core_contracts.errors import (
    ContextTooSmall,
    DomainError,
    IllegalTransition,
    MappingError,
    PolicyViolation,
)
from core_contracts.events import (
    ALLOWED_ATTRIBUTE_KEYS,
    COUNTERPARTY_BEARING_EVENT_TYPES,
    CanonicalEvent,
    CanonicalEventType,
)
from core_contracts.external import ExternalSignal, ScopeType, SignalType
from core_contracts.graph import CircleSnapshot, EdgeWeight, PatternType
from core_contracts.ids import new_id
from core_contracts.incentives import Incentive
from core_contracts.recommendation import (
    ALLOWED_TRANSITIONS,
    Candidate,
    ExternalSignalRef,
    FactSheet,
    ReasonSource,
    Recommendation,
    RecommendationStatus,
    RunnerUp,
    SubjectType,
    assert_transition,
)
from core_contracts.scores import ImpactScore, ImpactSegment, ReasonFactor, RiskScore

__all__ = [
    "ALLOWED_ATTRIBUTE_KEYS",
    "ALLOWED_TRANSITIONS",
    "COUNTERPARTY_BEARING_EVENT_TYPES",
    "Candidate",
    "CanonicalEvent",
    "CanonicalEventType",
    "CircleSnapshot",
    "ContextTooSmall",
    "DomainError",
    "EdgeWeight",
    "ExternalSignal",
    "ExternalSignalRef",
    "FactSheet",
    "IllegalTransition",
    "ImpactScore",
    "ImpactSegment",
    "Incentive",
    "MappingError",
    "PatternType",
    "PolicyViolation",
    "ReasonFactor",
    "ReasonSource",
    "Recommendation",
    "RecommendationStatus",
    "RiskScore",
    "RunnerUp",
    "ScopeType",
    "SignalType",
    "SubjectType",
    "assert_transition",
    "new_id",
]
