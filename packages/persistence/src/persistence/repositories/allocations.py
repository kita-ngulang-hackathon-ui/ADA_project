"""Allocation runs and candidates."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import AllocationCandidate, AllocationRun


def create_run(
    session: Session,
    *,
    tenant_id: str,
    budget_idr: int,
    strategy: str,
    ranking_strategy: str,
    context_row_count: int,
    objective_value_idr: int,
    candidate_count: int,
    selected_count: int,
    pipeline_run_id: uuid.UUID | None = None,
    created_by: str | None = None,
) -> AllocationRun:
    row = AllocationRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        pipeline_run_id=pipeline_run_id,
        budget_idr=budget_idr,
        strategy=strategy,
        ranking_strategy=ranking_strategy,
        context_row_count=context_row_count,
        objective_value_idr=objective_value_idr,
        candidate_count=candidate_count,
        selected_count=selected_count,
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


def add_candidates(session: Session, *, tenant_id: str, allocation_run_id: uuid.UUID, candidates: list[dict]) -> list[AllocationCandidate]:
    """Persists the FULL candidate list -- selected and excluded, each with
    an exclusion_reason -- not only the winners (demo beat 3 requires the
    comparison)."""
    rows = [
        AllocationCandidate(id=uuid.uuid4(), tenant_id=tenant_id, allocation_run_id=allocation_run_id, **c)
        for c in candidates
    ]
    session.add_all(rows)
    session.flush()
    return rows


def get_run(session: Session, *, tenant_id: str, allocation_run_id: uuid.UUID) -> AllocationRun | None:
    return session.execute(
        select(AllocationRun).where(
            AllocationRun.tenant_id == tenant_id, AllocationRun.id == allocation_run_id
        )
    ).scalar_one_or_none()


def list_candidates(session: Session, *, tenant_id: str, allocation_run_id: uuid.UUID) -> list[AllocationCandidate]:
    stmt = (
        select(AllocationCandidate)
        .where(
            AllocationCandidate.tenant_id == tenant_id,
            AllocationCandidate.allocation_run_id == allocation_run_id,
        )
        .order_by(AllocationCandidate.user_rank)
    )
    return list(session.execute(stmt).scalars().all())
