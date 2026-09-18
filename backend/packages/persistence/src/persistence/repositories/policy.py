"""policy_decisions persistence: audit trail of every ALLOW/DENY, including
denials that never became a recommendation (requirement 7, §4)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import PolicyDecision


def write_decisions(session: Session, *, tenant_id: str, rows: list[dict]) -> list[PolicyDecision]:
    written = [PolicyDecision(id=uuid.uuid4(), tenant_id=tenant_id, **r) for r in rows]
    session.add_all(written)
    session.flush()
    return written


def list_for_candidate(session: Session, *, tenant_id: str, candidate_ref: str) -> list[PolicyDecision]:
    stmt = select(PolicyDecision).where(
        PolicyDecision.tenant_id == tenant_id, PolicyDecision.candidate_ref == candidate_ref
    )
    return list(session.execute(stmt).scalars().all())
