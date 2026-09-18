"""Per-tenant event type mapping config (requirement 1). Onboarding a new
client is inserting rows here -- no scoring or decision code changes."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import EventTypeMapping


def list_mappings(session: Session, *, tenant_id: str, active_only: bool = False) -> list[EventTypeMapping]:
    stmt = select(EventTypeMapping).where(EventTypeMapping.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(EventTypeMapping.active.is_(True))
    stmt = stmt.order_by(EventTypeMapping.client_event_type)
    return list(session.execute(stmt).scalars().all())


def upsert_mapping(
    session: Session,
    *,
    tenant_id: str,
    client_event_type: str,
    canonical_event_type: str,
    amount_field_path: str,
    counterparty_field_path: str | None,
    occurred_at_field_path: str,
) -> EventTypeMapping:
    """Insert a new mapping row, or reactivate/replace an existing one for
    the same (tenant_id, client_event_type). UNIQUE(tenant_id,
    client_event_type) in the schema is what makes this well-defined."""
    existing = session.execute(
        select(EventTypeMapping).where(
            EventTypeMapping.tenant_id == tenant_id,
            EventTypeMapping.client_event_type == client_event_type,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.canonical_event_type = canonical_event_type
        existing.amount_field_path = amount_field_path
        existing.counterparty_field_path = counterparty_field_path
        existing.occurred_at_field_path = occurred_at_field_path
        existing.active = True
        session.flush()
        return existing

    row = EventTypeMapping(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        client_event_type=client_event_type,
        canonical_event_type=canonical_event_type,
        amount_field_path=amount_field_path,
        counterparty_field_path=counterparty_field_path,
        occurred_at_field_path=occurred_at_field_path,
    )
    session.add(row)
    session.flush()
    return row
