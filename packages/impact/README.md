# impact (L1) — Intervention Impact Engine

Estimates what an incentive is worth to a specific user (requirement 6).
Two models: one fitted on historically incentivized users, one on
non-incentivized users. Run the candidate through both.
`impact_score = P(stay | incentivized) − P(stay | not incentivized)`.

## Layer rules
- Imports: `core_contracts`, `numpy`, `scikit-learn`, `tabpfn`. No I/O.
- Both context sets from one tenant only.

## Files to implement

| File | What to implement |
|---|---|
| `two_model.py` | `estimate(treated_context, control_context, candidate_features) -> ImpactScore`. Uses TabPFN (in-context) for each arm; sklearn fallback. Raise `ContextTooSmall` when an arm has fewer than `IMPACT_MIN_TRAIN_ROWS`. |
| `segments.py` | `segment(impact) -> ImpactSegment`. `PERSUADABLE`: `impact_score > IMPACT_THRESHOLD`. `SURE_THING`: both probabilities high, small gap. `LOST_CAUSE`: both low, small gap. `SLEEPING_DOG`: `impact_score < -IMPACT_THRESHOLD`. Thresholds passed in. |

## Tests to write
- Planted persuadable users (synthetic P3) get `PERSUADABLE`.
- Planted sleeping dogs (P5) get negative impact and `SLEEPING_DOG`.
- Too-small arm raises `ContextTooSmall`.

## Related
Requirement 6, demo beat 2. Config: `IMPACT_SEED`, `IMPACT_MIN_TRAIN_ROWS`, `IMPACT_SURE_THING_P_NOT_INCENTIVIZED`, `IMPACT_THRESHOLD`.
