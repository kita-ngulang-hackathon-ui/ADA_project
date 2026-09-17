"""Pipeline orchestration (see services/worker/README.md for the 10 stages).

INGEST -> EXTERNAL -> GRAPH -> RISK -> IMPACT -> POLICY -> RANK -> ALLOCATE -> EXPLAIN -> PERSIST

- Every stage records PENDING/RUNNING/DONE/FAILED/SKIPPED with a detail dict.
- Config values are passed explicitly into L1 functions; L1 never reads env.
- GRAPH is skipped for tenant profile types outside PIPELINE_GRAPH_PROFILES (open decision §6).
- PERSIST writes PENDING_APPROVAL recommendations only. Nothing here can approve or deliver.
"""
import hashlib
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import fmean
from typing import Any

import allocator
import churn_risk
import external_signals
import graph_signal
import impact
import pandas as pd
import ranker
from core_contracts import (
    AllocationDecision,
    Arm,
    Candidate,
    CanonicalEventType,
    ContextTooSmall,
    ExclusionReason,
    FeatureSnapshot,
    ImpactScore,
    MappingError,
    PolicyDecision,
    RankedCandidate,
    RankingStrategy,
    ReasonFactor,
    Recommendation,
    RecommendationStatus,
    RiskScore,
    RuleCode,
    UserFacts,
    assert_transition,
)
from explain import build_fact_sheet, fact_sheet_hash
from ingest_mapping import TenantMappingConfig, normalize
from measurement import assign_arm
from policy_guard import PolicyConfig, evaluate
from pydantic import ValidationError

from worker import feed_adapter
from worker.churn_scorer import ChurnScorerUnavailable, load_mapping
from worker.llm_narrator import narrate_or_fallback
from worker.store import PipelineStore, StageRecord

log = logging.getLogger(__name__)

STAGES = ["INGEST", "EXTERNAL", "GRAPH", "RISK", "IMPACT", "POLICY", "RANK", "ALLOCATE", "EXPLAIN", "PERSIST"]

ACTOR = "app_worker"
MODEL_HEURISTIC = "HEURISTIC_NO_CONTEXT"


@dataclass
class StageOutcome:
    stage: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRunResult:
    run_id: str
    tenant_id: str
    status: str  # DONE | FAILED
    stages: list[StageOutcome]
    recommendation_ids: list[str]


@dataclass
class Pick:
    """One recommendation to explain and persist: a user pick or a group bundle pick."""

    arm: Arm
    top: RankedCandidate
    runner_up: RankedCandidate | None
    candidate_ids: tuple[str, ...]
    rank: int | None
    group_id: str | None = None
    members: tuple[str, ...] = ()


@dataclass
class _Run:
    tenant_id: str
    run_id: str
    now: datetime
    tenant: Any = None
    events: list = field(default_factory=list)
    events_by_user: dict = field(default_factory=dict)
    users: list[str] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    signal_of: dict = field(default_factory=dict)
    snapshots: dict = field(default_factory=dict)
    circles: list = field(default_factory=list)
    features: dict = field(default_factory=dict)
    risk: dict[str, RiskScore] = field(default_factory=dict)
    scorer_features: dict[str, dict] = field(default_factory=dict)
    impact: dict[str, ImpactScore] = field(default_factory=dict)
    segments: dict = field(default_factory=dict)
    business_value: dict[str, int] = field(default_factory=dict)
    labeled: list = field(default_factory=list)
    incentives: dict = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)
    decisions: dict[str, PolicyDecision] = field(default_factory=dict)
    user_facts: dict[str, UserFacts] = field(default_factory=dict)
    exclusions: dict[str, ExclusionReason] = field(default_factory=dict)
    ranked: list[RankedCandidate] = field(default_factory=list)
    allocation: Any = None
    arms: dict[str, Arm] = field(default_factory=dict)
    picks: list[Pick] = field(default_factory=list)
    narrations: dict[int, tuple[str, str, str]] = field(default_factory=dict)
    recommendation_ids: list[str] = field(default_factory=list)


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- stages

