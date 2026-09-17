"""Transaction-circle graph types (requirement 4, 5).

Counterparty data is structural only (active/inactive, frequency).
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class PatternType(str, Enum):
    CIRCLE_SPECIFIC = "CIRCLE_SPECIFIC"
    MARKET_DRIVEN = "MARKET_DRIVEN"
    STABLE = "STABLE"


class EdgeWeight(BaseModel):
    """A single recency-decayed relationship edge (ARCHITECTURE.md §7.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_pseudonym: str
    counterparty_pseudonym: str
    weight: float

    @field_validator("weight")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weight must be non-negative")
        return v


class CircleSnapshot(BaseModel):
    """A user's circle-stability snapshot at pipeline-run time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    circle_size: int
    neighbor_activity_ratio_now: float
    neighbor_activity_ratio_30d_ago: float
    delta_stability: float
    pattern_type: PatternType

    @field_validator("circle_size")
    @classmethod
    def _non_negative_size(cls, v: int) -> int:
        if v < 0:
            raise ValueError("circle_size must be non-negative")
        return v
