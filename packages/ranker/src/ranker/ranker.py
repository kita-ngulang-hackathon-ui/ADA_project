"""Priority scoring: TabPFNRegressor or FALLBACK (requirement 7, stage 2).

TODO:
- If len(context) < min_context_rows: priority = impact_score * business_value_idr, strategy FALLBACK.
- Else TabPFNRegressor in-context predict, strategy TABPFN.
- Deterministic tie-break.
"""


def rank(context, candidates, *, min_context_rows: int, seed: int):
    raise NotImplementedError
