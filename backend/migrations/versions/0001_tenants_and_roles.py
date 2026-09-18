"""0001 tenants and roles

Revision ID: 0001_tenants_and_roles
Revises:
Create Date: 2026-09-17

Tables: tenants, api_keys, event_type_mappings, incentives
Roles: app_worker, app_console, app_readonly (ARCHITECTURE.md §9, mechanism 4;
persistence/roles.sql documents the intent this migration applies).
"""
import os

from alembic import op

revision = "0001_tenants_and_roles"
down_revision = None
branch_labels = None
depends_on = None

# Role passwords come from the environment at migrate time, never hardcoded
# and never defaulted -- .env.example requires them (APP_*_DB_PASSWORD).
_ROLES = ("app_worker", "app_console", "app_readonly")


def _role_password_env(role: str) -> str:
    return f"APP_{role.removeprefix('app_').upper()}_DB_PASSWORD"


def upgrade() -> None:
    for role in _ROLES:
        password = os.environ.get(_role_password_env(role))
        if not password:
            raise RuntimeError(
                f"{_role_password_env(role)} is not set; refusing to create {role} "
                "with a default or empty password"
            )
        if "'" in password:
            raise RuntimeError(f"{_role_password_env(role)} must not contain a single quote")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    CREATE ROLE {role} LOGIN PASSWORD '{password}';
                END IF;
            END
            $$;
            """
        )

    op.execute(
        """
        CREATE TABLE tenants (
        	id UUID NOT NULL, 
        	slug VARCHAR NOT NULL, 
        	display_name VARCHAR NOT NULL, 
        	profile_type VARCHAR NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT ck_tenants_profile_type CHECK (profile_type IN ('WALLET','LENDING')), 
        	UNIQUE (slug)
        );

        CREATE TABLE api_keys (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	key_hash VARCHAR NOT NULL, 
        	label VARCHAR NOT NULL, 
        	active BOOLEAN NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	last_used_at TIMESTAMP WITH TIME ZONE, 
        	PRIMARY KEY (id), 
        	UNIQUE (key_hash)
        );

        CREATE TABLE event_type_mappings (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	client_event_type VARCHAR NOT NULL, 
        	canonical_event_type VARCHAR NOT NULL, 
        	amount_field_path VARCHAR NOT NULL, 
        	counterparty_field_path VARCHAR, 
        	occurred_at_field_path VARCHAR NOT NULL, 
        	active BOOLEAN NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_event_type_mappings UNIQUE (tenant_id, client_event_type)
        );

        CREATE TABLE incentives (
        	id UUID NOT NULL, 
        	tenant_id UUID NOT NULL, 
        	code VARCHAR NOT NULL, 
        	display_name VARCHAR NOT NULL, 
        	cost_idr BIGINT NOT NULL, 
        	encourages_borrowing BOOLEAN NOT NULL, 
        	subject_type VARCHAR NOT NULL, 
        	active BOOLEAN NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT uq_incentives_tenant_code UNIQUE (tenant_id, code)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS incentives CASCADE")
    op.execute("DROP TABLE IF EXISTS event_type_mappings CASCADE")
    op.execute("DROP TABLE IF EXISTS api_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE")
    for role in _ROLES:
        op.execute(f"DROP ROLE IF EXISTS {role}")