def _ingest(run: _Run, store: PipelineStore, settings, **_) -> dict:
    config = TenantMappingConfig.from_dict(run.tenant.mapping)
    secret = settings.pseudonym_hmac_secret.encode()
    processed = unmapped = 0
    while True:
        claimed = store.claim_raw_events(run.tenant_id, settings.worker_batch_size)
        if not claimed:
            break
        canonical = []
        for raw in claimed:
            try:
                event = normalize(run.tenant_id, raw.body, config, secret)
            except MappingError as exc:
                store.mark_raw_event(run.tenant_id, raw.raw_event_id, "UNMAPPED", str(exc))
                unmapped += 1
                continue
            canonical.append(event)
            if event.attributes:
                store.upsert_user_attributes(run.tenant_id, event.user_pseudonym, event.attributes)
            store.mark_raw_event(run.tenant_id, raw.raw_event_id, "PROCESSED")
            processed += 1
        store.save_canonical_events(run.tenant_id, canonical)

    # The 30-days-ago graph needs a full lookback window of its own.
    since = run.now - timedelta(days=settings.pipeline_graph_lookback_days
                                + settings.pipeline_activity_window_days)
    run.events = [e for e in store.load_canonical_events(run.tenant_id, since) if e.occurred_at <= run.now]
    by_user = defaultdict(list)
    for e in run.events:
        by_user[e.user_pseudonym].append(e)
    run.events_by_user = dict(by_user)
    run.users = sorted(by_user)
    run.attributes = store.load_user_attributes(run.tenant_id)
    return {"processed": processed, "unmapped": unmapped, "users_in_window": len(run.users)}


def _external(run: _Run, store: PipelineStore, settings, feed_loader, **_) -> dict:
    items, source = feed_loader(settings)
    signals, rejected = [], 0
    for item in items:
        try:
            signals.append(external_signals.to_signal(item))
        except (ValueError, ValidationError):
            rejected += 1
    store.save_external_signals(signals)
    for user in run.users:
        attrs = run.attributes.get(user, {})
        run.signal_of[user] = external_signals.resolve_for_user(
            signals, tenant_slug=run.tenant.slug, region_code=attrs.get("region_code"),
            cohort_key=attrs.get("cohort_key"), now=run.now,
            max_age_days=settings.external_signal_max_age_days,
        )
    attached = sum(1 for s in run.signal_of.values() if s is not None)
    return {"source": source, "signals": len(signals), "rejected": rejected,
            "users_with_signal": attached}


def _graph(run: _Run, store: PipelineStore, settings, **_) -> dict:
    if run.tenant.profile_type.upper() not in settings.graph_profiles:
        run.snapshots = {u: graph_signal.empty_snapshot(u) for u in run.users}
        return {"skipped": True, "reason": f"profile {run.tenant.profile_type} not in graph profiles"}
    edges, run.snapshots = graph_signal.snapshot_users(
        run.events, run.users, now=run.now,
        lookback_days=settings.pipeline_graph_lookback_days,
        activity_window_days=settings.pipeline_activity_window_days,
        half_life_days=settings.pipeline_edge_decay_halflife_days,
        min_interactions=settings.pipeline_min_edge_interactions,
        cohort_of={u: run.attributes.get(u, {}).get("cohort_key") for u in run.users},
        external_value_of={u: (s.value if s else None) for u, s in run.signal_of.items()},
        dip_threshold=settings.pattern_dip_threshold,
        cohort_dip_threshold=settings.pattern_cohort_dip_threshold,
    )
    run.circles = graph_signal.find_circles(edges, min_size=settings.pipeline_circle_min_size)
    store.save_circles(run.tenant_id, run.run_id, list(run.snapshots.values()), run.circles)
    patterns = defaultdict(int)
    for s in run.snapshots.values():
        patterns[s.pattern_type.value] += 1
    return {"edges": len(edges), "circles": len(run.circles), "patterns": dict(patterns)}


def _heuristic_risk(f: dict) -> float:
    """Used only when there are too few labeled rows for in-context scoring; labeled in the model name."""
    recency = min(f["recency_days"] / 30.0, 1.0)
    dip = min(max(-f["delta_stability"], 0.0), 1.0)
    quiet = 1.0 - min(f["frequency_30d"] / 10.0, 1.0)
    return round(0.5 * recency + 0.3 * dip + 0.2 * quiet, 4)


