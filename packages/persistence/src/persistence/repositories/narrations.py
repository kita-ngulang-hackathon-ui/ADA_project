"""Narration cache, keyed by fact_sheet_hash (requirement 9). Guarantees
identical narration text on re-run of the same fact sheet."""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from persistence.models import Narration


def save(session: Session, *, tenant_id: str, fact_sheet_hash: str, text: str, source: str) -> None:
    """Idempotent on (tenant_id, fact_sheet_hash): a re-run of the same fact
    sheet keeps the first narration rather than overwriting it, since the
    guarantee is "identical text", not "latest text"."""
    stmt = (
        pg_insert(Narration)
        .values(fact_sheet_hash=fact_sheet_hash, tenant_id=tenant_id, text=text, model=source)
        .on_conflict_do_nothing(index_elements=["fact_sheet_hash", "tenant_id"])
    )
    session.execute(stmt)
