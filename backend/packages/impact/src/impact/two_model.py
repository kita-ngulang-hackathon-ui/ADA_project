"""Two-model counterfactual impact estimate (requirement 6).

Model A sees historically incentivized users, model B non-incentivized users
(both in-context, label = retained). A candidate runs through both:
impact_score = P(stay | incentivized) - P(stay | not incentivized).

TabPFN is an optional extra while its weights are being trained; a seeded sklearn
random forest stands in and the model name records which one ran.
"""
from core_contracts import ContextTooSmall, CrossTenantContext, ImpactScore

MODEL_TABPFN = "TABPFN_TWO_MODEL"
MODEL_STAND_IN = "SKLEARN_RANDOM_FOREST_TWO_MODEL"


def _columns(rows) -> list[str]:
    return sorted({c for r in rows for c in r.features})


def _matrix(feature_dicts, columns) -> list[list[float]]:
    return [[float(f.get(c, 0.0)) for c in columns] for f in feature_dicts]


def _fit_predict(X, y, query, *, seed: int, use_tabpfn: bool) -> tuple[list[float], bool]:
    """P(retained) per query row; second value is True when TabPFN produced it."""
    if len(set(y)) < 2:
        return [float(y[0])] * len(query), False
    if use_tabpfn:
        try:
            from tabpfn import TabPFNClassifier  # optional extra

            model = TabPFNClassifier(device="cpu", random_state=seed)
            model.fit(X, y)
            col = list(model.classes_).index(1)
            return [float(p[col]) for p in model.predict_proba(query)], True
        except Exception:
            pass
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=seed)
    model.fit(X, y)
    col = list(model.classes_).index(1)
    return [float(p[col]) for p in model.predict_proba(query)], False


def estimate_batch(treated_context, control_context, candidate_features: list[dict], *,
                   seed: int, min_rows: int, use_tabpfn: bool = True) -> list[ImpactScore]:
    treated, control = list(treated_context), list(control_context)
    tenants = {r.tenant_id for r in treated + control}
    if len(tenants) > 1:
        raise CrossTenantContext(f"impact context spans {len(tenants)} tenants")
    for name, arm in (("treated", treated), ("control", control)):
        if len(arm) < min_rows:
            raise ContextTooSmall(f"{name} arm has {len(arm)} rows, need {min_rows}")
    if not candidate_features:
        return []

    columns = _columns(treated + control)
    query = _matrix(candidate_features, columns)
    treated = sorted(treated, key=lambda r: r.source_outcome_id)
    control = sorted(control, key=lambda r: r.source_outcome_id)
    p_inc, tab_a = _fit_predict(_matrix([r.features for r in treated], columns),
                                [int(r.retained) for r in treated], query,
                                seed=seed, use_tabpfn=use_tabpfn)
    p_not, tab_b = _fit_predict(_matrix([r.features for r in control], columns),
                                [int(r.retained) for r in control], query,
                                seed=seed, use_tabpfn=use_tabpfn)
    model = MODEL_TABPFN if (tab_a and tab_b) else MODEL_STAND_IN
    return [
        ImpactScore(p_incentivized=a, p_not_incentivized=b, model=model)
        for a, b in zip(p_inc, p_not)
    ]


def estimate(treated_context, control_context, candidate_features, *, seed: int, min_rows: int):
    return estimate_batch(treated_context, control_context, [candidate_features],
                          seed=seed, min_rows=min_rows)[0]
