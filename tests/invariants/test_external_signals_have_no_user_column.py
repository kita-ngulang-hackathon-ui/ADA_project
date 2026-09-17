"""Invariant: External signals carry no user or counterparty column (§4 external signal boundary).

Covers the ExternalSignal model. The DB table half needs Postgres and lands with the persistence layer.
"""
from datetime import UTC, datetime

import pytest
from core_contracts import ExternalSignal
from external_signals import to_signal
from pydantic import ValidationError

FORBIDDEN = ("user", "counterparty", "pseudonym", "customer", "account")


def test_external_signals_have_no_user_column() -> None:
    for name in ExternalSignal.model_fields:
        assert not any(word in name.lower() for word in FORBIDDEN), name

    base = dict(signal_id="s", source="canned", scope_type="CLIENT", scope_key="demo-wallet",
                signal_type="NEWS_SENTIMENT", value=0.1, observed_at=datetime.now(UTC))
    with pytest.raises(ValidationError):
        ExternalSignal(**base, user_pseudonym="abc")
    with pytest.raises(ValueError):
        to_signal({**base, "scope_type": "USER", "scope_key": "someone"})
