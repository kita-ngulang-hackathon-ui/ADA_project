"""External signal attribution (requirement 3: "records which external signal contributed").

contribution = risk(with signal) - risk(signal neutralized to 0)

score_fn(context_X, context_y, query_X) -> list[float] of churn probabilities.
"""
from churn_risk.features import FEATURE_COLUMNS


def contributions(score_fn, context_X, context_y, query_rows, signal_column: str) -> list[float]:
    """Batch version: one model call over the original and neutralized rows."""
    if not query_rows:
        return []
    col = FEATURE_COLUMNS.index(signal_column)
    neutral = []
    for row in query_rows:
        copy = list(row)
        copy[col] = 0.0
        neutral.append(copy)
    probs = score_fn(context_X, context_y, list(query_rows) + neutral)
    n = len(query_rows)
    return [
        0.0 if query_rows[i][col] == 0.0 else probs[i] - probs[n + i]
        for i in range(n)
    ]


def external_signal_contribution(score_fn, context_X, context_y, query_row, signal_column: str) -> float:
    return contributions(score_fn, context_X, context_y, [query_row], signal_column)[0]
