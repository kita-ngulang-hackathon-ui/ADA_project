# feedback (L1)

Continual improvement (requirement 11). Turns measured outcomes
(treated/control, retained or not) into labeled rows that the next pipeline
run passes to churn-risk and ranker as TabPFN context. No retraining.

## Layer rules
- Imports: `core_contracts` only. No I/O.

## Files to implement

| File | What to implement |
|---|---|
| `labeled_examples.py` | `to_labeled_examples(outcomes, feature_snapshots) -> list[LabeledExample]`. Use the feature snapshot captured at recommendation time (not current features) to avoid leakage. Dedupe by `(tenant_id, outcome_event_id)`. `summarize(new, total)` returns the counter shown in the demo ("new labeled examples added"). Respect `FEEDBACK_MIN_ROWS_PER_CYCLE` and `FEEDBACK_USE_IN_CONTEXT` flag. |

## Tests to write
- Duplicate outcome does not create a second example.
- Example uses the feature snapshot, not later data.

## Related
Requirement 11, demo beat 6. Descoped per §4 flag to "log and show counter" if time runs short.
