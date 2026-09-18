"""allocator (L1) — Decision Engine stage 3: 0-1 knapsack budget allocation with runner-ups."""
from allocator.groups import bundle_group
from allocator.items import DPTooLarge, KnapsackItem
from allocator.selection import STRATEGY_DP, STRATEGY_GREEDY, AllocatorConfig, allocate

__all__ = [
    "STRATEGY_DP",
    "STRATEGY_GREEDY",
    "AllocatorConfig",
    "DPTooLarge",
    "KnapsackItem",
    "allocate",
    "bundle_group",
]