def _risk_trained(run: _Run, store: PipelineStore, settings, scorer) -> dict:
    """Score with the resident trained TabPFN scorer loaded from the artifact bundle."""
    if scorer is None:
        raise ChurnScorerUnavailable("CHURN_SCORER_ENABLED=true but no trained scorer was loaded")
    mapping = load_mapping(settings.churn_scorer_mapping_path)
    for user in run.users:
        run.scorer_features[user] = churn_risk.build_snapshot_features(
            run.events_by_user[user], now=run.now, attributes=run.attributes.get(user),
            external_signal=run.signal_of.get(user), profile_type=run.tenant.profile_type,
            business_value_idr=run.business_value[user], mapping=mapping,
        )
    if not run.users:
        return {"model": scorer.model_name, "device": scorer.device, "scored": 0}

    as_of = run.now.date().isoformat()
    candidates = pd.DataFrame(
        [{"user_id": u, "snapshot_date": as_of, **run.scorer_features[u]} for u in run.users]
    )
    risk, neutral = scorer.predict_with_neutral(candidates, churn_risk.NEUTRAL_SIGNAL)
    attributed = 0
    for i, user in enumerate(run.users):
        signal = run.signal_of.get(user)
        contribution = float(risk[i] - neutral[i]) if signal is not None else 0.0
        attributed += signal is not None
        run.risk[user] = RiskScore(
            user_pseudonym=user, churn_risk=float(risk[i]), model=scorer.model_name,
            context_row_count=scorer.context_row_count,
            external_signal_id=signal.signal_id if signal else None,
            external_signal_contribution=contribution,
        )
    store.save_risk_scores(run.tenant_id, run.run_id, list(run.risk.values()))
    return {"model": scorer.model_name, "device": scorer.device,
            "context_rows": scorer.context_row_count, "scored": len(run.risk),
            "users_with_signal_attribution": attributed}


def _risk(run: _Run, store: PipelineStore, settings, churn_scorer=None, **_) -> dict:
    run.labeled = store.load_labeled_examples(run.tenant_id)
    for user in run.users:
        f = churn_risk.build_features(run.events_by_user[user], run.snapshots.get(user),
                                      run.signal_of.get(user), now=run.now)
        run.features[user] = f
        # monetary_30d_idr is a 30-day window, so it stands in for one month of volume.
        run.business_value[user] = int(f["monetary_30d_idr"] * settings.pipeline_business_value_months)

    if settings.churn_scorer_enabled:
        return _risk_trained(run, store, settings, churn_scorer)

    try:
        context_X, context_y = churn_risk.select_context(
            run.labeled, max_rows=settings.tabpfn_max_context_rows,
            min_rows=settings.risk_min_context_rows, seed=settings.tabpfn_seed,
        )
    except ContextTooSmall as exc:
        for user in run.users:
            run.risk[user] = RiskScore(user_pseudonym=user, churn_risk=_heuristic_risk(run.features[user]),
                                       model=MODEL_HEURISTIC, context_row_count=len(run.labeled))
        store.save_risk_scores(run.tenant_id, run.run_id, list(run.risk.values()))
        return {"model": MODEL_HEURISTIC, "reason": str(exc), "scored": len(run.risk)}

    rows = [churn_risk.to_row(run.features[u]) for u in run.users]
    scores = churn_risk.score(context_X, context_y, rows, seed=settings.tabpfn_seed,
                              model_cache_dir=settings.tabpfn_model_cache_dir,
                              query_ids=run.users, use_tabpfn=settings.tabpfn_enabled)
    run.risk = {s.user_pseudonym: s for s in scores}

    with_signal = [u for u in run.users if run.signal_of.get(u) is not None]
    if with_signal:
        def score_fn(cX, cy, q):
            return churn_risk.predict_positive(cX, cy, q, seed=settings.tabpfn_seed,
                                               model_cache_dir=settings.tabpfn_model_cache_dir,
                                               use_tabpfn=settings.tabpfn_enabled)[0]

        contribs = churn_risk.contributions(score_fn, context_X, context_y,
                                            [churn_risk.to_row(run.features[u]) for u in with_signal],
                                            "external_signal_value")
        for user, contribution in zip(with_signal, contribs):
            run.risk[user] = run.risk[user].model_copy(update={
                "external_signal_id": run.signal_of[user].signal_id,
                "external_signal_contribution": contribution,
            })
    store.save_risk_scores(run.tenant_id, run.run_id, list(run.risk.values()))
    model = scores[0].model if scores else None
    return {"model": model, "context_rows": len(context_X), "scored": len(run.risk)}


