"""Contact log reads. Sole input to the policy-guard frequency-cap check
(requirement 7); writes happen on the console/delivery path, not here."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import ContactLog


def load_contact_times(session: Session, *, tenant_id: str) -> dict[str, list[datetime]]:
    stmt = select(ContactLog.user_pseudonym, ContactLog.contacted_at).where(ContactLog.tenant_id == tenant_id)
    by_user: dict[str, list[datetime]] = defaultdict(list)
    for pseudonym, contacted_at in session.execute(stmt).all():
        by_user[pseudonym].append(contacted_at)
    return dict(by_user)
