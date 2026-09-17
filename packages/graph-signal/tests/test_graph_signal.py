"""graph-signal unit tests (hand-built stand-ins for planted patterns P1/P2)."""
from datetime import UTC, datetime, timedelta

from core_contracts import CanonicalEvent, CanonicalEventType, PatternType
from graph_signal import build_edges, find_circles, snapshot_users, tag_pattern

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _transfer(n, a: str, b: str, days_ago: float) -> CanonicalEvent:
    return CanonicalEvent(tenant_id="t", client_event_id=f"e{n}", event_type=CanonicalEventType.P2P_TRANSFER,
                          occurred_at=NOW - timedelta(days=days_ago), user_pseudonym=a,
                          counterparty_pseudonym=b, amount_idr=1000)


def _payment(n, a: str, days_ago: float) -> CanonicalEvent:
    return CanonicalEvent(tenant_id="t", client_event_id=f"p{n}", event_type=CanonicalEventType.PAYMENT,
                          occurred_at=NOW - timedelta(days=days_ago), user_pseudonym=a, amount_idr=1000)


def test_recency_decay_older_weighs_less() -> None:
    recent = build_edges([_transfer(i, "a", "b", 1) for i in range(3)], now=NOW, window_days=90,
                         half_life_days=21, min_interactions=3)
    old = build_edges([_transfer(i, "a", "c", 60) for i in range(3)], now=NOW, window_days=90,
                      half_life_days=21, min_interactions=3)
    assert recent[0].weight > old[0].weight


def test_min_interactions_and_non_counterparty_events_filtered() -> None:
    events = [_transfer(1, "a", "b", 1), _transfer(2, "b", "a", 2), _payment(3, "a", 1)]
    assert build_edges(events, now=NOW, window_days=90, half_life_days=21, min_interactions=3) == []
    edges = build_edges(events, now=NOW, window_days=90, half_life_days=21, min_interactions=2)
    assert len(edges) == 1 and edges[0].interaction_count == 2


def test_tag_pattern_rules() -> None:
    kw = dict(dip_threshold=0.1, cohort_dip_threshold=0.3)
    assert tag_pattern(-0.05, -0.5, -0.5, **kw) == PatternType.STABLE
    assert tag_pattern(-0.6, -0.5, -0.4, **kw) == PatternType.MARKET_DRIVEN
    assert tag_pattern(-0.6, -0.5, 0.2, **kw) == PatternType.CIRCLE_SPECIFIC
    assert tag_pattern(-0.6, 0.0, -0.4, **kw) == PatternType.CIRCLE_SPECIFIC


def _circle_world(hub: str = "a", others=("b", "c", "d"), prefix: str = ""):
    """hub's neighbors transacted 40-80 days ago, then went silent. e has no circle."""
    events, n = [], 0
    for day in range(40, 80, 5):
        for other in others:
            n += 1
            events.append(_transfer(f"{prefix}{n}", hub, other, day))
            n += 1
            events.append(_transfer(f"{prefix}{n}", other, hub, day + 0.5))
    events += [_payment(f"{prefix}1", hub, 2), _payment(f"{prefix}2", "e", 2)]
    return events


def test_circle_churn_tags_circle_specific_and_lonely_user_stable() -> None:
    events = _circle_world()
    kwargs = dict(now=NOW, lookback_days=90, activity_window_days=30, half_life_days=21,
                  min_interactions=3, dip_threshold=0.1, cohort_dip_threshold=0.3)
    _, snaps = snapshot_users(events, ["a", "e"], cohort_of={"a": "c1", "e": "c1"},
                              external_value_of={"a": 0.2, "e": None}, **kwargs)
    assert snaps["a"].circle_size == 3
    assert snaps["a"].delta_stability < -0.9
    assert snaps["a"].pattern_type == PatternType.CIRCLE_SPECIFIC
    assert snaps["e"].circle_size == 0 and snaps["e"].pattern_type == PatternType.STABLE


def test_cohort_wide_dip_with_negative_signal_is_market_driven() -> None:
    # Two separate circles in the same cohort dip together, and the cohort signal is negative.
    events = _circle_world() + _circle_world("x", ("y", "z", "w"), prefix="x")
    kwargs = dict(now=NOW, lookback_days=90, activity_window_days=30, half_life_days=21,
                  min_interactions=3, dip_threshold=0.1, cohort_dip_threshold=0.3)
    users = ["a", "x"]
    _, snaps = snapshot_users(events, users, cohort_of={u: "c3" for u in users},
                              external_value_of={u: -0.6 for u in users}, **kwargs)
    assert snaps["a"].pattern_type == PatternType.MARKET_DRIVEN
    assert snaps["x"].pattern_type == PatternType.MARKET_DRIVEN
    _, positive = snapshot_users(events, users, cohort_of={u: "c3" for u in users},
                                 external_value_of={u: 0.4 for u in users}, **kwargs)
    assert positive["a"].pattern_type == PatternType.CIRCLE_SPECIFIC


def test_circles_are_deterministic_and_sized() -> None:
    edges = build_edges(_circle_world(), now=NOW - timedelta(days=30), window_days=90,
                        half_life_days=21, min_interactions=3)
    first = find_circles(edges, min_size=3)
    assert first == find_circles(list(reversed(edges)), min_size=3)
    assert first[0].members == ("a", "b", "c", "d")
    assert find_circles(edges, min_size=5) == []
