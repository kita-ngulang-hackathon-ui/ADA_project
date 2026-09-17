"""external-signals unit tests."""
from datetime import UTC, datetime, timedelta

import pytest
from core_contracts import ScopeType
from external_signals import resolve_for_user, to_signal

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _item(scope: str, key: str, value: float = -0.4, age_days: int = 1) -> dict:
    return {"source": "canned", "scope_type": scope, "scope_key": key,
            "signal_type": "NEWS_SENTIMENT", "value": value,
            "observed_at": (NOW - timedelta(days=age_days)).isoformat(), "headline": "h"}


def test_value_is_clamped() -> None:
    assert to_signal(_item("CLIENT", "demo-wallet", value=3.0)).value == 1.0
    assert to_signal(_item("CLIENT", "demo-wallet", value=-7)).value == -1.0


def test_user_scope_rejected() -> None:
    with pytest.raises(ValueError):
        to_signal(_item("USER", "someone"))


def test_specificity_order_cohort_region_client() -> None:
    signals = [to_signal(_item("CLIENT", "w")), to_signal(_item("REGION", "ID-JK")),
               to_signal(_item("COHORT", "c1"))]
    kwargs = dict(tenant_slug="w", now=NOW, max_age_days=14)
    assert resolve_for_user(signals, region_code="ID-JK", cohort_key="c1", **kwargs).scope_type == ScopeType.COHORT
    assert resolve_for_user(signals, region_code="ID-JK", cohort_key="c9", **kwargs).scope_type == ScopeType.REGION
    assert resolve_for_user(signals, region_code=None, cohort_key=None, **kwargs).scope_type == ScopeType.CLIENT
    assert resolve_for_user(signals, tenant_slug="other", region_code=None, cohort_key=None,
                            now=NOW, max_age_days=14) is None


def test_stale_signals_ignored() -> None:
    signals = [to_signal(_item("COHORT", "c1", age_days=30)), to_signal(_item("CLIENT", "w"))]
    found = resolve_for_user(signals, tenant_slug="w", region_code=None, cohort_key="c1",
                             now=NOW, max_age_days=14)
    assert found.scope_type == ScopeType.CLIENT
