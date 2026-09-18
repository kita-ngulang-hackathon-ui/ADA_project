"""Client ingestion API (`/v1`, requirement 1). Bearer API key -> tenant; every
write here runs on the worker-role engine (`db_for_ingest`), the only role
migration 0006 grants INSERT on raw_events / outcome_events.

Validates request shape only; never maps or scores inline (that is the
worker's job, once it picks up an unprocessed raw_events row). Every
endpoint here must stay fast -- the client's own transaction never depends
on this call succeeding (§4, "no client-side SDK", never in the critical
path).
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from core_contracts.errors import IllegalTransition
from fastapi import APIRouter, Depends, Query
from persistence.repositories import events as events_repo
from persistence.repositories import measurement as measurement_repo
from persistence.repositories import recommendations as recommendations_repo
from pydantic import BaseModel, Field, ValidationError, field_validator

from api import errors
from api.auth import require_tenant_api_key
from api.deps import db_for_ingest
from api.rate_limit import get_ingest_limiter
from api.settings import get_settings

router = APIRouter(prefix="/v1", tags=["ingestion"])

log = logging.getLogger(__name__)


def _first_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(p) for p in first["loc"]) or "body"
    return f"{location}: {first['msg']}"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _rfc3339_or_raise(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid RFC 3339 timestamp") from exc


class RawEventIn(BaseModel):
    client_event_id: str
    event_type: str
    occurred_at: str
    user_ref: str
    user_attributes: dict[str, str] | None = None
    payload: dict = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def _rfc3339(cls, v: str) -> str:
        _rfc3339_or_raise(v, "occurred_at")
        return v


class EventAccepted(BaseModel):
    accepted: bool = True
    raw_event_id: str
    duplicate: bool


@router.post("/events", status_code=202)
def post_event(
    body: RawEventIn,
    tenant_id: str = Depends(require_tenant_api_key),
) -> EventAccepted:
    settings = get_settings()
    get_ingest_limiter(settings.ingest_rate_limit_per_min).check(tenant_id)

    with db_for_ingest(tenant_id) as session:
        raw_event_id, duplicate = events_repo.insert_raw_event(
            session,
            tenant_id=tenant_id,
            client_event_id=body.client_event_id,
            payload=body.model_dump(mode="json"),
        )
    return EventAccepted(raw_event_id=str(raw_event_id), duplicate=duplicate)


class BatchIn(BaseModel):
    # Raw dicts, validated one by one below: a single malformed event must not
    # reject the whole batch, which is what `list[RawEventIn]` would do here.
    events: list[dict]


class RejectedEvent(BaseModel):
    index: int
    client_event_id: str | None
    code: str
    message: str


class BatchAccepted(BaseModel):
    accepted_count: int
    duplicate_count: int
    rejected: list[RejectedEvent]


@router.post("/events:batch", status_code=202)
def post_events_batch(
    body: BatchIn,
    tenant_id: str = Depends(require_tenant_api_key),
) -> BatchAccepted:
    settings = get_settings()
    get_ingest_limiter(settings.ingest_rate_limit_per_min).check(tenant_id)

    if len(body.events) > settings.ingest_max_batch_size:
        raise errors.payload_too_large(
            f"batch of {len(body.events)} exceeds INGEST_MAX_BATCH_SIZE={settings.ingest_max_batch_size}"
        )

    accepted = 0
    duplicates = 0
    rejected: list[RejectedEvent] = []

    with db_for_ingest(tenant_id) as session:
        for i, raw in enumerate(body.events):
            client_event_id = raw.get("client_event_id") if isinstance(raw, dict) else None
            try:
                event = RawEventIn.model_validate(raw)
            except ValidationError as exc:
                rejected.append(RejectedEvent(index=i, client_event_id=client_event_id,
                                              code="VALIDATION_FAILED", message=_first_error(exc)))
                continue
            try:
                # A savepoint per row: without it the first failed INSERT aborts
                # the transaction and every later row fails with it.
                with session.begin_nested():
                    _raw_id, is_dup = events_repo.insert_raw_event(
                        session,
                        tenant_id=tenant_id,
                        client_event_id=event.client_event_id,
                        payload=event.model_dump(mode="json"),
                    )
            except Exception:
                log.exception("batch event %s could not be stored", i)
                rejected.append(RejectedEvent(index=i, client_event_id=event.client_event_id,
                                              code="INTERNAL", message="event could not be stored"))
                continue
            if is_dup:
                duplicates += 1
            else:
                accepted += 1

    return BatchAccepted(accepted_count=accepted, duplicate_count=duplicates, rejected=rejected)


# ---------------------------------------------------------------------------
# Outcomes (requirement 10, 11)
# ---------------------------------------------------------------------------


class OutcomeIn(BaseModel):
    client_outcome_id: str
    user_ref: str
    experiment_id: str
    outcome_type: Literal["RESPONDED", "RETAINED", "CHURNED"]
    observed_at: str
    value_idr: int | None = None

    @field_validator("observed_at")
    @classmethod
    def _rfc3339(cls, v: str) -> str:
        _rfc3339_or_raise(v, "observed_at")
        return v


@router.post("/outcomes", status_code=202)
def post_outcome(body: OutcomeIn, tenant_id: str = Depends(require_tenant_api_key)) -> dict:
    settings = get_settings()
    get_ingest_limiter(settings.ingest_rate_limit_per_min).check(tenant_id)

    try:
        experiment_uuid = uuid.UUID(body.experiment_id)
    except ValueError as exc:
        raise errors.validation_failed("experiment_id is not a valid id") from exc

    observed_at = _rfc3339_or_raise(body.observed_at, "observed_at")
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    with db_for_ingest(tenant_id) as session:
        experiment = measurement_repo.get_experiment(session, tenant_id=tenant_id, experiment_id=experiment_uuid)
        if experiment is None:
            raise errors.not_found(f"experiment {body.experiment_id} not found")
        # user_ref here is already the pseudonym the client was given back
        # by a prior recommendation pull -- ingestion never re-derives a raw
        # user_ref into a pseudonym outside the worker's mapping boundary.
        measurement_repo.record_outcome(
            session,
            tenant_id=tenant_id,
            experiment_id=experiment_uuid,
            user_pseudonym=body.user_ref,
            outcome_type=body.outcome_type,
            value_idr=body.value_idr,
            observed_at=observed_at,
        )
    return {"accepted": True}


# ---------------------------------------------------------------------------
# Recommendations pull (requirement 8) -- APPROVED only, ever.
# ---------------------------------------------------------------------------


class RecommendationOut(BaseModel):
    recommendation_id: str
    subject_type: str
    user_pseudonym: str | None
    circle_id: str | None
    incentive_code: str
    cost_idr: int
    reason_text: str | None
    approved_at: str | None
    expires_at: str | None


class RecommendationList(BaseModel):
    items: list[RecommendationOut]
    next_cursor: str | None = None


@router.get("/recommendations")
def list_approved_recommendations(
    status: str = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: int = Query(default=0),
    tenant_id: str = Depends(require_tenant_api_key),
) -> RecommendationList:
    if status != "APPROVED":
        # A client cannot see a recommendation that has not cleared human
        # approval, and never sees an unapproved runner-up.
        raise errors.forbidden("status must be APPROVED; no other value is ever returned on this surface")

    with db_for_ingest(tenant_id) as session:
        rows = recommendations_repo.list_approved(session, tenant_id=tenant_id, limit=limit, offset=cursor)

    items = [
        RecommendationOut(
            recommendation_id=str(r.id),
            subject_type=r.subject_type,
            user_pseudonym=r.user_pseudonym,
            circle_id=str(r.circle_id) if r.circle_id else None,
            incentive_code=r.incentive_code,
            cost_idr=r.cost_idr,
            reason_text=r.reason_text,
            approved_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            expires_at=None,
        )
        for r in rows
    ]
    next_cursor = str(cursor + limit) if len(rows) == limit else None
    return RecommendationList(items=items, next_cursor=next_cursor)


class DeliveryAckIn(BaseModel):
    delivered_at: str
    delivery_ref: str | None = None
    channel: str | None = None


@router.post("/recommendations/{recommendation_id}/delivery-ack")
def delivery_ack(
    recommendation_id: str,
    body: DeliveryAckIn,
    tenant_id: str = Depends(require_tenant_api_key),
) -> dict:
    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError as exc:
        raise errors.not_found("recommendation not found") from exc

    with db_for_ingest(tenant_id) as session:
        try:
            row = recommendations_repo.mark_delivered(
                session, tenant_id=tenant_id, recommendation_id=rec_uuid, delivery_ref=body.delivery_ref
            )
        except LookupError as exc:
            raise errors.not_found(str(exc)) from exc
        except IllegalTransition as exc:
            raise errors.conflict(str(exc)) from exc

    return {"recommendation_id": str(row.id), "status": row.status}
