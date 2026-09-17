"""Transaction-circle graph types (requirement 4, 5).

Counterparty data is structural only (active/inactive, frequency).
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict


class PatternType(str, Enum):
    CIRCLE_SPECIFIC = "CIRCLE_SPECIFIC"
    MARKET_DRIVEN = "MARKET_DRIVEN"
    STABLE = "STABLE"


class Edge(BaseModel):
    """Undirected, recency-decayed relationship. Endpoints are stored sorted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_pseudonym: str
    counterparty_pseudonym: str
    weight: float
    interaction_count: int


class CircleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_pseudonym: str
    circle_size: int
    neighbor_activity_ratio_now: float
    neighbor_activity_ratio_30d_ago: float
    delta_stability: float
    pattern_type: PatternType


class Circle(BaseModel):
    """A transaction group usable for a group recommendation (requirement 5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    circle_id: str
    members: tuple[str, ...]
