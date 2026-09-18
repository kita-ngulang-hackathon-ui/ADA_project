"""CanonicalEvent invariants (README "Tests to write")."""
from datetime import datetime, timezone

import pytest
from core_contracts.events import CanonicalEvent, CanonicalEventType
from pydantic import ValidationError


def _base_kwargs(**overrides):
    kwargs = dict(
        tenant_id="t1",
        client_event_id="evt_1",
        event_type=CanonicalEventType.P2P_TRANSFER,
        occurred_at=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        user_pseudonym="u_abc",
        counterparty_pseudonym="u_def",
        amount_idr=150000,
        attributes={},
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_event_constructs():
    event = CanonicalEvent(**_base_kwargs())
    assert event.amount_idr == 150000


def test_amount_must_be_int_not_float():
    with pytest.raises(ValidationError):
        CanonicalEvent(**_base_kwargs(amount_idr=150000.5))


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        CanonicalEvent(**_base_kwargs(occurred_at=datetime(2026, 9, 17, 10, 0)))


def test_unknown_attribute_key_rejected():
    with pytest.raises(ValidationError):
        CanonicalEvent(**_base_kwargs(attributes={"device_id": "abc123"}))


def test_frozen_and_extra_forbidden():
    event = CanonicalEvent(**_base_kwargs())
    with pytest.raises(ValidationError):
        event.amount_idr = 1
    with pytest.raises(ValidationError):
        CanonicalEvent(**_base_kwargs(), unexpected_field="x")
