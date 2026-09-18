"""0005 measurement feedback

Revision ID: 0005_measurement_feedback
Revises: 0004_decisioning
Create Date: 2026-09-17

Tables: experiments, experiment_assignments, outcome_events, labeled_examples, audit_log
"""
from alembic import op

revision = "0005_measurement_feedback"
down_revision = "0004_decisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE experiments (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	name VARCHAR NOT NULL, 
        	control_pct INTEGER NOT NULL, 
        	naive_pct INTEGER NOT NULL, 
        	started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	ended_at TIMESTAMP WITH TIME ZONE, 
        	PRIMARY KEY (id)
        );

        CREATE TABLE experiment_assignments (
        	tenant_id UUID NOT NULL, 
        	experiment_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	arm VARCHAR NOT NULL, 
        	assigned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (tenant_id, experiment_id, user_pseudonym), 
        	CONSTRAINT ck_experiment_assignments_arm CHECK (arm IN ('CONTROL','NAIVE','ENGINE'))
        );

        CREATE TABLE outcome_events (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	experiment_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	outcome_type VARCHAR NOT NULL, 
        	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	value_idr BIGINT, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_outcome_events_type CHECK (outcome_type IN ('RESPONDED','RETAINED','CHURNED'))
        );

        CREATE TABLE labeled_examples (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	source_experiment_id UUID, 
        	source_outcome_id UUID, 
        	user_pseudonym VARCHAR NOT NULL, 
        	arm VARCHAR NOT NULL, 
        	treated BOOLEAN NOT NULL, 
        	retained BOOLEAN NOT NULL, 
        	realized_value_idr BIGINT, 
        	feature_snapshot JSONB NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_labeled_examples_dedupe UNIQUE (tenant_id, source_outcome_id)
        );

        CREATE TABLE audit_log (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	actor VARCHAR NOT NULL, 
        	action VARCHAR NOT NULL, 
        	entity_type VARCHAR NOT NULL, 
        	entity_id VARCHAR NOT NULL, 
        	at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	detail JSONB NOT NULL, 
        	PRIMARY KEY (id)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS labeled_examples CASCADE")
    op.execute("DROP TABLE IF EXISTS outcome_events CASCADE")
    op.execute("DROP TABLE IF EXISTS experiment_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS experiments CASCADE")
