"""GET list/detail; POST /{id}/approve, /{id}/reject (reviewer required, 409
on illegal transition); POST /{id}/delivery-ack (requirement 8).

This is the human approval gate. `require_console_reviewer` guarantees a
named reviewer reached this handler at all (401 otherwise); `assert_transition`
via persistence.repositories.recommendations then guarantees the state
machine allows the move; the database's own CHECK constraints, trigger, and
role grants (migration 0006) are a fourth, independent backstop that holds
even if every line in this file were deleted.
"""
from __future__ import annotations

import uuid

from core_contracts.errors import IllegalTransition
from fastapi import APIRouter, Depends, Query
from persistence.repositories import recommendations as recommendations_repo
from pydantic import BaseModel

from api import errors
from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_ingest, db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-recommendations"])


class RecommendationOut(BaseModel):
    id: str
    allocation_run_id: str
    subject_type: str
    user_pseudonym: str | None
    circle_id: str | None
    incentive_code: str
    cost_idr: int
    priority_idr: int
    user_rank: int
    is_runner_up: bool
    status: str
    reason_text: str | None
    reason_source: str | None
    created_at: str
    submitted_at: str | None
    reviewed_by: str | None
    reviewed_at: str | None
    review_note: str | None
    delivered_at: str | None


def _to_out(row) -> RecommendationOut:
    return RecommendationOut(
        id=str(row.id),
        allocation_run_id=str(row.allocation_run_id),
        subject_type=row.subject_type,
        user_pseudonym=row.user_pseudonym,
        circle_id=str(row.circle_id) if row.circle_id else None,
        incentive_code=row.incentive_code,
        cost_idr=row.cost_idr,
        priority_idr=row.priority_idr,
        user_rank=row.user_rank,
        is_runner_up=row.is_runner_up,
        status=row.status,
        reason_text=row.reason_text,
        reason_source=row.reason_source,
        created_at=row.created_at.isoformat(),
        submitted_at=row.submitted_at.isoformat() if row.submitted_at else None,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
        review_note=row.review_note,
        delivered_at=row.delivered_at.isoformat() if row.delivered_at else None,
    )


class RecommendationList(BaseModel):
    items: list[RecommendationOut]
    next_cursor: str | None = None


@router.get("/recommendations")
def list_recommendations(
    limit: int = Query(default=50, ge=1, le=500),
    cursor: int = Query(default=0, ge=0),
    console: ConsoleSession = Depends(require_console_reviewer),
) -> RecommendationList:
    """Pending approval queue (DEMO_SCRIPT beat 4: "everything sits in
    PENDING_APPROVAL")."""
    with db_for_tenant(console.tenant_id) as session:
        rows = recommendations_repo.list_pending(session, tenant_id=console.tenant_id, limit=limit, offset=cursor)
    next_cursor = str(cursor + limit) if len(rows) == limit else None
    return RecommendationList(items=[_to_out(r) for r in rows], next_cursor=next_cursor)


@router.get("/recommendations/{recommendation_id}")
def get_recommendation(
    recommendation_id: str, console: ConsoleSession = Depends(require_console_reviewer)
) -> RecommendationOut:
    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError as exc:
        raise errors.not_found("recommendation not found") from exc

    with db_for_tenant(console.tenant_id) as session:
        row = recommendations_repo.get(session, tenant_id=console.tenant_id, recommendation_id=rec_uuid)
    if row is None:
        raise errors.not_found(f"recommendation {recommendation_id} not found")
    return _to_out(row)


class ReviewIn(BaseModel):
    note: str | None = None


@router.post("/recommendations/{recommendation_id}/approve")
def approve_recommendation(
    recommendation_id: str,
    body: ReviewIn,
    console: ConsoleSession = Depends(require_console_reviewer),
) -> RecommendationOut:
    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError as exc:
        raise errors.not_found("recommendation not found") from exc

    with db_for_tenant(console.tenant_id) as session:
        try:
            row = recommendations_repo.approve(
                session,
                tenant_id=console.tenant_id,
                recommendation_id=rec_uuid,
                reviewer_id=console.reviewer_id,
                note=body.note,
            )
        except LookupError as exc:
            raise errors.not_found(str(exc)) from exc
        except IllegalTransition as exc:
            # Covers both an illegal state edge and "approving a runner-up
            # when its sibling is already approved" (API_CONTRACTS.md 409).
            raise errors.conflict(str(exc)) from exc
    return _to_out(row)


@router.post("/recommendations/{recommendation_id}/reject")
def reject_recommendation(
    recommendation_id: str,
    body: ReviewIn,
    console: ConsoleSession = Depends(require_console_reviewer),
) -> RecommendationOut:
    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError as exc:
        raise errors.not_found("recommendation not found") from exc

    with db_for_tenant(console.tenant_id) as session:
        try:
            row = recommendations_repo.reject(
                session,
                tenant_id=console.tenant_id,
                recommendation_id=rec_uuid,
                reviewer_id=console.reviewer_id,
                note=body.note,
            )
        except LookupError as exc:
            raise errors.not_found(str(exc)) from exc
        except IllegalTransition as exc:
            raise errors.conflict(str(exc)) from exc
    return _to_out(row)


class DeliveryAckIn(BaseModel):
    delivery_ref: str | None = None


@router.post("/recommendations/{recommendation_id}/delivery-ack")
def console_delivery_ack(
    recommendation_id: str,
    body: DeliveryAckIn,
    console: ConsoleSession = Depends(require_console_reviewer),
) -> RecommendationOut:
    """Console-side mirror of the client's own delivery-ack (`POST
    /v1/recommendations/{id}/delivery-ack`), for demoing the transition from
    the ops side without a second browser tab."""
    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError as exc:
        raise errors.not_found("recommendation not found") from exc

    # delivered_at/delivery_ref are granted to the worker role, not the console one.
    with db_for_ingest(console.tenant_id) as session:
        try:
            row = recommendations_repo.mark_delivered(
                session, tenant_id=console.tenant_id, recommendation_id=rec_uuid,
                delivery_ref=body.delivery_ref, actor=console.reviewer_id,
            )
        except LookupError as exc:
            raise errors.not_found(str(exc)) from exc
        except IllegalTransition as exc:
            raise errors.conflict(str(exc)) from exc
    return _to_out(row)
