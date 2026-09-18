# services/api (L3)

FastAPI app with two surfaces (see `API_CONTRACTS.md` in the spec):

- **Ingestion API** `/v1` — called by the client fintech's backend. Bearer API key per tenant.
- **Console API** `/console/v1` — used by the Next.js console (ops reviewer, measurement views). Session cookie.

The API never runs the scoring pipeline inline. Ingestion writes raw rows and
returns `202 Accepted` immediately, so the client's real transaction never waits
on this system (§4, "no client-side SDK").

## Layer rules
- May import: `core_contracts`, `ingest_mapping` (only for mapping validation), `persistence`.
- Must not import scoring packages (`churn_risk`, `impact`, `ranker`, `allocator`, `explain` narrator). Those run in the worker.
- Connects to Postgres as `app_console` (`DATABASE_URL`) for console routes -- the only role that can approve -- and as `app_worker` (`WORKER_DATABASE_URL`) for ingestion routes and delivery acks, the only role granted those inserts and updates.

## Files

| File | What to implement |
|---|---|
| `src/api/main.py` | App factory. Mount routers, error handlers, CORS from `API_CORS_ORIGINS`, request id middleware, request timeout `API_REQUEST_TIMEOUT_SECONDS`. |
| `src/api/settings.py` | `pydantic-settings` class reading `.env` keys (`DATABASE_URL`, `INGEST_API_KEY_*`, `CONSOLE_*`, rate limits). |
| `src/api/auth.py` | `require_tenant_api_key` (Bearer key to tenant, constant-time compare). `require_console_reviewer` (session cookie; reviewer id must be in `CONSOLE_DEMO_REVIEWERS`; never defaulted). |
| `src/api/errors.py` | Error envelope `{"error": {"code", "message", "details", "request_id"}}`. Codes: `VALIDATION_FAILED` 400, `UNAUTHENTICATED` 401, `FORBIDDEN` 403, `NOT_FOUND` 404, `CONFLICT` 409, `PAYLOAD_TOO_LARGE` 413, `RATE_LIMITED` 429, `INTERNAL` 500. |
| `src/api/rate_limit.py` | In-memory token bucket per API key: `INGEST_RATE_LIMIT_PER_MIN`, `CONSOLE_RATE_LIMIT_PER_MIN`. 429 with `Retry-After`. |
| `src/api/routers/health.py` | `GET /v1/health` — no auth, returns `{status, version, time}`. |
| `src/api/routers/ingest.py` | `POST /v1/events` (single) and `POST /v1/events:batch` (max 500, partial acceptance). Validate shape, insert raw row idempotently, return `202` with `raw_event_id` and `duplicate` flag. No enrichment or scoring here. |
| `src/api/routers/console/tenants.py` | `GET /console/v1/tenants`. |
| `src/api/routers/console/mappings.py` | `GET/POST /console/v1/mappings` — per-tenant event type mapping config (onboarding a client = config). |
| `src/api/routers/console/users.py` | `GET /console/v1/users` (filters: `max_delta_stability`, `pattern_type`, `segment`), `GET /console/v1/users/{pseudonym}/risk`. |
| `src/api/routers/console/external_signals.py` | `GET /console/v1/external-signals` — read-only, keyed by scope, never by user. |
| `src/api/routers/console/pipeline.py` | `POST /console/v1/pipeline/run` enqueues a run (`202 QUEUED`); `GET /console/v1/pipeline/runs/{id}` shows stage status. |
| `src/api/routers/console/allocations.py` | `POST /console/v1/allocations` (budget, strategy) and `GET` result with selected, runner-ups, exclusion reasons. |
| `src/api/routers/console/recommendations.py` | `GET` list/detail. `POST /{id}/approve` and `/{id}/reject` require `reviewer_id` from the session (401 without it, 409 on illegal transition). `POST /{id}/delivery-ack` for the simulated client surface. |
| `src/api/routers/console/measurement.py` | `GET /console/v1/measurement/{experiment_id}` — arms, retention, lift vs control and naive, `synthetic_data: true`. |
| `src/api/routers/console/feedback.py` | `POST /console/v1/outcomes` records outcomes; `GET /console/v1/feedback/summary` returns the labeled-examples counter. |
| `src/api/routers/console/audit.py` | `GET /console/v1/audit-log`. |

## Conventions
- JSON, UTF-8, RFC 3339 timestamps with offset, money as integer IDR, ULID ids.
- Cursor pagination (`limit` default 50, max 500).
- Tenant resolved from auth, then `persistence.session.tenant_session`.

## Tests to write
- `202` on valid event, duplicate returns `duplicate: true`.
- Approve without reviewer returns 401; approve twice returns 409.
- Ingestion still returns quickly when the worker is down.

## Related
Requirements 1, 8, 12; §4 no SDK, resilience.
