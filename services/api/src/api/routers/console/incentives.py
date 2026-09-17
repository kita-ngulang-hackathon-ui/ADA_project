"""GET /console/v1/incentives -- the catalog including encourages_borrowing,
which policy-guard reads for the responsible-lending check (API_CONTRACTS.md;
not in this service's own README table, but present in the API contract).
Catalog contents are an open decision (§6); this only reads whatever
fixtures/incentives.json seeded into the table.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from persistence.repositories import incentives as incentives_repo
from pydantic import BaseModel

from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-incentives"])


class IncentiveOut(BaseModel):
    code: str
    display_name: str
    cost_idr: int
    encourages_borrowing: bool
    subject_type: str
    active: bool


@router.get("/incentives")
def list_incentives(console: ConsoleSession = Depends(require_console_reviewer)) -> list[IncentiveOut]:
    with db_for_tenant(console.tenant_id) as session:
        rows = incentives_repo.list_incentives(session, tenant_id=console.tenant_id)
    return [
        IncentiveOut(
            code=r.code, display_name=r.display_name, cost_idr=r.cost_idr,
            encourages_borrowing=r.encourages_borrowing, subject_type=r.subject_type, active=r.active,
        )
        for r in rows
    ]
