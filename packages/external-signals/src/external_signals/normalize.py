"""FeedItem -> ExternalSignal. Pure.

TODO:
- Clamp value to [-1, 1].
- Reject any item whose scope is not CLIENT/REGION/COHORT.
"""


def to_signal(item):
    raise NotImplementedError
