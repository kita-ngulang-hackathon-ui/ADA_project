"""Knapsack item: one allocatable unit (a single candidate or an indivisible group bundle)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class KnapsackItem:
    item_id: str
    choice_key: str  # at most one item per choice key (a user, or "group:<id>")
    cost_idr: int
    value: float
    candidate_ids: tuple[str, ...]


class DPTooLarge(Exception):
    """rows * capacity exceeds max_dp_cells; caller falls back to greedy."""
