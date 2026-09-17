"""POST/GET /console/v1/allocations -- budget run result: selected,
runner-ups, exclusion reasons (requirement 7).

Same layering rule as pipeline.py: this service does not run policy-guard,
ranker, or allocator -- it records the requested budget as a pending
allocation_runs row for the worker to fill in, then GET reads back whatever
the worker wrote (or 202/empty while it is still running). Demo beat 3 needs
the FULL candidate list, selected and excluded, which is why the read model
below always returns every allocation_candidates row for the run, not only
the winners.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from persistence.repositories import allocations as allocations_repo
from pydantic import BaseModel

from api import errors
from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-allocations"])


class AllocationRequestIn(BaseModel):
    budget_idr: int
    experiment_id: str | None = None
    dry_run: bool = False


class AllocationAccepted(BaseModel):
    allocation_run_id: str
    budget_idr: int
    status: str = "PENDING"


@router.post("/allocations", status_code=202)
def request_allocation(
    body: AllocationRequestIn, console: ConsoleSession = Depends(require_console_reviewer)
) -> AllocationAccepted:
    if body.budget_idr <= 0:
        raise errors.validation_failed("budget_idr must be a positive integer")

    with db_for_tenant(console.tenant_id) as session:
        run = allocations_repo.create_run(
            session,
            tenant_id=console.tenant_id,
            budget_idr=body.budget_idr,
            strategy="EXACT_DP",
            ranking_strategy="FALLBACK",
            context_row_count=0,
            objective_value_idr=0,
            candidate_count=0,
            selected_count=0,
            created_by=console.reviewer_id,
        )
    return AllocationAccepted(allocation_run_id=str(run.id), budget_idr=body.budget_idr)


class CandidateOut(BaseModel):
    subject_type: str
    user_pseudonym: str | None
    circle_id: str | None
    incentive_code: str
    cost_idr: int
    churn_risk: float | None
    impact_score: float | None
    segment: str | None
    pattern_type: str | None
    priority_idr: int | None
    user_rank: int | None
    selected: bool
    exclusion_reason: str | None


class AllocationRunOut(BaseModel):
    allocation_run_id: str
    budget_idr: int
    strategy: str
    ranking_strategy: str
    context_row_count: int
    objective_value_idr: int
    candidate_count: int
    selected_count: int
    synthetic_data: bool = True
    candidates: list[CandidateOut]


@router.get("/allocations/{allocation_run_id}")
def get_allocation(
    allocation_run_id: str, console: ConsoleSession = Depends(require_console_reviewer)
) -> AllocationRunOut:
    try:
        run_uuid = uuid.UUID(allocation_run_id)
    except ValueError as exc:
        raise errors.not_found("allocation run not found") from exc

    with db_for_tenant(console.tenant_id) as session:
        run = allocations_repo.get_run(session, tenant_id=console.tenant_id, allocation_run_id=run_uuid)
        if run is None:
            raise errors.not_found(f"allocation run {allocation_run_id} not found")
        candidates = allocations_repo.list_candidates(session, tenant_id=console.tenant_id, allocation_run_id=run_uuid)

    return AllocationRunOut(
        allocation_run_id=str(run.id),
        budget_idr=run.budget_idr,
        strategy=run.strategy,
        ranking_strategy=run.ranking_strategy,
        context_row_count=run.context_row_count,
        objective_value_idr=run.objective_value_idr,
        candidate_count=run.candidate_count,
        selected_count=run.selected_count,
        candidates=[
            CandidateOut(
                subject_type=c.subject_type,
                user_pseudonym=c.user_pseudonym,
                circle_id=str(c.circle_id) if c.circle_id else None,
                incentive_code=c.incentive_code,
                cost_idr=c.cost_idr,
                churn_risk=c.churn_risk,
                impact_score=c.impact_score,
                segment=c.segment,
                pattern_type=c.pattern_type,
                priority_idr=c.priority_idr,
                user_rank=c.user_rank,
                selected=c.selected,
                exclusion_reason=c.exclusion_reason,
            )
            for c in candidates
        ],
    )
