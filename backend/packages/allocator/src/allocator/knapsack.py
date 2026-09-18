"""Exact 0-1 knapsack via dynamic programming (requirement 7, stage 3).

Multiple-choice variant: at most one item per choice key (one incentive per user,
one reward per group). Costs are scaled by cost_scale_idr with ceil, so the
result never overspends the real budget.
"""
import math
from array import array

from allocator.items import DPTooLarge, KnapsackItem


def solve(items, *, budget_idr: int, cost_scale_idr: int, max_dp_cells: int):
    """Return the item_ids of an optimal selection (value-maximizing, deterministic)."""
    usable = [i for i in items if i.value > 0 and i.cost_idr <= budget_idr]
    if not usable:
        return []
    capacity = budget_idr // cost_scale_idr
    groups: dict[str, list[KnapsackItem]] = {}
    for item in sorted(usable, key=lambda i: (i.choice_key, i.item_id)):
        groups.setdefault(item.choice_key, []).append(item)
    keys = sorted(groups)
    if len(keys) * (capacity + 1) > max_dp_cells:
        raise DPTooLarge(f"{len(keys)} x {capacity + 1} cells exceeds {max_dp_cells}")

    weight = {i.item_id: math.ceil(i.cost_idr / cost_scale_idr) for i in usable}
    best = [0.0] * (capacity + 1)
    choices: list[array] = []
    for key in keys:
        nxt = best[:]
        choice = array("i", [-1]) * (capacity + 1)
        for idx, item in enumerate(groups[key]):
            w = weight[item.item_id]
            for c in range(w, capacity + 1):
                candidate = best[c - w] + item.value
                if candidate > nxt[c] + 1e-9:
                    nxt[c] = candidate
                    choice[c] = idx
        best = nxt
        choices.append(choice)

    c = max(range(capacity + 1), key=lambda k: (best[k], -k))
    selected = []
    for g in range(len(keys) - 1, -1, -1):
        idx = choices[g][c]
        if idx >= 0:
            item = groups[keys[g]][idx]
            selected.append(item.item_id)
            c -= weight[item.item_id]
    return sorted(selected)
