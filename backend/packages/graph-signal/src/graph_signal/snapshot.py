"""Per-user circle snapshots: ratio now vs 30 days ago, cohort median, pattern tag."""
from datetime import timedelta
from statistics import median

from core_contracts import CircleSnapshot, PatternType

from graph_signal.build import build_edges, neighbors
from graph_signal.pattern import tag_pattern
from graph_signal.stability import delta_stability, neighbor_activity_ratio


def active_users(events, *, start, end) -> set[str]:
    """Pseudonyms that initiated any event in [start, end). Structural fact only."""
    return {e.user_pseudonym for e in events if start <= e.occurred_at < end}


def empty_snapshot(user_pseudonym: str) -> CircleSnapshot:
    return CircleSnapshot(
        user_pseudonym=user_pseudonym, circle_size=0, neighbor_activity_ratio_now=0.0,
        neighbor_activity_ratio_30d_ago=0.0, delta_stability=0.0, pattern_type=PatternType.STABLE,
    )


def snapshot_users(events, users, *, now, lookback_days: int, activity_window_days: int,
                   half_life_days: float, min_interactions: int, cohort_of: dict,
                   external_value_of: dict, dip_threshold: float, cohort_dip_threshold: float):
    """Return (edges_now, {user: CircleSnapshot}).

    The past ratio uses the graph as it looked `activity_window_days` ago, so a
    circle that only formed recently does not read as a dip.
    """
    past = now - timedelta(days=activity_window_days)
    edges_now = build_edges(events, now=now, window_days=lookback_days,
                            half_life_days=half_life_days, min_interactions=min_interactions)
    edges_past = build_edges(events, now=past, window_days=lookback_days,
                             half_life_days=half_life_days, min_interactions=min_interactions)
    active_now = active_users(events, start=now - timedelta(days=activity_window_days), end=now)
    active_past = active_users(events, start=past - timedelta(days=activity_window_days), end=past)

    raw: dict[str, tuple[int, float, float, float]] = {}
    for user in users:
        size = len(neighbors(user, edges_now))
        r_now = neighbor_activity_ratio(user, edges_now, active_now)
        r_past = neighbor_activity_ratio(user, edges_past, active_past)
        has_past = bool(neighbors(user, edges_past))
        delta = delta_stability(r_now, r_past) if (size and has_past) else 0.0
        raw[user] = (size, r_now, r_past, delta)

    by_cohort: dict = {}
    for user, (size, _, _, delta) in raw.items():
        if size:
            by_cohort.setdefault(cohort_of.get(user), []).append(delta)

    snapshots = {}
    for user, (size, r_now, r_past, delta) in raw.items():
        if not size:
            snapshots[user] = empty_snapshot(user)
            continue
        cohort_deltas = by_cohort.get(cohort_of.get(user)) or [0.0]
        pattern = tag_pattern(delta, median(cohort_deltas), external_value_of.get(user),
                              dip_threshold=dip_threshold, cohort_dip_threshold=cohort_dip_threshold)
        snapshots[user] = CircleSnapshot(
            user_pseudonym=user, circle_size=size, neighbor_activity_ratio_now=r_now,
            neighbor_activity_ratio_30d_ago=r_past, delta_stability=delta, pattern_type=pattern,
        )
    return edges_now, snapshots
