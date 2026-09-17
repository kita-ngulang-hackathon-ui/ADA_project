# services/worker (L3)

Runs the whole pipeline and all I/O that L1 packages are not allowed to do:
reading/writing the DB, fetching the external feed, calling the LLM.

## Pipeline (one run per tenant)

1. `ingest` — claim raw events, normalize via `ingest_mapping`, write canonical events.
2. `external` — load feed via `feed_adapter`, normalize via `external_signals`.
3. `graph` — `graph_signal`: edges, `delta_stability`, pattern, circles (skippable per tenant profile).
4. `risk` — `churn_risk` with labeled examples as context.
5. `impact` — `impact` two-model estimate and segment.
6. `policy` — `policy_guard` hard filters; store every decision.
7. `rank` — `ranker` priority (TabPFN or FALLBACK).
8. `allocate` — `allocator` knapsack, top pick + runner-up, measurement arm assignment.
9. `explain` — `explain` fact sheet, `llm_narrator` call, validator, template fallback.
10. `persist` — recommendations saved as `PENDING_APPROVAL`. **The worker stops here.** It has no code path and no DB rights to approve or deliver (requirement 8).

## Layer rules
- May import every L1 package and `persistence`. Connects as `app_worker` DB role.
- Never import FastAPI or anything from `services/api`.

## Files to implement

| File | What to implement |
|---|---|
| `src/worker/main.py` | Poll loop: every `WORKER_POLL_INTERVAL_SECONDS` claim raw events (`FOR UPDATE SKIP LOCKED`) and queued pipeline runs. Graceful shutdown. Retries up to `WORKER_MAX_RETRIES`, then mark failed. Reclaim stale claims after `WORKER_STALE_CLAIM_SECONDS`. |
| `src/worker/settings.py` | Settings for `WORKER_*`, `PIPELINE_*`, `TABPFN_*`, `IMPACT_*`, `RANKER_*`, `ALLOCATOR_*`, `POLICY_*`, `EXPLAIN_*`, `MEASUREMENT_*`, `FEEDBACK_*`, `EXTERNAL_*`. |
| `src/worker/pipeline.py` | `run_pipeline(tenant_id, run_id)`. Calls the stages above in order, records per-stage status on the run row, passes config values explicitly into L1 functions. |
| `src/worker/feed_adapter.py` | `load_feed()`: `EXTERNAL_SIGNAL_SOURCE=canned` reads `fixtures/external/*.json`; `live` fetches from `EXTERNAL_SIGNAL_LIVE_BASE_URL` with a short timeout and falls back to the last snapshot, then to canned. Never blocks the pipeline. |
| `src/worker/llm_narrator.py` | Implements `explain.narrator_protocol.Narrator` with `httpx`. Provider/model from `EXPLAIN_LLM_*` (open decision). Timeout `EXPLAIN_LLM_TIMEOUT_S`, temperature 0. Cache by `fact_sheet_hash`. Any failure or validator rejection falls back to `explain.template`. `EXPLAIN_LLM_ENABLED=false` means template only (offline demo). |
| `src/worker/store.py` | `PipelineStore` Protocol: everything the pipeline reads and writes. No approve/reject/deliver method exists. |
| `src/worker/memory_store.py` | `InMemoryStore` implementing the Protocol, tenant-isolated. Used by tests and the offline CLI until the Postgres store lands. |
| `src/worker/outcomes.py` | Turn outcome events into labeled examples via `feedback`, persist them, update the counter. |

## Tests to write
- Pipeline on the seeded fixture produces `PENDING_APPROVAL` rows and no `APPROVED` rows.
- LLM disabled: every narration has `reason_source="TEMPLATE"`.
- Live feed timeout falls back to canned feed.

## Related
Requirements 1–11; §4 resilience during judging.
