# measurement (L1)

Measures real incremental impact against a held-out control and a naive
baseline (requirement 10, demo beat 6).

## Arms
- `CONTROL`: randomly withheld from otherwise-qualifying candidates at selection time.
- `NAIVE`: risk-score-only targeting (everyone above `MEASUREMENT_NAIVE_RISK_THRESHOLD`), no impact model, no optimization.
- `ENGINE`: full Decision Engine output.

## Layer rules
- Imports: `core_contracts` only. No I/O. Secret passed in.

## Files to implement

| File | What to implement |
|---|---|
| `assignment.py` | `assign_arm(tenant_id, experiment_id, user_pseudonym, secret, control_pct, naive_pct)`. Bucket = `int(HMAC_SHA256(secret, f"{tenant_id}:{experiment_id}:{user}")) mod 100`. Deterministic and reproducible; a user's arm never changes within an experiment. |
| `lift.py` | `compute_lift(outcomes)`. Retention rate per arm, `lift_vs_control`, `lift_vs_naive`, spend per arm, incremental value per IDR. Report `None` (not a fake number) when an arm is below `MEASUREMENT_MIN_ARM_SIZE`. Always carry `synthetic_data: true`. |

## Tests to write
- Assignment is stable across runs and roughly matches configured percentages.
- Small arm returns `None` lift, not 0.

## Related
Requirement 10. Config: `MEASUREMENT_*`, `MEASUREMENT_HMAC_SECRET`.
