"""Pipeline run tracking. Backs POST /console/v1/pipeline/run (202 QUEUED)
and GET /console/v1/pipeline/runs/{id} (per-stage status)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

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


def claim_queued(session: Session, *, tenant_id: str, limit: int = 1) -> list[PipelineRun]:
    """Claim QUEUED runs for this worker. `FOR UPDATE SKIP LOCKED` means a
    second worker replica polling the same tenant takes different rows
    instead of blocking or double-running one.

    Claiming sets status=RUNNING, refreshes started_at (the claim time the
    stale-reclaim window measures from) and increments attempts.
    """
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.tenant_id == tenant_id, PipelineRun.status == "QUEUED")
        .order_by(PipelineRun.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = list(session.execute(stmt).scalars().all())
    now = datetime.now(UTC)
    for row in rows:
        row.status = "RUNNING"
        row.started_at = now
        row.attempts += 1
    session.flush()
    return rows


def reclaim_stale(
    session: Session, *, tenant_id: str, stale_seconds: int, max_retries: int
) -> list[PipelineRun]:
    """Recover runs whose worker died mid-run: RUNNING rows untouched for
    longer than the stale window go back to QUEUED, or to FAILED once they
    have burned the retry budget. Returns the rows that changed."""
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_seconds)
    stmt = (
        select(PipelineRun)
        .where(
            PipelineRun.tenant_id == tenant_id,
            PipelineRun.status == "RUNNING",
            PipelineRun.started_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    )
    rows = list(session.execute(stmt).scalars().all())
    for row in rows:
        if row.attempts >= max_retries:
            row.status = "FAILED"
            row.error = f"abandoned after {row.attempts} attempt(s); no worker finished the run"
            row.finished_at = datetime.now(UTC)
        else:
            row.status = "QUEUED"
    session.flush()
    return rows


def requeue_or_fail(
    session: Session, *, tenant_id: str, run_id: uuid.UUID, max_retries: int, error: str | None = None
) -> PipelineRun | None:
    """Outcome of a run that finished unsuccessfully: queue it for another
    attempt, or mark it FAILED once the retry budget is gone."""
    row = get_run(session, tenant_id=tenant_id, run_id=run_id)
    if row is None:
        return None
    if row.attempts >= max_retries:
        row.status = "FAILED"
        row.error = error
        row.finished_at = datetime.now(UTC)
    else:
        row.status = "QUEUED"
        row.error = error
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
