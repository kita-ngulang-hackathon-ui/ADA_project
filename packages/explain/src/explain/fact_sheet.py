"""Fact sheet: the only information the narrator may use (requirement 9).

Floats are rounded here, once, so the text, the validator, and the hash all see
the same values. synthetic_data is always true for the demo (honesty rule, §4).
"""
import hashlib
import json

from core_contracts import FactSheet

PROB_DECIMALS = 4
VALUE_DECIMALS = 2


def _r(value: float | None, digits: int = PROB_DECIMALS) -> float | None:
    return None if value is None else round(float(value), digits)


def _pick(ranked, display_name: str) -> dict:
    c = ranked.candidate
    return {
        "candidate_id": c.candidate_id,
        "incentive_code": c.incentive_code,
        "display_name": display_name,
        "cost_idr": int(c.cost_idr),
        "priority": _r(ranked.priority, VALUE_DECIMALS),
        "ranking_strategy": ranked.ranking_strategy.value,
    }


def build_fact_sheet(candidate, risk, impact, circle, policy, allocation, *,
                     runner_up=None, display_names: dict[str, str], external_signal=None,
                     arm, subject_type: str = "USER", subject_ref: str | None = None,
                     member_count: int = 1, activity_window_days: int = 30,
                     reason_factors=()):
    """candidate / runner_up: RankedCandidate. allocation: dict with strategy, budget_idr,
    spent_idr, selected_count, rank."""
    c = candidate.candidate
    circle_facts = None
    if circle is not None and circle.circle_size > 0:
        circle_facts = {
            "circle_size": circle.circle_size,
            "neighbor_activity_ratio_now": _r(circle.neighbor_activity_ratio_now),
            "neighbor_activity_ratio_30d_ago": _r(circle.neighbor_activity_ratio_30d_ago),
            "delta_stability": _r(circle.delta_stability),
            "activity_window_days": activity_window_days,
            "pattern_type": circle.pattern_type.value,
        }
    impact_facts = None
    if impact is not None:
        impact_facts = {
            "p_incentivized": _r(impact.p_incentivized),
            "p_not_incentivized": _r(impact.p_not_incentivized),
            "impact_score": _r(impact.impact_score),
            "segment": c.segment.value,
            "model": impact.model,
        }
    signal_facts = None
    if external_signal is not None:
        signal_facts = {
            "scope_type": external_signal.scope_type.value,
            "scope_key": external_signal.scope_key,
            "signal_type": external_signal.signal_type.value,
            "value": _r(external_signal.value),
        }
    return FactSheet(
        subject_type=subject_type,
        subject_ref=subject_ref or c.user_pseudonym,
        member_count=member_count,
        arm=arm,
        top_pick=_pick(candidate, display_names.get(c.incentive_code, c.incentive_code)),
        runner_up=(
            _pick(runner_up, display_names.get(runner_up.candidate.incentive_code,
                                               runner_up.candidate.incentive_code))
            if runner_up is not None else None
        ),
        risk={
            "churn_risk": _r(risk.churn_risk),
            "model": risk.model,
            "external_signal_contribution": _r(risk.external_signal_contribution),
        },
        circle=circle_facts,
        impact=impact_facts,
        external_signal=signal_facts,
        policy={
            "outcome": policy.outcome,
            "rules_checked": sorted(r.rule_code.value for r in policy.results),
        },
        allocation={k: allocation[k] for k in sorted(allocation)},
        reason_factors=[f.model_dump(mode="json") for f in reason_factors],
        synthetic_data=True,
    )


def canonical_json(fact_sheet) -> str:
    return json.dumps(fact_sheet.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def fact_sheet_hash(fact_sheet) -> str:
    return hashlib.sha256(canonical_json(fact_sheet).encode()).hexdigest()
