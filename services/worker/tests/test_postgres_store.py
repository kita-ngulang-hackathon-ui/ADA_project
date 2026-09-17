"""Integration test for PostgresPipelineStore against a real, migrated
Postgres (docker compose up postgres; alembic upgrade head) -- run as the
app_worker role, exercising the Protocol methods in the same order
worker.pipeline.run_pipeline() calls them, including the cross-call caches
(GRAPH -> RISK, ALLOCATE -> PERSIST) that only a real sequential run
exercises.

Skips cleanly (not silently) when Postgres credentials/connectivity are not
available, mirroring tests/invariants/conftest.py's convention.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
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
    ImpactSegment,
    LabeledExample,
    PatternType,
    RankingStrategy,
    Recommendation,
    RecommendationStatus,
    RiskScore,
    RuleCode,
    RuleResult,
    ScopeType,
    SignalType,
)
from core_contracts import (
    PolicyDecision as PolicyDecisionModel,
)
from worker.postgres_store import PostgresPipelineStore
from worker.store import StageRecord

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if _ENV_PATH.is_file():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    values.update(os.environ)
    return values


_ENV = _load_env()


def _env(key: str) -> str | None:
    value = _ENV.get(key)
    return None if not value or value == "__TBD__" else value


def _can_connect(url: str) -> bool:
    try:
        engine = sa.create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:  # noqa: BLE001 -- connection failures vary by driver/OS; any of them means "skip"
        return False


@pytest.fixture(scope="module")
def db_urls() -> dict[str, str]:
    host = _env("POSTGRES_HOST") or "localhost"
    port = _env("POSTGRES_PORT") or "5432"
    db = _env("POSTGRES_DB") or "retention"
    superuser_pw = _env("POSTGRES_PASSWORD")
    worker_pw = _env("APP_WORKER_DB_PASSWORD")
    if not (superuser_pw and worker_pw):
        pytest.skip("Postgres credentials not available -- see tests/invariants/README.md")
    superuser_url = f"postgresql+psycopg://postgres:{superuser_pw}@{host}:{port}/{db}"
    if not _can_connect(superuser_url):
        pytest.skip(f"cannot reach Postgres at {host}:{port}")
    return {
        "superuser": superuser_url,
        "worker": f"postgresql+psycopg://app_worker:{worker_pw}@{host}:{port}/{db}",
    }


@pytest.fixture
def superuser_engine(db_urls):
    engine = sa.create_engine(db_urls["superuser"])
    yield engine
    engine.dispose()


@pytest.fixture
def worker_engine(db_urls):
    engine = sa.create_engine(db_urls["worker"])
    yield engine
    engine.dispose()


@pytest.fixture
def tenant_id(superuser_engine) -> str:
    """A fresh WALLET tenant with one active event-type mapping and two
    incentives (one individual, one group), cleaned up afterward."""
    tid = str(uuid.uuid4())
    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, display_name, profile_type) "
                "VALUES (:id, :slug, 'Store Test Tenant', 'WALLET')"
            ),
            {"id": tid, "slug": f"store-test-{tid[:8]}"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO event_type_mappings "
                "(id, tenant_id, client_event_type, canonical_event_type, amount_field_path, "
                " occurred_at_field_path, active) "
                "VALUES (gen_random_uuid(), :tid, 'txn.payment', 'PAYMENT', 'amount', 'created_at', true)"
            ),
            {"tid": tid},
        )
        conn.execute(
            sa.text(
                "INSERT INTO incentives "
                "(id, tenant_id, code, display_name, cost_idr, encourages_borrowing, "
                " changes_credit_terms, subject_type, applicable_profile_types, active) "
                "VALUES (gen_random_uuid(), :tid, 'CASHBACK', 'Cashback', 25000, false, "
                " false, 'USER', '[]'::jsonb, true)"
            ),
            {"tid": tid},
        )
    yield tid
    with superuser_engine.begin() as conn:
        for table in (
            "recommendations", "allocation_candidates", "allocation_runs", "policy_decisions",
            "impact_scores", "risk_scores", "circle_members", "transaction_circles",
            "narrations", "feature_snapshots", "labeled_examples", "outcome_events",
            "experiment_assignments", "experiments", "external_signals", "canonical_events",
            "raw_events", "users", "audit_log", "contact_log", "incentives", "event_type_mappings",
        ):
            conn.execute(sa.text(f"DELETE FROM {table} WHERE tenant_id = :tid"), {"tid": tid})
        conn.execute(sa.text("DELETE FROM tenants WHERE id = :tid"), {"tid": tid})


def test_full_pipeline_store_round_trip(worker_engine, superuser_engine, tenant_id) -> None:
    store = PostgresPipelineStore(worker_engine, tenant_id)
    now = datetime(2026, 9, 17, tzinfo=UTC)
    run_id = str(uuid.uuid4())
    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO pipeline_runs (id, tenant_id, status, stages, reason_source_counts) "
                "VALUES (:id, :tid, 'RUNNING', '{}'::jsonb, '{}'::jsonb)"
            ),
            {"id": run_id, "tid": tenant_id},
        )

    # --- tenant + mapping ---
    tenant = store.get_tenant(tenant_id)
    assert tenant.profile_type == "WALLET"
    assert tenant.mapping["mappings"][0]["client_event_type"] == "txn.payment"

    # --- ingest: raw event -> canonical event round trip ---
    with worker_engine.begin() as conn:
        conn.execute(sa.text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        conn.execute(
            sa.text(
                "INSERT INTO raw_events (id, tenant_id, client_event_id, payload) "
                "VALUES (gen_random_uuid(), :tid, 'evt-1', '{}'::jsonb)"
            ),
            {"tid": tenant_id},
        )

    claimed = store.claim_raw_events(tenant_id, 10)
    assert len(claimed) == 1
    store.mark_raw_event(tenant_id, claimed[0].raw_event_id, "PROCESSED")

    canonical = CanonicalEvent(
        tenant_id=tenant_id, client_event_id="evt-1", event_type=CanonicalEventType.PAYMENT,
        occurred_at=now - timedelta(days=1), user_pseudonym="user-a", amount_idr=50_000,
    )
    added = store.save_canonical_events(tenant_id, [canonical])
    assert added == 1
    loaded = store.load_canonical_events(tenant_id, now - timedelta(days=30))
    assert len(loaded) == 1 and loaded[0].client_event_id == "evt-1"

    # --- user attributes ---
    store.upsert_user_attributes(tenant_id, "user-a", {"region_code": "ID-JK", "cohort_key": "gold"})
    attrs = store.load_user_attributes(tenant_id)
    assert attrs["user-a"] == {"region_code": "ID-JK", "cohort_key": "gold"}

    # --- incentives ---
    incentives = store.load_incentives(tenant_id)
    assert len(incentives) == 1
    assert incentives[0].code == "CASHBACK"
    assert incentives[0].is_group is False
    assert incentives[0].applicable_profile_types == ()

    # --- external signals ---
    store.save_external_signals([
        ExternalSignal(source="test", scope_type=ScopeType.REGION, scope_key="ID-JK",
                       signal_type=SignalType.NEWS_SENTIMENT, value=-0.2, observed_at=now)
    ])
    with superuser_engine.connect() as conn:
        count = conn.execute(
            sa.text("SELECT count(*) FROM external_signals WHERE tenant_id = :tid"), {"tid": tenant_id}
        ).scalar_one()
    assert count == 1

    # --- stage bookkeeping ---
    store.record_stage(StageRecord(run_id, tenant_id, "INGEST", "DONE", {}))

    # --- circles: GRAPH -> RISK bridge ---
    snapshot = CircleSnapshot(user_pseudonym="user-a", circle_size=3,
                              neighbor_activity_ratio_now=0.4, neighbor_activity_ratio_30d_ago=0.9,
                              delta_stability=-0.5, pattern_type=PatternType.CIRCLE_SPECIFIC)
    circle = Circle(circle_id="circle-abc", members=("user-a", "user-b", "user-c"))
    store.save_circles(tenant_id, run_id, [snapshot], [circle])
    assert "circle-abc" in store._circle_id_by_str
    with superuser_engine.connect() as conn:
        member_count = conn.execute(
            sa.text("SELECT count(*) FROM circle_members WHERE tenant_id = :tid"), {"tid": tenant_id}
        ).scalar_one()
    assert member_count == 3

    risk = RiskScore(user_pseudonym="user-a", churn_risk=0.8, model="HEURISTIC_NO_CONTEXT", context_row_count=0)
    store.save_risk_scores(tenant_id, run_id, [risk])
    with superuser_engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT delta_stability, pattern_type FROM risk_scores WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).one()
    assert row.delta_stability == -0.5
    assert row.pattern_type == "CIRCLE_SPECIFIC"

    # --- impact scores + segments ---
    impact_score = ImpactScore(p_incentivized=0.7, p_not_incentivized=0.3, model="FALLBACK")
    store.save_impact_scores(tenant_id, run_id, {"user-a": impact_score},
                             {"user-a": ImpactSegment.PERSUADABLE})
    with superuser_engine.connect() as conn:
        segment = conn.execute(
            sa.text("SELECT segment FROM impact_scores WHERE tenant_id = :tid"), {"tid": tenant_id}
        ).scalar_one()
    assert segment == "PERSUADABLE"

    # --- policy decisions ---
    decision = PolicyDecisionModel(
        candidate_id="cand-1", user_pseudonym="user-a", outcome="ALLOW",
        results=(RuleResult(rule_code=RuleCode.FREQUENCY_CAP, allowed=True, reason="ok"),),
    )
    store.save_policy_decisions(tenant_id, run_id, [decision])
    with superuser_engine.connect() as conn:
        outcome = conn.execute(
            sa.text("SELECT outcome FROM policy_decisions WHERE tenant_id = :tid"), {"tid": tenant_id}
        ).scalar_one()
    assert outcome == "ALLOW"

    # --- experiment + arms ---
    experiment_id = store.get_or_create_experiment(tenant_id, control_pct=20, naive_pct=20)
    assert store.get_or_create_experiment(tenant_id, control_pct=20, naive_pct=20) == experiment_id
    store.save_arm_assignments(tenant_id, experiment_id, {"user-a": Arm.ENGINE})

    # --- allocation: individual candidate + group candidate ---
    individual = Candidate(
        candidate_id="cand-1", tenant_id=tenant_id, user_pseudonym="user-a", incentive_code="CASHBACK",
        cost_idr=25_000, business_value_idr=100_000, churn_risk=0.8, impact_score=0.4,
        segment=ImpactSegment.PERSUADABLE, pattern_type=PatternType.CIRCLE_SPECIFIC,
    )
    group_member = Candidate(
        candidate_id="cand-2", tenant_id=tenant_id, user_pseudonym="user-b", incentive_code="CASHBACK",
        cost_idr=25_000, business_value_idr=80_000, group_id="circle-abc", churn_risk=0.6,
        impact_score=0.3, segment=ImpactSegment.PERSUADABLE, pattern_type=PatternType.CIRCLE_SPECIFIC,
    )
    decisions = (
        AllocationDecision(candidate_id="cand-1", choice_key="user-a", selected=True, priority=40_000,
                           cost_idr=25_000, rank=1),
        AllocationDecision(candidate_id="cand-2", choice_key="group:circle-abc", selected=True,
                           priority=24_000, cost_idr=25_000, rank=2),
    )
    result = AllocationResult(strategy="EXACT_DP", budget_idr=100_000, spent_idr=50_000,
                              objective_value_idr=64_000.0, decisions=decisions)
    store.save_allocation(tenant_id, run_id, result, [], [individual, group_member],
                          RankingStrategy.FALLBACK, 42)
    assert store._allocation_run_id is not None
    with superuser_engine.connect() as conn:
        candidate_rows = conn.execute(
            sa.text("SELECT subject_type, circle_id, incentive_code FROM allocation_candidates "
                    "WHERE tenant_id = :tid ORDER BY user_rank"),
            {"tid": tenant_id},
        ).all()
    assert candidate_rows[0].subject_type == "USER"
    assert candidate_rows[1].subject_type == "GROUP"
    assert candidate_rows[1].circle_id is not None
    assert all(r.incentive_code == "CASHBACK" for r in candidate_rows)

    # --- narration ---
    store.save_narration(tenant_id, run_id, "hash-1", "Test narration text.", "TEMPLATE")
    with superuser_engine.connect() as conn:
        text = conn.execute(
            sa.text("SELECT text FROM narrations WHERE tenant_id = :tid AND fact_sheet_hash = 'hash-1'"),
            {"tid": tenant_id},
        ).scalar_one()
    assert text == "Test narration text."

    # --- feature snapshots ---
    fs = FeatureSnapshot(tenant_id=tenant_id, run_id=run_id, user_pseudonym="user-a",
                         features={"recency_days": 5.0}, churn_risk=0.8, impact_score=0.4,
                         pattern_type="CIRCLE_SPECIFIC", incentive_code="CASHBACK",
                         cost_idr=25_000, business_value_idr=100_000)
    store.save_feature_snapshots([fs])
    fs_loaded = store.load_feature_snapshots(tenant_id)
    assert (run_id, "user-a") in fs_loaded
    assert fs_loaded[(run_id, "user-a")].churn_risk == 0.8

    # --- recommendations: USER and GROUP ---
    user_rec = Recommendation(
        recommendation_id="rec-1", tenant_id=tenant_id, run_id=run_id, candidate_id="cand-1",
        arm=Arm.ENGINE, status=RecommendationStatus.PENDING_APPROVAL, incentive_code="CASHBACK",
        cost_idr=25_000, priority=40_000.0, user_pseudonym="user-a", reason_text="because",
        reason_source="TEMPLATE", fact_sheet_hash="hash-1", created_at=now,
    )
    group_rec = Recommendation(
        recommendation_id="rec-2", tenant_id=tenant_id, run_id=run_id, candidate_id="cand-2",
        arm=Arm.ENGINE, status=RecommendationStatus.PENDING_APPROVAL, incentive_code="CASHBACK",
        cost_idr=25_000, priority=24_000.0, group_id="circle-abc", member_pseudonyms=("user-b", "user-c"),
        reason_text="because group", reason_source="TEMPLATE", fact_sheet_hash="hash-2", created_at=now,
    )
    store.create_recommendations([user_rec, group_rec])
    with superuser_engine.connect() as conn:
        rec_rows = conn.execute(
            sa.text("SELECT subject_type, status, allocation_run_id FROM recommendations "
                    "WHERE tenant_id = :tid ORDER BY subject_type"),
            {"tid": tenant_id},
        ).all()
    assert len(rec_rows) == 2
    assert all(r.status == "PENDING_APPROVAL" for r in rec_rows)
    assert all(r.allocation_run_id == store._allocation_run_id for r in rec_rows)

    # --- audit ---
    store.append_audit(tenant_id, "app_worker", "RECOMMENDATION_CREATED", "recommendation", "rec-1", {"x": 1})
    with superuser_engine.connect() as conn:
        audit_count = conn.execute(
            sa.text("SELECT count(*) FROM audit_log WHERE tenant_id = :tid"), {"tid": tenant_id}
        ).scalar_one()
    assert audit_count == 1

    # --- feedback loop: outcome -> labeled example round trip ---
    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO outcome_events (id, tenant_id, experiment_id, user_pseudonym, "
                " outcome_type, observed_at, value_idr) "
                "VALUES (gen_random_uuid(), :tid, :eid, 'user-a', 'RETAINED', :observed_at, 5000)"
            ),
            {"tid": tenant_id, "eid": experiment_id, "observed_at": now},
        )
    outcomes = store.load_outcomes(tenant_id)
    assert len(outcomes) == 1
    assert outcomes[0].arm == Arm.ENGINE
    assert outcomes[0].treated is True
    assert outcomes[0].retained is True
    assert outcomes[0].run_id == run_id

    example = LabeledExample(
        tenant_id=tenant_id, source_outcome_id=outcomes[0].outcome_event_id, user_pseudonym="user-a",
        features={"recency_days": 5.0}, arm=Arm.ENGINE, treated=True, retained=True,
        churn_risk=0.8, impact_score=0.4, pattern_type="CIRCLE_SPECIFIC", incentive_code="CASHBACK",
        cost_idr=25_000, business_value_idr=100_000, realized_value_idr=95_000.0,
    )
    store.save_labeled_examples([example])
    labeled = store.load_labeled_examples(tenant_id)
    assert len(labeled) == 1
    assert labeled[0].source_outcome_id == outcomes[0].outcome_event_id
    assert labeled[0].realized_value_idr == 95_000.0

    # --- contact log ---
    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO contact_log (id, tenant_id, user_pseudonym, contacted_at) "
                "VALUES (gen_random_uuid(), :tid, 'user-a', :now)"
            ),
            {"tid": tenant_id, "now": now},
        )
    contacts = store.load_contact_times(tenant_id)
    assert len(contacts["user-a"]) == 1
