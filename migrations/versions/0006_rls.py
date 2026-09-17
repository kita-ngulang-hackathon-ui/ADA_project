"""0006 rls

Revision ID: 0006_rls
Revises: 0005_measurement_feedback
Create Date: 2026-09-17

Requirement 8 structural enforcement (ARCHITECTURE.md §9) and tenant
isolation (§11): the BEFORE UPDATE transition trigger, column-level grants
that keep `app_worker` unable to ever write APPROVED, and Row-Level Security
on every domain table.

This mirrors packages/persistence/src/persistence/roles.sql, which documents
the same intent for readers who never run `alembic history`.
"""
from alembic import op

revision = "0006_rls"
down_revision = "0005_measurement_feedback"
branch_labels = None
depends_on = None

# Every table with a tenant_id column except `tenants` (nothing wider to
# scope it by) and `api_keys` (auth must resolve tenant_id FROM the key
# before app.tenant_id exists -- see persistence/repositories/tenants.py).
RLS_TABLES = (
    "allocation_candidates",
    "allocation_runs",
    "audit_log",
    "canonical_events",
    "circle_members",
    "contact_log",
    "counterparty_nodes",
    "event_type_mappings",
    "experiment_assignments",
    "experiments",
    "external_signals",
    "impact_scores",
    "incentives",
    "labeled_examples",
    "narrations",
    "outcome_events",
    "pipeline_runs",
    "policy_decisions",
    "raw_events",
    "recommendations",
    "relationship_edges",
    "risk_scores",
    "transaction_circles",
    "users",
)


def upgrade() -> None:
    # ---- Mechanism 3: BEFORE UPDATE trigger mirroring the frozen state
    # machine in core_contracts.recommendation.ALLOWED_TRANSITIONS. Even a
    # raw UPDATE issued from a psql prompt as a superuser cannot bypass this.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_recommendation_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;

            IF NOT (
                (OLD.status = 'DRAFT' AND NEW.status = 'PENDING_APPROVAL')
                OR (OLD.status = 'PENDING_APPROVAL' AND NEW.status IN ('APPROVED', 'REJECTED', 'EXPIRED'))
                OR (OLD.status = 'APPROVED' AND NEW.status = 'DELIVERED')
            ) THEN
                RAISE EXCEPTION
                    'illegal recommendation status transition: % -> %', OLD.status, NEW.status
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_recommendations_transition ON recommendations;
        CREATE TRIGGER trg_recommendations_transition
            BEFORE UPDATE ON recommendations
            FOR EACH ROW
            EXECUTE FUNCTION check_recommendation_transition();
        """
    )

    # ---- Mechanism 4: separate database roles. app_worker can INSERT a
    # recommendation and later move it to EXPIRED or DELIVERED (the two
    # transitions the worker/ingestion path legitimately drives), but has NO
    # grant on the columns (status->APPROVED path needs reviewed_by,
    # reviewed_at) that would let it reach APPROVED. Only app_console can.
    op.execute(
        """
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

        GRANT SELECT, INSERT ON
            raw_events, canonical_events, external_signals,
            users, counterparty_nodes, relationship_edges,
            transaction_circles, circle_members,
            risk_scores, impact_scores,
            pipeline_runs, policy_decisions,
            allocation_runs, allocation_candidates,
            narrations, contact_log,
            experiment_assignments, outcome_events, labeled_examples
        TO app_worker;
        GRANT UPDATE ON raw_events, pipeline_runs TO app_worker;
        GRANT INSERT ON recommendations TO app_worker;
        GRANT UPDATE (status, delivered_at, delivery_ref) ON recommendations TO app_worker;

        GRANT SELECT ON
            tenants, api_keys, event_type_mappings, incentives,
            raw_events, canonical_events, external_signals,
            users, counterparty_nodes, relationship_edges,
            transaction_circles, circle_members,
            risk_scores, impact_scores,
            pipeline_runs, policy_decisions,
            allocation_runs, allocation_candidates,
            recommendations, narrations, contact_log,
            experiments, experiment_assignments, outcome_events,
            labeled_examples, audit_log
        TO app_console;
        GRANT INSERT ON event_type_mappings, incentives, experiments, pipeline_runs, audit_log TO app_console;
        GRANT UPDATE ON event_type_mappings, incentives TO app_console;
        GRANT UPDATE (status, reviewed_by, reviewed_at, review_note) ON recommendations TO app_console;
        """
    )

    # ---- Row-Level Security: a missing `WHERE tenant_id = ...` in
    # application code returns zero rows of another tenant, not their data.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_worker, app_console, app_readonly")
    op.execute("DROP TRIGGER IF EXISTS trg_recommendations_transition ON recommendations")
    op.execute("DROP FUNCTION IF EXISTS check_recommendation_transition()")
