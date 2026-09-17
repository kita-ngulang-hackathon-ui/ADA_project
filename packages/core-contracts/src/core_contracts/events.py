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
    """Fixed canonical vocabulary (ARCHITECTURE.md §7.1). Adding a tenant never
    changes this list — only their mapping rows."""

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
    FEATURE_USED = "FEATURE_USED"
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
COUNTERPARTY_BEARING_EVENT_TYPES = COUNTERPARTY_EVENT_TYPES

# Attributes whitelist: coarse groupings only, never a name, contact detail,
# or device identifier (§4).
ALLOWED_ATTRIBUTE_KEYS: frozenset[str] = frozenset({"channel", "region_code", "cohort_key"})


class CanonicalEvent(BaseModel):
    """The one event shape every downstream package sees. Frozen, extra='forbid'."""

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

    @field_validator("attributes")
    @classmethod
    def _whitelist_attributes(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = set(value) - ALLOWED_ATTRIBUTE_KEYS
        if unknown:
            raise ValueError(f"attributes contains non-whitelisted keys: {sorted(unknown)}")
        return value
