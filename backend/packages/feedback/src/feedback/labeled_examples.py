"""Outcomes -> labeled examples for the next TabPFN context (requirement 11).

Uses the feature snapshot captured at recommendation time, never current data,
so labels cannot leak into features. Deduped by (tenant_id, outcome_event_id).
"""
from core_contracts import LabeledExample


def to_labeled_examples(outcomes, feature_snapshots, *, existing_outcome_ids=frozenset()):
    """feature_snapshots: {(run_id, user_pseudonym): FeatureSnapshot}.

    Outcomes without a snapshot are skipped (nothing trustworthy to learn from).
    """
    seen = {tuple(k) for k in existing_outcome_ids}
    examples = []
    for o in sorted(outcomes, key=lambda o: o.outcome_event_id):
        key = (o.tenant_id, o.outcome_event_id)
        if key in seen:
            continue
        snap = feature_snapshots.get((o.run_id, o.user_pseudonym))
        if snap is None or snap.tenant_id != o.tenant_id:
            continue
        seen.add(key)
        kept = snap.business_value_idr if o.retained else 0
        examples.append(LabeledExample(
            tenant_id=o.tenant_id,
            source_outcome_id=o.outcome_event_id,
            user_pseudonym=o.user_pseudonym,
            features=dict(snap.features),
            arm=o.arm,
            treated=o.treated,
            retained=o.retained,
            churn_risk=snap.churn_risk,
            impact_score=snap.impact_score,
            pattern_type=snap.pattern_type,
            incentive_code=snap.incentive_code if o.treated else None,
            cost_idr=snap.cost_idr if o.treated else 0,
            business_value_idr=snap.business_value_idr,
            realized_value_idr=float(kept - (o.spend_idr if o.treated else 0)),
        ))
    return examples


def summarize(new_examples, total_examples: int, *, min_rows_per_cycle: int = 0,
              use_in_context: bool = True) -> dict:
    """Counter for the demo ("new labeled examples added")."""
    new_count = len(new_examples)
    return {
        "new_labeled_examples": new_count,
        "total_labeled_examples": total_examples,
        "meets_min_rows_per_cycle": new_count >= min_rows_per_cycle,
        "used_in_next_context": use_in_context and new_count >= min_rows_per_cycle,
        "synthetic_data": True,
    }
