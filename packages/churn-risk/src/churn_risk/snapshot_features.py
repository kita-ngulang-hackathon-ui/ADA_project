"""Snapshot features for the trained TabPFN churn scorer (requirement 3).

The scorer artifact (artifacts/context_schema.json) expects 12 features in a
fixed order. This module derives them from one user's canonical events, using
only events on or before `now` so nothing from after the snapshot leaks in.

All vocabulary and scale choices come from the `mapping` dict the caller passes
(fixtures/churn_scorer_mapping.json); this module never reads files or env.
"""
from datetime import timedelta

from core_contracts import CanonicalEventType, ScopeType, SignalType

SNAPSHOT_FEATURE_COLUMNS: list[str] = [
    "client_profile",
    "region",
    "txn_count_30d",
    "active_days_30d",
    "days_since_last_txn",
    "avg_amount_30d",
    "total_amount_30d",
    "amount_trend_90d",
    "activity_trend_90d",
    "external_sentiment",
    "external_signal_name",
    "base_business_value",
]

# Neutral values used to estimate how much the external signal moved the score.
NEUTRAL_SIGNAL = {"external_sentiment": 0.0, "external_signal_name": "stable"}

TRANSACTION_EVENT_TYPES: frozenset[CanonicalEventType] = frozenset({
    CanonicalEventType.PAYMENT,
    CanonicalEventType.P2P_TRANSFER,
    CanonicalEventType.TOPUP,
    CanonicalEventType.WITHDRAWAL,
    CanonicalEventType.SPLIT_BILL_CREATED,
    CanonicalEventType.SPLIT_BILL_SETTLED,
    CanonicalEventType.RECURRING_PAYMENT,
    CanonicalEventType.LOAN_REPAYMENT,
})

WINDOW_DAYS = 30
MAX_RECENCY_DAYS = 60


def _trend(recent: float, prior_a: float, prior_b: float) -> float:
    """(last window - mean of the two prior windows) / larger of the two, clipped to [-1, 1]."""
    baseline = (prior_a + prior_b) / 2.0
    scale = max(recent, baseline)
    if scale <= 0:
        return 0.0
    return max(-1.0, min(1.0, (recent - baseline) / scale))


def signal_name(external_signal, support_contacts: int, mapping: dict) -> str:
    rules = mapping["signal_rules"]
    if support_contacts >= rules["support_friction_min_contacts"]:
        return "support_friction"
    if external_signal is None:
        return "stable"
    value = external_signal.value
    if value >= rules["positive_threshold"]:
        return "positive_momentum"
    if value <= -rules["negative_threshold"]:
        if (external_signal.scope_type == ScopeType.COHORT
                or external_signal.signal_type == SignalType.SECTOR_TREND):
            return "income_pressure"
        return "competitor_pull"
    return "stable"


def build_snapshot_features(events, *, now, attributes: dict | None, external_signal,
                            profile_type: str, business_value_idr: float, mapping: dict) -> dict:
    """Return the 12 scorer features for one user, keyed in SNAPSHOT_FEATURE_COLUMNS order."""
    attributes = attributes or {}
    past = [e for e in events if e.occurred_at <= now]
    txns = sorted((e for e in past if e.event_type in TRANSACTION_EVENT_TYPES),
                  key=lambda e: e.occurred_at)
    support_contacts = sum(
        1 for e in past
        if e.event_type == CanonicalEventType.SUPPORT_CONTACT
        and e.occurred_at > now - timedelta(days=WINDOW_DAYS)
    )

    windows = []  # [last 30d, 30-60d, 60-90d]
    for k in range(3):
        end, start = now - timedelta(days=WINDOW_DAYS * k), now - timedelta(days=WINDOW_DAYS * (k + 1))
        windows.append([e for e in txns if start < e.occurred_at <= end])

    scale = float(mapping["amount_scale_idr"])
    amounts = [sum(e.amount_idr or 0 for e in w) / scale for w in windows]
    counts = [float(len(w)) for w in windows]
    recent = windows[0]

    if txns:
        recency = min((now - txns[-1].occurred_at).total_seconds() / 86400, MAX_RECENCY_DAYS)
    else:
        recency = MAX_RECENCY_DAYS

    # Kept inside the range the scorer's context covers.
    low, high = mapping["base_business_value_range"]
    profiles = mapping["profile_by_type"]
    regions = mapping["region_by_code"]
    features = {
        "client_profile": profiles.get(profile_type.upper(), mapping["default_profile"]),
        "region": regions.get(attributes.get("region_code"), mapping["default_region"]),
        "txn_count_30d": len(recent),
        "active_days_30d": len({e.occurred_at.date() for e in recent}),
        "days_since_last_txn": int(recency),
        "avg_amount_30d": amounts[0] / len(recent) if recent else 0.0,
        "total_amount_30d": amounts[0],
        "amount_trend_90d": _trend(*amounts),
        "activity_trend_90d": _trend(*counts),
        "external_sentiment": float(external_signal.value) if external_signal else 0.0,
        "external_signal_name": signal_name(external_signal, support_contacts, mapping),
        "base_business_value": min(max(float(business_value_idr) / mapping["business_value_scale_idr"],
                                       low), high),
    }
    return {c: features[c] for c in SNAPSHOT_FEATURE_COLUMNS}
