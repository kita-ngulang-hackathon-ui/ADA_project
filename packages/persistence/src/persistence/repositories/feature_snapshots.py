"""Feature snapshots (requirement 11): the features/scores active at
recommendation time, read back by the feedback loop so labeled examples
never leak later data into their own features."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import FeatureSnapshotRow


def save_many(session: Session, *, tenant_id: str, rows: list[dict]) -> None:
    """Each row dict matches FeatureSnapshotRow columns (run_id,
    user_pseudonym, features, churn_risk, impact_score, pattern_type,
    incentive_code, cost_idr, business_value_idr)."""
    if not rows:
        return
    session.add_all(FeatureSnapshotRow(id=uuid.uuid4(), tenant_id=tenant_id, **r) for r in rows)


def load_all(session: Session, *, tenant_id: str) -> list[FeatureSnapshotRow]:
    stmt = select(FeatureSnapshotRow).where(FeatureSnapshotRow.tenant_id == tenant_id)
    return list(session.execute(stmt).scalars().all())
