"""Per-tenant event mapping config (requirement 1).

Onboarding a new client is inserting rows here -- no scoring or decision
code changes.
"""
from __future__ import annotations

from core_contracts.errors import MappingError
from core_contracts.events import CanonicalEventType
from pydantic import BaseModel, ConfigDict, field_validator


class EventTypeMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_event_type: str
    canonical_event_type: CanonicalEventType
    amount_field_path: str
    counterparty_field_path: str | None = None
    occurred_at_field_path: str
    active: bool = True


class TenantMappingConfig(BaseModel):
    """A validated, lookup-ready set of mappings for one tenant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    mappings: tuple[EventTypeMapping, ...]

    @field_validator("mappings")
    @classmethod
    def _no_duplicate_client_event_type(
        cls, v: tuple[EventTypeMapping, ...]
    ) -> tuple[EventTypeMapping, ...]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for m in v:
            if m.client_event_type in seen:
                duplicates.add(m.client_event_type)
            seen.add(m.client_event_type)
        if duplicates:
            raise ValueError(f"duplicate client_event_type rows: {sorted(duplicates)}")
        return v

    def lookup(self, client_event_type: str) -> EventTypeMapping:
        for m in self.mappings:
            if m.client_event_type == client_event_type and m.active:
                return m
        raise MappingError(
            f"no active mapping for client_event_type={client_event_type!r} "
            f"in tenant {self.tenant_id!r}"
        )

    @classmethod
    def from_dict(cls, tenant_id: str, rows: list[dict]) -> TenantMappingConfig:
        """Loader from plain dicts (the API reads JSON from DB/fixtures and
        passes it in as this shape)."""
        return cls(
            tenant_id=tenant_id,
            mappings=tuple(EventTypeMapping(**row) for row in rows),
        )
