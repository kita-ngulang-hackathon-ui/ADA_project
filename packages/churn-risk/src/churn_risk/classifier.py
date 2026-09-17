"""TabPFN churn classifier with deterministic fallback (requirement 3).

TODO:
- Lazy-import tabpfn; on ImportError or runtime failure use sklearn fallback.
- fit(context) + predict_proba(query) per call; no persisted trained model.
- Return RiskScore list with model name + context_row_count.
"""


def score(context_X, context_y, query_X, *, seed: int, model_cache_dir: str | None = None):
    raise NotImplementedError
