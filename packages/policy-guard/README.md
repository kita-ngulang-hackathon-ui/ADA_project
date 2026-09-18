# policy-guard (L1)

Decision Engine stage 1: hard filters that run **before** any model ranking
(requirement 7). These are guarantees, not predictions, so they are plain rules.

## Layer rules
- Imports: `core_contracts` only. No I/O. No models.
- Every candidate gets an explicit `ALLOW` or `DENY` with a rule code. Denials
  are stored (`policy_decisions` table) so the audit trail shows them.

## Files

| File | What to implement |
|---|---|
| `rules.py` | One pure function per rule, each returning `RuleResult(rule_code, allowed, reason)`. `RESPONSIBLE_LENDING`: deny when `incentive.encourages_borrowing` and the user has `LOAN_REPAYMENT_LATE` count >= `RESPONSIBLE_LENDING_MIN_LATE_EVENTS` in `RESPONSIBLE_LENDING_LOOKBACK_DAYS`. `FREQUENCY_CAP`: deny when contacts in `FREQUENCY_CAP_WINDOW_DAYS` >= `FREQUENCY_CAP_MAX_CONTACTS`. `NO_CREDIT_DECISION`: deny any incentive that changes credit limit or pricing. `SEGMENT_EXCLUDED`: deny `SURE_THING`, `LOST_CAUSE`, `SLEEPING_DOG`. |
| `guard.py` | `evaluate(candidate, user_facts, config) -> PolicyDecision`. Runs all rules, collects every denial (not only the first). Frequency cap missing from config means **fail closed** (deny). |

## Open decision
Exact frequency-cap threshold (§6). `.env.example` leaves it `__TBD__`.

## Tests to write
- Repayment-stressed user never gets a borrowing incentive.
- Missing cap config denies everything.
- All denial reasons are reported.

## Related
Requirement 7 (stage 1), §4 responsible lending, frequency capping, no credit decisions.
