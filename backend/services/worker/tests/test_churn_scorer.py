"""Trained churn scorer bundle loading and input contract (synthetic artifacts)."""
import json
import shutil

import pandas as pd
import pytest
from churn_risk import NEUTRAL_SIGNAL, SNAPSHOT_FEATURE_COLUMNS
from worker.churn_scorer import ChurnRiskScorer, ChurnScorerUnavailable, load_scorer, main
from worker_world import ARTIFACTS, FakeTabPFN, fake_scorer, make_settings

DEMO_ROW = {
    "user_id": "SYN-DEMO-001",
    "snapshot_date": "2026-09-17",
    "client_profile": "PayLater Explorer",
    "region": "Central",
    "txn_count_30d": 7,
    "active_days_30d": 5,
    "days_since_last_txn": 12,
    "avg_amount_30d": 42.50,
    "total_amount_30d": 297.50,
    "amount_trend_90d": -0.20,
    "activity_trend_90d": -0.35,
    "external_sentiment": -0.40,
    "external_signal_name": "competitor_pull",
    "base_business_value": 185.00,
}


def test_feature_order_matches_artifact_schema() -> None:
    schema = json.loads((ARTIFACTS / "context_schema.json").read_text(encoding="utf-8"))
    assert [f["name"] for f in schema["model_features_ordered"]] == SNAPSHOT_FEATURE_COLUMNS
    assert fake_scorer().feature_names == SNAPSHOT_FEATURE_COLUMNS


def test_fits_on_context_rows_only_with_recorded_constructor() -> None:
    scorer = fake_scorer()
    assert scorer.context_row_count == 8948
    assert scorer.model.fit_rows == 8948
    assert scorer.model.kwargs["device"] == "cpu"
    assert scorer.model.kwargs["categorical_features_indices"] == [0, 1, 10]
    assert scorer.model.kwargs["n_estimators"] == 4


def test_predict_output_contract() -> None:
    out = fake_scorer().predict(pd.DataFrame([DEMO_ROW]))
    assert list(out.columns) == ["user_id", "churn_risk", "as_of"]
    row = out.iloc[0]
    assert row["user_id"] == "SYN-DEMO-001" and row["as_of"] == "2026-09-17"
    assert 0.0 <= row["churn_risk"] <= 1.0


def test_neutralized_signal_scored_in_one_batch() -> None:
    risk, neutral = fake_scorer().predict_with_neutral(pd.DataFrame([DEMO_ROW]), NEUTRAL_SIGNAL)
    assert risk[0] > neutral[0]  # negative sentiment raises risk in the fake model


@pytest.mark.parametrize("change", [
    {"region": "Atlantis"},
    {"external_signal_name": "unknown_signal"},
    {"txn_count_30d": "many"},
    {"snapshot_date": "not-a-date"},
])
def test_rejects_invalid_candidates(change) -> None:
    with pytest.raises(ValueError):
        fake_scorer().predict(pd.DataFrame([{**DEMO_ROW, **change}]))


def test_rejects_missing_column() -> None:
    row = {k: v for k, v in DEMO_ROW.items() if k != "region"}
    with pytest.raises(ValueError, match="missing columns"):
        fake_scorer().predict(pd.DataFrame([row]))


def test_tampered_bundle_fails_loudly(tmp_path) -> None:
    bundle = tmp_path / "artifacts"
    shutil.copytree(ARTIFACTS, bundle)
    schema = bundle / "context_schema.json"
    schema.write_text(schema.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity check failed"):
        ChurnRiskScorer(bundle, device="cpu", classifier_factory=FakeTabPFN)
    settings = make_settings(churn_scorer_artifact_dir=str(bundle))
    with pytest.raises(ChurnScorerUnavailable):
        load_scorer(settings, classifier_factory=FakeTabPFN)
    with pytest.raises(SystemExit):
        main(["--artifact-dir", str(bundle), "--verify"])


def test_missing_bundle_fails_loudly(tmp_path) -> None:
    settings = make_settings(churn_scorer_artifact_dir=str(tmp_path / "nope"))
    with pytest.raises(ChurnScorerUnavailable, match="Missing scorer artifact"):
        load_scorer(settings, classifier_factory=FakeTabPFN)


