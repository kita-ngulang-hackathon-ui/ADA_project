"""SQLAlchemy 2.0 declarative models (ARCHITECTURE.md §8).

Every domain table carries tenant_id UUID NOT NULL. Money is always BIGINT
IDR. Row-Level Security policies and role grants live in `roles.sql` /
migrations; this module only defines the shape.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# --------------------------------------------------------------------------
# Tenancy and configuration
# --------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("profile_type IN ('WALLET','LENDING')", name="ck_tenants_profile_type"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    profile_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    key_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventTypeMapping(Base):
    __tablename__ = "event_type_mappings"
    __table_args__ = (UniqueConstraint("tenant_id", "client_event_type", name="uq_event_type_mappings"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_event_type: Mapped[str] = mapped_column(String, nullable=False)
    canonical_event_type: Mapped[str] = mapped_column(String, nullable=False)
    amount_field_path: Mapped[str] = mapped_column(String, nullable=False)
    counterparty_field_path: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at_field_path: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IncentiveModel(Base):
    __tablename__ = "incentives"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_incentives_tenant_code"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    cost_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    encourages_borrowing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Anything touching credit limits or pricing (section 4); flagged so policy-guard can deny it.
    changes_credit_terms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # subject_type='GROUP' IS core_contracts.Incentive.is_group -- no separate column.
    subject_type: Mapped[str] = mapped_column(String, nullable=False, default="USER")
    # Empty list means applicable to every tenant profile type.
    applicable_profile_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# --------------------------------------------------------------------------
# Events and external signals
# --------------------------------------------------------------------------


class RawEvent(Base):
    __tablename__ = "raw_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_event_id", name="uq_raw_events_idempotency"),
        Index(
            "ix_raw_events_unprocessed",
            "tenant_id",
            "processed_at",
            postgresql_where=Text("processed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_event_id: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    process_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CanonicalEventRow(Base):
    __tablename__ = "canonical_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    raw_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    canonical_type: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counterparty_pseudonym: Mapped[str | None] = mapped_column(String, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ExternalSignalRow(Base):
    __tablename__ = "external_signals"
    __table_args__ = (
        CheckConstraint("scope_type IN ('CLIENT','REGION','COHORT')", name="ck_external_signals_scope"),
        # NO user_pseudonym / counterparty_pseudonym column exists on this table.
        # That absence is the enforcement of the section-4 external-signal boundary --
        # see tests/invariants/test_external_signals_have_no_user_column.py.
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope_type: Mapped[str] = mapped_column(String, nullable=False)
    scope_key: Mapped[str] = mapped_column(String, nullable=False)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Users and graph
# --------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_state IN ('NEW','ACTIVE','COOLING','DORMANT','CHURNED')",
            name="ck_users_lifecycle_state",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String, nullable=False, default="NEW")
    region_code: Mapped[str | None] = mapped_column(String, nullable=True)
    cohort_key: Mapped[str | None] = mapped_column(String, nullable=True)


class CounterpartyNode(Base):
    """Structural facts only -- no column can hold a name, contact detail,
    amount, or any other counterparty attribute (section 4, no-counterparty-profiling)."""

    __tablename__ = "counterparty_nodes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    counterparty_pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_count_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_own_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RelationshipEdge(Base):
    __tablename__ = "relationship_edges"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_pseudonym", "counterparty_pseudonym", "edge_type",
            name="uq_relationship_edges",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    counterparty_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    edge_type: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    txn_count_90d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cadence_days: Mapped[float | None] = mapped_column(nullable=True)
    decay_weight: Mapped[float] = mapped_column(nullable=False, default=0.0)


class TransactionCircle(Base):
    __tablename__ = "transaction_circles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    stability_score: Mapped[float | None] = mapped_column(nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CircleMember(Base):
    __tablename__ = "circle_members"

    circle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_pseudonym: Mapped[str] = mapped_column(String, primary_key=True)


# --------------------------------------------------------------------------
# Scores
# --------------------------------------------------------------------------


class RiskScoreRow(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint(
            "pattern_type IN ('CIRCLE_SPECIFIC','MARKET_DRIVEN','STABLE')",
            name="ck_risk_scores_pattern_type",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # churn_risk and delta_stability are stored SEPARATELY, never pre-blended (ADR-013).
    churn_risk: Mapped[float] = mapped_column(nullable=False)
    delta_stability: Mapped[float] = mapped_column(nullable=False)
    pattern_type: Mapped[str] = mapped_column(String, nullable=False)
    external_signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    external_signal_contribution: Mapped[float | None] = mapped_column(nullable=True)
    context_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ImpactScoreRow(Base):
    __tablename__ = "impact_scores"
    __table_args__ = (
        CheckConstraint(
            "segment IN ('PERSUADABLE','SURE_THING','LOST_CAUSE','SLEEPING_DOG')",
            name="ck_impact_scores_segment",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    incentive_code: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    p_incentivized: Mapped[float] = mapped_column(nullable=False)
    p_not_incentivized: Mapped[float] = mapped_column(nullable=False)
    impact_score: Mapped[float] = mapped_column(nullable=False)
    segment: Mapped[str] = mapped_column(String, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


# --------------------------------------------------------------------------
# Pipeline runs (drives GET /console/v1/pipeline/runs/{id})
# --------------------------------------------------------------------------

# Kept in step with worker.pipeline.STAGES (services/worker/tests/test_pipeline.py asserts it).
PIPELINE_STAGES: tuple[str, ...] = (
    "INGEST", "FEEDBACK", "EXTERNAL", "GRAPH", "RISK", "IMPACT", "POLICY", "RANK", "ALLOCATE",
    "EXPLAIN", "PERSIST",
)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')", name="ck_pipeline_runs_status"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="QUEUED")
    # Incremented on every claim. The worker retries up to WORKER_MAX_RETRIES,
    # counting a crashed (stale RUNNING) claim as one attempt.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stages: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    external_source: Mapped[str | None] = mapped_column(String, nullable=True)
    ranking_strategy: Mapped[str | None] = mapped_column(String, nullable=True)
    context_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_source_counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Decisioning
# --------------------------------------------------------------------------


class AllocationRun(Base):
    __tablename__ = "allocation_runs"
    __table_args__ = (
        CheckConstraint("strategy IN ('EXACT_DP','GREEDY_DENSITY')", name="ck_allocation_runs_strategy"),
        CheckConstraint(
            "ranking_strategy IN ('TABPFN','FALLBACK')", name="ck_allocation_runs_ranking_strategy"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    budget_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    ranking_strategy: Mapped[str] = mapped_column(String, nullable=False)
    context_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    objective_value_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)


class AllocationCandidate(Base):
    __tablename__ = "allocation_candidates"
    __table_args__ = (
        CheckConstraint("subject_type IN ('USER','GROUP')", name="ck_allocation_candidates_subject_type"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    allocation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    user_pseudonym: Mapped[str | None] = mapped_column(String, nullable=True)
    circle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    incentive_code: Mapped[str] = mapped_column(String, nullable=False)
    churn_risk: Mapped[float | None] = mapped_column(nullable=True)
    impact_score: Mapped[float | None] = mapped_column(nullable=True)
    segment: Mapped[str | None] = mapped_column(String, nullable=True)
    pattern_type: Mapped[str | None] = mapped_column(String, nullable=True)
    priority_idr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("subject_type IN ('USER','GROUP')", name="ck_recommendations_subject_type"),
        CheckConstraint(
            "(subject_type = 'USER' AND user_pseudonym IS NOT NULL AND circle_id IS NULL) OR "
            "(subject_type = 'GROUP' AND circle_id IS NOT NULL AND user_pseudonym IS NULL)",
            name="ck_recommendations_subject_exclusive",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','EXPIRED','DELIVERED')",
            name="ck_recommendations_status",
        ),
        # Requirement 8, mechanism 3: APPROVED/DELIVERED require a reviewer.
        CheckConstraint(
            "status <> 'APPROVED' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_recommendations_approved_needs_reviewer",
        ),
        CheckConstraint(
            "status <> 'REJECTED' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_recommendations_rejected_needs_reviewer",
        ),
        CheckConstraint(
            "status <> 'DELIVERED' OR (reviewed_by IS NOT NULL AND delivered_at IS NOT NULL)",
            name="ck_recommendations_delivered_needs_review_and_delivery",
        ),
        # Top pick OR runner-up per (tenant, run, user), never both -- partial unique index.
        Index(
            "uq_recommendations_active_per_user",
            "tenant_id", "allocation_run_id", "user_pseudonym",
            unique=True,
            postgresql_where=Text("status IN ('APPROVED','DELIVERED')"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    allocation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    allocation_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    user_pseudonym: Mapped[str | None] = mapped_column(String, nullable=True)
    circle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    incentive_code: Mapped[str] = mapped_column(String, nullable=False)
    cost_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    priority_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    user_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_runner_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_factors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason_source: Mapped[str | None] = mapped_column(String, nullable=True)
    fact_sheet_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_ref: Mapped[str | None] = mapped_column(String, nullable=True)


class Narration(Base):
    """Validated LLM output cache, keyed by fact_sheet_hash -- guarantees
    identical narration text on re-run."""

    __tablename__ = "narrations"

    fact_sheet_hash: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyDecision(Base):
    """Audit trail of every ALLOW/DENY, including denials that never became
    a recommendation."""

    __tablename__ = "policy_decisions"
    __table_args__ = (CheckConstraint("outcome IN ('ALLOW','DENY')", name="ck_policy_decisions_outcome"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    candidate_ref: Mapped[str] = mapped_column(String, nullable=False)
    rule_code: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContactLog(Base):
    """Sole input to the frequency-cap check."""

    __tablename__ = "contact_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Measurement and feedback
# --------------------------------------------------------------------------


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    control_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    naive_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        CheckConstraint("arm IN ('CONTROL','NAIVE','ENGINE')", name="ck_experiment_assignments_arm"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    arm: Mapped[str] = mapped_column(String, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutcomeEvent(Base):
    __tablename__ = "outcome_events"
    __table_args__ = (
        CheckConstraint(
            "outcome_type IN ('RESPONDED','RETAINED','CHURNED')", name="ck_outcome_events_type"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    outcome_type: Mapped[str] = mapped_column(String, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_idr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class LabeledExample(Base):
    __tablename__ = "labeled_examples"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_outcome_id", name="uq_labeled_examples_dedupe"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_experiment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_outcome_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    arm: Mapped[str] = mapped_column(String, nullable=False)
    treated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retained: Mapped[bool] = mapped_column(Boolean, nullable=False)
    realized_value_idr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    feature_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureSnapshotRow(Base):
    """Features and scores captured at recommendation time (requirement 11).

    Feedback reads this snapshot, never later data, so labeled examples never
    leak outcome information back into their own features.
    """

    __tablename__ = "feature_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "user_pseudonym", name="uq_feature_snapshots_run_user"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_pseudonym: Mapped[str] = mapped_column(String, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    churn_risk: Mapped[float | None] = mapped_column(nullable=True)
    impact_score: Mapped[float | None] = mapped_column(nullable=True)
    pattern_type: Mapped[str | None] = mapped_column(String, nullable=True)
    incentive_code: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    business_value_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Append-only. No update/delete path exists in the repository layer."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


# Tables that must carry RLS: every domain table except `tenants` (there is
# no wider tenant to scope it by) and `api_keys` (auth must resolve tenant_id
# FROM the api key before app.tenant_id can be set -- RLS on this table would
# make that lookup impossible).
_NO_RLS_TABLES = frozenset({"tenants", "api_keys"})
RLS_TABLE_NAMES: tuple[str, ...] = tuple(
    t.name for t in Base.metadata.sorted_tables if t.name not in _NO_RLS_TABLES
)
