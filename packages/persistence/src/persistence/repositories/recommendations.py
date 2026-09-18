"""Recommendation persistence (requirement 8).

Worker code must never call approve()/mark_delivered() -- only the console
path does, and even if it tried, the `app_worker` database role has no grant
permitting the write (see roles.sql). This module is a second, independent
enforcement layer on top of that: it calls core_contracts.assert_transition
before every status-changing write.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core_contracts.errors import IllegalTransition
from core_contracts.recommendation import RecommendationStatus, assert_transition
from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import Recommendation
from persistence.repositories import audit as audit_repo

# A subject may hold one live recommendation per allocation run: approving a
# runner-up whose sibling is already approved (or delivered) is the 409 the
# console contract promises, and the status check alone cannot see it.
_LIVE_STATUSES = (RecommendationStatus.APPROVED.value, RecommendationStatus.DELIVERED.value)


def create_pending(session: Session, *, tenant_id: str, **fields) -> Recommendation:
    """Worker path: the only status a freshly created recommendation may
    carry is PENDING_APPROVAL (DRAFT is transient / not persisted)."""
    assert_transition(
        RecommendationStatus.DRAFT, RecommendationStatus.PENDING_APPROVAL, reviewer_id=None
    )
    row = Recommendation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=RecommendationStatus.PENDING_APPROVAL.value,
        submitted_at=datetime.now(UTC),
        **fields,
    )
    session.add(row)
    session.flush()
    return row


def _load_for_update(session: Session, *, tenant_id: str, recommendation_id: uuid.UUID) -> Recommendation:
    """Lock the row for the rest of the transaction, so two reviewers acting
    at the same time serialize instead of both reading PENDING_APPROVAL."""
    row = session.execute(
        select(Recommendation)
        .where(Recommendation.tenant_id == tenant_id, Recommendation.id == recommendation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(f"recommendation {recommendation_id} not found for tenant {tenant_id}")
    return row


def _assert_no_live_sibling(session: Session, row: Recommendation) -> None:
    sibling = select(Recommendation.id).where(
        Recommendation.tenant_id == row.tenant_id,
        Recommendation.allocation_run_id == row.allocation_run_id,
        Recommendation.id != row.id,
        Recommendation.status.in_(_LIVE_STATUSES),
    )
    if row.circle_id is not None:
        sibling = sibling.where(Recommendation.circle_id == row.circle_id)
    else:
        sibling = sibling.where(Recommendation.user_pseudonym == row.user_pseudonym)
    if session.execute(sibling.limit(1)).scalar_one_or_none() is not None:
        raise IllegalTransition(
            f"recommendation {row.id} has a sibling already approved in this allocation run"
        )


def get(session: Session, *, tenant_id: str, recommendation_id: uuid.UUID) -> Recommendation | None:
    return session.execute(
        select(Recommendation).where(
            Recommendation.tenant_id == tenant_id, Recommendation.id == recommendation_id
        )
    ).scalar_one_or_none()


def list_pending(session: Session, *, tenant_id: str, limit: int = 50, offset: int = 0) -> list[Recommendation]:
    stmt = (
        select(Recommendation)
        .where(
            Recommendation.tenant_id == tenant_id,
            Recommendation.status == RecommendationStatus.PENDING_APPROVAL.value,
        )
        .order_by(Recommendation.created_at)
        .offset(offset)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def list_by_statuses(
    session: Session, *, tenant_id: str, statuses: list[str], limit: int = 200, offset: int = 0
) -> list[Recommendation]:
    """Console-side multi-status read (dashboard's Actions view groups
    PENDING_APPROVAL/APPROVED/REJECTED/DELIVERED into one lifecycle)."""
    stmt = (
        select(Recommendation)
        .where(Recommendation.tenant_id == tenant_id, Recommendation.status.in_(statuses))
        .order_by(Recommendation.created_at)
        .offset(offset)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def list_approved(session: Session, *, tenant_id: str, limit: int = 50, offset: int = 0) -> list[Recommendation]:
    """Backs `GET /v1/recommendations?status=APPROVED` -- the only status
    value the ingestion-side pull endpoint accepts."""
    stmt = (
        select(Recommendation)
        .where(
            Recommendation.tenant_id == tenant_id,
            Recommendation.status == RecommendationStatus.APPROVED.value,
        )
        .order_by(Recommendation.reviewed_at)
        .offset(offset)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def approve(
    session: Session,
    *,
    tenant_id: str,
    recommendation_id: uuid.UUID,
    reviewer_id: str,
    note: str | None = None,
) -> Recommendation:
    row = _load_for_update(session, tenant_id=tenant_id, recommendation_id=recommendation_id)
    assert_transition(
        RecommendationStatus(row.status), RecommendationStatus.APPROVED, reviewer_id=reviewer_id
    )
    _assert_no_live_sibling(session, row)
    row.status = RecommendationStatus.APPROVED.value
    row.reviewed_by = reviewer_id
    row.reviewed_at = datetime.now(UTC)
    row.review_note = note
    session.flush()
    _audit(session, row, actor=reviewer_id, action="RECOMMENDATION_APPROVED", note=note)
    return row


def reject(
    session: Session,
    *,
    tenant_id: str,
    recommendation_id: uuid.UUID,
    reviewer_id: str,
    note: str | None = None,
) -> Recommendation:
    row = _load_for_update(session, tenant_id=tenant_id, recommendation_id=recommendation_id)
    assert_transition(
        RecommendationStatus(row.status), RecommendationStatus.REJECTED, reviewer_id=reviewer_id
    )
    row.status = RecommendationStatus.REJECTED.value
    row.reviewed_by = reviewer_id
    row.reviewed_at = datetime.now(UTC)
    row.review_note = note
    session.flush()
    _audit(session, row, actor=reviewer_id, action="RECOMMENDATION_REJECTED", note=note)
    return row


def mark_delivered(
    session: Session,
    *,
    tenant_id: str,
    recommendation_id: uuid.UUID,
    delivery_ref: str | None = None,
    actor: str = "api_delivery_ack",
) -> Recommendation:
    """Client-side delivery-ack. Legal only from APPROVED; reviewed_by must
    already be set (it was, to reach APPROVED at all)."""
    row = _load_for_update(session, tenant_id=tenant_id, recommendation_id=recommendation_id)
    assert_transition(
        RecommendationStatus(row.status), RecommendationStatus.DELIVERED, reviewer_id=row.reviewed_by
    )
    row.status = RecommendationStatus.DELIVERED.value
    row.delivered_at = datetime.now(UTC)
    row.delivery_ref = delivery_ref
    session.flush()
    _audit(session, row, actor=actor, action="RECOMMENDATION_DELIVERED", note=delivery_ref)
    return row


def _audit(session: Session, row: Recommendation, *, actor: str, action: str, note: str | None) -> None:
    """Every status change leaves a trail, in the same transaction as the
    change itself -- an approval that commits without its audit row, or the
    other way round, is not possible."""
    audit_repo.append(
        session, tenant_id=row.tenant_id, actor=actor, action=action,
        entity_type="recommendation", entity_id=str(row.id),
        detail={"status": row.status, "note": note},
    )
