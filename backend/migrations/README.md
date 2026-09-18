# migrations

Alembic migrations for the PostgreSQL 16 schema. Models live in
`packages/persistence/src/persistence/models.py`.

## Plan for migrations
1. `0001_tenants_and_roles` — roles `app_worker`, `app_console`, `app_readonly`; `tenants`; `event_type_mappings`.
2. `0002_events` — `raw_events` (unique `tenant_id, client_event_id`), `canonical_events`, `external_signals` (no user column).
3. `0003_graph_and_scores` — `users`, `counterparty_nodes`, `relationship_edges`, `transaction_circles`, `circle_members`, `risk_scores`, `impact_scores`.
4. `0004_decisioning` — `policy_decisions`, `allocation_runs`, `allocation_candidates`, `recommendations`, `narrations`; CHECK constraints and transition trigger (see `persistence/roles.sql`).
5. `0005_measurement_feedback` — `experiments`, `experiment_assignments`, `outcome_events`, `labeled_examples`, `audit_log`.
6. `0006_rls` — enable RLS and tenant policies on every domain table; column grants.

## Rules
- Migrations must be reversible (`downgrade` implemented).
- Never edit an applied migration; add a new one.
- `make migrate` runs `alembic upgrade head` as the superuser, then role provisioning.
