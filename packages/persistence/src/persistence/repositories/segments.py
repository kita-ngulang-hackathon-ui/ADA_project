"""Per-user spend/frequency/risk rollup for the console dashboard's segment
view. Not part of API_CONTRACTS.md -- the pipeline itself has no notion of
RFM-style segments, only churn_risk and the four IMPACT segments. This
aggregates real ingested transaction volume (canonical_events.amount_idr)
and real churn_risk (risk_scores) so the dashboard's segment cards reflect
actual data rather than placeholders.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models import CanonicalEventRow, RiskScoreRow, User

MONETARY_TIERS = ("lowest-spenders", "low-spenders", "moderate-spenders", "big-spenders", "high-rollers")


def get_user_segments(session: Session, *, tenant_id: str, window_days: int = 30) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=window_days)

    latest_risk = (
        select(RiskScoreRow.user_pseudonym, RiskScoreRow.churn_risk)
        .where(RiskScoreRow.tenant_id == tenant_id)
        .distinct(RiskScoreRow.user_pseudonym)
        .order_by(RiskScoreRow.user_pseudonym, RiskScoreRow.computed_at.desc())
        .subquery()
    )

    volume = (
        select(
            CanonicalEventRow.user_pseudonym.label("user_pseudonym"),
            func.sum(CanonicalEventRow.amount_idr).label("monetary"),
            func.count().label("frequency"),
        )
        .where(CanonicalEventRow.tenant_id == tenant_id, CanonicalEventRow.occurred_at >= since)
        .group_by(CanonicalEventRow.user_pseudonym)
        .subquery()
    )

    stmt = (
        select(
            User.user_pseudonym,
            latest_risk.c.churn_risk,
            func.coalesce(volume.c.monetary, 0),
            func.coalesce(volume.c.frequency, 0),
        )
        .where(User.tenant_id == tenant_id)
        .outerjoin(latest_risk, latest_risk.c.user_pseudonym == User.user_pseudonym)
        .outerjoin(volume, volume.c.user_pseudonym == User.user_pseudonym)
    )
    rows = session.execute(stmt).all()
    if not rows:
        return []

    risks = sorted(r for _, r, _, _ in rows if r is not None)
    monetary_sorted = sorted(m for _, _, m, _ in rows)
    frequency_sorted = sorted(f for _, _, _, f in rows)

    def tercile(value: float, ordered: list[float]) -> str:
        if not ordered:
            return "low"
        lo = ordered[len(ordered) // 3] if len(ordered) >= 3 else ordered[0]
        hi = ordered[(2 * len(ordered)) // 3] if len(ordered) >= 3 else ordered[-1]
        if value <= lo:
            return "low"
        if value <= hi:
            return "medium"
        return "high"

    def quintile_tier(value: float, ordered: list[float]) -> str:
        if not ordered:
            return MONETARY_TIERS[0]
        rank = sum(1 for v in ordered if v <= value) / len(ordered)
        index = min(int(rank * 5), 4)
        return MONETARY_TIERS[index]

    frequency_cutoff = frequency_sorted[int(len(frequency_sorted) * 2 / 3)] if len(frequency_sorted) >= 3 else None

    out = []
    for pseudonym, churn_risk, monetary, frequency in rows:
        risk_band = tercile(churn_risk, risks) if churn_risk is not None else "low"
        segment_ids = [quintile_tier(monetary, monetary_sorted)]
        if frequency_cutoff is not None and frequency >= frequency_cutoff and frequency > 0:
            segment_ids.append("frequent-buyers")
        out.append({
            "user_pseudonym": pseudonym,
            "churn_risk": churn_risk,
            "risk_band": risk_band,
            "segment_ids": segment_ids,
        })
    return out
