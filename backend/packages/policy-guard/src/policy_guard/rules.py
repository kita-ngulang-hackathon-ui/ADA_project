"""Individual hard rules (requirement 7, §4). Pure functions.

Rule codes: RESPONSIBLE_LENDING, FREQUENCY_CAP, NO_CREDIT_DECISION, SEGMENT_EXCLUDED.
These are guarantees, not predictions.
"""
from datetime import timedelta

from core_contracts import ImpactSegment, RuleCode, RuleResult

EXCLUDED_SEGMENTS = frozenset(
    {ImpactSegment.SURE_THING, ImpactSegment.LOST_CAUSE, ImpactSegment.SLEEPING_DOG}
)


def _ok(code: RuleCode) -> RuleResult:
    return RuleResult(rule_code=code, allowed=True, reason="passed")


def responsible_lending(candidate, user_facts, *, lookback_days: int, min_late_events: int):
    if not candidate.encourages_borrowing:
        return _ok(RuleCode.RESPONSIBLE_LENDING)
    since = user_facts.now - timedelta(days=lookback_days)
    late = sum(1 for t in user_facts.late_repayment_at if since <= t <= user_facts.now)
    if late >= min_late_events:
        return RuleResult(
            rule_code=RuleCode.RESPONSIBLE_LENDING, allowed=False,
            reason=f"borrowing incentive denied: {late} late repayment(s) in {lookback_days} days",
        )
    return _ok(RuleCode.RESPONSIBLE_LENDING)


def frequency_cap(candidate, user_facts, *, max_contacts: int | None, window_days: int | None):
    """Fail closed when the cap is not configured."""
    if max_contacts is None or window_days is None:
        return RuleResult(
            rule_code=RuleCode.FREQUENCY_CAP, allowed=False,
            reason="frequency cap not configured (open decision); failing closed",
        )
    since = user_facts.now - timedelta(days=window_days)
    contacts = sum(1 for t in user_facts.contacted_at if since <= t <= user_facts.now)
    if contacts >= max_contacts:
        return RuleResult(
            rule_code=RuleCode.FREQUENCY_CAP, allowed=False,
            reason=f"{contacts} contact(s) in {window_days} days reaches cap {max_contacts}",
        )
    return _ok(RuleCode.FREQUENCY_CAP)


def no_credit_decision(candidate):
    if candidate.changes_credit_terms:
        return RuleResult(
            rule_code=RuleCode.NO_CREDIT_DECISION, allowed=False,
            reason="incentive changes credit limit or pricing; not an engagement action",
        )
    return _ok(RuleCode.NO_CREDIT_DECISION)


def segment_excluded(candidate):
    if candidate.segment in EXCLUDED_SEGMENTS:
        return RuleResult(
            rule_code=RuleCode.SEGMENT_EXCLUDED, allowed=False,
            reason=f"segment {candidate.segment.value} is not worth an incentive",
        )
    return _ok(RuleCode.SEGMENT_EXCLUDED)
