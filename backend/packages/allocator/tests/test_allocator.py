"""allocator unit tests."""
import itertools

from allocator import (
    STRATEGY_DP,
    STRATEGY_GREEDY,
    AllocatorConfig,
    KnapsackItem,
    allocate,
    knapsack,
)
from core_contracts import (
    Candidate,
    ExclusionReason,
    ImpactSegment,
    PatternType,
    RankedCandidate,
    RankingStrategy,
)

CONFIG = AllocatorConfig(strategy="auto", cost_scale_idr=1000, max_dp_cells=1_000_000)


def _ranked(cid: str, user: str, cost: int, priority: float, group: str | None = None,
            code: str = "X", segment=ImpactSegment.PERSUADABLE) -> RankedCandidate:
    c = Candidate(candidate_id=cid, tenant_id="t", user_pseudonym=user, incentive_code=code,
                  cost_idr=cost, business_value_idr=100_000, group_id=group, churn_risk=0.5,
                  impact_score=0.2, segment=segment, pattern_type=PatternType.STABLE)
    return RankedCandidate(candidate=c, priority=priority, ranking_strategy=RankingStrategy.FALLBACK)


def test_dp_is_optimal_on_small_cases() -> None:
    items = [KnapsackItem(f"i{n}", f"u{n}", cost, value, (f"i{n}",))
             for n, (cost, value) in enumerate([(5000, 10), (4000, 7), (3000, 6), (2000, 3)])]
    chosen = knapsack.solve(items, budget_idr=9000, cost_scale_idr=1000, max_dp_cells=10_000)
    best = max(
        (combo for r in range(len(items) + 1) for combo in itertools.combinations(items, r)
         if sum(i.cost_idr for i in combo) <= 9000),
        key=lambda combo: sum(i.value for i in combo),
    )
    assert sum(i.value for i in items if i.item_id in chosen) == sum(i.value for i in best) == 17


def test_one_pick_per_user_with_runner_up() -> None:
    result = allocate([_ranked("a1", "u", 1000, 10.0, code="A"), _ranked("a2", "u", 1000, 8.0, code="B")],
                      budget_idr=10_000, config=CONFIG)
    by_id = {d.candidate_id: d for d in result.decisions}
    assert by_id["a1"].selected and by_id["a1"].rank == 1
    assert not by_id["a2"].selected and by_id["a2"].is_runner_up
    assert by_id["a2"].exclusion_reason == ExclusionReason.RUNNER_UP
    assert result.strategy == STRATEGY_DP


def test_group_bundle_never_partially_selected() -> None:
    group = [_ranked(f"g{i}", f"m{i}", 3000, 5.0, group="circle-1") for i in range(3)]
    result = allocate(group + [_ranked("solo", "s", 4000, 6.0)], budget_idr=8000, config=CONFIG)
    selected = {d.candidate_id for d in result.selected}
    assert not ({"g0", "g1", "g2"} & selected) or {"g0", "g1", "g2"} <= selected
    assert selected == {"solo"}  # bundle costs 9000 > budget
    result = allocate(group, budget_idr=9000, config=CONFIG)
    assert {d.candidate_id for d in result.selected} == {"g0", "g1", "g2"}


def test_persuadable_beats_higher_risk_lost_cause() -> None:
    persuadable = _ranked("p", "persuadable", 5000, 40_000.0)
    lost_cause = _ranked("l", "lost", 5000, 0.0, segment=ImpactSegment.LOST_CAUSE)
    result = allocate([lost_cause, persuadable], budget_idr=5000, config=CONFIG)
    by_id = {d.candidate_id: d for d in result.decisions}
    assert by_id["p"].selected
    assert by_id["l"].exclusion_reason == ExclusionReason.NO_EXPECTED_GAIN


def test_budget_exhausted_reason_and_spend() -> None:
    result = allocate([_ranked("a", "u1", 6000, 10.0), _ranked("b", "u2", 6000, 9.0)],
                      budget_idr=7000, config=CONFIG)
    by_id = {d.candidate_id: d for d in result.decisions}
    assert by_id["a"].selected and by_id["b"].exclusion_reason == ExclusionReason.BUDGET_EXHAUSTED
    assert result.spent_idr == 6000 and result.objective_value_idr == 10.0


def test_greedy_fallback_above_cell_limit() -> None:
    tiny = AllocatorConfig(strategy="auto", cost_scale_idr=1, max_dp_cells=10)
    result = allocate([_ranked("a", "u1", 1000, 10.0)], budget_idr=5000, config=tiny)
    assert result.strategy == STRATEGY_GREEDY
    assert [d.candidate_id for d in result.selected] == ["a"]
