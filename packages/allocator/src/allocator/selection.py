"""Allocation entry point: selection, runner-ups, exclusion reasons.

TODO:
- Choose DP or greedy per config/size.
- For each user: top pick + best non-selected runner-up.
- Every non-selected candidate gets an exclusion_reason.
"""


def allocate(candidates, *, budget_idr: int, config):
    raise NotImplementedError
