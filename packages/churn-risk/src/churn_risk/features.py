"""Feature engineering for churn risk (requirement 3).

TODO:
- FEATURE_COLUMNS: fixed ordered list.
- build_features(): behavioral RFM + tenure + session gap, graph features,
  external signal value (0.0 if none). Deterministic output.
"""

FEATURE_COLUMNS: list[str] = []  # TODO


def build_features(events, circle_snapshot, external_signal, *, now):
    raise NotImplementedError
