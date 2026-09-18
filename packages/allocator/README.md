# allocator (L1)

Decision Engine stage 3 (requirement 7). Allocates a fixed budget across ranked
candidates to maximize total priority (incremental retained value). Output is a
top pick plus a visible runner-up per user, and a clear exclusion reason for
everyone not selected (demo beat 3).

## Layer rules
- Imports: `core_contracts` only. Pure Python, no solver dependency (ADR-011).

## Files

| File | What to implement |
|---|---|
| `knapsack.py` | Exact 0-1 DP knapsack. Costs scaled by `ALLOCATOR_COST_SCALE_IDR` to keep the table small. At most one incentive per user (multiple-choice constraint). Guard table size with `ALLOCATOR_MAX_DP_CELLS`. |
| `greedy.py` | Fallback when DP is too large: sort by priority / cost, take while budget allows. Mark `strategy="GREEDY_DENSITY"`. |
| `groups.py` | Group candidates (requirement 5) are indivisible bundles: all members or none, one combined cost and value. |
| `selection.py` | `allocate(candidates, budget_idr, config) -> AllocationResult`. Selected list, top pick + runner-up per user, excluded list with `exclusion_reason` (`BUDGET_EXHAUSTED`, `RUNNER_UP`, `POLICY_DENIED`, `SEGMENT_*`). Records `objective_value_idr` and `strategy`. |

## Tests to write
- DP result is optimal on small hand-made cases.
- Group bundle is never partially selected.
- A persuadable user beats a higher-risk lost cause (demo beat 3).
- Greedy fallback triggers above the cell limit.

## Related
Requirements 5, 7. Config: `ALLOCATOR_STRATEGY`, `ALLOCATOR_COST_SCALE_IDR`, `ALLOCATOR_MAX_DP_CELLS`, `DEFAULT_BUDGET_IDR`.
