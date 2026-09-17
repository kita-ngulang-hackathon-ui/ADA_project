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

from core_contracts.recommendation import RecommendationStatus, assert_transition
from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import Recommendation


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
    row = get(session, tenant_id=tenant_id, recommendation_id=recommendation_id)
    if row is None:
        raise LookupError(f"recommendation {recommendation_id} not found for tenant {tenant_id}")
    assert_transition(
        RecommendationStatus(row.status), RecommendationStatus.APPROVED, reviewer_id=reviewer_id
    )
    row.status = RecommendationStatus.APPROVED.value
    row.reviewed_by = reviewer_id
    row.reviewed_at = datetime.now(UTC)
    row.review_note = note
    session.flush()
    return row


def reject(
    session: Session,
    *,
    tenant_id: str,
    recommendation_id: uuid.UUID,
    reviewer_id: str,
    note: str | None = None,
) -> Recommendation:
    row = get(session, tenant_id=tenant_id, recommendation_id=recommendation_id)
    if row is None:
        raise LookupError(f"recommendation {recommendation_id} not found for tenant {tenant_id}")
    assert_transition(
        RecommendationStatus(row.status), RecommendationStatus.REJECTED, reviewer_id=reviewer_id
    )
    row.status = RecommendationStatus.REJECTED.value
    row.reviewed_by = reviewer_id
    row.reviewed_at = datetime.now(UTC)
    row.review_note = note
    session.flush()
    return row


def mark_delivered(
    session: Session,
    *,
    tenant_id: str,
    recommendation_id: uuid.UUID,
    delivery_ref: str | None = None,
) -> Recommendation:
    """Client-side delivery-ack. Legal only from APPROVED; reviewed_by must
    already be set (it was, to reach APPROVED at all)."""
    row = get(session, tenant_id=tenant_id, recommendation_id=recommendation_id)
    if row is None:
        raise LookupError(f"recommendation {recommendation_id} not found for tenant {tenant_id}")
    assert_transition(
        RecommendationStatus(row.status), RecommendationStatus.DELIVERED, reviewer_id=row.reviewed_by
    )
    row.status = RecommendationStatus.DELIVERED.value
    row.delivered_at = datetime.now(UTC)
    row.delivery_ref = delivery_ref
    session.flush()
    return row
