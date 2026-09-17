"""Score types produced by churn-risk and impact (requirements 3, 6)."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class ImpactSegment(str, Enum):
    PERSUADABLE = "PERSUADABLE"
    SURE_THING = "SURE_THING"
    LOST_CAUSE = "LOST_CAUSE"
    SLEEPING_DOG = "SLEEPING_DOG"


class RiskScore(BaseModel):
    """Output of churn-risk (requirement 3). churn_risk and delta_stability are
    never pre-blended — ADR-013."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    churn_risk: float
    model: str
    external_signal_contribution: float | None = None
    context_row_count: int

    @field_validator("churn_risk")
    @classmethod
    def _range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("churn_risk must be in [0, 1]")
        return v

    @field_validator("context_row_count")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("context_row_count must be non-negative")
        return v


class ImpactScore(BaseModel):
    """Output of the Intervention Impact Engine (requirement 6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    p_incentivized: float
    p_not_incentivized: float
    impact_score: float

    @field_validator("p_incentivized", "p_not_incentivized")
    @classmethod
    def _prob_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("probabilities must be in [0, 1]")
        return v


class ReasonFactor(BaseModel):
    """One factor cited in a human-readable explanation (requirement 9)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    direction: str
    weight: float
    evidence: dict[str, int | float | str | bool | None] = {}
