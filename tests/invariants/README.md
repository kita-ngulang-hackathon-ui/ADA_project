# tests/invariants

Non-skippable tests for the system's hard guarantees. `make test-invariants`
runs them. A failure here blocks the demo build.

| Test | Guarantee |
|---|---|
| `test_worker_role_cannot_approve.py` | As DB role `app_worker`, updating a recommendation to `APPROVED` or `DELIVERED` fails (requirement 8). |
| `test_rls_blocks_cross_tenant_read.py` | With `app.tenant_id` set to tenant A, a query without `WHERE tenant_id` returns zero rows of tenant B (§4 no cross-client sharing). |
| `test_external_signals_have_no_user_column.py` | `external_signals` table and `ExternalSignal` model have no user/counterparty column (§4 external signal boundary). |
| `test_tabpfn_context_single_tenant.py` | Context builders in `churn_risk` and `ranker` reject rows from more than one tenant. |
| `test_narration_rejects_unknown_numbers.py` | `explain.validator` rejects a narration containing a number absent from the fact sheet (requirement 9). |
| `test_policy_guard_responsible_lending.py` | A repayment-stressed user never receives a borrowing incentive, regardless of ranker output (requirement 7, §4). |

DB tests need Postgres from `docker compose up postgres`.
