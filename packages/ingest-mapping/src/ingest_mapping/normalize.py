"""Normalize a raw client event into a CanonicalEvent. Pure function.

In: raw client JSON (`client_event_id`, `event_type`, `occurred_at`,
`user_ref`, `payload`, `user_attributes`). Out: CanonicalEvent.
"""
from __future__ import annotations

from datetime import datetime

from core_contracts.errors import MappingError
from core_contracts.events import ALLOWED_ATTRIBUTE_KEYS, CanonicalEvent

from ingest_mapping.mapping_config import TenantMappingConfig
from ingest_mapping.pseudonymize import pseudonymize


def _resolve_path(payload: dict, path: str):
    """Resolve a dotted field path (e.g. "payload.amount") against the raw
    event dict. Returns None if any segment is missing."""
    current = payload
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def normalize(tenant_id: str, raw_event: dict, config: TenantMappingConfig, secret: bytes) -> CanonicalEvent:
    client_event_type = raw_event.get("event_type")
    if not client_event_type:
        raise MappingError("raw event is missing event_type")

    mapping = config.lookup(client_event_type)  # raises MappingError if unknown/inactive

    amount_raw = _resolve_path(raw_event, mapping.amount_field_path)
    if amount_raw is None:
        raise MappingError(
            f"amount_field_path {mapping.amount_field_path!r} not found in payload "
            f"for client_event_type={client_event_type!r}"
        )
    try:
        amount_idr = int(amount_raw)
    except (TypeError, ValueError) as exc:
        raise MappingError(f"amount at {mapping.amount_field_path!r} is not numeric: {amount_raw!r}") from exc

    occurred_at_raw = _resolve_path(raw_event, mapping.occurred_at_field_path)
    if occurred_at_raw is None:
        raise MappingError(
            f"occurred_at_field_path {mapping.occurred_at_field_path!r} not found in payload"
        )
    occurred_at = (
        occurred_at_raw
        if isinstance(occurred_at_raw, datetime)
        else datetime.fromisoformat(str(occurred_at_raw))
    )

    user_ref = raw_event.get("user_ref")
    if not user_ref:
        raise MappingError("raw event is missing user_ref")
    user_pseudonym = pseudonymize(tenant_id, str(user_ref), secret)

    counterparty_pseudonym = None
    if mapping.counterparty_field_path:
        counterparty_ref = _resolve_path(raw_event, mapping.counterparty_field_path)
        if counterparty_ref is not None:
            counterparty_pseudonym = pseudonymize(tenant_id, str(counterparty_ref), secret)

    # Drop attributes not on the whitelist -- never pass through a name,
    # contact detail, or device identifier (§4).
    raw_attributes = raw_event.get("user_attributes") or {}
    attributes = {
        k: str(v) for k, v in raw_attributes.items() if k in ALLOWED_ATTRIBUTE_KEYS
    }

    client_event_id = raw_event.get("client_event_id")
    if not client_event_id:
        raise MappingError("raw event is missing client_event_id")

    return CanonicalEvent(
        tenant_id=tenant_id,
        client_event_id=client_event_id,
        event_type=mapping.canonical_event_type,
        occurred_at=occurred_at,
        user_pseudonym=user_pseudonym,
        counterparty_pseudonym=counterparty_pseudonym,
        amount_idr=amount_idr,
        attributes=attributes,
    )
