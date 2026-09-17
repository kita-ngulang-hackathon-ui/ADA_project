"""User directory and risk-detail reads (demo beats 1-2).

`GET /console/v1/users/{pseudonym}/risk` joins the latest risk_scores row
with the latest impact_scores rows and the circle snapshot -- churn_risk and
circle stability are returned separately, never pre-blended (ADR-013)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import ImpactScoreRow, RiskScoreRow, User


def list_users(
    session: Session,
    *,
    tenant_id: str,
    max_delta_stability: float | None = None,
    pattern_type: str | None = None,
    segment: str | None = None,
    min_churn_risk: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    """Filters on negative delta_stability with unchanged individual
    activity are how the demo locates the divergent user (API_CONTRACTS.md)."""
    stmt = select(User).where(User.tenant_id == tenant_id)

    needs_risk_join = max_delta_stability is not None or pattern_type is not None or min_churn_risk is not None
    if needs_risk_join:
        latest_risk = (
            select(RiskScoreRow.user_pseudonym, RiskScoreRow.delta_stability, RiskScoreRow.pattern_type, RiskScoreRow.churn_risk)
            .where(RiskScoreRow.tenant_id == tenant_id)
            .distinct(RiskScoreRow.user_pseudonym)
            .order_by(RiskScoreRow.user_pseudonym, RiskScoreRow.computed_at.desc())
            .subquery()
        )
        stmt = stmt.join(latest_risk, latest_risk.c.user_pseudonym == User.user_pseudonym)
        if max_delta_stability is not None:
            stmt = stmt.where(latest_risk.c.delta_stability <= max_delta_stability)
        if pattern_type is not None:
            stmt = stmt.where(latest_risk.c.pattern_type == pattern_type)
        if min_churn_risk is not None:
            stmt = stmt.where(latest_risk.c.churn_risk >= min_churn_risk)

    if segment is not None:
        latest_impact = (
            select(ImpactScoreRow.user_pseudonym, ImpactScoreRow.segment)
            .where(ImpactScoreRow.tenant_id == tenant_id)
            .distinct(ImpactScoreRow.user_pseudonym)
            .order_by(ImpactScoreRow.user_pseudonym, ImpactScoreRow.computed_at.desc())
            .subquery()
        )
        stmt = stmt.join(latest_impact, latest_impact.c.user_pseudonym == User.user_pseudonym)
        stmt = stmt.where(latest_impact.c.segment == segment)

    stmt = stmt.order_by(User.user_pseudonym).offset(offset).limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_user(session: Session, *, tenant_id: str, user_pseudonym: str) -> User | None:
    return session.execute(
        select(User).where(User.tenant_id == tenant_id, User.user_pseudonym == user_pseudonym)
    ).scalar_one_or_none()


def get_latest_impact_scores(session: Session, *, tenant_id: str, user_pseudonym: str) -> list[ImpactScoreRow]:
    """All per-incentive impact rows for one user's latest compute -- the
    console picks the PERSUADABLE one(s) to show."""
    stmt = (
        select(ImpactScoreRow)
        .where(ImpactScoreRow.tenant_id == tenant_id, ImpactScoreRow.user_pseudonym == user_pseudonym)
        .order_by(ImpactScoreRow.incentive_code, ImpactScoreRow.computed_at.desc())
    )
    return list(session.execute(stmt).scalars().all())
