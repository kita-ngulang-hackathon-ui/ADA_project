"""Priority scoring: TabPFNRegressor or FALLBACK (requirement 7, stage 2).

- Fewer than min_context_rows: priority = impact_score * business_value_idr, strategy FALLBACK.
- Otherwise in-context regression: TabPFN when installed (TABPFN), else a seeded sklearn
  stand-in (SKLEARN_STAND_IN) while the TabPFN weights are being trained.
- Output sorted by priority desc, ties broken by candidate_id for determinism.
"""
from core_contracts import RankedCandidate, RankingStrategy

from ranker.context import RankerContext, row


def _candidate_row(c) -> list[float]:
    return row(impact_score=c.impact_score, churn_risk=c.churn_risk, pattern_type=c.pattern_type,
               cost_idr=c.cost_idr, business_value_idr=c.business_value_idr)


def _regress(context: RankerContext, query, *, seed: int, use_tabpfn: bool):
    if use_tabpfn:
        try:
            from tabpfn import TabPFNRegressor  # optional extra

            model = TabPFNRegressor(device="cpu", random_state=seed)
            model.fit(context.X, context.y)
            return [float(v) for v in model.predict(query)], RankingStrategy.TABPFN
        except Exception:
            pass
    from sklearn.ensemble import RandomForestRegressor

    model = RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=seed)
    model.fit(context.X, context.y)
    return [float(v) for v in model.predict(query)], RankingStrategy.SKLEARN_STAND_IN


def rank(context, candidates, *, min_context_rows: int, seed: int, use_tabpfn: bool = True):
    candidates = sorted(candidates, key=lambda c: c.candidate_id)
    if not candidates:
        return []
    if context is None or len(context) < min_context_rows:
        priorities = [c.impact_score * c.business_value_idr for c in candidates]
        strategy = RankingStrategy.FALLBACK
    else:
        priorities, strategy = _regress(context, [_candidate_row(c) for c in candidates],
                                        seed=seed, use_tabpfn=use_tabpfn)
    ranked = [
        RankedCandidate(candidate=c, priority=p, ranking_strategy=strategy)
        for c, p in zip(candidates, priorities)
    ]
    return sorted(ranked, key=lambda r: (-r.priority, r.candidate.candidate_id))
