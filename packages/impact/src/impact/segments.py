"""Map an ImpactScore to one of four segments (requirement 6)."""
from core_contracts import ImpactSegment


def segment(impact, *, impact_threshold: float, sure_thing_p: float):
    """PERSUADABLE: gap > threshold. SLEEPING_DOG: gap < -threshold.
    Otherwise small gap: SURE_THING when they stay anyway (p_not >= sure_thing_p), else LOST_CAUSE.
    """
    if impact.impact_score > impact_threshold:
        return ImpactSegment.PERSUADABLE
    if impact.impact_score < -impact_threshold:
        return ImpactSegment.SLEEPING_DOG
    if impact.p_not_incentivized >= sure_thing_p:
        return ImpactSegment.SURE_THING
    return ImpactSegment.LOST_CAUSE
