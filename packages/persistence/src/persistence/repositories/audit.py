"""Append-only audit log. No update/delete functions exist -- on purpose."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import AuditLog


def append(
    session: Session,
    *,
    tenant_id: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
    )
    session.add(row)
    session.flush()
    return row


def list_recent(session: Session, *, tenant_id: str, limit: int = 50, offset: int = 0) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
