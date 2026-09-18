"""Invariant: app_worker cannot set a recommendation to APPROVED (requirement 8).

Two independent barriers are exercised here, matching persistence/roles.sql:
1. app_worker has no UPDATE grant on reviewed_by/reviewed_at -- an attempt to
   set them alongside status='APPROVED' fails on a column permission error
   before either the CHECK constraint or the trigger is even reached.
2. Even touching only the `status` column (which app_worker CAN write, for
   the EXPIRED and client-driven DELIVERED transitions) fails the
   ck_recommendations_approved_needs_reviewer CHECK constraint, because
   reviewed_by/reviewed_at remain NULL -- app_worker has no way to satisfy it.

app_worker legitimately CAN drive APPROVED -> DELIVERED (the client's
delivery-ack, routed through the ingestion API's app_worker role, per
ARCHITECTURE.md's transition table). That is correct and this test does not
attempt to block it -- only APPROVED itself must be unreachable by app_worker.
"""
import uuid

import pytest
import sqlalchemy as sa


def new_uuid() -> str:
    return str(uuid.uuid4())


def set_tenant(conn: sa.Connection, tenant_id: str) -> None:
    """SET LOCAL does not accept bind parameters over the Postgres wire
    protocol, so this validates tenant_id is a UUID and formats it directly
    -- the same approach persistence.session.tenant_session() uses."""
    uuid.UUID(str(tenant_id))
    conn.execute(sa.text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


@pytest.fixture
def pending_recommendation(superuser_engine, pg_dsn_parts):
    """Create one tenant + allocation_run + PENDING_APPROVAL recommendation
    directly as the superuser (which bypasses RLS as the table owner), then
    clean it up afterward."""
    tenant_id = new_uuid()
    run_id = new_uuid()
    rec_id = new_uuid()

    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, display_name, profile_type) "
                "VALUES (:id, :slug, 'Invariant Test Tenant', 'WALLET')"
            ),
            {"id": tenant_id, "slug": f"invariant-test-{tenant_id[:8]}"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO allocation_runs "
                "(id, tenant_id, budget_idr, strategy, ranking_strategy, "
                " context_row_count, objective_value_idr, candidate_count, selected_count) "
                "VALUES (:id, :tenant_id, 1000000, 'EXACT_DP', 'FALLBACK', 0, 0, 0, 0)"
            ),
            {"id": run_id, "tenant_id": tenant_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO recommendations "
                "(id, tenant_id, allocation_run_id, subject_type, user_pseudonym, "
                " incentive_code, cost_idr, priority_idr, user_rank, is_runner_up, "
                " reason_factors, status) "
                "VALUES (:id, :tenant_id, :run_id, 'USER', 'u_test', 'CASHBACK', 25000, "
                " 0, 1, false, '[]'::jsonb, 'PENDING_APPROVAL')"
            ),
            {"id": rec_id, "tenant_id": tenant_id, "run_id": run_id},
        )

    yield {"tenant_id": tenant_id, "recommendation_id": rec_id}

    with superuser_engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM recommendations WHERE id = :id"), {"id": rec_id})
        conn.execute(sa.text("DELETE FROM allocation_runs WHERE id = :id"), {"id": run_id})
        conn.execute(sa.text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _still_pending(superuser_engine, rec_id: str) -> bool:
    with superuser_engine.connect() as conn:
        status = conn.execute(
            sa.text("SELECT status FROM recommendations WHERE id = :id"), {"id": rec_id}
        ).scalar_one()
    return status == "PENDING_APPROVAL"


def test_worker_cannot_approve_by_touching_reviewer_columns(
    worker_engine, superuser_engine, pending_recommendation
) -> None:
    """The obvious attack: set status + reviewed_by + reviewed_at together.
    Blocked by a column-level permission error -- app_worker has no UPDATE
    grant on reviewed_by/reviewed_at at all."""
    tenant_id = pending_recommendation["tenant_id"]
    rec_id = pending_recommendation["recommendation_id"]

    with pytest.raises(sa.exc.DBAPIError) as exc_info:
        with worker_engine.begin() as conn:
            set_tenant(conn, tenant_id)
            conn.execute(
                sa.text(
                    "UPDATE recommendations "
                    "SET status = 'APPROVED', reviewed_by = 'sneaky_worker', reviewed_at = now() "
                    "WHERE id = :id"
                ),
                {"id": rec_id},
            )
    assert "permission denied" in str(exc_info.value).lower()
    assert _still_pending(superuser_engine, rec_id)


def test_worker_cannot_approve_by_touching_status_alone(
    worker_engine, superuser_engine, pending_recommendation
) -> None:
    """app_worker DOES have UPDATE grant on `status` alone (needed for
    EXPIRED/DELIVERED). Setting it to APPROVED without a reviewer still
    fails -- the CHECK constraint requires reviewed_by/reviewed_at to
    already be non-null, and app_worker has no way to make that true."""
    tenant_id = pending_recommendation["tenant_id"]
    rec_id = pending_recommendation["recommendation_id"]

    with pytest.raises(sa.exc.DBAPIError) as exc_info:
        with worker_engine.begin() as conn:
            set_tenant(conn, tenant_id)
            conn.execute(
                sa.text("UPDATE recommendations SET status = 'APPROVED' WHERE id = :id"),
                {"id": rec_id},
            )
    message = str(exc_info.value).lower()
    assert "check constraint" in message or "permission denied" in message
    assert _still_pending(superuser_engine, rec_id)


def test_worker_can_legitimately_reach_expired(
    worker_engine, superuser_engine, pending_recommendation
) -> None:
    """Sanity check that the role split isn't just globally locked down --
    app_worker CAN write the one status transition it legitimately drives
    without a reviewer (the scheduled PENDING_APPROVAL -> EXPIRED move)."""
    tenant_id = pending_recommendation["tenant_id"]
    rec_id = pending_recommendation["recommendation_id"]

    with worker_engine.begin() as conn:
        set_tenant(conn, tenant_id)
        conn.execute(
            sa.text("UPDATE recommendations SET status = 'EXPIRED' WHERE id = :id"), {"id": rec_id}
        )

    with superuser_engine.connect() as conn:
        status = conn.execute(
            sa.text("SELECT status FROM recommendations WHERE id = :id"), {"id": rec_id}
        ).scalar_one()
    assert status == "EXPIRED"