def _impact(run: _Run, store: PipelineStore, settings, **_) -> dict:
    treated = [e for e in run.labeled if e.treated]
    control = [e for e in run.labeled if not e.treated]
    try:
        scores = impact.estimate_batch(treated, control, [run.features[u] for u in run.users],
                                       seed=settings.impact_seed,
                                       min_rows=settings.impact_min_train_rows,
                                       use_tabpfn=settings.tabpfn_enabled)
    except ContextTooSmall as exc:
        return {"available": False, "reason": str(exc)}
    run.impact = dict(zip(run.users, scores))
    counts = defaultdict(int)
    for user, s in run.impact.items():
        seg = impact.segment(s, impact_threshold=settings.impact_threshold,
                             sure_thing_p=settings.impact_sure_thing_p_not_incentivized)
        run.segments[user] = seg
        counts[seg.value] += 1
    store.save_impact_scores(run.tenant_id, run.run_id, run.impact, run.segments)
    return {"available": True, "model": scores[0].model if scores else None,
            "treated_rows": len(treated), "control_rows": len(control), "segments": dict(counts)}


def _policy_config(settings, *, apply_segment_rule: bool = True) -> PolicyConfig:
    return PolicyConfig(
        responsible_lending_lookback_days=settings.responsible_lending_lookback_days,
        responsible_lending_min_late_events=settings.responsible_lending_min_late_events,
        frequency_cap_max_contacts=settings.frequency_cap_max_contacts,
        frequency_cap_window_days=settings.frequency_cap_window_days,
        apply_segment_rule=apply_segment_rule,
    )


def _exclusion_for(decision: PolicyDecision, segment) -> ExclusionReason:
    hard = [d for d in decision.denials if d.rule_code != RuleCode.SEGMENT_EXCLUDED]
    if hard:
        return ExclusionReason(f"POLICY_{hard[0].rule_code.value}")
    return ExclusionReason(f"SEGMENT_{segment.value}")


def _candidate(run: _Run, user: str, incentive, group_id: str | None = None) -> Candidate:
    return Candidate(
        candidate_id=_id("cand", run.run_id, user, incentive.code, group_id or ""),
        tenant_id=run.tenant_id,
        user_pseudonym=user,
        incentive_code=incentive.code,
        cost_idr=incentive.cost_idr,
        business_value_idr=run.business_value[user],
        encourages_borrowing=incentive.encourages_borrowing,
        changes_credit_terms=incentive.changes_credit_terms,
        group_id=group_id,
        churn_risk=run.risk[user].churn_risk,
        impact_score=run.impact[user].impact_score,
        segment=run.segments[user],
        pattern_type=run.snapshots[user].pattern_type,
    )


