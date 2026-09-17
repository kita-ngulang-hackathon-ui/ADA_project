"""POST /console/v1/pipeline/run (202 QUEUED) and GET
/console/v1/pipeline/runs/{id} -- stage progress.

The API only enqueues: it writes a `pipeline_runs` row with every stage
PENDING and returns immediately. The worker (not this service -- README:
"Must not import scoring packages... those run in the worker") polls for
QUEUED runs and drives them through ingest-mapping/graph-signal/churn-risk/
impact/policy-guard/ranker/allocator/explain in order, updating stage status
as it goes. This endpoint can never produce an APPROVED recommendation --
it cannot even produce a scored one.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from persistence.repositories import pipeline as pipeline_repo
from pydantic import BaseModel

from api import errors
from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-pipeline"])


class RunAccepted(BaseModel):
    run_id: str
    status: str = "QUEUED"


@router.post("/pipeline/run", status_code=202)
def run_pipeline(console: ConsoleSession = Depends(require_console_reviewer)) -> RunAccepted:
    with db_for_tenant(console.tenant_id) as session:
        run = pipeline_repo.create_run(session, tenant_id=console.tenant_id)
    return RunAccepted(run_id=str(run.id))


class RunOut(BaseModel):
    run_id: str
    status: str
    stages: dict[str, str]
    external_source: str | None
    ranking_strategy: str | None
    context_row_count: int | None
    reason_source_counts: dict[str, int]
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


@router.get("/pipeline/runs/{run_id}")
def get_pipeline_run(run_id: str, console: ConsoleSession = Depends(require_console_reviewer)) -> RunOut:
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as exc:
        raise errors.not_found("pipeline run not found") from exc

    with db_for_tenant(console.tenant_id) as session:
        run = pipeline_repo.get_run(session, tenant_id=console.tenant_id, run_id=run_uuid)
    if run is None:
        raise errors.not_found(f"pipeline run {run_id} not found")

    return RunOut(
        run_id=str(run.id),
        status=run.status,
        stages=run.stages,
        external_source=run.external_source,
        ranking_strategy=run.ranking_strategy,
        context_row_count=run.context_row_count,
        reason_source_counts=run.reason_source_counts,
        error=run.error,
        created_at=run.created_at.isoformat(),
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )
