"""User directory and risk-detail reads (demo beats 1-2).

`GET /console/v1/users/{pseudonym}/risk` joins the latest risk_scores row
with the latest impact_scores rows and the circle snapshot -- churn_risk and
circle stability are returned separately, never pre-blended (ADR-013)."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from persistence.models import ImpactScoreRow, RiskScoreRow, User

# core_contracts.events.ALLOWED_ATTRIBUTE_KEYS that this table has columns
# for. "channel" is whitelisted on CanonicalEvent but nothing downstream
# reads it back off a user, so it is accepted and dropped rather than stored.
_STORED_ATTRIBUTE_KEYS = ("region_code", "cohort_key")


def upsert_attributes(
    session: Session, *, tenant_id: str, user_pseudonym: str, attributes: dict, observed_at: datetime | None = None
) -> None:
    """Ensures the user row exists (first hook a new pseudonym passes through
    is here, during INGEST) and applies any of region_code/cohort_key found
    in `attributes`. Never overwrites an existing value with a missing one --
    a later event without cohort_key must not erase an earlier one."""
    now = observed_at or datetime.now(UTC)
    values = {
        "tenant_id": tenant_id,
        "user_pseudonym": user_pseudonym,
        "first_seen_at": now,
        "last_event_at": now,
        "lifecycle_state": "ACTIVE",
        "region_code": attributes.get("region_code"),
        "cohort_key": attributes.get("cohort_key"),
    }
    stmt = pg_insert(User).values(**values)
    update_cols = {"last_event_at": stmt.excluded.last_event_at}
    for key in _STORED_ATTRIBUTE_KEYS:
        if attributes.get(key) is not None:
            update_cols[key] = stmt.excluded[key]
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id", "user_pseudonym"], set_=update_cols
    )
    session.execute(stmt)


def load_attributes(session: Session, *, tenant_id: str) -> dict[str, dict]:
    stmt = select(User.user_pseudonym, User.region_code, User.cohort_key).where(User.tenant_id == tenant_id)
    result = {}
    for pseudonym, region_code, cohort_key in session.execute(stmt).all():
        attrs = {}
        if region_code is not None:
            attrs["region_code"] = region_code
        if cohort_key is not None:
            attrs["cohort_key"] = cohort_key
        result[pseudonym] = attrs
    return result


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
