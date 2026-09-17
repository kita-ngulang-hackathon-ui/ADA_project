"""Run all hard rules for a candidate and return a PolicyDecision.

TODO:
- Evaluate every rule, collect all denials.
- outcome = ALLOW only if no rule denies.
"""


def evaluate(candidate, user_facts, config):
    raise NotImplementedError
