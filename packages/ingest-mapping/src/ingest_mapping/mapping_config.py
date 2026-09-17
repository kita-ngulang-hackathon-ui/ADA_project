"""Per-tenant event mapping config (requirement 1).

Onboarding a new client is a config change: a list of EventTypeMapping rows.
"""
from core_contracts import CanonicalEventType, MappingError
from pydantic import BaseModel, ConfigDict, model_validator


class EventTypeMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_event_type: str
    canonical_event_type: CanonicalEventType
    amount_field_path: str | None = None
    counterparty_field_path: str | None = None
    occurred_at_field_path: str = "occurred_at"
    active: bool = True


class TenantMappingConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_slug: str
    profile_type: str
    mappings: tuple[EventTypeMapping, ...]
    # user_attributes keys copied onto canonical events; everything else is dropped.
    attribute_whitelist: tuple[str, ...] = ("region_code", "cohort_key")

    @model_validator(mode="after")
    def _no_duplicates(self) -> "TenantMappingConfig":
        seen: set[str] = set()
        for m in self.mappings:
            if m.client_event_type in seen:
                raise ValueError(f"duplicate client_event_type {m.client_event_type!r}")
            seen.add(m.client_event_type)
        return self

    @classmethod
    def from_dict(cls, data: dict | str, rows: list[dict] | None = None, *,
                  profile_type: str = "UNSPECIFIED") -> "TenantMappingConfig":
        """Load either a full fixture dict, or (tenant, mapping rows) as the API stores them."""
        if rows is not None:
            return cls(tenant_slug=str(data), profile_type=profile_type,
                       mappings=tuple(EventTypeMapping(**row) for row in rows))
        return cls.model_validate({k: v for k, v in data.items() if not k.startswith("_")})

    def lookup(self, client_event_type: str) -> "EventTypeMapping":
        for m in self.mappings:
            if m.client_event_type == client_event_type:
                if not m.active:
                    raise MappingError(f"event type {client_event_type!r} is inactive")
                return m
        raise MappingError(f"unknown event type {client_event_type!r}")
