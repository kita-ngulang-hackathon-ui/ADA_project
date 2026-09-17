"""External signal reads (requirement 2). Read-only from the API's point of
view -- items are written only by the worker's feed adapter. Keyed by scope,
never by user."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import ExternalSignalRow


def list_signals(
    session: Session,
    *,
    tenant_id: str,
    scope_type: str | None = None,
    scope_key: str | None = None,
    signal_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ExternalSignalRow]:
    stmt = select(ExternalSignalRow).where(ExternalSignalRow.tenant_id == tenant_id)
    if scope_type is not None:
        stmt = stmt.where(ExternalSignalRow.scope_type == scope_type)
    if scope_key is not None:
        stmt = stmt.where(ExternalSignalRow.scope_key == scope_key)
    if signal_type is not None:
        stmt = stmt.where(ExternalSignalRow.signal_type == signal_type)
    stmt = stmt.order_by(ExternalSignalRow.observed_at.desc()).offset(offset).limit(limit)
    return list(session.execute(stmt).scalars().all())


def insert_signals(session: Session, *, tenant_id: str, rows: list[dict]) -> list[ExternalSignalRow]:
    """Worker-only write path (the feed adapter). Each row dict matches
    ExternalSignalRow columns; none may contain a user or counterparty key
    because that column does not exist on this model."""
    written = [ExternalSignalRow(id=uuid.uuid4(), tenant_id=tenant_id, **r) for r in rows]
    session.add_all(written)
    session.flush()
    return written
