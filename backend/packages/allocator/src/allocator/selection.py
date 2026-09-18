"""Allocation entry point: selection, runner-ups, exclusion reasons.

- Choose exact DP or greedy per config and size.
- Each choice key (user or group) gets at most one pick; its best other option is
  the visible runner-up.
- Every non-selected candidate gets an exclusion_reason.
"""
from dataclasses import dataclass

from core_contracts import AllocationDecision, AllocationResult, ExclusionReason

from allocator import greedy, knapsack
from allocator.groups import bundle_group
from allocator.items import DPTooLarge, KnapsackItem

STRATEGY_DP = "EXACT_DP"
STRATEGY_GREEDY = "GREEDY_DENSITY"


@dataclass(frozen=True)
class AllocatorConfig:
    strategy: str = "auto"  # auto | exact_dp | greedy_density
    cost_scale_idr: int = 1000
    max_dp_cells: int = 20_000_000


def _items(candidates) -> list[KnapsackItem]:
    items = []
    bundles: dict[tuple[str, str], list] = {}
    for r in candidates:
        c = r.candidate
        if c.group_id is None:
            items.append(KnapsackItem(item_id=c.candidate_id, choice_key=c.user_pseudonym,
                                      cost_idr=c.cost_idr, value=r.priority,
                                      candidate_ids=(c.candidate_id,)))
        else:
            bundles.setdefault((c.group_id, c.incentive_code), []).append(r)
    for (group_id, incentive), members in sorted(bundles.items()):
        items.append(bundle_group(f"{group_id}:{incentive}", members))
    return items


def allocate(candidates, *, budget_idr: int, config):
    items = _items(candidates)
    by_id = {i.item_id: i for i in items}

    strategy = STRATEGY_GREEDY
    if config.strategy.lower() in ("auto", "exact_dp"):
        try:
            chosen = knapsack.solve(items, budget_idr=budget_idr,
                                    cost_scale_idr=config.cost_scale_idr,
                                    max_dp_cells=config.max_dp_cells)
            strategy = STRATEGY_DP
        except DPTooLarge:
            chosen = greedy.solve(items, budget_idr=budget_idr)
    else:
        chosen = greedy.solve(items, budget_idr=budget_idr)

    chosen_items = sorted((by_id[i] for i in chosen), key=lambda i: (-i.value, i.item_id))
    picked_keys = {i.choice_key for i in chosen_items}
    rank_of = {item.item_id: n for n, item in enumerate(chosen_items, start=1)}

    runner_up_of: dict[str, str] = {}
    for item in sorted(items, key=lambda i: (-i.value, i.item_id)):
        if (item.choice_key in picked_keys and item.item_id not in rank_of
                and item.choice_key not in runner_up_of and item.value > 0):
            runner_up_of[item.choice_key] = item.item_id

    decisions = []
    for item in sorted(items, key=lambda i: (i.choice_key, i.item_id)):
        selected = item.item_id in rank_of
        if selected:
            reason = None
        elif item.value <= 0:
            reason = ExclusionReason.NO_EXPECTED_GAIN
        elif item.choice_key in picked_keys:
            reason = ExclusionReason.RUNNER_UP
        else:
            reason = ExclusionReason.BUDGET_EXHAUSTED
        for cid in item.candidate_ids:
            decisions.append(AllocationDecision(
                candidate_id=cid,
                choice_key=item.choice_key,
                selected=selected,
                priority=item.value,
                cost_idr=item.cost_idr,
                rank=rank_of.get(item.item_id),
                is_runner_up=runner_up_of.get(item.choice_key) == item.item_id,
                exclusion_reason=reason,
            ))

    return AllocationResult(
        strategy=strategy,
        budget_idr=budget_idr,
        spent_idr=sum(i.cost_idr for i in chosen_items),
        objective_value_idr=sum(i.value for i in chosen_items),
        decisions=tuple(decisions),
    )
