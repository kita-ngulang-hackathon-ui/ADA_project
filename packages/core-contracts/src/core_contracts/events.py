"""Canonical event shape (requirement 1).

Every client's events are mapped into this one shape by ingest-mapping.
Scoring and decision code only ever sees CanonicalEvent.
user_pseudonym / counterparty_pseudonym are HMAC pseudonyms, never raw IDs.
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class CanonicalEventType(str, Enum):
    """Fixed canonical vocabulary (ARCHITECTURE §7.1)."""

    PAYMENT = "PAYMENT"
    P2P_TRANSFER = "P2P_TRANSFER"
    TOPUP = "TOPUP"
    WITHDRAWAL = "WITHDRAWAL"
    SPLIT_BILL_CREATED = "SPLIT_BILL_CREATED"
    SPLIT_BILL_SETTLED = "SPLIT_BILL_SETTLED"
    RECURRING_PAYMENT = "RECURRING_PAYMENT"
    LOAN_DISBURSED = "LOAN_DISBURSED"
    LOAN_REPAYMENT = "LOAN_REPAYMENT"
    LOAN_REPAYMENT_LATE = "LOAN_REPAYMENT_LATE"
    SESSION_OPEN = "SESSION_OPEN"
    SUPPORT_CONTACT = "SUPPORT_CONTACT"


# Event types that carry a counterparty and therefore form graph edges (requirement 4).
COUNTERPARTY_EVENT_TYPES: frozenset[CanonicalEventType] = frozenset(
    {
        CanonicalEventType.P2P_TRANSFER,
        CanonicalEventType.SPLIT_BILL_CREATED,
        CanonicalEventType.SPLIT_BILL_SETTLED,
        CanonicalEventType.RECURRING_PAYMENT,
    }
)


class CanonicalEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    client_event_id: str
    event_type: CanonicalEventType
    occurred_at: datetime
    user_pseudonym: str
    amount_idr: int | None = None
    counterparty_pseudonym: str | None = None
    attributes: dict[str, Any] = {}

    @field_validator("occurred_at")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value
