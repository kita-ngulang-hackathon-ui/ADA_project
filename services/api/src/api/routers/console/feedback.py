"""GET /console/v1/feedback/summary -- labeled-examples counter (requirement
11, demo beat 6).

Outcome posting itself lives on the ingestion surface (`POST /v1/outcomes`
in routers/ingest.py, per API_CONTRACTS.md) since it is the client's
backend that reports outcomes, authenticated with its API key, not a
console session. This router only reads the counter back.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from persistence.repositories import feedback as feedback_repo
from pydantic import BaseModel

from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-feedback"])


class FeedbackSummaryOut(BaseModel):
    tenant_id: str
    synthetic_data: bool = True
    labeled_examples_total: int
    new_since_last_run: int
    by_arm: dict[str, int]


@router.get("/feedback/summary")
def feedback_summary(console: ConsoleSession = Depends(require_console_reviewer)) -> FeedbackSummaryOut:
    with db_for_tenant(console.tenant_id) as session:
        result = feedback_repo.summary(session, tenant_id=console.tenant_id)
    return FeedbackSummaryOut(tenant_id=console.tenant_id, **result)
