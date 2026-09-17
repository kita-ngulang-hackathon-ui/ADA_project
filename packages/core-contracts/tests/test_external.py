"""ExternalSignal boundary tests: no user field, value clamp (README)."""
from datetime import datetime, timezone

import pytest
from core_contracts.external import ExternalSignal, ScopeType, SignalType
from pydantic import ValidationError


def test_valid_signal():
    sig = ExternalSignal(
        scope_type=ScopeType.REGION,
        scope_key="ID-JB",
        signal_type=SignalType.NEWS_SENTIMENT,
        value=-0.62,
        observed_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
        source="canned",
    )
    assert sig.value == -0.62


def test_value_out_of_range_rejected():
    with pytest.raises(ValidationError):
        ExternalSignal(
            scope_type=ScopeType.REGION,
            scope_key="ID-JB",
            signal_type=SignalType.NEWS_SENTIMENT,
            value=1.5,
            observed_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
            source="canned",
        )


def test_no_user_field_can_be_added():
    """extra='forbid' means a user_pseudonym field is rejected outright."""
    with pytest.raises(ValidationError):
        ExternalSignal(
            scope_type=ScopeType.REGION,
            scope_key="ID-JB",
            signal_type=SignalType.NEWS_SENTIMENT,
            value=0.1,
            observed_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
            source="canned",
            user_pseudonym="u_should_not_exist",
        )


def test_model_has_no_user_field_defined():
    fields = ExternalSignal.model_fields
    assert not any("user" in name or "counterparty" in name for name in fields)
