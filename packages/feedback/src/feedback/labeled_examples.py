"""Outcomes -> labeled examples for the next TabPFN context (requirement 11).

TODO:
- LabeledExample model (tenant_id, features snapshot, arm, retained label, source outcome id).
- to_labeled_examples(): dedupe, use recommendation-time feature snapshot.
- summarize(): counts for the "new labeled examples added" demo counter.
"""


def to_labeled_examples(outcomes, feature_snapshots):
    raise NotImplementedError


def summarize(new_examples, total_examples: int) -> dict:
    raise NotImplementedError
