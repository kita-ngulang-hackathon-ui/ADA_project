"""Experiments, arm assignments, outcome events."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from persistence.models import Experiment, ExperimentAssignment, OutcomeEvent


def create_experiment(
    session: Session, *, tenant_id: str, name: str, control_pct: int, naive_pct: int
) -> Experiment:
    row = Experiment(
        id=uuid.uuid4(), tenant_id=tenant_id, name=name, control_pct=control_pct, naive_pct=naive_pct
    )
    session.add(row)
    session.flush()
    return row


def get_experiment(session: Session, *, tenant_id: str, experiment_id: uuid.UUID) -> Experiment | None:
    return session.execute(
        select(Experiment).where(Experiment.tenant_id == tenant_id, Experiment.id == experiment_id)
    ).scalar_one_or_none()


def get_active_experiment(session: Session, *, tenant_id: str) -> Experiment | None:
    """The one experiment a pipeline run assigns arms against. "Active" means
    not yet ended; the most recently started one wins if somehow more than
    one is open (there is no separate scheduler that would create that)."""
    stmt = (
        select(Experiment)
        .where(Experiment.tenant_id == tenant_id, Experiment.ended_at.is_(None))
        .order_by(Experiment.started_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def record_assignment(
    session: Session, *, tenant_id: str, experiment_id: uuid.UUID, user_pseudonym: str, arm: str
) -> None:
    """Idempotent: a user's arm never changes within an experiment (the
    upstream HMAC assignment is already deterministic, this just avoids a
    duplicate-key error on re-run)."""
    stmt = (
        pg_insert(ExperimentAssignment)
        .values(
            tenant_id=tenant_id, experiment_id=experiment_id, user_pseudonym=user_pseudonym, arm=arm
        )
        .on_conflict_do_nothing(
            index_elements=["tenant_id", "experiment_id", "user_pseudonym"]
        )
    )
    session.execute(stmt)


def list_assignments(session: Session, *, tenant_id: str, experiment_id: uuid.UUID) -> list[ExperimentAssignment]:
    stmt = select(ExperimentAssignment).where(
        ExperimentAssignment.tenant_id == tenant_id,
        ExperimentAssignment.experiment_id == experiment_id,
    )
    return list(session.execute(stmt).scalars().all())


def record_outcome(
    session: Session,
    *,
    tenant_id: str,
    experiment_id: uuid.UUID,
    user_pseudonym: str,
    outcome_type: str,
    value_idr: int | None,
    observed_at: datetime | None = None,
) -> OutcomeEvent:
    row = OutcomeEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        experiment_id=experiment_id,
        user_pseudonym=user_pseudonym,
        outcome_type=outcome_type,
        value_idr=value_idr,
        observed_at=observed_at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def load_outcomes(session: Session, *, tenant_id: str, experiment_id: uuid.UUID) -> list[OutcomeEvent]:
    stmt = select(OutcomeEvent).where(
        OutcomeEvent.tenant_id == tenant_id, OutcomeEvent.experiment_id == experiment_id
    )
    return list(session.execute(stmt).scalars().all())
