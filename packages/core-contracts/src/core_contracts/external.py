"""Canonical external market/sentiment signal (requirement 2).

Signals attach at CLIENT, REGION, or COHORT scope only. This model must
never carry a user or counterparty identifier (UU PDP boundary, §4).
"""
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class ScopeType(str, Enum):
    CLIENT = "CLIENT"
    REGION = "REGION"
    COHORT = "COHORT"


class SignalType(str, Enum):
    NEWS_SENTIMENT = "NEWS_SENTIMENT"
    SOCIAL_SENTIMENT = "SOCIAL_SENTIMENT"
    SECTOR_TREND = "SECTOR_TREND"


class ExternalSignal(BaseModel):
    """Cohort/region/client-level signal. No user field can be added: extra='forbid'
    plus the absence of any user/counterparty field in this schema is the enforcement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_type: ScopeType
    scope_key: str
    signal_type: SignalType
    value: float
    observed_at: datetime
    source: str

    @field_validator("value")
    @classmethod
    def _clamp_range(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError("value must be in [-1, 1]")
        return v

    @field_validator("observed_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return v.astimezone(UTC)
