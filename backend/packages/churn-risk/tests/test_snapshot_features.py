"""Snapshot features for the trained churn scorer."""
import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from churn_risk import SNAPSHOT_FEATURE_COLUMNS, build_snapshot_features
from core_contracts import CanonicalEvent, CanonicalEventType, ExternalSignal, ScopeType, SignalType

ROOT = Path(__file__).resolve().parents[3]
MAPPING = json.loads((ROOT / "fixtures" / "churn_scorer_mapping.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "artifacts" / "context_schema.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 9, 17, tzinfo=UTC)
_ids = itertools.count()


def _event(days_ago: float, etype=CanonicalEventType.PAYMENT, amount=50_000) -> CanonicalEvent:
    return CanonicalEvent(tenant_id="t", client_event_id=f"e{next(_ids)}", event_type=etype,
                          occurred_at=NOW - timedelta(days=days_ago), user_pseudonym="u",
                          amount_idr=amount)


def _signal(value: float, scope=ScopeType.REGION, stype=SignalType.NEWS_SENTIMENT) -> ExternalSignal:
    return ExternalSignal(signal_id="s", source="canned", scope_type=scope, scope_key="k",
                          signal_type=stype, value=value, observed_at=NOW)


def _build(events, signal=None, attributes=None, profile="WALLET", value=300_000):
    return build_snapshot_features(events, now=NOW, attributes=attributes, external_signal=signal,
                                   profile_type=profile, business_value_idr=value, mapping=MAPPING)


def test_columns_match_artifact_schema_order() -> None:
    assert SNAPSHOT_FEATURE_COLUMNS == [f["name"] for f in SCHEMA["model_features_ordered"]]
    assert list(_build([])) == SNAPSHOT_FEATURE_COLUMNS


def test_mapping_categories_are_in_schema_vocabulary() -> None:
    vocab = {f["name"]: set(f["categories"]) for f in SCHEMA["model_features_ordered"]
             if f["categories"]}
    profiles = set(MAPPING["profile_by_type"].values()) | {MAPPING["default_profile"]}
    regions = set(MAPPING["region_by_code"].values()) | {MAPPING["default_region"]}
    assert profiles <= vocab["client_profile"]
    assert regions <= vocab["region"]


def test_windows_amounts_and_recency() -> None:
    events = [_event(2), _event(2.5), _event(10), _event(45), _event(-3)]  # last one is in the future
    f = _build(events, attributes={"region_code": "ID-JK"})
    assert f["txn_count_30d"] == 3
    assert f["days_since_last_txn"] == 2
    assert f["total_amount_30d"] == 150.0 and f["avg_amount_30d"] == 50.0
    assert f["region"] == "Central" and f["client_profile"] == "Everyday Wallet"
    assert f["base_business_value"] == 12.0  # 300_000 / 25_000
    assert f["activity_trend_90d"] > 0


def test_no_activity_caps_recency_and_uses_defaults() -> None:
    f = _build([_event(80)], attributes={"region_code": "ZZ"}, profile="UNKNOWN")
    assert f["days_since_last_txn"] == 60
    assert f["txn_count_30d"] == 0 and f["avg_amount_30d"] == 0.0
    assert f["amount_trend_90d"] == -1.0
    assert f["region"] == MAPPING["default_region"]
    assert f["client_profile"] == MAPPING["default_profile"]


def test_sessions_are_not_transactions() -> None:
    assert _build([_event(1, CanonicalEventType.SESSION_OPEN, amount=None)])["txn_count_30d"] == 0


def test_signal_name_rules() -> None:
    assert _build([])["external_signal_name"] == "stable"
    assert _build([], _signal(0.3))["external_signal_name"] == "positive_momentum"
    assert _build([], _signal(-0.6, ScopeType.COHORT))["external_signal_name"] == "income_pressure"
    assert _build([], _signal(-0.3))["external_signal_name"] == "competitor_pull"
    assert _build([], _signal(-0.05))["external_signal_name"] == "stable"
    support = [_event(d, CanonicalEventType.SUPPORT_CONTACT, amount=None) for d in (1, 5)]
    assert _build(support, _signal(0.3))["external_signal_name"] == "support_friction"
    assert _build([], _signal(-0.4))["external_sentiment"] == -0.4


def test_business_value_clipped_to_context_range() -> None:
    assert _build([], value=0)["base_business_value"] == 10
    assert _build([], value=10**12)["base_business_value"] == 465
