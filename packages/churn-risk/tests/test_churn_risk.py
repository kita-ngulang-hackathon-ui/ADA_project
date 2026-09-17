"""churn-risk unit tests."""
import builtins
from datetime import UTC, datetime

import pytest
from churn_risk import (
    FEATURE_COLUMNS,
    build_features,
    external_signal_contribution,
    predict_positive,
    score,
    select_context,
    to_row,
)
from churn_risk.classifier import MODEL_STAND_IN
from core_contracts import Arm, ContextTooSmall, CrossTenantContext, LabeledExample

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _example(i: int, tenant: str = "t", retained: bool | None = None) -> LabeledExample:
    freq = float(i % 10)
    return LabeledExample(
        tenant_id=tenant, source_outcome_id=f"{tenant}-{i:04d}", user_pseudonym=f"u{i}",
        features={"frequency_30d": freq, "recency_days": 30.0 - freq * 3},
        arm=Arm.CONTROL, treated=False, retained=freq >= 5 if retained is None else retained,
    )


def test_feature_columns_are_stable() -> None:
    features = build_features([], None, None, now=NOW)
    assert list(features) == FEATURE_COLUMNS
    assert FEATURE_COLUMNS[0] == "recency_days" and FEATURE_COLUMNS[-1] == "external_signal_value"
    assert len(to_row(features)) == len(FEATURE_COLUMNS)


def test_context_from_two_tenants_raises() -> None:
    rows = [_example(i) for i in range(30)] + [_example(99, tenant="other")]
    with pytest.raises(CrossTenantContext):
        select_context(rows, max_rows=100, min_rows=10, seed=1)


def test_context_too_small_and_cap() -> None:
    with pytest.raises(ContextTooSmall):
        select_context([_example(i) for i in range(5)], max_rows=100, min_rows=10, seed=1)
    X, y = select_context([_example(i) for i in range(200)], max_rows=50, min_rows=10, seed=1)
    assert len(X) == len(y) <= 50
    assert set(y) == {0, 1}


def test_stand_in_used_and_labeled_when_tabpfn_missing(monkeypatch) -> None:
    real_import = builtins.__import__

    def no_tabpfn(name, *args, **kwargs):
        if name.startswith("tabpfn"):
            raise ImportError("tabpfn not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_tabpfn)
    X, y = select_context([_example(i) for i in range(60)], max_rows=100, min_rows=10, seed=1)
    scores = score(X, y, [to_row({"frequency_30d": 0.0, "recency_days": 30.0})], seed=1,
                   query_ids=["q"])
    assert scores[0].model == MODEL_STAND_IN
    assert scores[0].user_pseudonym == "q"
    assert scores[0].churn_risk > 0.5
    assert scores[0].context_row_count == len(X)


def test_attribution_zero_without_signal() -> None:
    X, y = select_context([_example(i) for i in range(60)], max_rows=100, min_rows=10, seed=1)

    def score_fn(cX, cy, q):
        return predict_positive(cX, cy, q, seed=1, use_tabpfn=False)[0]

    row = to_row({"frequency_30d": 2.0})
    assert external_signal_contribution(score_fn, X, y, row, "external_signal_value") == 0.0
