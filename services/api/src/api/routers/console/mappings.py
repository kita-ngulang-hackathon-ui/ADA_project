"""GET/POST /console/v1/mappings -- per-tenant event type mapping config
(requirement 1). Onboarding a new client is inserting rows here; no scoring
or decision code changes. `ingest_mapping.EventTypeMapping` validates the
shape before anything is persisted -- this is the one place the API is
allowed to import an L1 package (README: "only for mapping validation")."""
from __future__ import annotations

from core_contracts.events import CanonicalEventType
from fastapi import APIRouter, Depends
from ingest_mapping.mapping_config import EventTypeMapping
from persistence.repositories import mappings as mappings_repo
from pydantic import BaseModel, ValidationError

from api import errors
from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant

router = APIRouter(prefix="/console/v1", tags=["console-mappings"])


class MappingOut(BaseModel):
    client_event_type: str
    canonical_event_type: str
    amount_field_path: str
    counterparty_field_path: str | None
    occurred_at_field_path: str
    active: bool


class MappingIn(BaseModel):
    client_event_type: str
    canonical_event_type: str
    amount_field_path: str
    counterparty_field_path: str | None = None
    occurred_at_field_path: str


@router.get("/mappings")
def list_mappings(console: ConsoleSession = Depends(require_console_reviewer)) -> list[MappingOut]:
    with db_for_tenant(console.tenant_id) as session:
        rows = mappings_repo.list_mappings(session, tenant_id=console.tenant_id)
    return [
        MappingOut(
            client_event_type=r.client_event_type,
            canonical_event_type=r.canonical_event_type,
            amount_field_path=r.amount_field_path,
            counterparty_field_path=r.counterparty_field_path,
            occurred_at_field_path=r.occurred_at_field_path,
            active=r.active,
        )
        for r in rows
    ]


@router.post("/mappings", status_code=201)
def create_mapping(
    body: MappingIn, console: ConsoleSession = Depends(require_console_reviewer)
) -> MappingOut:
    # Validate the shape through ingest_mapping's own model before writing
    # -- this is the "mapping validation" the layer rule carves out.
    try:
        validated = EventTypeMapping(
            client_event_type=body.client_event_type,
            canonical_event_type=CanonicalEventType(body.canonical_event_type),
            amount_field_path=body.amount_field_path,
            counterparty_field_path=body.counterparty_field_path,
            occurred_at_field_path=body.occurred_at_field_path,
        )
    except (ValidationError, ValueError) as exc:
        raise errors.validation_failed(str(exc)) from exc

    with db_for_tenant(console.tenant_id) as session:
        row = mappings_repo.upsert_mapping(
            session,
            tenant_id=console.tenant_id,
            client_event_type=validated.client_event_type,
            canonical_event_type=validated.canonical_event_type.value,
            amount_field_path=validated.amount_field_path,
            counterparty_field_path=validated.counterparty_field_path,
            occurred_at_field_path=validated.occurred_at_field_path,
        )
    return MappingOut(
        client_event_type=row.client_event_type,
        canonical_event_type=row.canonical_event_type,
        amount_field_path=row.amount_field_path,
        counterparty_field_path=row.counterparty_field_path,
        occurred_at_field_path=row.occurred_at_field_path,
        active=row.active,
    )
