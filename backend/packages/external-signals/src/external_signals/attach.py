"""Attach the right external signal to a user's context (requirement 2).

Resolution order: COHORT -> REGION -> CLIENT. Freshness window from
EXTERNAL_SIGNAL_MAX_AGE_DAYS (passed in, not read from env).
"""
from datetime import timedelta

from core_contracts import ScopeType


def resolve_for_user(signals, *, tenant_slug: str, region_code: str | None,
                     cohort_key: str | None, now, max_age_days: int):
    """Return the most specific fresh signal, or None. Within a scope the newest wins."""
    oldest = now - timedelta(days=max_age_days)
    wanted = [
        (ScopeType.COHORT, cohort_key),
        (ScopeType.REGION, region_code),
        (ScopeType.CLIENT, tenant_slug),
    ]
    for scope, key in wanted:
        if key is None:
            continue
        matches = [
            s for s in signals
            if s.scope_type == scope and s.scope_key == key and oldest <= s.observed_at <= now
        ]
        if matches:
            return max(matches, key=lambda s: (s.observed_at, s.signal_id))
    return None
