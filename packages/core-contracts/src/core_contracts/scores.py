"""Score types produced by churn-risk and impact (requirements 3, 6).

TODO:
- RiskScore (churn_risk, model name, external_signal_contribution, context_row_count).
- ImpactScore (p_incentivized, p_not_incentivized, impact_score = difference).
- ImpactSegment enum: PERSUADABLE, SURE_THING, LOST_CAUSE, SLEEPING_DOG.
- ReasonFactor (code, direction, weight, evidence) used by explain.
"""
from enum import Enum


class ImpactSegment(str, Enum):
    """TODO."""


class RiskScore:
    """TODO."""


class ImpactScore:
    """TODO."""


class ReasonFactor:
    """TODO."""
