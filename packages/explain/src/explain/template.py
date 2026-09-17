"""Deterministic template fallback narration (reason_source="TEMPLATE").

Built only from fact sheet values, formatted so validate_narration accepts it.
"""


def _idr(amount: int) -> str:
    return "Rp " + f"{amount:,}".replace(",", ".")


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def render_template(fact_sheet) -> str:
    fs = fact_sheet
    top = fs.top_pick
    subject = "this transaction circle" if fs.subject_type == "GROUP" else "this user"
    parts = [(
        f"Recommended for {subject}: {top['display_name']} (cost {_idr(top['cost_idr'])}, "
        f"priority {top['priority']:.2f} via {top['ranking_strategy']})."
    )]
    parts.append(f"Churn risk is {_pct(fs.risk['churn_risk'])} ({fs.risk['model']}).")
    if fs.circle:
        c = fs.circle
        parts.append(
            f"Active share of the circle moved from {_pct(c['neighbor_activity_ratio_30d_ago'])} "
            f"to {_pct(c['neighbor_activity_ratio_now'])} over {c['activity_window_days']} days "
            f"across {c['circle_size']} counterparties, tagged {c['pattern_type']}."
        )
    if fs.impact:
        i = fs.impact
        parts.append(
            f"Estimated chance to stay is {_pct(i['p_incentivized'])} with the incentive and "
            f"{_pct(i['p_not_incentivized'])} without it, so the segment is {i['segment']}."
        )
    if fs.external_signal:
        s = fs.external_signal
        direction = "negative" if s["value"] < 0 else "non-negative"
        parts.append(
            f"Market context: {s['signal_type']} for {s['scope_type']} {s['scope_key']} "
            f"is {direction} ({s['value']:.2f})."
        )
    if fs.runner_up:
        r = fs.runner_up
        parts.append(
            f"Runner-up: {r['display_name']} (cost {_idr(r['cost_idr'])}, "
            f"priority {r['priority']:.2f})."
        )
    parts.append("Based on synthetic demo data; a human reviewer must approve before any action.")
    return " ".join(parts)
