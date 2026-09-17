"""churn-risk (L1) — TabPFN churn classifier with in-context examples and signal attribution."""
from churn_risk.attribution import contributions, external_signal_contribution
from churn_risk.classifier import predict_positive, score
from churn_risk.context import assert_single_tenant, select_context
from churn_risk.features import FEATURE_COLUMNS, build_features, to_row

__all__ = [
    "FEATURE_COLUMNS",
    "assert_single_tenant",
    "build_features",
    "contributions",
    "external_signal_contribution",
    "predict_positive",
    "score",
    "select_context",
    "to_row",
]
