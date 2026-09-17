"""GET /console/v1/external-signals -- read-only, keyed by scope, never by
user (requirement 2). Items are written only by the worker's feed adapter."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from persistence.repositories import external_signals as signals_repo
from pydantic import BaseModel

from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-external-signals"])


class SignalOut(BaseModel):
    signal_id: str
    scope_type: str
    scope_key: str
    signal_type: str
    value: float
    observed_at: str
    source: str


class SignalList(BaseModel):
    source: str
    synthetic_data: bool
    items: list[SignalOut]


@router.get("/external-signals")
def list_external_signals(
    scope_type: str | None = Query(default=None),
    scope_key: str | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    console: ConsoleSession = Depends(require_console_reviewer),
) -> SignalList:
    with db_for_tenant(console.tenant_id) as session:
        rows = signals_repo.list_signals(
            session,
            tenant_id=console.tenant_id,
            scope_type=scope_type,
            scope_key=scope_key,
            signal_type=signal_type,
            limit=limit,
        )
    items = [
        SignalOut(
            signal_id=str(r.id),
            scope_type=r.scope_type,
            scope_key=r.scope_key,
            signal_type=r.signal_type,
            value=r.value,
            observed_at=r.observed_at.isoformat(),
            source=r.source,
        )
        for r in rows
    ]
    return SignalList(source=items[0].source if items else "canned", synthetic_data=True, items=items)
