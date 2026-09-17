"""Risk, impact, and graph snapshot persistence; labeled-example reads."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import ImpactScoreRow, LabeledExample, RiskScoreRow, TransactionCircle


def write_risk_scores(session: Session, *, tenant_id: str, rows: list[dict]) -> list[RiskScoreRow]:
    """Each row dict matches RiskScoreRow columns. churn_risk and
    delta_stability are always written to separate columns -- never blended
    (ADR-013)."""
    written = [RiskScoreRow(id=uuid.uuid4(), tenant_id=tenant_id, **r) for r in rows]
    session.add_all(written)
    session.flush()
    return written


def write_impact_scores(session: Session, *, tenant_id: str, rows: list[dict]) -> list[ImpactScoreRow]:
    written = [ImpactScoreRow(id=uuid.uuid4(), tenant_id=tenant_id, **r) for r in rows]
    session.add_all(written)
    session.flush()
    return written


def write_circle_snapshots(session: Session, *, tenant_id: str, rows: list[dict]) -> list[TransactionCircle]:
    written = [TransactionCircle(id=uuid.uuid4(), tenant_id=tenant_id, **r) for r in rows]
    session.add_all(written)
    session.flush()
    return written


def get_latest_risk_score(session: Session, *, tenant_id: str, user_pseudonym: str) -> RiskScoreRow | None:
    stmt = (
        select(RiskScoreRow)
        .where(RiskScoreRow.tenant_id == tenant_id, RiskScoreRow.user_pseudonym == user_pseudonym)
        .order_by(RiskScoreRow.computed_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def load_labeled_examples(session: Session, *, tenant_id: str, limit: int | None = None) -> list[LabeledExample]:
    """Reads for TabPFN in-context selection (requirements 3, 7, 11). Always
    scoped to exactly one tenant -- callers in churn-risk/ranker assert this
    themselves too (defense in depth, not reliance on this filter alone)."""
    stmt = (
        select(LabeledExample)
        .where(LabeledExample.tenant_id == tenant_id)
        .order_by(LabeledExample.created_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())
