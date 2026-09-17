"""Normalize a raw client event into a CanonicalEvent. Pure function.

Raw shape: client_event_id, event_type, occurred_at, user_ref, payload, user_attributes.
Raises MappingError on unknown/inactive event types or unresolvable fields; the
worker marks the raw row `unmapped` and carries on.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from core_contracts import CanonicalEvent, MappingError
from pydantic import ValidationError

from ingest_mapping.mapping_config import TenantMappingConfig
from ingest_mapping.pseudonymize import pseudonymize

_MISSING = object()


def resolve_path(data: dict, path: str) -> Any:
    """Resolve a dotted path such as "payload.recipient.ref". Returns _MISSING when absent."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _to_idr(value: Any) -> int:
    if isinstance(value, bool):
        raise MappingError("amount must be numeric")
    try:
        return int(Decimal(str(value)).to_integral_value())
    except (InvalidOperation, ValueError) as exc:
        raise MappingError("amount is not numeric") from exc


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise MappingError("occurred_at is not RFC 3339") from exc
    else:
        raise MappingError("occurred_at missing")
    if parsed.tzinfo is None:
        raise MappingError("occurred_at must carry a timezone offset")
    return parsed


def normalize(tenant_id: str, raw_event: dict, config: TenantMappingConfig, secret: bytes):
    mapping = config.lookup(str(raw_event.get("event_type")))

    user_ref = raw_event.get("user_ref")
    if not user_ref:
        raise MappingError("user_ref missing")
    client_event_id = raw_event.get("client_event_id")
    if not client_event_id:
        raise MappingError("client_event_id missing")

    occurred_at = _to_datetime(resolve_path(raw_event, mapping.occurred_at_field_path))

    amount_idr = None
    if mapping.amount_field_path:
        raw_amount = resolve_path(raw_event, mapping.amount_field_path)
        if raw_amount is _MISSING:
            raise MappingError(f"amount field {mapping.amount_field_path!r} missing")
        amount_idr = _to_idr(raw_amount)

    counterparty = None
    if mapping.counterparty_field_path:
        raw_cp = resolve_path(raw_event, mapping.counterparty_field_path)
        if raw_cp is _MISSING or not raw_cp:
            raise MappingError(f"counterparty field {mapping.counterparty_field_path!r} missing")
        counterparty = pseudonymize(tenant_id, str(raw_cp), secret)

    user_attributes = raw_event.get("user_attributes") or {}
    attributes = {
        k: user_attributes[k]
        for k in config.attribute_whitelist
        if k in user_attributes and isinstance(user_attributes[k], (str, int, float))
    }

    try:
        return CanonicalEvent(
            tenant_id=tenant_id,
            client_event_id=str(client_event_id),
            event_type=mapping.canonical_event_type,
            occurred_at=occurred_at,
            user_pseudonym=pseudonymize(tenant_id, str(user_ref), secret),
            amount_idr=amount_idr,
            counterparty_pseudonym=counterparty,
            attributes=attributes,
        )
    except ValidationError as exc:
        raise MappingError("event failed canonical validation") from exc
