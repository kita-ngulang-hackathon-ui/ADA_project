"""Pattern tagging: CIRCLE_SPECIFIC vs MARKET_DRIVEN vs STABLE (requirement 4).

if delta_stability > -dip_threshold:                       STABLE
elif cohort_median_delta < -cohort_dip_threshold and external < 0: MARKET_DRIVEN
else:                                                      CIRCLE_SPECIFIC

TODO: implement tag_pattern; thresholds come from config, passed in.
"""


def tag_pattern(delta_stability: float, cohort_median_delta: float,
                external_signal_value: float | None, *, dip_threshold: float,
                cohort_dip_threshold: float):
    raise NotImplementedError
