"""Score types produced by churn-risk and impact (requirements 3, 6)."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, computed_field


class ImpactSegment(str, Enum):
    PERSUADABLE = "PERSUADABLE"
    SURE_THING = "SURE_THING"
    LOST_CAUSE = "LOST_CAUSE"
    SLEEPING_DOG = "SLEEPING_DOG"


class RiskScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_pseudonym: str
    churn_risk: float
    model: str
    context_row_count: int
    external_signal_id: str | None = None
    external_signal_contribution: float = 0.0


class ImpactScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    p_incentivized: float
    p_not_incentivized: float
    model: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def impact_score(self) -> float:
        return self.p_incentivized - self.p_not_incentivized


class ReasonFactor(BaseModel):
    """One computed fact that supports a recommendation, for the explain step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    direction: str  # "INCREASES_RISK" | "DECREASES_RISK" | "SUPPORTS_PICK"
    weight: float
    evidence: dict[str, float | int | str] = {}
