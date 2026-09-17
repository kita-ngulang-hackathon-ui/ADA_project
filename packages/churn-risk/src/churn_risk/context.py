"""In-context example selection for TabPFN (requirements 3, 11).

Label for churn risk: 1 = churned (not retained), 0 = retained.
"""
import random

from core_contracts import ContextTooSmall, CrossTenantContext

from churn_risk.features import to_row


def assert_single_tenant(rows) -> None:
    tenants = {r.tenant_id for r in rows}
    if len(tenants) > 1:
        raise CrossTenantContext(f"context rows span {len(tenants)} tenants")


def select_context(labeled_rows, *, max_rows: int, min_rows: int, seed: int):
    """Return (X, y). Stratified by label, capped at max_rows, seeded."""
    rows = list(labeled_rows)
    assert_single_tenant(rows)
    if len(rows) < min_rows:
        raise ContextTooSmall(f"{len(rows)} context rows, need {min_rows}")

    rows.sort(key=lambda r: r.source_outcome_id)
    if len(rows) > max_rows:
        rng = random.Random(seed)
        by_label = {True: [r for r in rows if r.retained], False: [r for r in rows if not r.retained]}
        picked = []
        for group in by_label.values():
            take = round(max_rows * len(group) / len(rows))
            picked.extend(rng.sample(group, min(take, len(group))))
        rows = sorted(picked, key=lambda r: r.source_outcome_id)[:max_rows]

    X = [to_row(r.features) for r in rows]
    y = [0 if r.retained else 1 for r in rows]
    return X, y
