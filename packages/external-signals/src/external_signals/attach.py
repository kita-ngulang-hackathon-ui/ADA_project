"""Attach the right external signal to a user's context (requirement 2).

Resolution order: COHORT -> REGION -> CLIENT. Freshness window from
EXTERNAL_SIGNAL_MAX_AGE_DAYS (passed in, not read from env).

TODO: implement resolve_for_user.
"""


def resolve_for_user(signals, *, tenant_slug: str, region_code: str | None,
                     cohort_key: str | None, now, max_age_days: int):
    raise NotImplementedError
