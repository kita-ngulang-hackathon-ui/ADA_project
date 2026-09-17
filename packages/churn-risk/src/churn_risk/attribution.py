"""External signal attribution (requirement 3: "records which external signal contributed").

contribution = risk(with signal) - risk(signal neutralized to 0)

TODO: implement using classifier.score on paired query rows.
"""


def external_signal_contribution(score_fn, context_X, context_y, query_row, signal_column: str) -> float:
    raise NotImplementedError
