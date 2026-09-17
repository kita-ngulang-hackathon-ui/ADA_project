"""End-to-end pipeline tests on the in-memory store (synthetic data)."""
import inspect
from datetime import UTC, datetime

import pytest
from core_contracts import (
    Arm,
    ExclusionReason,
    Recommendation,
    RecommendationStatus,
    RuleCode,
)
from worker.memory_store import InMemoryStore
from worker.pipeline import STAGES, run_pipeline
from worker.store import PipelineStore
from worker_world import NOW, PAYLATER_ID, WALLET_ID, build_store, make_settings


def _all_decisions(store, tenant_id):
    result, extra = store.allocations[tenant_id][-1]
    return list(result.decisions) + extra


def test_wallet_run_produces_pending_recommendations_only(store, settings) -> None:
    result = run_pipeline(WALLET_ID, "run-1", store=store, settings=settings, now=NOW)

    assert result.status == "DONE", [(s.stage, s.detail) for s in result.stages]
    assert [s.stage for s in result.stages] == STAGES
    assert all(s.status == "DONE" for s in result.stages)

    recs = list(store.recommendations[WALLET_ID].values())
    assert recs, "expected at least one recommendation"
    assert all(r.status == RecommendationStatus.PENDING_APPROVAL for r in recs)
    assert all(r.reviewed_by is None for r in recs)
    assert all(r.reason_source == "TEMPLATE" for r in recs)
    assert all("synthetic" in r.reason_text for r in recs)
    assert {r.arm for r in recs} <= {Arm.ENGINE, Arm.NAIVE}


def test_wallet_run_details(store, settings) -> None:
    result = run_pipeline(WALLET_ID, "run-1", store=store, settings=settings, now=NOW)
    stages = {s.stage: s for s in result.stages}

    assert stages["INGEST"].detail["unmapped"] == 1
    assert stages["EXTERNAL"].detail["source"] == "canned"
    assert stages["GRAPH"].detail["circles"] >= 2
    assert stages["RANK"].detail["ranking_strategy"] == "FALLBACK"

    # w1..w3 went silent, so w0's circle destabilized.
    snaps = {s.user_pseudonym: s for s in store.circle_snapshots[WALLET_ID]}
    assert any(s.delta_stability < -0.5 for s in snaps.values())

    decisions = _all_decisions(store, WALLET_ID)
    reasons = {d.exclusion_reason for d in decisions if not d.selected}
    assert ExclusionReason.CONTROL_HOLDOUT in reasons
    assert any(d.is_runner_up for d in decisions)
    recs = [r for r in store.recommendations[WALLET_ID].values() if r.arm == Arm.ENGINE]
    assert any(r.runner_up_candidate_id for r in recs)

    # Raw user refs and non-whitelisted attributes never reach canonical events.
    for e in store.canonical_events[WALLET_ID].values():
        assert not e.user_pseudonym.startswith("w")
        assert "full_name" not in e.attributes


def test_budget_is_respected(store, settings) -> None:
    run_pipeline(WALLET_ID, "run-1", store=store, settings=settings, now=NOW)
    result, _ = store.allocations[WALLET_ID][-1]
    assert result.spent_idr <= settings.default_budget_idr


def test_paylater_skips_graph_and_denies_borrowing_to_stressed_user(store, settings) -> None:
    result = run_pipeline(PAYLATER_ID, "run-p", store=store, settings=settings, now=NOW)
    stages = {s.stage: s for s in result.stages}
    assert result.status == "DONE"
    assert stages["GRAPH"].status == "SKIPPED"

    lending_denials = [
        d for d in store.policy_decisions[PAYLATER_ID]
        if any(r.rule_code == RuleCode.RESPONSIBLE_LENDING for r in d.denials)
    ]
    assert lending_denials, "repayment-stressed user must be denied the borrowing incentive"
    stressed = {d.user_pseudonym for d in lending_denials}
    assert len(stressed) == 1
    for rec in store.recommendations[PAYLATER_ID].values():
        if rec.user_pseudonym in stressed:
            assert rec.incentive_code != "INSTALLMENT_DISCOUNT_NEXT_PURCHASE"


def test_unset_frequency_cap_fails_closed(store) -> None:
    settings = make_settings(frequency_cap_max_contacts="__TBD__", frequency_cap_window_days="__TBD__")
    assert settings.frequency_cap_max_contacts is None
    result = run_pipeline(WALLET_ID, "run-cap", store=store, settings=settings, now=NOW)

    assert result.status == "DONE"
    assert result.recommendation_ids == []
    assert all(
        any(r.rule_code == RuleCode.FREQUENCY_CAP for r in d.denials)
        for d in store.policy_decisions[WALLET_ID]
    )


def test_frequency_cap_denies_recently_contacted_user(store, settings) -> None:
    run_pipeline(WALLET_ID, "run-a", store=store, settings=settings, now=NOW)
    target = next(iter(store.recommendations[WALLET_ID].values())).user_pseudonym
    store.recommendations.clear()
    store.policy_decisions.clear()
    store.add_contacts(WALLET_ID, target, [NOW, NOW, NOW])
    run_pipeline(WALLET_ID, "run-b", store=store, settings=settings, now=NOW)
    denied = [d for d in store.policy_decisions[WALLET_ID] if d.user_pseudonym == target]
    assert denied and all(
        any(r.rule_code == RuleCode.FREQUENCY_CAP for r in d.denials) for d in denied
    )


def test_run_is_deterministic(settings) -> None:
    first, second = build_store(), build_store()
    run_pipeline(WALLET_ID, "run-1", store=first, settings=settings, now=NOW)
    run_pipeline(WALLET_ID, "run-1", store=second, settings=settings, now=NOW)
    assert first.recommendations[WALLET_ID] == second.recommendations[WALLET_ID]


def test_stage_failure_is_recorded_and_stops_the_run(store, settings) -> None:
    def broken_feed(_settings):
        raise RuntimeError("feed exploded")

    result = run_pipeline(WALLET_ID, "run-x", store=store, settings=settings, now=NOW,
                          feed_loader=broken_feed)
    stages = {s.stage: s.status for s in result.stages}
    assert result.status == "FAILED"
    assert stages["INGEST"] == "DONE" and stages["EXTERNAL"] == "FAILED"
    assert stages["PERSIST"] == "PENDING"
    assert not store.recommendations[WALLET_ID]


def test_store_port_has_no_approval_path() -> None:
    names = {n for n, _ in inspect.getmembers(PipelineStore)}
    for forbidden in ("approve", "reject", "deliver", "update_status", "set_status"):
        assert not any(forbidden in n for n in names)


def test_memory_store_refuses_non_pending_rows() -> None:
    store = InMemoryStore()
    rec = Recommendation(
        recommendation_id="r", tenant_id="t", run_id="run", candidate_id="c", arm=Arm.ENGINE,
        status=RecommendationStatus.APPROVED, incentive_code="X", cost_idr=1, priority=1.0,
        reason_text="x", reason_source="TEMPLATE", fact_sheet_hash="h",
        created_at=datetime.now(UTC), reviewed_by="ops_reviewer_1",
        reviewed_at=datetime.now(UTC),
    )
    with pytest.raises(PermissionError):
        store.create_recommendations([rec])
