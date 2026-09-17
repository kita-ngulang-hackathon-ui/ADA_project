"""Exact 0-1 knapsack via dynamic programming (requirement 7, stage 3).

TODO:
- Scale costs by cost_scale_idr (ceil) to bound table width.
- Enforce one item per user (multiple-choice knapsack groups).
- Raise if rows * capacity > max_dp_cells so caller can fall back.
"""


def solve(items, *, budget_idr: int, cost_scale_idr: int, max_dp_cells: int):
    raise NotImplementedError
