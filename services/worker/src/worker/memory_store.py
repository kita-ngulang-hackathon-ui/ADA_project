"""In-memory PipelineStore for tests and the offline CLI.

Every collection is keyed by tenant_id, and readers only ever look inside one
tenant's bucket, mirroring the RLS isolation of the Postgres store.
"""
from collections import defaultdict
from datetime import datetime
from typing import Any

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
    RecommendationStatus,
    RiskScore,
)

from worker.store import RawEventRecord, StageRecord, TenantRecord


class InMemoryStore:
    def __init__(self) -> None:
        self.tenants: dict[str, TenantRecord] = {}
        self.raw_events: dict[str, list[RawEventRecord]] = defaultdict(list)
        self.canonical_events: dict[str, dict[str, CanonicalEvent]] = defaultdict(dict)
        self.user_attributes: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.incentives: dict[str, list[Incentive]] = defaultdict(list)
        self.external_signals: dict[str, ExternalSignal] = {}
        self.labeled_examples: dict[str, dict[str, LabeledExample]] = defaultdict(dict)
        self.contacts: dict[str, dict[str, list[datetime]]] = defaultdict(lambda: defaultdict(list))
        self.stages: list[StageRecord] = []
        self.circle_snapshots: dict[str, list[CircleSnapshot]] = defaultdict(list)
        self.circles: dict[str, list[Circle]] = defaultdict(list)
        self.risk_scores: dict[str, list[RiskScore]] = defaultdict(list)
        self.impact_scores: dict[str, dict[str, ImpactScore]] = defaultdict(dict)
        self.policy_decisions: dict[str, list[PolicyDecision]] = defaultdict(list)
        self.experiments: dict[str, str] = {}
        self.arm_assignments: dict[str, dict[str, Arm]] = defaultdict(dict)
        self.allocations: dict[str, list[tuple[AllocationResult, list[AllocationDecision]]]] = (
            defaultdict(list)
        )
        self.narrations: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.feature_snapshots: dict[str, dict[tuple[str, str], FeatureSnapshot]] = defaultdict(dict)
        self.recommendations: dict[str, dict[str, Recommendation]] = defaultdict(dict)
        self.audit_log: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.outcomes: dict[str, list[OutcomeEvent]] = defaultdict(list)

    # --- seeding helpers (not part of the Protocol) ---
    def add_tenant(self, tenant: TenantRecord) -> None:
        self.tenants[tenant.tenant_id] = tenant

    def add_raw_events(self, tenant_id: str, bodies: list[dict[str, Any]]) -> None:
        bucket = self.raw_events[tenant_id]
        known = {r.body.get("client_event_id") for r in bucket}
        for body in bodies:  # idempotent on client_event_id, like the unique index
            if body.get("client_event_id") in known:
                continue
            known.add(body.get("client_event_id"))
            bucket.append(RawEventRecord(raw_event_id=f"raw-{len(bucket) + 1}",
                                         tenant_id=tenant_id, body=body))

    def set_incentives(self, tenant_id: str, incentives: list[Incentive]) -> None:
        self.incentives[tenant_id] = list(incentives)

    def add_contacts(self, tenant_id: str, user_pseudonym: str, times: list[datetime]) -> None:
        self.contacts[tenant_id][user_pseudonym].extend(times)

    def add_outcomes(self, outcomes: list[OutcomeEvent]) -> None:
        for o in outcomes:
            self.outcomes[o.tenant_id].append(o)

    # --- Protocol ---
    def get_tenant(self, tenant_id: str) -> TenantRecord:
        return self.tenants[tenant_id]

    def claim_raw_events(self, tenant_id: str, limit: int) -> list[RawEventRecord]:
        return [r for r in self.raw_events[tenant_id] if r.status == "NEW"][:limit]

    def mark_raw_event(self, tenant_id: str, raw_event_id: str, status: str,
                       error: str | None = None) -> None:
        for r in self.raw_events[tenant_id]:
            if r.raw_event_id == raw_event_id:
                r.status, r.error = status, error

    def save_canonical_events(self, tenant_id: str, events: list[CanonicalEvent]) -> int:
        bucket = self.canonical_events[tenant_id]
        added = 0
        for e in events:
            if e.tenant_id != tenant_id:
                raise ValueError("canonical event written to the wrong tenant")
            if e.client_event_id not in bucket:
                bucket[e.client_event_id] = e
                added += 1
        return added

    def load_canonical_events(self, tenant_id: str, since: datetime) -> list[CanonicalEvent]:
        return sorted((e for e in self.canonical_events[tenant_id].values() if e.occurred_at >= since),
                      key=lambda e: (e.occurred_at, e.client_event_id))

    def upsert_user_attributes(self, tenant_id: str, user_pseudonym: str,
                               attributes: dict[str, Any]) -> None:
        self.user_attributes[tenant_id].setdefault(user_pseudonym, {}).update(attributes)

    def load_user_attributes(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        return {u: dict(a) for u, a in self.user_attributes[tenant_id].items()}

    def load_incentives(self, tenant_id: str) -> list[Incentive]:
        return list(self.incentives[tenant_id])

    def save_external_signals(self, signals: list[ExternalSignal]) -> None:
        for s in signals:
            self.external_signals[s.signal_id] = s

    def load_labeled_examples(self, tenant_id: str) -> list[LabeledExample]:
        return list(self.labeled_examples[tenant_id].values())

    def load_contact_times(self, tenant_id: str) -> dict[str, list[datetime]]:
        return {u: list(t) for u, t in self.contacts[tenant_id].items()}

    def record_stage(self, record: StageRecord) -> None:
        self.stages.append(record)

    def save_circles(self, tenant_id, run_id, snapshots, circles) -> None:
        self.circle_snapshots[tenant_id].extend(snapshots)
        self.circles[tenant_id].extend(circles)

    def save_risk_scores(self, tenant_id, run_id, scores) -> None:
        self.risk_scores[tenant_id].extend(scores)

    def save_impact_scores(self, tenant_id, run_id, scores, segments) -> None:
        self.impact_scores[tenant_id].update(scores)

    def save_policy_decisions(self, tenant_id, run_id, decisions) -> None:
        self.policy_decisions[tenant_id].extend(decisions)

    def get_or_create_experiment(self, tenant_id: str) -> str:
        return self.experiments.setdefault(tenant_id, f"exp-{tenant_id}-1")

    def save_arm_assignments(self, tenant_id, experiment_id, arms) -> None:
        for unit, arm in arms.items():
            existing = self.arm_assignments[tenant_id].setdefault(unit, arm)
            if existing != arm:
                raise ValueError("arm assignment changed within an experiment")

    def save_allocation(self, tenant_id, run_id, result, extra_decisions, candidates) -> None:
        # `candidates` is only needed by the Postgres store's richer
        # allocation_candidates audit table; the in-memory store has no
        # equivalent table, so it is accepted for Protocol compliance and
        # not retained.
        self.allocations[tenant_id].append((result, list(extra_decisions)))

    def save_narration(self, tenant_id, run_id, fact_sheet_hash, text, source) -> None:
        self.narrations[tenant_id].append(
            {"run_id": run_id, "fact_sheet_hash": fact_sheet_hash, "text": text, "source": source}
        )

    def save_feature_snapshots(self, snapshots: list[FeatureSnapshot]) -> None:
        for s in snapshots:
            self.feature_snapshots[s.tenant_id][(s.run_id, s.user_pseudonym)] = s

    def create_recommendations(self, recommendations: list[Recommendation]) -> None:
        for r in recommendations:
            # Mirrors the DB column grant: the worker role may only insert PENDING_APPROVAL rows.
            if r.status != RecommendationStatus.PENDING_APPROVAL or r.reviewed_by or r.reviewed_at:
                raise PermissionError("worker may only create PENDING_APPROVAL recommendations")
            self.recommendations[r.tenant_id][r.recommendation_id] = r

    def append_audit(self, tenant_id, actor, action, entity_type, entity_id, detail) -> None:
        self.audit_log[tenant_id].append({
            "actor": actor, "action": action, "entity_type": entity_type,
            "entity_id": entity_id, "detail": detail,
        })

    def load_outcomes(self, tenant_id: str) -> list[OutcomeEvent]:
        return list(self.outcomes[tenant_id])

    def load_feature_snapshots(self, tenant_id: str) -> dict[tuple[str, str], FeatureSnapshot]:
        return dict(self.feature_snapshots[tenant_id])

    def save_labeled_examples(self, examples: list[LabeledExample]) -> None:
        for e in examples:
            self.labeled_examples[e.tenant_id].setdefault(e.source_outcome_id, e)
