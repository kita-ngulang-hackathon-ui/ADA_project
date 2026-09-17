"""Individual hard rules (requirement 7, §4). Pure functions.

Rule codes: RESPONSIBLE_LENDING, FREQUENCY_CAP, NO_CREDIT_DECISION, SEGMENT_EXCLUDED.

TODO:
- RuleResult dataclass (rule_code, allowed, reason).
- One function per rule; thresholds passed in.
"""


def responsible_lending(candidate, user_facts, *, lookback_days: int, min_late_events: int):
    raise NotImplementedError


def frequency_cap(candidate, user_facts, *, max_contacts: int | None, window_days: int | None):
    """Fail closed when the cap is not configured."""
    raise NotImplementedError


def no_credit_decision(candidate):
    raise NotImplementedError


def segment_excluded(candidate):
    raise NotImplementedError
