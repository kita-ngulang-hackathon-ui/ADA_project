"""TabPFN churn classifier with deterministic stand-in (requirement 3).

In-context: fit(context) + predict_proba(query) on every call; nothing is persisted.
TabPFN is an optional extra while its weights are being trained. Without it (or when
it fails at runtime) a seeded sklearn random forest stands in, and the model name
recorded on every RiskScore says which one produced the number.
"""
from core_contracts import RiskScore

MODEL_TABPFN = "TABPFN_CLASSIFIER"
MODEL_STAND_IN = "SKLEARN_RANDOM_FOREST"
MODEL_CONSTANT = "CONSTANT_SINGLE_CLASS"


def _tabpfn(seed: int, model_cache_dir: str | None):
    from tabpfn import TabPFNClassifier  # optional extra

    # Weights location comes from TabPFN's own cache env (TABPFN_MODEL_CACHE_DIR); model_cache_dir
    # is kept in the signature for when the trained weights land.
    return TabPFNClassifier(device="cpu", random_state=seed)


def _stand_in(seed: int):
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=seed)


def predict_positive(context_X, context_y, query_X, *, seed: int,
                     model_cache_dir: str | None = None, use_tabpfn: bool = True):
    """Return (P(label == 1) per query row, model name)."""
    if not query_X:
        return [], MODEL_CONSTANT
    labels = set(context_y)
    if len(labels) < 2:
        only = next(iter(labels), 0)
        return [float(only)] * len(query_X), MODEL_CONSTANT

    if use_tabpfn:
        try:
            model = _tabpfn(seed, model_cache_dir)
            model.fit(context_X, context_y)
            return _positive_column(model, query_X), MODEL_TABPFN
        except Exception:  # ImportError, missing weights, runtime failure -> stand-in
            pass
    model = _stand_in(seed)
    model.fit(context_X, context_y)
    return _positive_column(model, query_X), MODEL_STAND_IN


def _positive_column(model, query_X) -> list[float]:
    classes = list(model.classes_)
    column = classes.index(1)
    return [float(p[column]) for p in model.predict_proba(query_X)]


def score(context_X, context_y, query_X, *, seed: int, model_cache_dir: str | None = None,
          query_ids: list[str] | None = None, use_tabpfn: bool = True):
    """Return one RiskScore per query row (churn_risk = P(churn))."""
    probs, model_name = predict_positive(context_X, context_y, query_X, seed=seed,
                                         model_cache_dir=model_cache_dir, use_tabpfn=use_tabpfn)
    ids = query_ids or [str(i) for i in range(len(query_X))]
    return [
        RiskScore(user_pseudonym=uid, churn_risk=p, model=model_name,
                  context_row_count=len(context_X))
        for uid, p in zip(ids, probs)
    ]
