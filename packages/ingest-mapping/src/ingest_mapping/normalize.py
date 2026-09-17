"""Normalize a raw client event into a CanonicalEvent. Pure function.

TODO:
- Resolve dotted field paths (e.g. "payload.amount").
- Map client_event_type -> canonical type via TenantMappingConfig.
- Pseudonymize user_ref and counterparty ref via pseudonymize.pseudonymize.
- amount -> int IDR; occurred_at -> tz-aware datetime.
- Raise MappingError on unknown/inactive event types.
"""


def normalize(tenant_id: str, raw_event: dict, config, secret: bytes):
    raise NotImplementedError
