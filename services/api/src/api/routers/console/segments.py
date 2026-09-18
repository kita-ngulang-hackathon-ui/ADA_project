"""GET /console/v1/segments -- per-user spend/frequency/risk rollup backing
the dashboard's RFM-style segment view. Not part of API_CONTRACTS.md; see
persistence.repositories.segments for what it actually aggregates and why.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from persistence.repositories import segments as segments_repo
from pydantic import BaseModel

from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-segments"])


class UserSegmentOut(BaseModel):
    user_pseudonym: str
    churn_risk: float | None
    risk_band: str
    segment_ids: list[str]


class SegmentList(BaseModel):
    items: list[UserSegmentOut]


@router.get("/segments")
def list_segments(console: ConsoleSession = Depends(require_console_reviewer)) -> SegmentList:
    with db_for_tenant(console.tenant_id) as session:
        rows = segments_repo.get_user_segments(session, tenant_id=console.tenant_id)
    return SegmentList(items=[UserSegmentOut(**r) for r in rows])
