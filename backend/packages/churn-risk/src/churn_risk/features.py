"""Feature engineering for churn risk (requirement 3).

FEATURE_COLUMNS is the fixed column order used for every model call.
build_features() takes one user's canonical events and is deterministic.
"""
from datetime import timedelta

from core_contracts import PatternType

ACTIVITY_WINDOW_DAYS = 30
# Used when a user has no event at all, so the value stays finite.
MAX_DAYS = 365.0

FEATURE_COLUMNS: list[str] = [
    "recency_days",
    "frequency_30d",
    "monetary_30d_idr",
    "tenure_days",
    "session_gap_days",
    "delta_stability",
    "circle_size",
    "pattern_circle_specific",
    "pattern_market_driven",
    "pattern_stable",
    "external_signal_value",
]


def build_features(events, circle_snapshot, external_signal, *, now):
    events = sorted((e for e in events if e.occurred_at <= now), key=lambda e: e.occurred_at)
    window_start = now - timedelta(days=ACTIVITY_WINDOW_DAYS)
    recent = [e for e in events if e.occurred_at >= window_start]

    def days(delta: timedelta) -> float:
        return delta.total_seconds() / 86400

    recency = days(now - events[-1].occurred_at) if events else MAX_DAYS
    tenure = days(now - events[0].occurred_at) if events else 0.0
    if len(recent) >= 2:
        span = days(recent[-1].occurred_at - recent[0].occurred_at)
        session_gap = span / (len(recent) - 1)
    else:
        session_gap = float(ACTIVITY_WINDOW_DAYS)

    pattern = circle_snapshot.pattern_type if circle_snapshot else PatternType.STABLE
    return {
        "recency_days": min(recency, MAX_DAYS),
        "frequency_30d": float(len(recent)),
        "monetary_30d_idr": float(sum(e.amount_idr or 0 for e in recent)),
        "tenure_days": min(tenure, MAX_DAYS),
        "session_gap_days": session_gap,
        "delta_stability": circle_snapshot.delta_stability if circle_snapshot else 0.0,
        "circle_size": float(circle_snapshot.circle_size) if circle_snapshot else 0.0,
        "pattern_circle_specific": 1.0 if pattern == PatternType.CIRCLE_SPECIFIC else 0.0,
        "pattern_market_driven": 1.0 if pattern == PatternType.MARKET_DRIVEN else 0.0,
        "pattern_stable": 1.0 if pattern == PatternType.STABLE else 0.0,
        "external_signal_value": external_signal.value if external_signal else 0.0,
    }


def to_row(features: dict[str, float]) -> list[float]:
    """Features dict -> list in FEATURE_COLUMNS order. Missing columns are 0.0."""
    return [float(features.get(c, 0.0)) for c in FEATURE_COLUMNS]
