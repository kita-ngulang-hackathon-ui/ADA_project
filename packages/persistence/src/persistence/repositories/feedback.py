"""Labeled-example writes and the "new labeled examples added" counter
(requirement 11). POST /console/v1/outcomes and GET
/console/v1/feedback/summary are both backed by this module."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from persistence.models import LabeledExample


def insert_labeled_examples(session: Session, *, tenant_id: str, rows: list[dict]) -> int:
    """Dedupe by (tenant_id, source_outcome_id) via ON CONFLICT DO NOTHING.
    Returns the count actually inserted (new rows only)."""
    if not rows:
        return 0
    stmt = (
        pg_insert(LabeledExample)
        .values([{"id": uuid.uuid4(), "tenant_id": tenant_id, **r} for r in rows])
        .on_conflict_do_nothing(index_elements=["tenant_id", "source_outcome_id"])
        .returning(LabeledExample.id)
    )
    inserted = session.execute(stmt).scalars().all()
    return len(inserted)


def summary(session: Session, *, tenant_id: str, since_hours: int = 24) -> dict:
    total = session.execute(
        select(func.count()).select_from(LabeledExample).where(LabeledExample.tenant_id == tenant_id)
    ).scalar_one()

    cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
    new_since = session.execute(
        select(func.count())
        .select_from(LabeledExample)
        .where(LabeledExample.tenant_id == tenant_id, LabeledExample.created_at >= cutoff)
    ).scalar_one()

    by_arm_rows = session.execute(
        select(LabeledExample.arm, func.count())
        .where(LabeledExample.tenant_id == tenant_id)
        .group_by(LabeledExample.arm)
    ).all()

    return {
        "labeled_examples_total": total,
        "new_since_last_run": new_since,
        "by_arm": {arm: count for arm, count in by_arm_rows},
    }