def _policy(run: _Run, store: PipelineStore, settings, **_) -> dict:
    profile = run.tenant.profile_type.upper()
    incentives = [
        i for i in store.load_incentives(run.tenant_id)
        if not i.applicable_profile_types or profile in {p.upper() for p in i.applicable_profile_types}
    ]
    run.incentives = {i.code: i for i in incentives}
    scored_users = [u for u in run.users if u in run.impact]
    for user in scored_users:
        for inc in incentives:
            if not inc.is_group:
                run.candidates.append(_candidate(run, user, inc))
    for circle in run.circles:
        members = [m for m in circle.members if m in run.impact]
        if len(members) < settings.pipeline_circle_min_size:
            continue
        for inc in incentives:
            if inc.is_group:
                run.candidates.extend(_candidate(run, m, inc, circle.circle_id) for m in members)

    contacts = store.load_contact_times(run.tenant_id)
    late = defaultdict(list)
    for e in run.events:
        if e.event_type == CanonicalEventType.LOAN_REPAYMENT_LATE:
            late[e.user_pseudonym].append(e.occurred_at)
    for user in scored_users:
        run.user_facts[user] = UserFacts(user_pseudonym=user, now=run.now,
                                         late_repayment_at=tuple(late[user]),
                                         contacted_at=tuple(contacts.get(user, ())))

    config = _policy_config(settings)
    for c in run.candidates:
        decision = evaluate(c, run.user_facts[c.user_pseudonym], config)
        run.decisions[c.candidate_id] = decision
        if not decision.allowed:
            run.exclusions[c.candidate_id] = _exclusion_for(decision, c.segment)

    bundles = defaultdict(list)
    for c in run.candidates:
        if c.group_id:
            bundles[(c.group_id, c.incentive_code)].append(c)
    for members in bundles.values():
        if any(m.candidate_id in run.exclusions for m in members):
            for m in members:
                run.exclusions.setdefault(m.candidate_id, ExclusionReason.GROUP_MEMBER_DENIED)

    store.save_policy_decisions(run.tenant_id, run.run_id, list(run.decisions.values()))
    denied = defaultdict(int)
    for d in run.decisions.values():
        for r in d.denials:
            denied[r.rule_code.value] += 1
    return {
        "candidates": len(run.candidates),
        "allowed": len(run.candidates) - len(run.exclusions),
        "denials_by_rule": dict(denied),
        "users_without_impact": len(run.users) - len(scored_users),
        "frequency_cap_configured": settings.frequency_cap_max_contacts is not None
        and settings.frequency_cap_window_days is not None,
    }


def _rank(run: _Run, store: PipelineStore, settings, **_) -> dict:
    allowed = [c for c in run.candidates if c.candidate_id not in run.exclusions]
    context = ranker.build_context(run.labeled)
    run.ranked = ranker.rank(context, allowed, min_context_rows=settings.ranker_min_context_rows,
                             seed=settings.tabpfn_seed, use_tabpfn=settings.tabpfn_enabled)
    strategy = run.ranked[0].ranking_strategy.value if run.ranked else None
    return {"ranked": len(run.ranked), "ranking_strategy": strategy, "context_rows": len(context)}


def _unit(c: Candidate) -> str:
    return f"group:{c.group_id}" if c.group_id else c.user_pseudonym


def _bundle_rep(members: list[RankedCandidate], priority: float) -> RankedCandidate:
    """A single representative for a group bundle: summed cost/value, mean scores."""
    first = members[0].candidate
    rep = first.model_copy(update={
        "candidate_id": _id("bundle", *sorted(m.candidate.candidate_id for m in members)),
        "cost_idr": sum(m.candidate.cost_idr for m in members),
        "business_value_idr": sum(m.candidate.business_value_idr for m in members),
        "churn_risk": fmean(m.candidate.churn_risk for m in members),
        "impact_score": fmean(m.candidate.impact_score for m in members),
    })
    return RankedCandidate(candidate=rep, priority=priority, ranking_strategy=members[0].ranking_strategy)


