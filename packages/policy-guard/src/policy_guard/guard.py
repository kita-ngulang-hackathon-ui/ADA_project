"""Run all hard rules for a candidate and return a PolicyDecision.

Every rule runs and every denial is reported, not only the first.
outcome = ALLOW only if no rule denies.
"""
from dataclasses import dataclass

from core_contracts import PolicyDecision

from policy_guard import rules


@dataclass(frozen=True)
class PolicyConfig:
    responsible_lending_lookback_days: int
    responsible_lending_min_late_events: int
    frequency_cap_max_contacts: int | None
    frequency_cap_window_days: int | None
    # The naive measurement arm ignores the impact model, so it skips the segment rule
    # but never the hard guarantees above.
    apply_segment_rule: bool = True


def evaluate(candidate, user_facts, config: PolicyConfig) -> PolicyDecision:
    results = [
        rules.responsible_lending(
            candidate, user_facts,
            lookback_days=config.responsible_lending_lookback_days,
            min_late_events=config.responsible_lending_min_late_events,
        ),
        rules.frequency_cap(
            candidate, user_facts,
            max_contacts=config.frequency_cap_max_contacts,
            window_days=config.frequency_cap_window_days,
        ),
        rules.no_credit_decision(candidate),
    ]
    if config.apply_segment_rule:
        results.append(rules.segment_excluded(candidate))
    outcome = "ALLOW" if all(r.allowed for r in results) else "DENY"
    return PolicyDecision(
        candidate_id=candidate.candidate_id,
        user_pseudonym=candidate.user_pseudonym,
        outcome=outcome,
        results=tuple(results),
    )
