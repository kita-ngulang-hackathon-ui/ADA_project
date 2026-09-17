# external-signals (L1)

Turns external market/sentiment feed items into `ExternalSignal` and picks the
signal that applies to a user's client/region/cohort (requirement 2).

## Layer rules
- Imports: `core_contracts` only. No HTTP. The worker's feed adapter fetches
  (canned fixture or live source) and passes items in.
- Never resolve a signal to an individual user or counterparty (§4).

## Files to implement

| File | What to implement |
|---|---|
| `feed_models.py` | `FeedItem` raw shape of the canned feed: `source`, `scope_type`, `scope_key`, `signal_type`, `value`, `observed_at`, `headline` (optional, display only). |
| `normalize.py` | `to_signal(item) -> ExternalSignal`. Clamp `value` to [-1, 1]. Reject items with a user-level scope. |
| `attach.py` | `resolve_for_user(signals, tenant_slug, region_code, cohort_key, now, max_age_days)`. Return the most specific fresh signal: COHORT, then REGION, then CLIENT. Ignore signals older than `EXTERNAL_SIGNAL_MAX_AGE_DAYS`. Return `None` when nothing applies. |

## Tests to write
- Specificity order COHORT > REGION > CLIENT.
- Stale signals are ignored.
- `ExternalSignal` has no user column (also covered by `tests/invariants`).

## Related
Requirement 2, §4 external signal boundary, open decision on live vs canned feed.
Fixture: `fixtures/external/canned_feed.json`.
