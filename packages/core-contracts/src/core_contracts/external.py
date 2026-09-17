"""Canonical external market/sentiment signal (requirement 2).

Signals attach at CLIENT, REGION, or COHORT scope only. This model must
never carry a user or counterparty identifier (UU PDP boundary, §4).
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ScopeType(str, Enum):
    CLIENT = "CLIENT"
    REGION = "REGION"
    COHORT = "COHORT"


class SignalType(str, Enum):
    NEWS_SENTIMENT = "NEWS_SENTIMENT"
    SOCIAL_SENTIMENT = "SOCIAL_SENTIMENT"
    SECTOR_TREND = "SECTOR_TREND"


class ExternalSignal(BaseModel):
    """No user field allowed: extra='forbid' rejects any attempt to add one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str
    source: str
    scope_type: ScopeType
    scope_key: str
    signal_type: SignalType
    value: float = Field(ge=-1.0, le=1.0)
    observed_at: datetime
