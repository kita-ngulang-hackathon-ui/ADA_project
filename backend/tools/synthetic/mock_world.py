"""A small synthetic world, built in memory, for demos that need no database.

All data here is synthetic and must be labeled as such wherever it is shown (§4).
This is deliberately not the full generator described in README.md: it plants no
labeled patterns and writes no fixtures. It exists so the pipeline has something
to run on -- enough users for the graph stage, and enough prior campaign rows for
the impact model -- while `generate.py` is still unwritten.

Seeded by DEFAULT_SEED (SYNTHETIC_SEED in .env, when the caller passes it):
same seed, same events, same labeled rows.
"""
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core_contracts import Arm, Incentive, LabeledExample
from worker.memory_store import InMemoryStore
from worker.store import TenantRecord

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "fixtures"

# WorkerSettings carries no SYNTHETIC_* field; the caller may override this.
DEFAULT_SEED = 20260917

WALLET_ID = "11111111-1111-1111-1111-111111111111"
PAYLATER_ID = "22222222-2222-2222-2222-222222222222"

# Feature vector of a prior campaign row. The impact model reads these columns;
# the churn scorer computes its own from events.
FEATURES = [
    "recency_days", "frequency_30d", "monetary_30d_idr", "tenure_days", "session_gap_days",
    "delta_stability", "circle_size", "pattern_circle_specific", "pattern_market_driven",
    "pattern_stable", "external_signal_value",
]


def _event(eid, etype, user, when, payload=None, region="ID-JK", cohort="cohort-1") -> dict:
    return {
        "client_event_id": eid,
        "event_type": etype,
        "occurred_at": when.isoformat(),
        "user_ref": user,
        "payload": payload or {},
        # full_name is dropped by the attribute whitelist; it is here to prove that.
        "user_attributes": {"region_code": region, "cohort_key": cohort, "full_name": "never-kept"},
    }


def wallet_events(now: datetime) -> list[dict]:
    """Two circles plus individual users, so the graph stage has edges to find."""
    events, n = [], 0

    def add(etype, user, days_ago, payload=None, cohort="cohort-1"):
        nonlocal n
        n += 1
        events.append(_event(f"w{n}", etype, user, now - timedelta(days=days_ago), payload,
                             cohort=cohort))

    # Circle A transfers among itself, then goes quiet in the last 30 days.
    circle_a = ["w0", "w1", "w2", "w3"]
    for day in range(40, 110, 6):
        for i, a in enumerate(circle_a):
            add("wallet.transfer.sent", a, day,
                {"amount": 25_000, "recipient_ref": circle_a[(i + 1) % 4]})
    for day in (3, 12):
        add("wallet.payment.merchant", "w0", day, {"amount": 60_000})

    # Circle B stays active throughout.
    circle_b = ["w4", "w5", "w6", "w7"]
    for day in range(1, 110, 5):
        for i, a in enumerate(circle_b):
            add("wallet.transfer.sent", a, day,
                {"amount": 30_000, "recipient_ref": circle_b[(i + 1) % 4]})

    # Individuals with no circle: w8..w15 barely active, w16..w19 busy.
    for u in range(8, 16):
        for day in (4, 19):
            add("wallet.payment.merchant", f"w{u}", day, {"amount": 40_000 + u * 1_000})
    for u in range(16, 20):
        for day in range(1, 30, 2):
            add("wallet.topup.completed", f"w{u}", day, {"amount": 100_000})

    add("wallet.unknown.thing", "w8", 2)  # unmapped vocabulary; the run marks it and carries on
    return events


def paylater_events(now: datetime) -> list[dict]:
    """A lending tenant, including one repayment-stressed user the policy guard denies."""
    events, n = [], 0

    def add(etype, user, days_ago, payload=None):
        nonlocal n
        n += 1
        events.append(_event(f"p{n}", etype, user, now - timedelta(days=days_ago), payload,
                             region="ID-JB", cohort="cohort-2"))

    for u in range(12):
        user = f"p{u}"
        add("paylater.loan.disbursed", user, 80, {"principal": 1_500_000})
        add("paylater.checkout.completed", user, 10, {"order_total": 200_000 + u * 5_000})
        add("paylater.installment.paid", user, 20, {"amount_paid": 250_000})
    for days in (5, 25):
        add("paylater.installment.overdue", "p0", days, {"amount_due": 250_000})
    return events


def labeled_examples(tenant_id: str, count: int, seed: int) -> list[LabeledExample]:
    """Prior campaign outcomes, the in-context rows the impact model needs.

    Treated users mostly stay; untreated low-activity users mostly leave. That
    spread is what makes quiet users PERSUADABLE and busy ones SURE_THING.
    """
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        freq = rng.choice([1, 2, 3, 12, 15, 20])
        treated = i % 2 == 0
        busy = freq >= 10
        retained = True if (treated or busy) else rng.random() < 0.1
        features = {c: 0.0 for c in FEATURES}
        features.update(recency_days=1.0 if busy else 20.0, frequency_30d=float(freq),
                        monetary_30d_idr=freq * 50_000.0, tenure_days=150.0,
                        session_gap_days=30.0 / freq, pattern_stable=1.0)
        rows.append(LabeledExample(
            tenant_id=tenant_id, source_outcome_id=f"{tenant_id}-o{i:04d}",
            user_pseudonym=f"hist{i}", features=features,
            arm=Arm.ENGINE if treated else Arm.CONTROL,
            treated=treated, retained=retained, churn_risk=0.5, impact_score=0.3,
            pattern_type="STABLE", incentive_code="CASHBACK_10K" if treated else None,
            cost_idr=10_000 if treated else 0, business_value_idr=freq * 150_000,
            realized_value_idr=float(freq * 150_000 if retained else 0),
        ))
    return rows


def _mapping(name: str) -> dict:
    return json.loads((FIXTURES / "mappings" / name).read_text(encoding="utf-8"))


def _incentives() -> list[Incentive]:
    data = json.loads((FIXTURES / "incentives.json").read_text(encoding="utf-8"))
    return [Incentive.model_validate(i) for i in data["incentives"]]


def build_store(settings, now: datetime | None = None,
                seed: int = DEFAULT_SEED) -> tuple[InMemoryStore, datetime]:
    """Both demo tenants, seeded with events, the incentive catalog and prior outcomes.

    The labeled-row count follows IMPACT_MIN_TRAIN_ROWS, doubled: the impact
    model counts the treated and control arms separately and every second row
    is treated. Too few and the stage reports unavailable, no candidate is
    built, and nothing is narrated.
    """
    now = now or datetime.now(UTC)
    rows = max(settings.impact_min_train_rows * 2, settings.risk_min_context_rows) + 100
    store = InMemoryStore()
    store.add_tenant(TenantRecord(WALLET_ID, "demo-wallet", "WALLET", _mapping("wallet.json")))
    store.add_tenant(TenantRecord(PAYLATER_ID, "demo-paylater", "LENDING", _mapping("paylater.json")))
    for tenant_id, events in ((WALLET_ID, wallet_events(now)), (PAYLATER_ID, paylater_events(now))):
        store.add_raw_events(tenant_id, events)
        store.set_incentives(tenant_id, _incentives())
        store.save_labeled_examples(labeled_examples(tenant_id, rows, seed=seed))
    return store, now
