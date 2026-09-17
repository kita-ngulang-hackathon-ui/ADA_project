"""0012 pipeline run attempts

Revision ID: 0012_pipeline_run_attempts
Revises: 0011_worker_experiments_audit
Create Date: 2026-09-17

The worker poll loop retries a failed run up to WORKER_MAX_RETRIES and
reclaims a stale RUNNING claim after WORKER_STALE_CLAIM_SECONDS. Both need a
durable attempt counter: an in-memory one would reset on worker restart,
which is exactly the case (a crashed worker) the retry budget exists for.

Claim time needs no new column -- `started_at` is already set on each claim,
so a RUNNING row whose started_at is older than the stale window is an
abandoned claim.
"""
from alembic import op

revision = "0012_pipeline_run_attempts"
down_revision = "0011_worker_experiments_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE pipeline_runs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE pipeline_runs DROP COLUMN attempts")
