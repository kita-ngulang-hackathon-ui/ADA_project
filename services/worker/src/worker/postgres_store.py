"""PostgresPipelineStore: the PipelineStore Protocol (worker.store) implemented
over `persistence` repositories.

Scope and lifetime: one instance is bound to one (engine, tenant_id) and is
meant to be constructed FRESH for each `run_pipeline()` call. It holds a few
small in-memory caches purely to bridge two Protocol calls within that SAME
run -- the Protocol itself has no "start of run" hook, and several DB writes
depend on state produced by an earlier call in the same run:

- `_snapshot_by_user`: GRAPH's `save_circles` -> RISK's `save_risk_scores`.
  `core_contracts.RiskScore` carries no delta_stability/pattern_type (ADR-013
  keeps them off the score object); `risk_scores` rows need both, sourced
  from the CircleSnapshot GRAPH already computed for that user.
- `_circle_id_by_str`: GRAPH's `save_circles` -> ALLOCATE/PERSIST resolving a
  `Circle.circle_id` (a content hash string, not a UUID) to the UUID primary
  key minted for its `transaction_circles` row.
- `_allocation_run_id`, `_alloc_candidate_row_id_by_candidate_id`: ALLOCATE's
  `save_allocation` -> PERSIST's `create_recommendations`, which needs the
  real `allocation_runs.id` (recommendations.allocation_run_id is NOT NULL)
  and, best-effort, the matching `allocation_candidates.id`.
- `_rank_context_rows`, `_rank_strategy_db`: cached off the RANK stage's
  `record_stage` detail, since `save_allocation`'s inputs (AllocationResult,
  AllocationDecision) carry neither a ranking strategy nor a context size,
  and `allocation_runs.ranking_strategy` / `.context_row_count` are NOT NULL.

Known, deliberate simplifications (see also migration 0008's docstring and
services/worker/store.py's `save_allocation` docstring for the two other
Protocol/schema gaps this file works around):

- `claim_raw_events` commits (releasing its `FOR UPDATE SKIP LOCKED` row
  locks) before `mark_raw_event` is called per item. Safe for the single
  worker replica this demo runs; a second replica could double-claim in the
  gap. Closing that fully needs one transaction spanning both calls, which
  the Protocol's per-call method shape does not offer.
- `record_stage` only persists stage -> status (`pipeline_runs.stages` has no
  slot for the detail dict); the RANK stage's detail is cached in memory
  (above) only for the one field `save_allocation` needs, not persisted.
- `load_outcomes` reconstructs `run_id`/`arm`/`treated`/`spend_idr` fields
  that `outcome_events` does not store as columns: `arm` via a join to
  `experiment_assignments`; `run_id` via the user's latest `feature_snapshots`
  row (outcomes without one are already dropped downstream by
  `feedback.to_labeled_examples`, so an unresolved run_id is harmless);
  `treated` as `arm != CONTROL`; `spend_idr` from the generic `value_idr`
  column. `outcome_type='RESPONDED'` is treated as `retained=True`.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from core_contracts import (
    AllocationDecision,
    AllocationResult,
    Arm,
    Candidate,
    CanonicalEvent,
    CanonicalEventType,
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
from persistence.models import ExperimentAssignment, FeatureSnapshotRow
from persistence.models import OutcomeEvent as OutcomeEventRow
from persistence.repositories import allocations, contacts, events, measurement, scores
from persistence.repositories import audit as audit_repo
from persistence.repositories import external_signals as external_signals_repo
from persistence.repositories import feature_snapshots as feature_snapshots_repo
from persistence.repositories import feedback as feedback_repo
from persistence.repositories import incentives as incentives_repo
from persistence.repositories import mappings as mappings_repo
from persistence.repositories import narrations as narrations_repo
from persistence.repositories import pipeline as pipeline_repo
from persistence.repositories import policy as policy_repo
from persistence.repositories import recommendations as recommendations_repo
from persistence.repositories import tenants as tenants_repo
from persistence.repositories import users as users_repo
from persistence.session import tenant_session
from sqlalchemy import Engine, select

from worker.store import RawEventRecord, StageRecord, TenantRecord

# allocation_runs.ranking_strategy CHECK only allows these two values, even
# though core_contracts.RankingStrategy has four -- SKLEARN_STAND_IN is still
# in-context scoring under the hood (TabPFN just isn't installed) so it is
# reported as TABPFN; NAIVE_RISK_ONLY never actually reaches an engine-arm
# allocation run, but maps to FALLBACK if it somehow did.
_RANKING_STRATEGY_FOR_DB = {
    "TABPFN": "TABPFN",
    "SKLEARN_STAND_IN": "TABPFN",
    "FALLBACK": "FALLBACK",
    "NAIVE_RISK_ONLY": "FALLBACK",
}


class PostgresPipelineStore:
    def __init__(self, engine: Engine, tenant_id: str) -> None:
        self._engine = engine
        self._tenant_id = tenant_id
        self._snapshot_by_user: dict[str, CircleSnapshot] = {}
        self._circle_id_by_str: dict[str, uuid.UUID] = {}
        self._allocation_run_id: uuid.UUID | None = None
        self._alloc_candidate_row_id_by_candidate_id: dict[str, uuid.UUID] = {}
        self._rank_context_rows: int = 0
        self._rank_strategy_db: str = "FALLBACK"

    def _session(self):
        return tenant_session(self._engine, self._tenant_id)

    # ---------------------------------------------------------- tenants, events

    def get_tenant(self, tenant_id: str) -> TenantRecord:
        with self._session() as session:
            tenant = tenants_repo.get_by_id(session, tenant_id=tenant_id)
            if tenant is None:
                raise LookupError(f"tenant {tenant_id} not found")
            rows = mappings_repo.list_mappings(session, tenant_id=tenant_id, active_only=True)
            mapping = {
                "tenant_slug": tenant.slug,
                "profile_type": tenant.profile_type,
                "mappings": [
                    {
                        "client_event_type": r.client_event_type,
                        "canonical_event_type": r.canonical_event_type,
                        "amount_field_path": r.amount_field_path,
                        "counterparty_field_path": r.counterparty_field_path,
                        "occurred_at_field_path": r.occurred_at_field_path,
                        "active": r.active,
                    }
                    for r in rows
                ],
            }
            return TenantRecord(
                tenant_id=str(tenant.id), slug=tenant.slug, profile_type=tenant.profile_type, mapping=mapping
            )

    def claim_raw_events(self, tenant_id: str, limit: int) -> list[RawEventRecord]:
        with self._session() as session:
            rows = events.claim_unprocessed(session, tenant_id=tenant_id, batch_size=limit)
            return [
                RawEventRecord(raw_event_id=str(r.id), tenant_id=tenant_id, body=r.payload, status="NEW")
                for r in rows
            ]

    def mark_raw_event(self, tenant_id: str, raw_event_id: str, status: str, error: str | None = None) -> None:
        with self._session() as session:
            rid = uuid.UUID(raw_event_id)
            if status == "PROCESSED":
                events.mark_processed(session, raw_event_id=rid)
            elif status == "UNMAPPED":
                events.mark_unmapped(session, raw_event_id=rid, error=error or "")
            else:
                raise ValueError(f"unknown raw event status {status!r}")

    def save_canonical_events(self, tenant_id: str, events_in: list[CanonicalEvent]) -> int:
        if not events_in:
            return 0
        with self._session() as session:
            rows = []
            for e in events_in:
                raw_id = events.get_raw_event_id_by_client_id(
                    session, tenant_id=tenant_id, client_event_id=e.client_event_id
                )
                if raw_id is None:
                    raise LookupError(f"no raw_events row for client_event_id {e.client_event_id!r}")
                rows.append({
                    "tenant_id": tenant_id,
                    "raw_event_id": raw_id,
                    "user_pseudonym": e.user_pseudonym,
                    "canonical_type": e.event_type.value,
                    "occurred_at": e.occurred_at,
                    "amount_idr": e.amount_idr or 0,
                    "counterparty_pseudonym": e.counterparty_pseudonym,
                    "attributes": e.attributes,
                })
            ids = events.insert_canonical_events(session, rows)
            return len(ids)

    def load_canonical_events(self, tenant_id: str, since: datetime) -> list[CanonicalEvent]:
        with self._session() as session:
            rows = events.load_since(session, tenant_id=tenant_id, since=since)
            return [
                CanonicalEvent(
                    tenant_id=row["tenant_id"],
                    client_event_id=row["client_event_id"],
                    event_type=CanonicalEventType(row["event_type"]),
                    occurred_at=row["occurred_at"],
                    user_pseudonym=row["user_pseudonym"],
                    amount_idr=row["amount_idr"],
                    counterparty_pseudonym=row["counterparty_pseudonym"],
                    attributes=row["attributes"],
                )
                for row in rows
            ]

    def upsert_user_attributes(self, tenant_id: str, user_pseudonym: str, attributes: dict[str, Any]) -> None:
        with self._session() as session:
            users_repo.upsert_attributes(
                session, tenant_id=tenant_id, user_pseudonym=user_pseudonym, attributes=attributes
            )

    def load_user_attributes(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        with self._session() as session:
            return users_repo.load_attributes(session, tenant_id=tenant_id)

    # ---------------------------------------------------------- catalog, signals, context

    def load_incentives(self, tenant_id: str) -> list[Incentive]:
        with self._session() as session:
            rows = incentives_repo.list_incentives(session, tenant_id=tenant_id, active_only=True)
            return [
                Incentive(
                    code=r.code,
                    display_name=r.display_name,
                    cost_idr=r.cost_idr,
                    encourages_borrowing=r.encourages_borrowing,
                    changes_credit_terms=r.changes_credit_terms,
                    is_group=r.subject_type == "GROUP",
                    applicable_profile_types=tuple(r.applicable_profile_types or ()),
                    active=r.active,
                )
                for r in rows
            ]

    def save_external_signals(self, signals: list[ExternalSignal]) -> None:
        if not signals:
            return
        rows = [
            {
                "scope_type": s.scope_type.value,
                "scope_key": s.scope_key,
                "signal_type": s.signal_type.value,
                "value": s.value,
                "observed_at": s.observed_at,
                "source": s.source,
            }
            for s in signals
        ]
        with self._session() as session:
            external_signals_repo.insert_signals(session, tenant_id=self._tenant_id, rows=rows)

    def load_labeled_examples(self, tenant_id: str) -> list[LabeledExample]:
        with self._session() as session:
            rows = scores.load_labeled_examples(session, tenant_id=tenant_id)
            examples = []
            for row in rows:
                snap = row.feature_snapshot or {}
                examples.append(LabeledExample(
                    tenant_id=tenant_id,
                    source_outcome_id=str(row.source_outcome_id) if row.source_outcome_id else str(row.id),
                    user_pseudonym=row.user_pseudonym,
                    features=snap.get("features", {}),
                    arm=Arm(row.arm),
                    treated=row.treated,
                    retained=row.retained,
                    churn_risk=snap.get("churn_risk"),
                    impact_score=snap.get("impact_score"),
                    pattern_type=snap.get("pattern_type"),
                    incentive_code=snap.get("incentive_code"),
                    cost_idr=snap.get("cost_idr", 0),
                    business_value_idr=snap.get("business_value_idr", 0),
                    realized_value_idr=float(row.realized_value_idr or 0),
                ))
            return examples

    def load_contact_times(self, tenant_id: str) -> dict[str, list[datetime]]:
        with self._session() as session:
            return contacts.load_contact_times(session, tenant_id=tenant_id)

    # ---------------------------------------------------------- run bookkeeping, stage outputs

    def record_stage(self, record: StageRecord) -> None:
        with self._session() as session:
            pipeline_repo.update_stage(
                session, tenant_id=record.tenant_id, run_id=uuid.UUID(record.run_id),
                stage=record.stage, status=record.status,
            )
        if record.stage == "RANK" and record.status == "DONE":
            self._rank_context_rows = int(record.detail.get("context_rows") or 0)
            strategy = record.detail.get("ranking_strategy")
            if strategy:
                self._rank_strategy_db = _RANKING_STRATEGY_FOR_DB.get(strategy, "FALLBACK")

    def save_circles(self, tenant_id: str, run_id: str, snapshots: list[CircleSnapshot], circles: list[Circle]) -> None:
        self._snapshot_by_user.update({s.user_pseudonym: s for s in snapshots})
        if not circles:
            return
        snap_by_user = {s.user_pseudonym: s for s in snapshots}
        with self._session() as session:
            for circle in circles:
                members = [snap_by_user[m] for m in circle.members if m in snap_by_user]
                stability = (
                    sum(m.delta_stability for m in members) / len(members) if members else None
                )
                [row] = scores.write_circle_snapshots(
                    session, tenant_id=tenant_id,
                    rows=[{"member_count": len(circle.members), "stability_score": stability}],
                )
                self._circle_id_by_str[circle.circle_id] = row.id
                scores.write_circle_members(
                    session, tenant_id=tenant_id, circle_id=row.id, user_pseudonyms=list(circle.members)
                )

    def save_risk_scores(self, tenant_id: str, run_id: str, scores_in: list[RiskScore]) -> None:
        if not scores_in:
            return
        rows = []
        for s in scores_in:
            snap = self._snapshot_by_user.get(s.user_pseudonym)
            rows.append({
                "user_pseudonym": s.user_pseudonym,
                "pipeline_run_id": uuid.UUID(run_id),
                "churn_risk": s.churn_risk,
                "delta_stability": snap.delta_stability if snap else 0.0,
                "pattern_type": snap.pattern_type.value if snap else "STABLE",
                "external_signal_id": uuid.UUID(s.external_signal_id) if s.external_signal_id else None,
                "external_signal_contribution": s.external_signal_contribution,
                "context_row_count": s.context_row_count,
                "features": {},
            })
        with self._session() as session:
            scores.write_risk_scores(session, tenant_id=tenant_id, rows=rows)

    def save_impact_scores(
        self, tenant_id: str, run_id: str, scores_in: dict[str, ImpactScore], segments: dict[str, Any]
    ) -> None:
        if not scores_in:
            return
        rows = [
            {
                "user_pseudonym": user,
                # The impact model estimates one incentivized-vs-not propensity per
                # user, not per catalog incentive -- incentive_code is NOT NULL on
                # this table but genuinely inapplicable here.
                "incentive_code": "GENERIC",
                "p_incentivized": s.p_incentivized,
                "p_not_incentivized": s.p_not_incentivized,
                "impact_score": s.impact_score,
                "segment": segments[user].value,
                "features": {},
            }
            for user, s in scores_in.items()
        ]
        with self._session() as session:
            scores.write_impact_scores(session, tenant_id=tenant_id, rows=rows)

    def save_policy_decisions(self, tenant_id: str, run_id: str, decisions: list[PolicyDecision]) -> None:
        if not decisions:
            return
        rows = []
        for decision in decisions:
            for result in decision.results:
                rows.append({
                    "recommendation_id": None,
                    "candidate_ref": decision.candidate_id,
                    "rule_code": result.rule_code.value,
                    "outcome": "ALLOW" if result.allowed else "DENY",
                    "detail": {"reason": result.reason, "user_pseudonym": decision.user_pseudonym},
                })
        with self._session() as session:
            policy_repo.write_decisions(session, tenant_id=tenant_id, rows=rows)

    def get_or_create_experiment(self, tenant_id: str) -> str:
        with self._session() as session:
            existing = measurement.get_active_experiment(session, tenant_id=tenant_id)
            if existing is not None:
                return str(existing.id)
            created = measurement.create_experiment(
                session, tenant_id=tenant_id, name="default", control_pct=20, naive_pct=20
            )
            return str(created.id)

    def save_arm_assignments(self, tenant_id: str, experiment_id: str, arms: dict[str, Arm]) -> None:
        if not arms:
            return
        exp_uuid = uuid.UUID(experiment_id)
        with self._session() as session:
            for unit, arm in arms.items():
                measurement.record_assignment(
                    session, tenant_id=tenant_id, experiment_id=exp_uuid, user_pseudonym=unit, arm=arm.value
                )

    def save_allocation(
        self, tenant_id: str, run_id: str, result: AllocationResult,
        extra_decisions: list[AllocationDecision], candidates: list[Candidate],
    ) -> None:
        candidates_by_id = {c.candidate_id: c for c in candidates}
        decisions_all = list(result.decisions) + list(extra_decisions)

        with self._session() as session:
            run_row = allocations.create_run(
                session, tenant_id=tenant_id, budget_idr=result.budget_idr, strategy=result.strategy,
                ranking_strategy=self._rank_strategy_db, context_row_count=self._rank_context_rows,
                objective_value_idr=round(result.objective_value_idr),
                candidate_count=len(candidates), selected_count=len(result.selected),
                pipeline_run_id=uuid.UUID(run_id),
            )
            self._allocation_run_id = run_row.id

            candidate_dicts = []
            for d in decisions_all:
                c = candidates_by_id.get(d.candidate_id)
                group_id = c.group_id if c else (
                    d.choice_key.removeprefix("group:") if d.choice_key.startswith("group:") else None
                )
                candidate_dicts.append({
                    "subject_type": "GROUP" if group_id else "USER",
                    "user_pseudonym": c.user_pseudonym if c else (None if group_id else d.choice_key),
                    "circle_id": self._circle_id_by_str.get(group_id) if group_id else None,
                    "incentive_code": c.incentive_code if c else "UNKNOWN",
                    "churn_risk": c.churn_risk if c else None,
                    "impact_score": c.impact_score if c else None,
                    "segment": c.segment.value if c else None,
                    "pattern_type": c.pattern_type.value if c else None,
                    "priority_idr": round(d.priority),
                    "cost_idr": d.cost_idr,
                    "user_rank": d.rank,
                    "selected": d.selected,
                    "exclusion_reason": d.exclusion_reason.value if d.exclusion_reason else None,
                })
            written = allocations.add_candidates(
                session, tenant_id=tenant_id, allocation_run_id=run_row.id, candidates=candidate_dicts
            )
            for d, row in zip(decisions_all, written):
                self._alloc_candidate_row_id_by_candidate_id[d.candidate_id] = row.id

    def save_narration(self, tenant_id: str, run_id: str, fact_sheet_hash: str, text: str, source: str) -> None:
        with self._session() as session:
            narrations_repo.save(session, tenant_id=tenant_id, fact_sheet_hash=fact_sheet_hash, text=text, source=source)

    def save_feature_snapshots(self, snapshots: list[FeatureSnapshot]) -> None:
        if not snapshots:
            return
        rows = [
            {
                "run_id": uuid.UUID(s.run_id),
                "user_pseudonym": s.user_pseudonym,
                "features": s.features,
                "churn_risk": s.churn_risk,
                "impact_score": s.impact_score,
                "pattern_type": s.pattern_type,
                "incentive_code": s.incentive_code,
                "cost_idr": s.cost_idr,
                "business_value_idr": s.business_value_idr,
            }
            for s in snapshots
        ]
        with self._session() as session:
            feature_snapshots_repo.save_many(session, tenant_id=self._tenant_id, rows=rows)

    def create_recommendations(self, recommendations: list[Recommendation]) -> None:
        if not recommendations:
            return
        if self._allocation_run_id is None:
            raise RuntimeError("create_recommendations called before save_allocation in this run")
        with self._session() as session:
            for rec in recommendations:
                circle_id = None
                if rec.group_id:
                    circle_id = self._circle_id_by_str.get(rec.group_id)
                    if circle_id is None:
                        raise LookupError(f"no persisted circle for group_id {rec.group_id!r}")
                recommendations_repo.create_pending(
                    session,
                    tenant_id=rec.tenant_id,
                    allocation_run_id=self._allocation_run_id,
                    allocation_candidate_id=self._alloc_candidate_row_id_by_candidate_id.get(rec.candidate_id),
                    subject_type="GROUP" if rec.group_id else "USER",
                    user_pseudonym=None if rec.group_id else rec.user_pseudonym,
                    circle_id=circle_id,
                    incentive_code=rec.incentive_code,
                    cost_idr=rec.cost_idr,
                    priority_idr=round(rec.priority),
                    user_rank=1,
                    is_runner_up=False,
                    reason_text=rec.reason_text,
                    reason_factors=[],
                    reason_source=rec.reason_source,
                    fact_sheet_hash=rec.fact_sheet_hash,
                )

    def append_audit(
        self, tenant_id: str, actor: str, action: str, entity_type: str, entity_id: str, detail: dict[str, Any]
    ) -> None:
        with self._session() as session:
            audit_repo.append(
                session, tenant_id=tenant_id, actor=actor, action=action,
                entity_type=entity_type, entity_id=entity_id, detail=detail,
            )

    # ---------------------------------------------------------- feedback loop

    def load_outcomes(self, tenant_id: str) -> list[OutcomeEvent]:
        with self._session() as session:
            stmt = (
                select(OutcomeEventRow, ExperimentAssignment.arm)
                .join(
                    ExperimentAssignment,
                    (ExperimentAssignment.tenant_id == OutcomeEventRow.tenant_id)
                    & (ExperimentAssignment.experiment_id == OutcomeEventRow.experiment_id)
                    & (ExperimentAssignment.user_pseudonym == OutcomeEventRow.user_pseudonym),
                )
                .where(OutcomeEventRow.tenant_id == tenant_id)
            )
            rows = session.execute(stmt).all()

            latest_run_stmt = (
                select(FeatureSnapshotRow.user_pseudonym, FeatureSnapshotRow.run_id, FeatureSnapshotRow.created_at)
                .where(FeatureSnapshotRow.tenant_id == tenant_id)
                .order_by(FeatureSnapshotRow.user_pseudonym, FeatureSnapshotRow.created_at.desc())
            )
            latest_run_by_user: dict[str, uuid.UUID] = {}
            for user, run_id, _created_at in session.execute(latest_run_stmt).all():
                latest_run_by_user.setdefault(user, run_id)

            outcomes = []
            for row, arm_value in rows:
                run_id = latest_run_by_user.get(row.user_pseudonym)
                arm = Arm(arm_value)
                outcomes.append(OutcomeEvent(
                    outcome_event_id=str(row.id),
                    tenant_id=tenant_id,
                    run_id=str(run_id) if run_id else "",
                    user_pseudonym=row.user_pseudonym,
                    arm=arm,
                    treated=arm != Arm.CONTROL,
                    retained=row.outcome_type in ("RETAINED", "RESPONDED"),
                    spend_idr=row.value_idr or 0,
                    observed_at=row.observed_at,
                ))
            return outcomes

    def load_feature_snapshots(self, tenant_id: str) -> dict[tuple[str, str], FeatureSnapshot]:
        with self._session() as session:
            rows = feature_snapshots_repo.load_all(session, tenant_id=tenant_id)
            return {
                (str(row.run_id), row.user_pseudonym): FeatureSnapshot(
                    tenant_id=tenant_id, run_id=str(row.run_id), user_pseudonym=row.user_pseudonym,
                    features=row.features, churn_risk=row.churn_risk, impact_score=row.impact_score,
                    pattern_type=row.pattern_type, incentive_code=row.incentive_code,
                    cost_idr=row.cost_idr, business_value_idr=row.business_value_idr,
                )
                for row in rows
            }

    def save_labeled_examples(self, examples: list[LabeledExample]) -> None:
        if not examples:
            return
        by_tenant: dict[str, list[dict]] = {}
        for e in examples:
            by_tenant.setdefault(e.tenant_id, []).append({
                "source_experiment_id": None,
                "source_outcome_id": _maybe_uuid(e.source_outcome_id),
                "user_pseudonym": e.user_pseudonym,
                "arm": e.arm.value,
                "treated": e.treated,
                "retained": e.retained,
                "realized_value_idr": round(e.realized_value_idr),
                "feature_snapshot": {
                    "features": e.features,
                    "churn_risk": e.churn_risk,
                    "impact_score": e.impact_score,
                    "pattern_type": e.pattern_type,
                    "incentive_code": e.incentive_code,
                    "cost_idr": e.cost_idr,
                    "business_value_idr": e.business_value_idr,
                },
            })
        with self._session() as session:
            for tenant_id, rows in by_tenant.items():
                feedback_repo.insert_labeled_examples(session, tenant_id=tenant_id, rows=rows)


def _maybe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
