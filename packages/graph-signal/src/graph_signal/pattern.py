"""Pattern tagging: CIRCLE_SPECIFIC vs MARKET_DRIVEN vs STABLE (requirement 4).

if delta_stability > -dip_threshold:                       STABLE
elif cohort_median_delta < -cohort_dip_threshold and external < 0: MARKET_DRIVEN
else:                                                      CIRCLE_SPECIFIC
"""
from core_contracts import PatternType


def tag_pattern(delta_stability: float, cohort_median_delta: float,
                external_signal_value: float | None, *, dip_threshold: float,
                cohort_dip_threshold: float):
    if delta_stability > -dip_threshold:
        return PatternType.STABLE
    if (
        cohort_median_delta < -cohort_dip_threshold
        and external_signal_value is not None
        and external_signal_value < 0
    ):
        return PatternType.MARKET_DRIVEN
    return PatternType.CIRCLE_SPECIFIC
