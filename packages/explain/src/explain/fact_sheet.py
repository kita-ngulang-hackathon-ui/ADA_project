"""Fact sheet: the only information the narrator may use (requirement 9).

TODO:
- Assemble FactSheet from upstream results (top pick + runner-up).
- Canonical JSON (sorted keys) -> sha256 -> fact_sheet_hash.
- Include synthetic_data flag (honesty rule, §4).
"""


def build_fact_sheet(candidate, risk, impact, circle, policy, allocation):
    raise NotImplementedError


def fact_sheet_hash(fact_sheet) -> str:
    raise NotImplementedError
