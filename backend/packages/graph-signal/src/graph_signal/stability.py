"""neighbor_activity_ratio and delta_stability (requirement 4).

delta_stability = neighbor_activity_ratio(now) - neighbor_activity_ratio(now - 30d)
"""
from graph_signal.build import neighbors


def neighbor_activity_ratio(user_pseudonym: str, edges, active_pseudonyms: set[str]) -> float:
    """Weighted share of the user's neighbors that were active. 0.0 when the user has no circle."""
    nbrs = neighbors(user_pseudonym, edges)
    total = sum(nbrs.values())
    if total <= 0:
        return 0.0
    return sum(w for n, w in nbrs.items() if n in active_pseudonyms) / total


def delta_stability(ratio_now: float, ratio_30d_ago: float) -> float:
    return ratio_now - ratio_30d_ago