def _allocate(run: _Run, store: PipelineStore, settings, **_) -> dict:
    experiment_id = store.get_or_create_experiment(run.tenant_id)
    secret = settings.measurement_hmac_secret.encode()
    units = set(run.users) | {_unit(c) for c in run.candidates}
    run.arms = {
        u: assign_arm(run.tenant_id, experiment_id, u, secret=secret,
                      control_pct=settings.measurement_control_pct,
                      naive_pct=settings.measurement_naive_pct)
        for u in sorted(units)
    }
    store.save_arm_assignments(run.tenant_id, experiment_id, run.arms)

    extra: list[AllocationDecision] = []

    def exclude(c: Candidate, reason: ExclusionReason, priority: float = 0.0) -> None:
        extra.append(AllocationDecision(candidate_id=c.candidate_id, choice_key=_unit(c),
                                        selected=False, priority=priority, cost_idr=c.cost_idr,
                                        exclusion_reason=reason))

    for c in run.candidates:
        if c.candidate_id in run.exclusions and run.arms[_unit(c)] != Arm.NAIVE:
            exclude(c, run.exclusions[c.candidate_id])

    engine = [r for r in run.ranked if run.arms[_unit(r.candidate)] == Arm.ENGINE]
    for r in run.ranked:
        if run.arms[_unit(r.candidate)] == Arm.CONTROL:
            exclude(r.candidate, ExclusionReason.CONTROL_HOLDOUT, r.priority)

    config = allocator.AllocatorConfig(strategy=settings.allocator_strategy,
                                       cost_scale_idr=settings.allocator_cost_scale_idr,
                                       max_dp_cells=settings.allocator_max_dp_cells)
    run.allocation = allocator.allocate(engine, budget_idr=settings.default_budget_idr, config=config)

    ranked_by_id = {r.candidate.candidate_id: r for r in engine}
    by_key = defaultdict(list)
    for d in run.allocation.decisions:
        by_key[d.choice_key].append(d)
    for key, decisions in sorted(by_key.items()):
        chosen = [d for d in decisions if d.selected]
        if not chosen:
            continue
        runner = [d for d in decisions if d.is_runner_up]
        top_members = [ranked_by_id[d.candidate_id] for d in chosen]
        runner_members = [ranked_by_id[d.candidate_id] for d in runner]
        if key.startswith("group:"):
            top = _bundle_rep(top_members, chosen[0].priority)
            runner_rep = _bundle_rep(runner_members, runner[0].priority) if runner else None
            run.picks.append(Pick(arm=Arm.ENGINE, top=top, runner_up=runner_rep,
                                  candidate_ids=tuple(d.candidate_id for d in chosen),
                                  rank=chosen[0].rank, group_id=key.removeprefix("group:"),
                                  members=tuple(m.candidate.user_pseudonym for m in top_members)))
        else:
            run.picks.append(Pick(arm=Arm.ENGINE, top=top_members[0],
                                  runner_up=runner_members[0] if runner else None,
                                  candidate_ids=(chosen[0].candidate_id,), rank=chosen[0].rank))

    naive_picks = _naive_arm(run, settings, exclude)
    store.save_allocation(run.tenant_id, run.run_id, run.allocation, extra, run.candidates)
    return {
        "experiment_id": experiment_id,
        "strategy": run.allocation.strategy,
        "budget_idr": run.allocation.budget_idr,
        "spent_idr": run.allocation.spent_idr,
        "engine_picks": len(run.picks) - naive_picks,
        "naive_picks": naive_picks,
        "arms": {a.value: sum(1 for u in run.users if run.arms[u] == a) for a in Arm},
    }


def _naive_arm(run: _Run, settings, exclude: Callable) -> int:
    """Baseline: every at-risk NAIVE user gets the cheapest individual incentive the hard rules allow.

    No impact model, no ranking, no budget optimization. Hard guarantees still apply.
    """
    config = _policy_config(settings, apply_segment_rule=False)
    by_user = defaultdict(list)
    for c in run.candidates:
        if run.arms[_unit(c)] == Arm.NAIVE:
            if c.group_id:
                exclude(c, ExclusionReason.NAIVE_NOT_CHOSEN)
            else:
                by_user[c.user_pseudonym].append(c)
    picks = 0
    for user, candidates in sorted(by_user.items()):
        if run.risk[user].churn_risk < settings.measurement_naive_risk_threshold:
            for c in candidates:
                exclude(c, ExclusionReason.NAIVE_BELOW_THRESHOLD)
            continue
        allowed = []
        for c in sorted(candidates, key=lambda c: (c.cost_idr, c.incentive_code)):
            decision = evaluate(c, run.user_facts[user], config)
            if decision.allowed:
                allowed.append(c)
            else:
                exclude(c, _exclusion_for(decision, c.segment))
        if not allowed:
            continue
        ranked = [RankedCandidate(candidate=c, priority=c.churn_risk,
                                  ranking_strategy=RankingStrategy.NAIVE_RISK_ONLY) for c in allowed]
        for r in ranked[1:]:
            exclude(r.candidate, ExclusionReason.NAIVE_NOT_CHOSEN, r.priority)
        run.picks.append(Pick(arm=Arm.NAIVE, top=ranked[0],
                              runner_up=ranked[1] if len(ranked) > 1 else None,
                              candidate_ids=(ranked[0].candidate.candidate_id,), rank=None))
        picks += 1
    return picks


