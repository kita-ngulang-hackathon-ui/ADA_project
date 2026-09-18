"""Measurement and feedback types (requirements 10, 11)."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Arm(str, Enum):
    CONTROL = "CONTROL"  # randomly withheld from otherwise-qualifying candidates
    NAIVE = "NAIVE"  # risk-score-only targeting, no impact model, no optimization
    ENGINE = "ENGINE"  # full Decision Engine output


class FeatureSnapshot(BaseModel):
    """Features and scores captured at recommendation time, keyed by (run_id, user_pseudonym).

    Feedback uses this snapshot, never later data, so labeled examples do not leak outcomes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    run_id: str
    user_pseudonym: str
    features: dict[str, float]
    churn_risk: float | None = None
    impact_score: float | None = None
    pattern_type: str | None = None
    incentive_code: str | None = None
    cost_idr: int = 0
    business_value_idr: int = 0


class OutcomeEvent(BaseModel):
    """Observed result for one user in one run after the observation window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome_event_id: str
    tenant_id: str
    run_id: str
    user_pseudonym: str
    arm: Arm
    treated: bool
    retained: bool
    spend_idr: int = 0
    observed_at: datetime


class LabeledExample(BaseModel):
    """One in-context row for the next TabPFN calls (churn-risk, impact, ranker)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    source_outcome_id: str
    user_pseudonym: str
    features: dict[str, float]
    arm: Arm
    treated: bool
    retained: bool
    churn_risk: float | None = None
    impact_score: float | None = None
    pattern_type: str | None = None
    incentive_code: str | None = None
    cost_idr: int = 0
    business_value_idr: int = 0
    # Proxy target for the ranker: value kept (retained * business value) minus spend.
    realized_value_idr: float = 0.0
