"""GET /console/v1/audit-log -- state transitions, reviewer actions,
configuration changes. Read-only; the append() write path lives only in
persistence.repositories.audit, called by other routers/worker."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from persistence.repositories import audit as audit_repo
from pydantic import BaseModel

from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-audit"])


class AuditEntryOut(BaseModel):
    id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str
    at: str
    detail: dict


class AuditList(BaseModel):
    items: list[AuditEntryOut]
    next_cursor: str | None = None


@router.get("/audit-log")
def list_audit_log(
    limit: int = Query(default=50, ge=1, le=500),
    cursor: int = Query(default=0, ge=0),
    console: ConsoleSession = Depends(require_console_reviewer),
) -> AuditList:
    with db_for_tenant(console.tenant_id) as session:
        rows = audit_repo.list_recent(session, tenant_id=console.tenant_id, limit=limit, offset=cursor)
    items = [
        AuditEntryOut(
            id=str(r.id), actor=r.actor, action=r.action, entity_type=r.entity_type,
            entity_id=r.entity_id, at=r.at.isoformat(), detail=r.detail,
        )
        for r in rows
    ]
    next_cursor = str(cursor + limit) if len(rows) == limit else None
    return AuditList(items=items, next_cursor=next_cursor)
