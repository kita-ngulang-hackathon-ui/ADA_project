# ranker (L1)

Decision Engine stage 2 (requirement 7). Scores candidates that survived the
policy guard with a second TabPFN pass (regressor) over `impact_score`,
`churn_risk`, `pattern_type`, `cost_idr`, and business value. Target: realized
incremental retained value from past labeled examples.

## Layer rules
- Imports: `core_contracts`, `numpy`, `tabpfn`. No I/O.

## Files

| File | What to implement |
|---|---|
| `context.py` | Build ranker context rows from `labeled_examples` (single tenant). Features: `impact_score`, `churn_risk`, `pattern_type`, `cost_idr`, `business_value_idr`. Target: realized incremental value. |
| `ranker.py` | `rank(context, candidates) -> list[RankedCandidate]` with `priority`. When context rows < `RANKER_MIN_CONTEXT_ROWS`, use `FALLBACK` = `impact_score * business_value_idr` and set `ranking_strategy="FALLBACK"`. Otherwise `ranking_strategy="TABPFN"`. Ties broken by candidate id for determinism. |

## Tests to write
- Fallback is used and labeled below min context.
- Output order is deterministic for equal priorities.

## Related
Requirements 7, 11. Config: `RANKER_MIN_CONTEXT_ROWS`.
