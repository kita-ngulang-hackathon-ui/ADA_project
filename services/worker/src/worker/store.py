"""Storage port for the pipeline.

The in-memory implementation (memory_store.py) runs the pipeline in tests and the
offline CLI. A Postgres implementation over `persistence` repositories will
implement the same Protocol.

There is deliberately no method that approves, rejects, or delivers a
recommendation: the worker can reach PENDING_APPROVAL and no further (requirement 8).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from core_contracts import (
    AllocationDecision,
    AllocationResult,
    Arm,
    CanonicalEvent,
    Circle,
    CircleSnapshot,
    ExternalSignal,
    FeatureSnapshot,
    ImpactScore,
    Incentive,
    LabeledExample,
    OutcomeEvent,
    PolicyDecision,
    Recommendation,
    RiskScore,
)


@dataclass(frozen=True)
class TenantRecord:
    tenant_id: str
    slug: str
    profile_type: str
    mapping: dict[str, Any]


@dataclass
class RawEventRecord:
    raw_event_id: str
    tenant_id: str
    body: dict[str, Any]
    status: str = "NEW"  # NEW | PROCESSED | UNMAPPED
    error: str | None = None


@dataclass
class StageRecord:
    run_id: str
    tenant_id: str
    stage: str
    status: str  # PENDING | RUNNING | DONE | FAILED | SKIPPED
    detail: dict[str, Any] = field(default_factory=dict)


class PipelineStore(Protocol):
    # Tenants, events
    def get_tenant(self, tenant_id: str) -> TenantRecord: ...
    def claim_raw_events(self, tenant_id: str, limit: int) -> list[RawEventRecord]: ...
    def mark_raw_event(self, tenant_id: str, raw_event_id: str, status: str,
                       error: str | None = None) -> None: ...
    def save_canonical_events(self, tenant_id: str, events: list[CanonicalEvent]) -> int: ...
    def load_canonical_events(self, tenant_id: str, since: datetime) -> list[CanonicalEvent]: ...
    def upsert_user_attributes(self, tenant_id: str, user_pseudonym: str,
                               attributes: dict[str, Any]) -> None: ...
    def load_user_attributes(self, tenant_id: str) -> dict[str, dict[str, Any]]: ...

    # Catalog, signals, context
    def load_incentives(self, tenant_id: str) -> list[Incentive]: ...
    def save_external_signals(self, signals: list[ExternalSignal]) -> None: ...
    def load_labeled_examples(self, tenant_id: str) -> list[LabeledExample]: ...
    def load_contact_times(self, tenant_id: str) -> dict[str, list[datetime]]: ...

    # Run bookkeeping and stage outputs
    def record_stage(self, record: StageRecord) -> None: ...
    def save_circles(self, tenant_id: str, run_id: str, snapshots: list[CircleSnapshot],
                     circles: list[Circle]) -> None: ...
    def save_risk_scores(self, tenant_id: str, run_id: str, scores: list[RiskScore]) -> None: ...
    def save_impact_scores(self, tenant_id: str, run_id: str,
                           scores: dict[str, ImpactScore]) -> None: ...
    def save_policy_decisions(self, tenant_id: str, run_id: str,
                              decisions: list[PolicyDecision]) -> None: ...
    def get_or_create_experiment(self, tenant_id: str) -> str: ...
    def save_arm_assignments(self, tenant_id: str, experiment_id: str,
                             arms: dict[str, Arm]) -> None: ...
    def save_allocation(self, tenant_id: str, run_id: str, result: AllocationResult,
                        extra_decisions: list[AllocationDecision]) -> None: ...
    def save_narration(self, tenant_id: str, run_id: str, fact_sheet_hash: str, text: str,
                       source: str) -> None: ...
    def save_feature_snapshots(self, snapshots: list[FeatureSnapshot]) -> None: ...
    def create_recommendations(self, recommendations: list[Recommendation]) -> None: ...
    def append_audit(self, tenant_id: str, actor: str, action: str, entity_type: str,
                     entity_id: str, detail: dict[str, Any]) -> None: ...

    # Feedback loop (requirement 11)
    def load_outcomes(self, tenant_id: str) -> list[OutcomeEvent]: ...
    def load_feature_snapshots(self, tenant_id: str) -> dict[tuple[str, str], FeatureSnapshot]: ...
    def save_labeled_examples(self, examples: list[LabeledExample]) -> None: ...
