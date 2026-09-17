"""0008 feature snapshots and incentive fields

Revision ID: 0008_feature_snapshots
Revises: 0007_worker_select_recs
Create Date: 2026-09-17

Two gaps found while implementing worker.postgres_store against the real
schema (PipelineStore Protocol in services/worker/src/worker/store.py):

1. `incentives` was missing `changes_credit_terms` and
   `applicable_profile_types` -- both read by worker/pipeline.py's `_policy`
   and `_candidate` stages via `core_contracts.Incentive`, but the table only
   ever had `encourages_borrowing`. `is_group` is NOT a new column: it is
   `subject_type = 'GROUP'`, already present since 0001.

2. `feature_snapshots` did not exist at all. `core_contracts.FeatureSnapshot`
   (requirement 11, the feedback loop) is keyed by (tenant_id, run_id,
   user_pseudonym) and captures the features/scores active at recommendation
   time so later labeled examples never leak outcome data into their own
   features -- no existing table matches that shape.
"""
from alembic import op

revision = "0008_feature_snapshots"
down_revision = "0007_worker_select_recs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE incentives
            ADD COLUMN changes_credit_terms BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN applicable_profile_types JSONB NOT NULL DEFAULT '[]';

        CREATE TABLE feature_snapshots (
        	id UUID NOT NULL,
        	tenant_id UUID NOT NULL,
        	run_id UUID NOT NULL,
        	user_pseudonym VARCHAR NOT NULL,
        	features JSONB NOT NULL,
        	churn_risk FLOAT,
        	impact_score FLOAT,
        	pattern_type VARCHAR,
        	incentive_code VARCHAR,
        	cost_idr BIGINT NOT NULL DEFAULT 0,
        	business_value_idr BIGINT NOT NULL DEFAULT 0,
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        	PRIMARY KEY (id),
        	CONSTRAINT uq_feature_snapshots_run_user UNIQUE (tenant_id, run_id, user_pseudonym)
        );

        ALTER TABLE feature_snapshots ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON feature_snapshots
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

        GRANT SELECT ON feature_snapshots TO app_readonly;
        GRANT SELECT, INSERT ON feature_snapshots TO app_worker;
        GRANT SELECT ON feature_snapshots TO app_console;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation ON feature_snapshots;
        DROP TABLE IF EXISTS feature_snapshots CASCADE;
        ALTER TABLE incentives
            DROP COLUMN changes_credit_terms,
            DROP COLUMN applicable_profile_types;
        """
    )
