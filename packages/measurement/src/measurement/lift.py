"""Incremental lift per arm (requirement 10).

TODO:
- retention_rate per arm; lift = engine - control, engine - naive.
- None when arm size < min_arm_size.
- Include synthetic_data flag.
"""


def compute_lift(outcomes, *, min_arm_size: int):
    raise NotImplementedError
