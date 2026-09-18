"""Raw feed item shape (canned fixture or live adapter output).

headline is display-only and never scored.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeedItem(BaseModel):
    # extra="ignore": live sources may send more fields; none of them reach scoring.
    model_config = ConfigDict(frozen=True, extra="ignore")

    source: str
    scope_type: str
    scope_key: str
    signal_type: str
    value: float
    observed_at: datetime
    headline: str | None = None
