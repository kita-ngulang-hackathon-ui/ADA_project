"""policy-guard unit tests."""
from datetime import UTC, datetime, timedelta

from core_contracts import Candidate, ImpactSegment, PatternType, RuleCode, UserFacts
from policy_guard import PolicyConfig, evaluate

NOW = datetime(2026, 9, 17, tzinfo=UTC)
CONFIG = PolicyConfig(responsible_lending_lookback_days=60, responsible_lending_min_late_events=1,
                      frequency_cap_max_contacts=3, frequency_cap_window_days=14)


def _candidate(**overrides) -> Candidate:
    values = dict(candidate_id="c1", tenant_id="t", user_pseudonym="u", incentive_code="X",
                  cost_idr=10000, business_value_idr=100000, churn_risk=0.7, impact_score=0.3,
                  segment=ImpactSegment.PERSUADABLE, pattern_type=PatternType.CIRCLE_SPECIFIC)
    values.update(overrides)
    return Candidate(**values)


def _facts(late=(), contacts=()) -> UserFacts:
    return UserFacts(user_pseudonym="u", now=NOW, late_repayment_at=tuple(late),
                     contacted_at=tuple(contacts))


def test_clean_candidate_allowed() -> None:
    assert evaluate(_candidate(), _facts(), CONFIG).outcome == "ALLOW"


def test_repayment_stressed_user_never_gets_borrowing_incentive() -> None:
    decision = evaluate(_candidate(encourages_borrowing=True), _facts(late=[NOW - timedelta(days=5)]), CONFIG)
    assert decision.outcome == "DENY"
    assert RuleCode.RESPONSIBLE_LENDING in {d.rule_code for d in decision.denials}
    # Old lateness outside the lookback does not count.
    assert evaluate(_candidate(encourages_borrowing=True),
                    _facts(late=[NOW - timedelta(days=90)]), CONFIG).outcome == "ALLOW"
    # Non-borrowing incentives are unaffected.
    assert evaluate(_candidate(), _facts(late=[NOW]), CONFIG).outcome == "ALLOW"


def test_missing_cap_config_denies_everything() -> None:
    config = PolicyConfig(60, 1, None, None)
    decision = evaluate(_candidate(), _facts(), config)
    assert decision.outcome == "DENY"
    assert [d.rule_code for d in decision.denials] == [RuleCode.FREQUENCY_CAP]


def test_frequency_cap_reached() -> None:
    decision = evaluate(_candidate(), _facts(contacts=[NOW - timedelta(days=d) for d in (1, 2, 3)]), CONFIG)
    assert RuleCode.FREQUENCY_CAP in {d.rule_code for d in decision.denials}


def test_all_denial_reasons_reported() -> None:
    decision = evaluate(
        _candidate(encourages_borrowing=True, changes_credit_terms=True, segment=ImpactSegment.LOST_CAUSE),
        _facts(late=[NOW], contacts=[NOW] * 3), CONFIG,
    )
    assert {d.rule_code for d in decision.denials} == set(RuleCode)


def test_segment_rule_can_be_skipped_for_naive_arm_only() -> None:
    naive = PolicyConfig(60, 1, 3, 14, apply_segment_rule=False)
    assert evaluate(_candidate(segment=ImpactSegment.SURE_THING), _facts(), naive).outcome == "ALLOW"
    assert evaluate(_candidate(segment=ImpactSegment.SURE_THING, encourages_borrowing=True),
                    _facts(late=[NOW]), naive).outcome == "DENY"
