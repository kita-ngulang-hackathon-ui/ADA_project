"""ranker unit tests."""
import pytest
from core_contracts import (
    Arm,
    Candidate,
    CrossTenantContext,
    ImpactSegment,
    LabeledExample,
    PatternType,
    RankingStrategy,
)
from ranker import build_context, rank


def _candidate(cid: str, impact: float, value: int) -> Candidate:
    return Candidate(candidate_id=cid, tenant_id="t", user_pseudonym=cid, incentive_code="X",
                     cost_idr=1000, business_value_idr=value, churn_risk=0.5, impact_score=impact,
                     segment=ImpactSegment.PERSUADABLE, pattern_type=PatternType.STABLE)


def _example(i: int, tenant: str = "t") -> LabeledExample:
    return LabeledExample(tenant_id=tenant, source_outcome_id=f"o{i:04d}", user_pseudonym=f"u{i}",
                          features={}, arm=Arm.ENGINE, treated=True, retained=i % 2 == 0,
                          churn_risk=0.5, impact_score=i / 100, pattern_type="STABLE",
                          cost_idr=1000, business_value_idr=100_000,
                          realized_value_idr=float(i * 1000))


def test_fallback_used_and_labeled_below_min_context() -> None:
    ranked = rank(build_context([_example(1)]), [_candidate("a", 0.2, 1000), _candidate("b", 0.1, 5000)],
                  min_context_rows=100, seed=1)
    assert all(r.ranking_strategy == RankingStrategy.FALLBACK for r in ranked)
    assert [r.candidate.candidate_id for r in ranked] == ["b", "a"]
    assert ranked[0].priority == pytest.approx(500.0)


def test_equal_priorities_are_ordered_deterministically() -> None:
    cands = [_candidate(c, 0.1, 1000) for c in ("c", "a", "b")]
    first = rank(None, cands, min_context_rows=1, seed=1)
    second = rank(None, list(reversed(cands)), min_context_rows=1, seed=1)
    assert [r.candidate.candidate_id for r in first] == ["a", "b", "c"]
    assert first == second


def test_model_path_used_with_enough_context() -> None:
    context = build_context([_example(i) for i in range(40)])
    ranked = rank(context, [_candidate("a", 0.35, 100_000)], min_context_rows=20, seed=1,
                  use_tabpfn=False)
    assert ranked[0].ranking_strategy == RankingStrategy.SKLEARN_STAND_IN


def test_context_rejects_multiple_tenants() -> None:
    with pytest.raises(CrossTenantContext):
        build_context([_example(1), _example(2, tenant="other")])
