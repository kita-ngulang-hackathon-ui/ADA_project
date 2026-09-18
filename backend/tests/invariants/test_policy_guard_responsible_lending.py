"""Invariant: Borrowing incentives are always denied to repayment-stressed users (requirement 7, §4).

Holds regardless of ranker output: the guard never sees priorities, and the
pipeline only ranks candidates the guard allowed.
"""
from datetime import UTC, datetime, timedelta

from core_contracts import Candidate, ImpactSegment, PatternType, RuleCode, UserFacts
from policy_guard import PolicyConfig, evaluate

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def test_policy_guard_responsible_lending() -> None:
    stressed = UserFacts(user_pseudonym="u", now=NOW, late_repayment_at=(NOW - timedelta(days=3),))
    for segment_rule in (True, False):
        config = PolicyConfig(60, 1, 99, 14, apply_segment_rule=segment_rule)
        for impact_score in (-1.0, 0.0, 0.99):
            candidate = Candidate(
                candidate_id="c", tenant_id="t", user_pseudonym="u", incentive_code="PAYLATER_DISCOUNT",
                cost_idr=1, business_value_idr=10**9, encourages_borrowing=True, churn_risk=0.99,
                impact_score=impact_score, segment=ImpactSegment.PERSUADABLE,
                pattern_type=PatternType.CIRCLE_SPECIFIC,
            )
            decision = evaluate(candidate, stressed, config)
            assert decision.outcome == "DENY"
            assert RuleCode.RESPONSIBLE_LENDING in {d.rule_code for d in decision.denials}
