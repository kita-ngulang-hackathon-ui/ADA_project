"""Outcome ingestion into labeled examples (requirements 10, 11).

Measured outcomes become new in-context rows for the next run's churn-risk,
impact, and ranker calls. No retraining.
"""
from feedback import summarize, to_labeled_examples
from measurement import compute_lift


def ingest_outcomes(store, tenant_id: str, settings) -> dict:
    outcomes = store.load_outcomes(tenant_id)
    existing = {(e.tenant_id, e.source_outcome_id) for e in store.load_labeled_examples(tenant_id)}
    new = to_labeled_examples(outcomes, store.load_feature_snapshots(tenant_id),
                              existing_outcome_ids=existing)
    if settings.feedback_use_in_context:
        store.save_labeled_examples(new)
    total = len(store.load_labeled_examples(tenant_id))
    return {
        "feedback": summarize(new, total, min_rows_per_cycle=settings.feedback_min_rows_per_cycle,
                              use_in_context=settings.feedback_use_in_context),
        "lift": compute_lift(outcomes, min_arm_size=settings.measurement_min_arm_size),
    }
