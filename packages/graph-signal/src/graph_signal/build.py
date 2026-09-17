"""Build recency-decayed transaction edges (requirement 4).

TODO:
- Filter to counterparty-bearing canonical events.
- weight = sum(0.5 ** (age_days / half_life_days)) over interactions in window.
- Drop edges with fewer than min_interactions.
"""


def build_edges(events, *, now, window_days: int, half_life_days: float,
                min_interactions: int):
    raise NotImplementedError
