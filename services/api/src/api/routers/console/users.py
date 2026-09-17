"""GET /console/v1/users (filters) and GET /console/v1/users/{pseudonym}/risk
-- risk, circle, pattern, reasons (demo beats 1-2).

churn_risk and circle stability are returned separately, never pre-blended
(ADR-013) -- the divergence between flat individual activity and a dropping
delta_stability IS the signal being demonstrated.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from persistence.repositories import scores as scores_repo
from persistence.repositories import users as users_repo
from pydantic import BaseModel

from api import errors
from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-users"])


class UserSummaryOut(BaseModel):
    user_pseudonym: str
    lifecycle_state: str
    region_code: str | None
    cohort_key: str | None


class UserList(BaseModel):
    items: list[UserSummaryOut]
    next_cursor: str | None = None


@router.get("/users")
def list_users(
    max_delta_stability: float | None = Query(default=None),
    pattern_type: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    min_churn_risk: float | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: int = Query(default=0, ge=0),
    console: ConsoleSession = Depends(require_console_reviewer),
) -> UserList:
    with db_for_tenant(console.tenant_id) as session:
        rows = users_repo.list_users(
            session,
            tenant_id=console.tenant_id,
            max_delta_stability=max_delta_stability,
            pattern_type=pattern_type,
            segment=segment,
            min_churn_risk=min_churn_risk,
            limit=limit,
            offset=cursor,
        )
    items = [
        UserSummaryOut(
            user_pseudonym=u.user_pseudonym,
            lifecycle_state=u.lifecycle_state,
            region_code=u.region_code,
            cohort_key=u.cohort_key,
        )
        for u in rows
    ]
    next_cursor = str(cursor + limit) if len(rows) == limit else None
    return UserList(items=items, next_cursor=next_cursor)


class CircleOut(BaseModel):
    circle_size: int
    neighbor_activity_ratio_now: float
    neighbor_activity_ratio_30d_ago: float
    delta_stability: float
    circle_edge_decay: float | None = None
    circle_dormant_members: int | None = None


class ExternalSignalRefOut(BaseModel):
    signal_id: str
    scope_type: str
    scope_key: str
    signal_type: str
    value: float
    contribution: float | None


class ImpactOut(BaseModel):
    incentive_code: str
    p_incentivized: float
    p_not_incentivized: float
    impact_score: float
    segment: str


class UserRiskOut(BaseModel):
    user_pseudonym: str
    lifecycle_state: str
    synthetic_data: bool = True
    churn_risk: float | None
    context_row_count: int | None
    circle: CircleOut | None
    pattern_type: str | None
    external_signal: ExternalSignalRefOut | None
    impacts: list[ImpactOut]


@router.get("/users/{user_pseudonym}/risk")
def get_user_risk(
    user_pseudonym: str, console: ConsoleSession = Depends(require_console_reviewer)
) -> UserRiskOut:
    with db_for_tenant(console.tenant_id) as session:
        user = users_repo.get_user(session, tenant_id=console.tenant_id, user_pseudonym=user_pseudonym)
        if user is None:
            raise errors.not_found(f"user {user_pseudonym!r} not found")

        risk = scores_repo.get_latest_risk_score(session, tenant_id=console.tenant_id, user_pseudonym=user_pseudonym)
        impacts = users_repo.get_latest_impact_scores(session, tenant_id=console.tenant_id, user_pseudonym=user_pseudonym)

    circle_out = None
    external_signal_out = None
    if risk is not None:
        features = risk.features or {}
        circle_out = CircleOut(
            circle_size=int(features.get("circle_size", 0)),
            neighbor_activity_ratio_now=float(features.get("neighbor_activity_ratio_now", 0.0)),
            neighbor_activity_ratio_30d_ago=float(features.get("neighbor_activity_ratio_30d_ago", 0.0)),
            delta_stability=risk.delta_stability,
            circle_edge_decay=features.get("circle_edge_decay"),
            circle_dormant_members=features.get("circle_dormant_members"),
        )
        if features.get("external_signal"):
            sig = features["external_signal"]
            external_signal_out = ExternalSignalRefOut(
                signal_id=sig.get("signal_id", ""),
                scope_type=sig.get("scope_type", ""),
                scope_key=sig.get("scope_key", ""),
                signal_type=sig.get("signal_type", ""),
                value=sig.get("value", 0.0),
                contribution=risk.external_signal_contribution,
            )

    return UserRiskOut(
        user_pseudonym=user.user_pseudonym,
        lifecycle_state=user.lifecycle_state,
        churn_risk=risk.churn_risk if risk else None,
        context_row_count=risk.context_row_count if risk else None,
        circle=circle_out,
        pattern_type=risk.pattern_type if risk else None,
        external_signal=external_signal_out,
        impacts=[
            ImpactOut(
                incentive_code=i.incentive_code,
                p_incentivized=i.p_incentivized,
                p_not_incentivized=i.p_not_incentivized,
                impact_score=i.impact_score,
                segment=i.segment,
            )
            for i in impacts
        ],
    )
