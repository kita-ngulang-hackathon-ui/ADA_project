"""Pipeline run tracking. Backs POST /console/v1/pipeline/run (202 QUEUED)
and GET /console/v1/pipeline/runs/{id} (per-stage status)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import PIPELINE_STAGES, PipelineRun


def create_run(session: Session, *, tenant_id: str) -> PipelineRun:
    row = PipelineRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status="QUEUED",
        stages={stage: "PENDING" for stage in PIPELINE_STAGES},
        reason_source_counts={"llm": 0, "template": 0},
    )
    session.add(row)
    session.flush()
    return row


def get_run(session: Session, *, tenant_id: str, run_id: uuid.UUID) -> PipelineRun | None:
    return session.execute(
        select(PipelineRun).where(PipelineRun.tenant_id == tenant_id, PipelineRun.id == run_id)
    ).scalar_one_or_none()


def update_stage(
    session: Session, *, tenant_id: str, run_id: uuid.UUID, stage: str, status: str
) -> PipelineRun | None:
    """`status` per stage is one of PENDING | RUNNING | DONE | FAILED. The
    worker calls this once per pipeline step (ARCHITECTURE.md §6)."""
    row = get_run(session, tenant_id=tenant_id, run_id=run_id)
    if row is None:
        return None
    stages = dict(row.stages)
    stages[stage] = status
    row.stages = stages
    if row.status == "QUEUED":
        row.status = "RUNNING"
        row.started_at = datetime.now(UTC)
    session.flush()
    return row


def finish_run(
    session: Session, *, tenant_id: str, run_id: uuid.UUID, succeeded: bool, error: str | None = None
) -> PipelineRun | None:
    row = get_run(session, tenant_id=tenant_id, run_id=run_id)
    if row is None:
        return None
    row.status = "SUCCEEDED" if succeeded else "FAILED"
    row.error = error
    row.finished_at = datetime.now(UTC)
    session.flush()
    return row
