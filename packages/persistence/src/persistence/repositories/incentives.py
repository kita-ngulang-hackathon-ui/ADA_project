"""Incentive catalog reads. Contents are an open decision (§6); this module
only reads whatever fixtures/incentives.json seeded into the incentives
table -- policy-guard reads encourages_borrowing from here (via the API's
GET /console/v1/incentives), never a hardcoded value."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import IncentiveModel


def list_incentives(session: Session, *, tenant_id: str, active_only: bool = True) -> list[IncentiveModel]:
    stmt = select(IncentiveModel).where(IncentiveModel.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(IncentiveModel.active.is_(True))
    return list(session.execute(stmt).scalars().order_by(IncentiveModel.code).all())
