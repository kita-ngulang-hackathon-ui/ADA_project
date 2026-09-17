"""Build recency-decayed transaction edges (requirement 4).

Only counterparty-bearing canonical events count. Edges are undirected;
weight = sum(0.5 ** (age_days / half_life_days)) over interactions in the window.
"""
from collections import defaultdict
from datetime import timedelta

from core_contracts import COUNTERPARTY_EVENT_TYPES, Edge


def build_edges(events, *, now, window_days: int, half_life_days: float,
                min_interactions: int):
    start = now - timedelta(days=window_days)
    weights: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for e in events:
        if e.event_type not in COUNTERPARTY_EVENT_TYPES or not e.counterparty_pseudonym:
            continue
        if not (start <= e.occurred_at <= now) or e.counterparty_pseudonym == e.user_pseudonym:
            continue
        a, b = sorted((e.user_pseudonym, e.counterparty_pseudonym))
        age_days = (now - e.occurred_at).total_seconds() / 86400
        weights[(a, b)] += 0.5 ** (age_days / half_life_days)
        counts[(a, b)] += 1
    return [
        Edge(user_pseudonym=a, counterparty_pseudonym=b, weight=weights[(a, b)],
             interaction_count=counts[(a, b)])
        for (a, b) in sorted(weights)
        if counts[(a, b)] >= min_interactions
    ]


def neighbors(user_pseudonym: str, edges) -> dict[str, float]:
    """Neighbor -> edge weight for one user."""
    result: dict[str, float] = {}
    for edge in edges:
        if edge.user_pseudonym == user_pseudonym:
            result[edge.counterparty_pseudonym] = edge.weight
        elif edge.counterparty_pseudonym == user_pseudonym:
            result[edge.user_pseudonym] = edge.weight
    return result
