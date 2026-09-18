"""Invariant: RLS hides other tenants' rows even without a tenant filter
(ARCHITECTURE.md §11, mechanism 2).

A missing `WHERE tenant_id = ...` in application code must return zero rows
of another tenant, not their data. Tested against `users` (a representative
RLS-protected table) and `external_signals` (which has no user column at
all, but still must not leak across tenants).
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
def two_tenants_with_users(superuser_engine):
    """Two tenants, one `users` row each, created as superuser (bypasses RLS
    as table owner). Cleaned up afterward."""
    tenant_a = new_uuid()
    tenant_b = new_uuid()

    with superuser_engine.begin() as conn:
        for tid, slug in ((tenant_a, "rls-test-a"), (tenant_b, "rls-test-b")):
            conn.execute(
                sa.text(
                    "INSERT INTO tenants (id, slug, display_name, profile_type) "
                    "VALUES (:id, :slug, 'RLS Test Tenant', 'WALLET')"
                ),
                {"id": tid, "slug": f"{slug}-{tid[:8]}"},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO users "
                    "(tenant_id, user_pseudonym, first_seen_at, last_event_at, lifecycle_state) "
                    "VALUES (:tid, :pseudo, now(), now(), 'ACTIVE')"
                ),
                {"tid": tid, "pseudo": f"u_{slug}"},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO external_signals "
                    "(id, tenant_id, scope_type, scope_key, signal_type, value, observed_at, source) "
                    "VALUES (gen_random_uuid(), :tid, 'REGION', 'ID-JK', 'NEWS_SENTIMENT', 0.1, now(), 'test')"
                ),
                {"tid": tid},
            )

    yield {"tenant_a": tenant_a, "tenant_b": tenant_b}

    with superuser_engine.begin() as conn:
        for tid in (tenant_a, tenant_b):
            conn.execute(sa.text("DELETE FROM external_signals WHERE tenant_id = :tid"), {"tid": tid})
            conn.execute(sa.text("DELETE FROM users WHERE tenant_id = :tid"), {"tid": tid})
            conn.execute(sa.text("DELETE FROM tenants WHERE id = :tid"), {"tid": tid})


def test_rls_blocks_cross_tenant_read_on_users(worker_engine, two_tenants_with_users) -> None:
    tenant_a = two_tenants_with_users["tenant_a"]
    tenant_b = two_tenants_with_users["tenant_b"]

    with worker_engine.begin() as conn:
        set_tenant(conn, tenant_a)
        # Deliberately no WHERE tenant_id clause -- RLS is the only thing
        # standing between this query and tenant B's row.
        rows = conn.execute(sa.text("SELECT tenant_id, user_pseudonym FROM users")).all()

    tenant_ids_seen = {str(r.tenant_id) for r in rows}
    assert tenant_a in tenant_ids_seen
    assert tenant_b not in tenant_ids_seen
    assert all(str(r.tenant_id) == tenant_a for r in rows)


def test_rls_blocks_cross_tenant_read_on_external_signals(worker_engine, two_tenants_with_users) -> None:
    """external_signals has no user column at all, but RLS must still scope
    it per tenant -- the §4 external-signal boundary and §11 tenant
    isolation are independent guarantees, both must hold simultaneously."""
    tenant_a = two_tenants_with_users["tenant_a"]
    tenant_b = two_tenants_with_users["tenant_b"]

    with worker_engine.begin() as conn:
        set_tenant(conn, tenant_b)
        rows = conn.execute(sa.text("SELECT tenant_id FROM external_signals")).all()

    tenant_ids_seen = {str(r.tenant_id) for r in rows}
    assert tenant_b in tenant_ids_seen
    assert tenant_a not in tenant_ids_seen


def test_rls_returns_zero_rows_when_tenant_id_unset(worker_engine, two_tenants_with_users) -> None:
    """No app.tenant_id set at all (current_setting(..., true) returns NULL)
    -- the policy's equality check against NULL is never true, so every row
    is hidden rather than every row being shown."""
    with worker_engine.begin() as conn:
        rows = conn.execute(sa.text("SELECT tenant_id FROM users")).all()
    assert rows == []
