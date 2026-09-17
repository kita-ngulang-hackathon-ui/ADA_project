"""0004 decisioning

Revision ID: 0004_decisioning
Revises: 0003_graph_and_scores
Create Date: 2026-09-17

Tables: pipeline_runs, policy_decisions, allocation_runs, allocation_candidates, recommendations, narrations, contact_log
"""
from alembic import op

revision = "0004_decisioning"
down_revision = "0003_graph_and_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE pipeline_runs (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	status VARCHAR NOT NULL, 
        	stages JSONB NOT NULL, 
        	external_source VARCHAR, 
        	ranking_strategy VARCHAR, 
        	context_row_count INTEGER, 
        	reason_source_counts JSONB NOT NULL, 
        	error TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	started_at TIMESTAMP WITH TIME ZONE, 
        	finished_at TIMESTAMP WITH TIME ZONE, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_pipeline_runs_status CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED'))
        );

        CREATE TABLE policy_decisions (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	recommendation_id UUID, 
        	candidate_ref VARCHAR NOT NULL, 
        	rule_code VARCHAR NOT NULL, 
        	outcome VARCHAR NOT NULL, 
        	detail JSONB NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_policy_decisions_outcome CHECK (outcome IN ('ALLOW','DENY'))
        );

        CREATE TABLE allocation_runs (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	pipeline_run_id UUID, 
        	budget_idr BIGINT NOT NULL, 
        	strategy VARCHAR NOT NULL, 
        	ranking_strategy VARCHAR NOT NULL, 
        	context_row_count INTEGER NOT NULL, 
        	objective_value_idr BIGINT NOT NULL, 
        	candidate_count INTEGER NOT NULL, 
        	selected_count INTEGER NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	created_by VARCHAR, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_allocation_runs_strategy CHECK (strategy IN ('EXACT_DP','GREEDY_DENSITY')), 
        	CONSTRAINT ck_allocation_runs_ranking_strategy CHECK (ranking_strategy IN ('TABPFN','FALLBACK'))
        );

        CREATE TABLE allocation_candidates (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	allocation_run_id UUID NOT NULL, 
        	subject_type VARCHAR NOT NULL, 
        	user_pseudonym VARCHAR, 
        	circle_id UUID, 
        	incentive_code VARCHAR NOT NULL, 
        	churn_risk FLOAT, 
        	impact_score FLOAT, 
        	segment VARCHAR, 
        	pattern_type VARCHAR, 
        	priority_idr BIGINT, 
        	cost_idr BIGINT NOT NULL, 
        	user_rank INTEGER, 
        	selected BOOLEAN NOT NULL, 
        	exclusion_reason VARCHAR, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_allocation_candidates_subject_type CHECK (subject_type IN ('USER','GROUP'))
        );

        CREATE TABLE recommendations (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	allocation_run_id UUID NOT NULL, 
        	allocation_candidate_id UUID, 
        	subject_type VARCHAR NOT NULL, 
        	user_pseudonym VARCHAR, 
        	circle_id UUID, 
        	incentive_code VARCHAR NOT NULL, 
        	cost_idr BIGINT NOT NULL, 
        	priority_idr BIGINT NOT NULL, 
        	user_rank INTEGER NOT NULL, 
        	is_runner_up BOOLEAN NOT NULL, 
        	status VARCHAR NOT NULL, 
        	reason_text TEXT, 
        	reason_factors JSONB NOT NULL, 
        	reason_source VARCHAR, 
        	fact_sheet_hash VARCHAR, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	submitted_at TIMESTAMP WITH TIME ZONE, 
        	reviewed_by VARCHAR, 
        	reviewed_at TIMESTAMP WITH TIME ZONE, 
        	review_note TEXT, 
        	delivered_at TIMESTAMP WITH TIME ZONE, 
        	delivery_ref VARCHAR, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_recommendations_subject_type CHECK (subject_type IN ('USER','GROUP')), 
        	CONSTRAINT ck_recommendations_subject_exclusive CHECK ((subject_type = 'USER' AND user_pseudonym IS NOT NULL AND circle_id IS NULL) OR (subject_type = 'GROUP' AND circle_id IS NOT NULL AND user_pseudonym IS NULL)), 
        	CONSTRAINT ck_recommendations_status CHECK (status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','EXPIRED','DELIVERED')), 
        	CONSTRAINT ck_recommendations_approved_needs_reviewer CHECK (status <> 'APPROVED' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)), 
        	CONSTRAINT ck_recommendations_rejected_needs_reviewer CHECK (status <> 'REJECTED' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)), 
        	CONSTRAINT ck_recommendations_delivered_needs_review_and_delivery CHECK (status <> 'DELIVERED' OR (reviewed_by IS NOT NULL AND delivered_at IS NOT NULL))
        );

        CREATE TABLE narrations (
        	fact_sheet_hash VARCHAR NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	text TEXT NOT NULL, 
        	model VARCHAR NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (fact_sheet_hash, tenant_id)
        );

        CREATE TABLE contact_log (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	recommendation_id UUID, 
        	contacted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS contact_log CASCADE")
    op.execute("DROP TABLE IF EXISTS narrations CASCADE")
    op.execute("DROP TABLE IF EXISTS recommendations CASCADE")
    op.execute("DROP TABLE IF EXISTS allocation_candidates CASCADE")
    op.execute("DROP TABLE IF EXISTS allocation_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS policy_decisions CASCADE")
    op.execute("DROP TABLE IF EXISTS pipeline_runs CASCADE")
