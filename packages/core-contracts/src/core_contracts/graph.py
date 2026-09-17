"""Transaction-circle graph types (requirement 4, 5).

TODO:
- PatternType enum: CIRCLE_SPECIFIC, MARKET_DRIVEN, STABLE.
- CircleSnapshot: circle_size, neighbor_activity_ratio_now,
  neighbor_activity_ratio_30d_ago, delta_stability, pattern_type.
- Edge: user_pseudonym, counterparty_pseudonym, weight (recency-decayed).
Counterparty data is structural only (active/inactive, frequency).
"""
from enum import Enum


class PatternType(str, Enum):
    """TODO."""


class Edge:
    """TODO."""


class CircleSnapshot:
    """TODO."""
