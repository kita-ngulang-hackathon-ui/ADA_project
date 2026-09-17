"""Canonical event shape (requirement 1).

Every client's events are mapped into this one shape by ingest-mapping.
Scoring and decision code only ever sees CanonicalEvent.

TODO:
- Define CanonicalEventType enum (see README for the fixed vocabulary).
- Define CanonicalEvent as a frozen Pydantic v2 model.
- amount_idr is int. occurred_at must be timezone-aware (validator).
- user_pseudonym / counterparty_pseudonym are HMAC pseudonyms, never raw IDs.
"""
from enum import Enum


class CanonicalEventType(str, Enum):
    """TODO: fill in the fixed canonical vocabulary."""


class CanonicalEvent:
    """TODO: convert to a pydantic.BaseModel (frozen=True, extra='forbid')."""
