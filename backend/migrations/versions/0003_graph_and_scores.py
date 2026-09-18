"""0003 graph and scores

Revision ID: 0003_graph_and_scores
Revises: 0002_events
Create Date: 2026-09-17

Tables: users, counterparty_nodes, relationship_edges, transaction_circles, circle_members, risk_scores, impact_scores
"""
from alembic import op

revision = "0003_graph_and_scores"
down_revision = "0002_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
        	tenant_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	last_event_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	lifecycle_state VARCHAR NOT NULL, 
        	region_code VARCHAR, 
        	cohort_key VARCHAR, 
        	PRIMARY KEY (tenant_id, user_pseudonym), 
        	CONSTRAINT ck_users_lifecycle_state CHECK (lifecycle_state IN ('NEW','ACTIVE','COOLING','DORMANT','CHURNED'))
        );

        CREATE TABLE counterparty_nodes (
        	tenant_id UUID NOT NULL, 
        	counterparty_pseudonym VARCHAR NOT NULL, 
        	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	event_count_30d INTEGER NOT NULL, 
        	is_active BOOLEAN NOT NULL, 
        	is_own_user BOOLEAN NOT NULL, 
        	PRIMARY KEY (tenant_id, counterparty_pseudonym)
        );

        CREATE TABLE relationship_edges (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	counterparty_pseudonym VARCHAR NOT NULL, 
        	edge_type VARCHAR NOT NULL, 
        	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	txn_count_90d INTEGER NOT NULL, 
        	cadence_days FLOAT, 
        	decay_weight FLOAT NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_relationship_edges UNIQUE (tenant_id, user_pseudonym, counterparty_pseudonym, edge_type)
        );

        CREATE TABLE transaction_circles (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	member_count INTEGER NOT NULL, 
        	stability_score FLOAT, 
        	computed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id)
        );

        CREATE TABLE circle_members (
        	circle_id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	PRIMARY KEY (circle_id, tenant_id, user_pseudonym)
        );

        CREATE TABLE risk_scores (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	computed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	pipeline_run_id UUID, 
        	churn_risk FLOAT NOT NULL, 
        	delta_stability FLOAT NOT NULL, 
        	pattern_type VARCHAR NOT NULL, 
        	external_signal_id UUID, 
        	external_signal_contribution FLOAT, 
        	context_row_count INTEGER NOT NULL, 
        	features JSONB NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_risk_scores_pattern_type CHECK (pattern_type IN ('CIRCLE_SPECIFIC','MARKET_DRIVEN','STABLE'))
        );

        CREATE TABLE impact_scores (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	incentive_code VARCHAR NOT NULL, 
        	computed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	p_incentivized FLOAT NOT NULL, 
        	p_not_incentivized FLOAT NOT NULL, 
        	impact_score FLOAT NOT NULL, 
        	segment VARCHAR NOT NULL, 
        	features JSONB NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_impact_scores_segment CHECK (segment IN ('PERSUADABLE','SURE_THING','LOST_CAUSE','SLEEPING_DOG'))
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS impact_scores CASCADE")
    op.execute("DROP TABLE IF EXISTS risk_scores CASCADE")
    op.execute("DROP TABLE IF EXISTS circle_members CASCADE")
    op.execute("DROP TABLE IF EXISTS transaction_circles CASCADE")
    op.execute("DROP TABLE IF EXISTS relationship_edges CASCADE")
    op.execute("DROP TABLE IF EXISTS counterparty_nodes CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
