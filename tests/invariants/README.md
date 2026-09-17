# tests/invariants

Non-skippable tests for the system's hard guarantees. `make test-invariants`
runs them. A failure here blocks the demo build.

| Test | Guarantee |
|---|---|
| `test_worker_role_cannot_approve.py` | As DB role `app_worker`, updating a recommendation to `APPROVED` always fails -- neither by touching `reviewed_by`/`reviewed_at` directly (column grant denies it) nor by touching `status` alone (the CHECK constraint denies it, since `reviewed_by`/`reviewed_at` stay NULL). `app_worker` legitimately CAN reach `EXPIRED` and `DELIVERED` (the scheduled expiry and the client's delivery-ack both route through it by design) -- also asserted, so the test can't pass by accident from an over-broad `REVOKE ALL`. |
| `test_rls_blocks_cross_tenant_read.py` | With `app.tenant_id` set to tenant A, a query without `WHERE tenant_id` returns zero rows of tenant B (§4 no cross-client sharing) -- checked against `users` and against `external_signals` (which has no user column at all but must still be tenant-scoped). Also: no `app.tenant_id` set at all returns zero rows, not every tenant's rows. |
| `test_external_signals_have_no_user_column.py` | `external_signals` table and `ExternalSignal` model have no user/counterparty column (§4 external signal boundary). |
| `test_tabpfn_context_single_tenant.py` | Context builders in `churn_risk` and `ranker` reject rows from more than one tenant. |
| `test_narration_rejects_unknown_numbers.py` | `explain.validator` rejects a narration containing a number absent from the fact sheet (requirement 9). |
| `test_policy_guard_responsible_lending.py` | A repayment-stressed user never receives a borrowing incentive, regardless of ranker output (requirement 7, §4). |

## Running the two DB-backed tests

`test_worker_role_cannot_approve.py` and `test_rls_blocks_cross_tenant_read.py`
need a live, migrated Postgres. `tests/invariants/conftest.py` skips them
(with a clear reason, never a silent pass) if it can't find working
credentials. To make them run:

1. `cp .env.example .env` and fill in secrets (or generate with
   `openssl rand -hex 32`). `POSTGRES_PORT=5433` avoids colliding with a
   native Postgres install already using `5432` -- change it back to `5432`
   if you don't have one.
2. `docker compose up -d postgres`, wait for it to report healthy
   (`docker compose ps`).
3. Migrations must run as the Postgres **superuser**, not `app_console`
   (migration `0001` creates the `app_worker`/`app_console`/`app_readonly`
   roles, so they can't exist yet on a fresh database):
   ```
   DATABASE_URL="postgresql+psycopg://postgres:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/retention" \
     uv run alembic -c migrations/alembic.ini upgrade head
   ```
4. `uv run pytest tests/invariants` (or `make test-invariants`) -- `conftest.py`
   reads `POSTGRES_PASSWORD`/`APP_*_DB_PASSWORD` from the environment first,
   falling back to parsing the repo-root `.env` directly, so it works
   whether or not you've `source`d it into the shell.

Each test creates its own tenant(s)/rows with random UUIDs and deletes them
in a fixture teardown -- safe to run repeatedly, and safe to run alongside
other data in the same database.
