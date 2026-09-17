"""0007 worker select on recommendations

Revision ID: 0007_worker_select_recs
Revises: 0006_rls
Create Date: 2026-09-17

Bugfix: migration 0006 granted app_worker INSERT and column-level UPDATE
(status, delivered_at, delivery_ref) on `recommendations`, but never SELECT.
Without SELECT, app_worker cannot even evaluate a `WHERE id = ...` clause --
`persistence.repositories.recommendations.mark_delivered()` (the worker's
own legitimate delivery-ack path) does a SELECT before its UPDATE and would
fail with "permission denied for table recommendations" in production.
Caught by tests/invariants/test_worker_role_cannot_approve.py::
test_worker_can_legitimately_reach_expired.

This does not weaken the requirement-8 guarantee: SELECT reveals no new
write capability, and the column-level UPDATE grants (still only status/
delivered_at/delivery_ref, never reviewed_by/reviewed_at) are unchanged.
"""
from alembic import op

revision = "0007_worker_select_recs"
down_revision = "0006_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON recommendations TO app_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON recommendations FROM app_worker")
