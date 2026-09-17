"""Per-tenant event mapping config (requirement 1).

TODO:
- EventTypeMapping pydantic model (see README for fields).
- TenantMappingConfig with lookup by client_event_type.
- from_dict() loader + validation (no duplicate client_event_type).
"""


class EventTypeMapping:
    """TODO."""


class TenantMappingConfig:
    """TODO."""

    def lookup(self, client_event_type: str) -> "EventTypeMapping":
        raise NotImplementedError
