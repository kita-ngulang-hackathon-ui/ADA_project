"""Canonical external market/sentiment signal (requirement 2).

Signals attach at CLIENT, REGION, or COHORT scope only. This model must
never carry a user or counterparty identifier (UU PDP boundary, §4).

TODO:
- ScopeType enum: CLIENT, REGION, COHORT.
- SignalType enum: NEWS_SENTIMENT, SOCIAL_SENTIMENT, SECTOR_TREND.
- ExternalSignal model with value constrained to [-1, 1], extra='forbid'.
"""
from enum import Enum


class ScopeType(str, Enum):
    """TODO."""


class SignalType(str, Enum):
    """TODO."""


class ExternalSignal:
    """TODO: pydantic model, no user field allowed."""
