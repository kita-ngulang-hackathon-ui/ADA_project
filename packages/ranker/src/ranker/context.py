"""Ranker in-context rows from labeled examples (requirements 7, 11).

X uses RANKER_COLUMNS; y is realized value (retained business value minus spend).
Only treated examples with recorded scores are usable. Single tenant only.
"""
from dataclasses import dataclass

from core_contracts import CrossTenantContext, PatternType

RANKER_COLUMNS: list[str] = [
    "impact_score",
    "churn_risk",
    "pattern_circle_specific",
    "pattern_market_driven",
    "pattern_stable",
    "cost_idr",
    "business_value_idr",
]


@dataclass(frozen=True)
class RankerContext:
    X: list[list[float]]
    y: list[float]

    def __len__(self) -> int:
        return len(self.X)


def row(*, impact_score: float, churn_risk: float, pattern_type, cost_idr: int,
        business_value_idr: int) -> list[float]:
    pattern = PatternType(pattern_type) if pattern_type else PatternType.STABLE
    return [
        float(impact_score),
        float(churn_risk),
        1.0 if pattern == PatternType.CIRCLE_SPECIFIC else 0.0,
        1.0 if pattern == PatternType.MARKET_DRIVEN else 0.0,
        1.0 if pattern == PatternType.STABLE else 0.0,
        float(cost_idr),
        float(business_value_idr),
    ]


def build_context(labeled_examples) -> RankerContext:
    examples = sorted(labeled_examples, key=lambda e: e.source_outcome_id)
    tenants = {e.tenant_id for e in examples}
    if len(tenants) > 1:
        raise CrossTenantContext(f"ranker context spans {len(tenants)} tenants")
    usable = [
        e for e in examples
        if e.treated and e.impact_score is not None and e.churn_risk is not None
    ]
    X = [
        row(impact_score=e.impact_score, churn_risk=e.churn_risk, pattern_type=e.pattern_type,
            cost_idr=e.cost_idr, business_value_idr=e.business_value_idr)
        for e in usable
    ]
    return RankerContext(X=X, y=[float(e.realized_value_idr) for e in usable])
