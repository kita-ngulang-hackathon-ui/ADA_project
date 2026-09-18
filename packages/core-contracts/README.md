# core-contracts (L0)

Shared domain vocabulary for the whole system. Every other package depends on
this one. This package depends on nothing in the workspace.

## Layer rules
- Layer L0. Imports allowed: the standard library and `pydantic` only.
- No I/O, no database, no HTTP, no `os.environ`.
- Keep it small. Add a type here only when two or more packages need it.

## Files

| File | What to implement |
|---|---|
| `events.py` | `CanonicalEvent` (Pydantic v2, frozen). Fields: `tenant_id`, `client_event_id`, `event_type` (canonical enum), `occurred_at` (tz-aware), `user_pseudonym`, `counterparty_pseudonym` (optional), `amount_idr` (int, never float), `attributes` (dict with only whitelisted keys). Also `CanonicalEventType` enum: `PAYMENT`, `P2P_TRANSFER`, `TOPUP`, `WITHDRAWAL`, `SPLIT_BILL_CREATED`, `SPLIT_BILL_SETTLED`, `RECURRING_PAYMENT`, `LOAN_DISBURSED`, `LOAN_REPAYMENT`, `LOAN_REPAYMENT_LATE`, `SESSION_OPEN`, `SUPPORT_CONTACT`. |
| `external.py` | `ExternalSignal` with `scope_type` (`CLIENT`, `REGION`, `COHORT`), `scope_key`, `signal_type` (`NEWS_SENTIMENT`, `SOCIAL_SENTIMENT`, `SECTOR_TREND`), `value` in [-1, 1], `observed_at`, `source`. It must have **no user field** (requirement 2, external signal boundary). |
| `graph.py` | `EdgeWeight`, `CircleSnapshot` (`circle_size`, `neighbor_activity_ratio_now`, `neighbor_activity_ratio_30d_ago`, `delta_stability`), `PatternType` enum (`CIRCLE_SPECIFIC`, `MARKET_DRIVEN`, `STABLE`). |
| `scores.py` | `RiskScore` (`churn_risk` in [0, 1], `model`, `external_signal_contribution`, `context_row_count`), `ImpactScore` (`p_incentivized`, `p_not_incentivized`, `impact_score`), `ImpactSegment` enum (`PERSUADABLE`, `SURE_THING`, `LOST_CAUSE`, `SLEEPING_DOG`), `ReasonFactor` (`code`, `direction`, `weight`, `evidence`). |
| `incentives.py` | `Incentive` (`code`, `cost_idr`, `encourages_borrowing: bool`, `is_group: bool`). The catalog content is an open decision; keep it data, not code. |
| `recommendation.py` | `RecommendationStatus` enum: `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `DELIVERED`. `ALLOWED_TRANSITIONS` map. `Candidate`, `Recommendation`, and `FactSheet` types. A pure `assert_transition(src, dst, reviewer_id)` that rejects `APPROVED`/`DELIVERED` without a human reviewer ID. This is the code-level mirror of the DB guard (requirement 8). |
| `errors.py` | Domain exceptions: `IllegalTransition`, `MappingError`, `ContextTooSmall`, `PolicyViolation`. |

## Invariants
- Money is always `int` IDR.
- Timestamps are timezone-aware. Store UTC. Display in Asia/Jakarta.
- The state machine is frozen. Change it only through a DECISIONS entry.

## Tests to write
- The transition table rejects every edge not listed.
- `assert_transition(..., "APPROVED", reviewer_id=None)` raises.
- `ExternalSignal` rejects unknown fields (no user field can be added).

## Related
Requirements 1–12 (`REQUIREMENTS (1).md` §3), requirement 8 state machine.
