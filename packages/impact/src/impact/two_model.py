"""Two-model counterfactual impact estimate (requirement 6).

TODO:
- Fit arm model on treated context, second on control context (in-context).
- p_incentivized, p_not_incentivized for the candidate; impact_score = diff.
- Deterministic seed; fallback model if TabPFN unavailable.
"""


def estimate(treated_context, control_context, candidate_features, *, seed: int, min_rows: int):
    raise NotImplementedError
