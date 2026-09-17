# churn-risk (L1)

Scores individual churn risk with a TabPFN classifier (requirement 3). There is
no training loop: labeled rows are passed in as context on every call, which
is what lets the feedback loop improve scores without retraining (requirement 11).

## Layer rules
- Imports: `core_contracts`, `numpy`, `scikit-learn`, `tabpfn`. No DB, no env.
- Model weights path is given by the caller (the worker). CPU only.
- Context rows must all belong to **one tenant** (no cross-client sharing, §4).

## Files to implement

| File | What to implement |
|---|---|
| `features.py` | `build_features(events, circle_snapshot, external_signal, now)`. Recency, frequency, monetary value, tenure, session gap, `delta_stability`, `circle_size`, `pattern_type` (one-hot), `external_signal_value` (0 when none). Fixed column order in `FEATURE_COLUMNS`. |
| `context.py` | `select_context(labeled_rows, max_rows, seed)`. Stratified sample capped at `TABPFN_MAX_CONTEXT_ROWS`. Assert single tenant. Raise `ContextTooSmall` below the minimum. |
| `classifier.py` | `score(context_X, context_y, query_X) -> list[RiskScore]` using `TabPFNClassifier(device="cpu")`. Deterministic seed. Fallback to `HistGradientBoostingClassifier` (or a logistic rule) when TabPFN is unavailable; record the model name used. |
| `snapshot_features.py` | `build_snapshot_features(...)`: the 12 features of the trained scorer contract (`artifacts/context_schema.json`), in `SNAPSHOT_FEATURE_COLUMNS` order. Pure; vocabulary and IDR scale come from the caller's mapping (`fixtures/churn_scorer_mapping.json`). |
| `attribution.py` | Estimate `external_signal_contribution` = score with signal − score with signal neutralized (set to 0). Output which external signal, if any, contributed. |

## Trained scorer
The worker loads the trained TabPFN bundle in `artifacts/` once at startup
(`services/worker/src/worker/churn_scorer.py`, see `TABPFN_CHURN_SCORER_INTEGRATION.md`).
The RISK stage scores with it using `build_snapshot_features`. The in-context
`classifier.py` path only runs when `CHURN_SCORER_ENABLED=false`.

## Tests to write
- Feature vector column order is stable.
- Context from two tenants raises.
- Fallback path is used and labeled when TabPFN import fails.
- Attribution is 0 when no external signal attached.

## Related
Requirements 3, 11. Config: `TABPFN_DEVICE`, `TABPFN_MODEL_CACHE_DIR`, `TABPFN_SEED`, `TABPFN_MAX_CONTEXT_ROWS`.
