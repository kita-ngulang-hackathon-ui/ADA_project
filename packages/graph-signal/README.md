# graph-signal (L1)

Builds the transaction-circle graph from canonical events, computes each user's
`delta_stability`, and tags the pattern as `CIRCLE_SPECIFIC`, `MARKET_DRIVEN`,
or `STABLE` (requirement 4). Also finds transaction groups for group
recommendations (requirement 5). Plain Python, no graph database (ADR-004).

## Layer rules
- Imports: `core_contracts` only. No I/O.
- Counterparty data is structural only: active/inactive and frequency.

## Files to implement

| File | What to implement |
|---|---|
| `build.py` | `build_edges(events, now, window_days, half_life_days) -> list[Edge]`. Use only counterparty-bearing canonical events (`P2P_TRANSFER`, `SPLIT_BILL_*`, `RECURRING_PAYMENT`). Weight = sum of `0.5 ** (age_days / half_life)`. Drop edges below `PIPELINE_MIN_EDGE_INTERACTIONS`. |
| `stability.py` | `neighbor_activity_ratio(user, edges, active_set)` = weighted share of neighbors active in the window. `delta_stability = ratio_now - ratio_30d_ago`. |
| `circles.py` | Group detection for group recommendations: connected components (or dense subgraphs) with size >= `PIPELINE_CIRCLE_MIN_SIZE`. Groups are indivisible units for the allocator. |
| `pattern.py` | `tag_pattern(delta_stability, cohort_median_delta, external_signal_value, thresholds)`. If `delta_stability > -PATTERN_DIP_THRESHOLD`: `STABLE`. Else if the cohort median also dips past `PATTERN_COHORT_DIP_THRESHOLD` and the external signal is negative: `MARKET_DRIVEN`. Else `CIRCLE_SPECIFIC`. |

## Open decision
Whether the paylater/lending profile gets this signal at all (§6). Keep the
pipeline able to skip this stage per tenant `profile_type`.

## Tests to write
- Recency decay: older interaction weighs less.
- Planted pattern P1 (circle churn) tags `CIRCLE_SPECIFIC`; P2 (cohort-wide dip) tags `MARKET_DRIVEN`.
- User with no circle gets `circle_size=0` and `STABLE`.

## Related
Requirements 4, 5. Synthetic planted patterns in `tools/synthetic`.