def _reason_factors(run: _Run, user: str) -> list[ReasonFactor]:
    risk = run.risk[user]
    factors = [ReasonFactor(code="CHURN_RISK", direction="INCREASES_RISK", weight=round(risk.churn_risk, 4))]
    snap = run.snapshots.get(user)
    if snap and snap.circle_size and snap.delta_stability < 0:
        factors.append(ReasonFactor(code="CIRCLE_DESTABILIZING", direction="INCREASES_RISK",
                                    weight=round(-snap.delta_stability, 4),
                                    evidence={"pattern_type": snap.pattern_type.value}))
    if risk.external_signal_contribution:
        direction = "INCREASES_RISK" if risk.external_signal_contribution > 0 else "DECREASES_RISK"
        factors.append(ReasonFactor(code="EXTERNAL_SIGNAL", direction=direction,
                                    weight=round(abs(risk.external_signal_contribution), 4)))
    if user in run.impact:
        factors.append(ReasonFactor(code="IMPACT_SCORE", direction="SUPPORTS_PICK",
                                    weight=round(run.impact[user].impact_score, 4)))
    return factors


def _explain(run: _Run, store: PipelineStore, settings, narrator, **_) -> dict:
    cache: dict = {}
    sources = defaultdict(int)
    display = {code: i.display_name for code, i in run.incentives.items()}
    for n, pick in enumerate(run.picks):
        c = pick.top.candidate
        user = c.user_pseudonym
        if pick.group_id:
            member_risk = [run.risk[m] for m in pick.members]
            risk = member_risk[0].model_copy(update={
                "user_pseudonym": pick.group_id,
                "churn_risk": fmean(r.churn_risk for r in member_risk),
                "external_signal_contribution": fmean(r.external_signal_contribution for r in member_risk),
            })
            member_impact = [run.impact[m] for m in pick.members]
            impact_score = ImpactScore(
                p_incentivized=fmean(i.p_incentivized for i in member_impact),
                p_not_incentivized=fmean(i.p_not_incentivized for i in member_impact),
                model=member_impact[0].model,
            )
            circle, signal = None, None
        else:
            risk, impact_score = run.risk[user], run.impact.get(user)
            circle, signal = run.snapshots.get(user), run.signal_of.get(user)
        if pick.arm == Arm.ENGINE:
            allocation = {"strategy": run.allocation.strategy, "budget_idr": run.allocation.budget_idr,
                          "spent_idr": run.allocation.spent_idr,
                          "selected_count": len({d.choice_key for d in run.allocation.selected}),
                          "rank": pick.rank}
            policy = run.decisions[pick.candidate_ids[0]]
        else:
            allocation = {"strategy": RankingStrategy.NAIVE_RISK_ONLY.value,
                          "risk_threshold": settings.measurement_naive_risk_threshold}
            policy = evaluate(c, run.user_facts[user], _policy_config(settings, apply_segment_rule=False))
        sheet = build_fact_sheet(
            pick.top, risk, impact_score, circle, policy, allocation,
            runner_up=pick.runner_up, display_names=display, external_signal=signal, arm=pick.arm,
            subject_type="GROUP" if pick.group_id else "USER",
            subject_ref=pick.group_id or user, member_count=len(pick.members) or 1,
            activity_window_days=settings.pipeline_activity_window_days,
            reason_factors=_reason_factors(run, user),
        )
        text, source = narrate_or_fallback(sheet, narrator, cache)
        digest = fact_sheet_hash(sheet)
        run.narrations[n] = (text, source, digest)
        store.save_narration(run.tenant_id, run.run_id, digest, text, source)
        sources[source] += 1
    return {"narrated": len(run.picks), "reason_sources": dict(sources),
            "llm_enabled": narrator is not None}


