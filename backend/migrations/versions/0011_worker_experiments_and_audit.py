"""0011 worker experiments and audit

Revision ID: 0011_worker_experiments_audit
Revises: 0010_worker_update_users
Create Date: 2026-09-17

Bugfix: migration 0006 omitted `experiments` and `audit_log` from
app_worker's grants entirely. `get_or_create_experiment` (SELECT to find the
tenant's active experiment, INSERT to create one on first run) and
`append_audit` (INSERT, after every recommendation the worker creates) both
need them. Caught by services/worker/tests/test_postgres_store.py.
"""
from alembic import op

revision = "0011_worker_experiments_audit"
down_revision = "0010_worker_update_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT, INSERT ON experiments TO app_worker")
    op.execute("GRANT SELECT, INSERT ON audit_log TO app_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON experiments FROM app_worker")
    op.execute("REVOKE SELECT, INSERT ON audit_log FROM app_worker")
