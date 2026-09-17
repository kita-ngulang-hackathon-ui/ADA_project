"""explain unit tests."""
from datetime import UTC, datetime

import pytest
from core_contracts import (
    Arm,
    Candidate,
    CircleSnapshot,
    ExternalSignal,
    ImpactScore,
    ImpactSegment,
    NarrationRejected,
    PatternType,
    PolicyDecision,
    RankedCandidate,
    RankingStrategy,
    RiskScore,
    RuleCode,
    RuleResult,
)
from explain import (
    build_fact_sheet,
    build_prompt,
    fact_sheet_hash,
    render_template,
    validate_narration,
)

USER = "9f2c4e1a7b3d5f60aa11bb22cc33dd44"


def _ranked(code: str, cost: int, priority: float) -> RankedCandidate:
    c = Candidate(candidate_id=f"cand-{code}", tenant_id="t", user_pseudonym=USER, incentive_code=code,
                  cost_idr=cost, business_value_idr=450_000, churn_risk=0.71, impact_score=0.41,
                  segment=ImpactSegment.PERSUADABLE, pattern_type=PatternType.CIRCLE_SPECIFIC)
    return RankedCandidate(candidate=c, priority=priority, ranking_strategy=RankingStrategy.FALLBACK)


def _sheet(with_extras: bool = True):
    top, runner = _ranked("CASHBACK_25K", 25_000, 184_500.0), _ranked("FEE_WAIVER", 7_500, 120_333.337)
    risk = RiskScore(user_pseudonym=USER, churn_risk=0.7123, model="SKLEARN_RANDOM_FOREST",
                     context_row_count=400, external_signal_contribution=0.0321)
    circle = CircleSnapshot(user_pseudonym=USER, circle_size=6, neighbor_activity_ratio_now=0.33,
                            neighbor_activity_ratio_30d_ago=0.83, delta_stability=-0.5,
                            pattern_type=PatternType.CIRCLE_SPECIFIC)
    impact = ImpactScore(p_incentivized=0.64, p_not_incentivized=0.23, model="m")
    signal = ExternalSignal(signal_id="s1", source="canned", scope_type="COHORT", scope_key="cohort-3",
                            signal_type="SECTOR_TREND", value=-0.62,
                            observed_at=datetime(2026, 9, 16, tzinfo=UTC))
    policy = PolicyDecision(candidate_id=top.candidate.candidate_id, user_pseudonym=USER, outcome="ALLOW",
                            results=(RuleResult(rule_code=RuleCode.FREQUENCY_CAP, allowed=True, reason="ok"),))
    return build_fact_sheet(
        top, risk, impact if with_extras else None, circle if with_extras else None, policy,
        {"strategy": "EXACT_DP", "budget_idr": 5_000_000, "spent_idr": 4_975_000, "selected_count": 12, "rank": 3},
        runner_up=runner if with_extras else None,
        display_names={"CASHBACK_25K": "Cashback Rp 25.000", "FEE_WAIVER": "Free transfers"},
        external_signal=signal if with_extras else None, arm=Arm.ENGINE,
    )


def test_same_fact_sheet_same_hash() -> None:
    assert fact_sheet_hash(_sheet()) == fact_sheet_hash(_sheet())
    assert fact_sheet_hash(_sheet()) != fact_sheet_hash(_sheet(with_extras=False))


def test_template_passes_validator_for_every_sheet() -> None:
    for sheet in (_sheet(), _sheet(with_extras=False)):
        text = render_template(sheet)
        validate_narration(text, sheet)
        assert "synthetic" in text
    assert "Runner-up" in render_template(_sheet())


def test_narration_with_invented_number_rejected() -> None:
    sheet = _sheet()
    validate_narration("Churn risk is 71% and the incentive costs Rp 25.000.", sheet)
    with pytest.raises(NarrationRejected):
        validate_narration("Churn risk is 93%.", sheet)
    with pytest.raises(NarrationRejected):
        validate_narration("Give them Rp 50.000 instead.", sheet)


def test_unknown_identifier_and_length_rejected() -> None:
    sheet = _sheet()
    validate_narration(f"User {USER} is at risk.", sheet)
    with pytest.raises(NarrationRejected):
        validate_narration("User deadbeefdeadbeefdeadbeef is at risk.", sheet)
    with pytest.raises(NarrationRejected):
        validate_narration("word " * 400, sheet)


def test_prompt_contains_only_the_sheet() -> None:
    system, user = build_prompt(_sheet())
    assert "ONLY" in system
    assert '"synthetic_data":true' in user
