"""Raw and canonical event persistence."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from persistence.models import CanonicalEventRow, RawEvent


def insert_raw_event(
    session: Session, *, tenant_id: str, client_event_id: str, payload: dict
) -> tuple[uuid.UUID, bool]:
    """Idempotent insert on (tenant_id, client_event_id).

    Returns (raw_event_id, duplicate). A replay of the same client_event_id
    returns the existing row's id with duplicate=True rather than erroring.
    """
    new_row_id = uuid.uuid4()
    stmt = (
        pg_insert(RawEvent)
        .values(
            id=new_row_id,
            tenant_id=tenant_id,
            client_event_id=client_event_id,
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "client_event_id"])
        .returning(RawEvent.id)
    )
    result = session.execute(stmt).scalar_one_or_none()
    if result is not None:
        return result, False

    existing = session.execute(
        select(RawEvent.id).where(
            RawEvent.tenant_id == tenant_id, RawEvent.client_event_id == client_event_id
        )
    ).scalar_one()
    return existing, True


def claim_unprocessed(session: Session, *, tenant_id: str, batch_size: int) -> list[RawEvent]:
    """SELECT ... FOR UPDATE SKIP LOCKED so multiple worker replicas never
    process the same raw row twice."""
    stmt = (
        select(RawEvent)
        .where(RawEvent.tenant_id == tenant_id, RawEvent.processed_at.is_(None))
        .order_by(RawEvent.received_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    return list(session.execute(stmt).scalars().all())


def mark_processed(session: Session, *, raw_event_id: uuid.UUID) -> None:
    session.execute(
        update(RawEvent)
        .where(RawEvent.id == raw_event_id)
        .values(processed_at=datetime.now(UTC), process_error=None)
    )


def mark_unmapped(session: Session, *, raw_event_id: uuid.UUID, error: str) -> None:
    """Unknown/inactive event types are flagged, never crash the worker."""
    session.execute(
        update(RawEvent)
        .where(RawEvent.id == raw_event_id)
        .values(processed_at=datetime.now(UTC), process_error=error)
    )


def insert_canonical_events(session: Session, rows: list[dict]) -> list[uuid.UUID]:
    """Bulk-insert already-normalized canonical events. Each row dict matches
    CanonicalEventRow columns (tenant_id, raw_event_id, user_pseudonym,
    canonical_type, occurred_at, amount_idr, counterparty_pseudonym, attributes)."""
    if not rows:
        return []
    ids = [uuid.uuid4() for _ in rows]
    session.execute(
        CanonicalEventRow.__table__.insert(),
        [{"id": i, **row} for i, row in zip(ids, rows)],
    )
    return ids
