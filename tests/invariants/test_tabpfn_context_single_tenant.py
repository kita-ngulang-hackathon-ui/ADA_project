"""Invariant: TabPFN context builders reject multi-tenant rows (§4 no cross-client sharing)."""
import pytest
from churn_risk import select_context
from core_contracts import Arm, CrossTenantContext, LabeledExample
from impact import estimate_batch
from ranker import build_context


def _row(i: int, tenant: str, treated: bool = True) -> LabeledExample:
    return LabeledExample(tenant_id=tenant, source_outcome_id=f"{tenant}-{i}", user_pseudonym=f"u{i}",
                          features={"f": float(i)}, arm=Arm.ENGINE, treated=treated,
                          retained=i % 2 == 0, churn_risk=0.5, impact_score=0.1)


def test_tabpfn_context_single_tenant() -> None:
    mixed = [_row(i, "tenant-a") for i in range(50)] + [_row(0, "tenant-b")]
    with pytest.raises(CrossTenantContext):
        select_context(mixed, max_rows=1000, min_rows=1, seed=1)
    with pytest.raises(CrossTenantContext):
        build_context(mixed)
    control = [_row(i, "tenant-a", treated=False) for i in range(50)]
    with pytest.raises(CrossTenantContext):
        estimate_batch(mixed, control, [{"f": 1.0}], seed=1, min_rows=1)
