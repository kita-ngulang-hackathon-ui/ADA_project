"""Integration: real TabPFN checkpoint over the artifact bundle (synthetic data).

Skipped without TABPFN_TOKEN (environment or root .env). Slow on CPU: the ~9k-row
context is fit once per session, then every test reuses the resident scorer.
Deselected by default; run with `make test-tabpfn`.
"""
import pandas as pd
import pytest
from core_contracts import RecommendationStatus
from worker.pipeline import run_pipeline
from worker_world import NOW, WALLET_ID, build_store, make_settings, real_scorer, tabpfn_token

pytestmark = [
    pytest.mark.tabpfn,
    pytest.mark.skipif(not tabpfn_token(), reason="needs TABPFN_TOKEN for the checkpoint"),
]

DEMO_ROW = {
    "user_id": "SYN-DEMO-001", "snapshot_date": "2026-09-17",
    "client_profile": "PayLater Explorer", "region": "Central",
    "txn_count_30d": 7, "active_days_30d": 5, "days_since_last_txn": 12,
    "avg_amount_30d": 42.50, "total_amount_30d": 297.50,
    "amount_trend_90d": -0.20, "activity_trend_90d": -0.35,
    "external_sentiment": -0.40, "external_signal_name": "competitor_pull",
    "base_business_value": 185.00,
}


def test_real_scorer_ranks_dormant_user_above_active_user() -> None:
    scorer = real_scorer()
    active = {**DEMO_ROW, "user_id": "active", "txn_count_30d": 30, "active_days_30d": 22,
              "days_since_last_txn": 0, "amount_trend_90d": 0.3, "activity_trend_90d": 0.3,
              "external_sentiment": 0.5, "external_signal_name": "positive_momentum"}
    dormant = {**DEMO_ROW, "user_id": "dormant", "txn_count_30d": 1, "active_days_30d": 1,
               "days_since_last_txn": 45, "amount_trend_90d": -0.9, "activity_trend_90d": -0.9}
    out = scorer.predict(pd.DataFrame([DEMO_ROW, active, dormant])).set_index("user_id")
    assert out["churn_risk"].between(0.0, 1.0).all()
    assert out.loc["dormant", "churn_risk"] > out.loc["active", "churn_risk"]
    assert (out["as_of"] == "2026-09-17").all()


def test_real_pipeline_run_reaches_pending_approval() -> None:
    store = build_store()
    settings = make_settings(churn_scorer_device="auto")
    result = run_pipeline(WALLET_ID, "run-real", store=store, settings=settings, now=NOW,
                          churn_scorer=real_scorer())
    stages = {s.stage: s for s in result.stages}

    assert result.status == "DONE", [(s.stage, s.detail) for s in result.stages]
    assert stages["RISK"].detail["model"] == "TABPFN_ARTIFACT_4c210c32"
    assert stages["RISK"].detail["context_rows"] == 8948
    scores = store.risk_scores[WALLET_ID]
    assert len(scores) == stages["RISK"].detail["scored"] > 0
    assert all(0.0 <= s.churn_risk <= 1.0 for s in scores)
    assert len({round(s.churn_risk, 6) for s in scores}) > 1  # not a constant stand-in

    recs = list(store.recommendations[WALLET_ID].values())
    assert recs and all(r.status == RecommendationStatus.PENDING_APPROVAL for r in recs)
