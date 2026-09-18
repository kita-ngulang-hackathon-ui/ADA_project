"""Greedy density fallback when DP is too large.

Sort by value / cost desc, pick while budget allows, one item per choice key.
"""


def solve(items, *, budget_idr: int):
    remaining = budget_idr
    taken_keys: set[str] = set()
    selected = []
    usable = [i for i in items if i.value > 0]
    for item in sorted(usable, key=lambda i: (-(i.value / max(i.cost_idr, 1)), i.item_id)):
        if item.choice_key in taken_keys or item.cost_idr > remaining:
            continue
        selected.append(item.item_id)
        taken_keys.add(item.choice_key)
        remaining -= item.cost_idr
    return sorted(selected)