def _persist(run: _Run, store: PipelineStore, settings, **_) -> dict:
    recommendations = []
    for n, pick in enumerate(run.picks):
        assert_transition(RecommendationStatus.DRAFT, RecommendationStatus.PENDING_APPROVAL, None)
        text, source, digest = run.narrations[n]
        c = pick.top.candidate
        recommendations.append(Recommendation(
            recommendation_id=_id("rec", run.run_id, *pick.candidate_ids),
            tenant_id=run.tenant_id,
            run_id=run.run_id,
            candidate_id=c.candidate_id,
            arm=pick.arm,
            status=RecommendationStatus.PENDING_APPROVAL,
            incentive_code=c.incentive_code,
            cost_idr=c.cost_idr,
            priority=pick.top.priority,
            user_pseudonym=None if pick.group_id else c.user_pseudonym,
            group_id=pick.group_id,
            member_pseudonyms=pick.members,
            runner_up_candidate_id=pick.runner_up.candidate.candidate_id if pick.runner_up else None,
            reason_text=text,
            reason_source=source,
            fact_sheet_hash=digest,
            created_at=run.now,
        ))
    store.create_recommendations(recommendations)
    run.recommendation_ids = [r.recommendation_id for r in recommendations]

    pick_of = {}
    for pick in run.picks:
        for user in pick.members or (pick.top.candidate.user_pseudonym,):
            pick_of[user] = pick
    snapshots = []
    for user in run.users:
        pick = pick_of.get(user)
        snapshots.append(FeatureSnapshot(
            tenant_id=run.tenant_id, run_id=run.run_id, user_pseudonym=user,
            features=run.features[user],
            churn_risk=run.risk[user].churn_risk,
            impact_score=run.impact[user].impact_score if user in run.impact else None,
            pattern_type=run.snapshots[user].pattern_type.value,
            incentive_code=pick.top.candidate.incentive_code if pick else None,
            cost_idr=run.incentives[pick.top.candidate.incentive_code].cost_idr if pick else 0,
            business_value_idr=run.business_value[user],
        ))
    store.save_feature_snapshots(snapshots)
    for r in recommendations:
        store.append_audit(run.tenant_id, ACTOR, "RECOMMENDATION_CREATED", "recommendation",
                           r.recommendation_id, {"status": r.status.value, "arm": r.arm.value})
    return {"recommendations": len(recommendations), "status": RecommendationStatus.PENDING_APPROVAL.value}


_STAGE_FUNCS = {
    "INGEST": _ingest, "EXTERNAL": _external, "GRAPH": _graph, "RISK": _risk, "IMPACT": _impact,
    "POLICY": _policy, "RANK": _rank, "ALLOCATE": _allocate, "EXPLAIN": _explain, "PERSIST": _persist,
}


def run_pipeline(tenant_id: str, run_id: str, *, store: PipelineStore, settings,
                 now: datetime | None = None, narrator=None,
                 feed_loader: Callable = feed_adapter.load_feed,
                 churn_scorer=None) -> PipelineRunResult:
    run = _Run(tenant_id=tenant_id, run_id=run_id, now=now or datetime.now(UTC))
    run.tenant = store.get_tenant(tenant_id)
    outcomes = [StageOutcome(stage=s, status="PENDING") for s in STAGES]
    for outcome in outcomes:
        store.record_stage(StageRecord(run_id, tenant_id, outcome.stage, "PENDING"))

    status = "DONE"
    for outcome in outcomes:
        store.record_stage(StageRecord(run_id, tenant_id, outcome.stage, "RUNNING"))
        try:
            detail = _STAGE_FUNCS[outcome.stage](run, store, settings, narrator=narrator,
                                                 feed_loader=feed_loader, churn_scorer=churn_scorer)
        except Exception as exc:
            log.exception("stage %s failed for run %s", outcome.stage, run_id)
            outcome.status, outcome.detail = "FAILED", {"error": f"{type(exc).__name__}: {exc}"}
            store.record_stage(StageRecord(run_id, tenant_id, outcome.stage, "FAILED", outcome.detail))
            status = "FAILED"
            break
        outcome.status = "SKIPPED" if detail.pop("skipped", False) else "DONE"
        outcome.detail = detail
        store.record_stage(StageRecord(run_id, tenant_id, outcome.stage, outcome.status, detail))

    return PipelineRunResult(run_id=run_id, tenant_id=tenant_id, status=status, stages=outcomes,
                             recommendation_ids=run.recommendation_ids)
