"""neighbor_activity_ratio and delta_stability (requirement 4).

delta_stability = neighbor_activity_ratio(now) - neighbor_activity_ratio(now - 30d)

TODO: implement both functions, weighting neighbors by edge weight.
"""


def neighbor_activity_ratio(user_pseudonym: str, edges, active_pseudonyms: set[str]) -> float:
    raise NotImplementedError


def delta_stability(ratio_now: float, ratio_30d_ago: float) -> float:
    raise NotImplementedError
