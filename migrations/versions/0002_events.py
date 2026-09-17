"""0002 events

Revision ID: 0002_events
Revises: 0001_tenants_and_roles
Create Date: 2026-09-17

Tables: raw_events, canonical_events, external_signals
"""
from alembic import op

revision = "0002_events"
down_revision = "0001_tenants_and_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE raw_events (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	client_event_id VARCHAR NOT NULL, 
        	received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	payload JSONB NOT NULL, 
        	processed_at TIMESTAMP WITH TIME ZONE, 
        	process_error TEXT, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_raw_events_idempotency UNIQUE (tenant_id, client_event_id)
        );

        CREATE TABLE canonical_events (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	raw_event_id UUID NOT NULL, 
        	user_pseudonym VARCHAR NOT NULL, 
        	canonical_type VARCHAR NOT NULL, 
        	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	amount_idr BIGINT NOT NULL, 
        	counterparty_pseudonym VARCHAR, 
        	attributes JSONB NOT NULL, 
        	PRIMARY KEY (id)
        );

        CREATE TABLE external_signals (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	scope_type VARCHAR NOT NULL, 
        	scope_key VARCHAR NOT NULL, 
        	signal_type VARCHAR NOT NULL, 
        	value FLOAT NOT NULL, 
        	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	source VARCHAR NOT NULL, 
        	ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_external_signals_scope CHECK (scope_type IN ('CLIENT','REGION','COHORT'))
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS external_signals CASCADE")
    op.execute("DROP TABLE IF EXISTS canonical_events CASCADE")
    op.execute("DROP TABLE IF EXISTS raw_events CASCADE")
