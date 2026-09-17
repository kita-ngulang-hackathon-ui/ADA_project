# persistence (L2)

All database access. SQLAlchemy 2.0 models, tenant-scoped sessions with
Row-Level Security, and repositories. Only `services/api` and
`services/worker` import this package. Schema migrations live in the root
`migrations/` folder (Alembic).

## Layer rules
- Imports: `core_contracts`, `sqlalchemy`, `psycopg`, `alembic`. Never an L1 package.
- Every domain table has `tenant_id UUID NOT NULL` and an RLS policy.
- Repositories take a session that already has the tenant set. They never accept a raw tenant filter from the caller as the only guard.

## Files to implement

| File | What to implement |
|---|---|
| `models.py` | Tables from ARCHITECTURE §8: `tenants`, `event_type_mappings`, `raw_events` (unique `tenant_id, client_event_id`), `canonical_events`, `external_signals` (**no user column**), `users`, `counterparty_nodes`, `relationship_edges`, `transaction_circles`, `circle_members`, `risk_scores`, `impact_scores`, `policy_decisions`, `allocation_runs`, `allocation_candidates`, `recommendations`, `narrations`, `experiments`, `experiment_assignments`, `outcome_events`, `labeled_examples`, `audit_log`. Money as `BIGINT` IDR. |
| `session.py` | Engine factory from `DATABASE_URL`. `tenant_session(tenant_id)` context manager that runs `SET LOCAL app.tenant_id = :tid` inside the transaction. |
| `repositories/events.py` | Insert raw events idempotently (`ON CONFLICT DO NOTHING`), claim unprocessed rows with `FOR UPDATE SKIP LOCKED`, write canonical events. |
| `repositories/scores.py` | Write/read risk, impact, circle snapshots; read labeled examples for context. |
| `repositories/recommendations.py` | Create `DRAFT`/`PENDING_APPROVAL` rows. Approve/reject/deliver **only** through the console role; never from worker code. |
| `repositories/allocations.py` | Allocation runs and candidates with exclusion reasons. |
| `repositories/measurement.py` | Experiments, assignments, outcomes, lift inputs. |
| `repositories/audit.py` | Append-only audit log writes. |
| `roles.sql` | Reference SQL (applied by a migration): roles `app_worker`, `app_console`, `app_readonly`; column grants so only `app_console` can update `status`, `reviewed_by`, `reviewed_at`; CHECK constraints (`APPROVED` requires `reviewed_by` and `reviewed_at`); `BEFORE UPDATE` trigger that rejects illegal status transitions. |

## Invariants
- Worker role cannot reach `APPROVED` or `DELIVERED` (tested in `tests/invariants`).
- RLS blocks cross-tenant reads even with a missing `WHERE tenant_id`.

## Tests to write
- Idempotent insert of the same `client_event_id`.
- `test_worker_role_cannot_approve`, `test_rls_blocks_cross_tenant_read` (integration, need Postgres).

## Related
Requirement 8, §4 tenant isolation. ADR-003 (PostgreSQL), ADR-005 (RLS), ADR-006 (structural approval guard).
