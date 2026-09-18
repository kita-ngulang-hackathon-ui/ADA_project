"""Small hand-built synthetic world for worker tests. All data here is synthetic."""
import json
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core_contracts import Arm, Incentive, LabeledExample
from worker.churn_scorer import ChurnRiskScorer
from worker.memory_store import InMemoryStore
from worker.settings import WorkerSettings
from worker.store import TenantRecord

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures"
ARTIFACTS = ROOT / "artifacts"
NOW = datetime(2026, 9, 17, tzinfo=UTC)
WALLET_ID = "11111111-1111-1111-1111-111111111111"
PAYLATER_ID = "22222222-2222-2222-2222-222222222222"

FEATURES = [
    "recency_days", "frequency_30d", "monetary_30d_idr", "tenure_days", "session_gap_days",
    "delta_stability", "circle_size", "pattern_circle_specific", "pattern_market_driven",
    "pattern_stable", "external_signal_value",
]


def make_settings(**overrides) -> WorkerSettings:
    values = dict(
        pseudonym_hmac_secret="test-pseudonym-secret",
        measurement_hmac_secret="test-measurement-secret",
        external_signal_fixture_dir=str(FIXTURES / "external"),
        frequency_cap_max_contacts=3,  # test-only value; the real cap is an open decision
        frequency_cap_window_days=14,
        risk_min_context_rows=20,
        impact_min_train_rows=20,
        ranker_min_context_rows=10_000,  # force FALLBACK ranking in tests
        default_budget_idr=40_000,
        measurement_control_pct=30,
        measurement_naive_pct=20,
        measurement_naive_risk_threshold=0.0,
        tabpfn_enabled=False,
        churn_scorer_enabled=True,
        churn_scorer_artifact_dir=str(ARTIFACTS),
        churn_scorer_device="cpu",
        churn_scorer_mapping_path=str(FIXTURES / "churn_scorer_mapping.json"),
        explain_llm_enabled=False,
    )
    values.update(overrides)
    return WorkerSettings(_env_file=None, **values)


class FakeTabPFN:
    """Stands in for TabPFNClassifier in tests: risk rises with recency, no weights needed."""

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.fit_rows = 0

    def fit(self, X, y):
        self.fit_rows = len(X)
        self.classes_ = sorted({int(v) for v in y})
        return self

    def predict_proba(self, X):
        p = (X["days_since_last_txn"].astype(float) / 60.0).clip(0.02, 0.98)
        p = (p - X["external_sentiment"].astype(float) * 0.1).clip(0.0, 1.0)
        return [[1.0 - v, v] for v in p]


_SCORER: ChurnRiskScorer | None = None
_REAL_SCORER: ChurnRiskScorer | None = None


def tabpfn_token() -> str | None:
    """TABPFN_TOKEN from the environment or the gitignored root .env."""
    from dotenv import dotenv_values

    return os.environ.get("TABPFN_TOKEN") or dotenv_values(ROOT / ".env").get("TABPFN_TOKEN") or None


def real_scorer() -> ChurnRiskScorer:
    """Real TabPFN over the artifact bundle, built once per session (slow on CPU)."""
    global _REAL_SCORER
    if _REAL_SCORER is None:
        os.environ.setdefault("TABPFN_TOKEN", tabpfn_token() or "")
        _REAL_SCORER = ChurnRiskScorer(ARTIFACTS, device="auto")
    return _REAL_SCORER


def fake_scorer() -> ChurnRiskScorer:
    """Real artifact bundle + fake classifier, built once per test session."""
    global _SCORER
    if _SCORER is None:
        _SCORER = ChurnRiskScorer(ARTIFACTS, device="cpu", classifier_factory=FakeTabPFN)
    return _SCORER


def _labeled(tenant_id: str, n: int, seed: int) -> list[LabeledExample]:
    """Treated users mostly stay; untreated low-activity users mostly leave.

    That makes low-activity users PERSUADABLE and busy users SURE_THINGs.
    """
    rng = random.Random(seed)
    rows = []
    for i in range(n):
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
            user_pseudonym=f"hist{i}", features=features, arm=Arm.ENGINE if treated else Arm.CONTROL,
            treated=treated, retained=retained, churn_risk=0.5, impact_score=0.3,
            pattern_type="STABLE", incentive_code="CASHBACK_10K" if treated else None,
            cost_idr=10_000 if treated else 0, business_value_idr=freq * 150_000,
            realized_value_idr=float(freq * 150_000 if retained else 0),
        ))
    return rows


def _event(eid, etype, user, when, payload=None, region="ID-JK", cohort="cohort-1"):
    return {
        "client_event_id": eid, "event_type": etype, "occurred_at": when.isoformat(),
        "user_ref": user, "payload": payload or {},
        "user_attributes": {"region_code": region, "cohort_key": cohort, "full_name": "never-kept"},
    }


def wallet_events() -> list[dict]:
    events, n = [], 0

    def add(etype, user, days_ago, payload=None, cohort="cohort-1"):
        nonlocal n
        n += 1
        events.append(_event(f"w{n}", etype, user, NOW - timedelta(days=days_ago), payload, cohort=cohort))

    # Circle A: w0..w3 transfer often. w1..w3 go silent in the last 30 days; w0 stays lightly active.
    circle_a = ["w0", "w1", "w2", "w3"]
    for day in range(40, 110, 6):
        for i, a in enumerate(circle_a):
            b = circle_a[(i + 1) % 4]
            add("wallet.transfer.sent", a, day, {"amount": 25000, "recipient_ref": b})
    for day in (3, 12):
        add("wallet.payment.merchant", "w0", day, {"amount": 60000})
    # Circle B: w4..w7 healthy and busy.
    circle_b = ["w4", "w5", "w6", "w7"]
    for day in range(1, 110, 5):
        for i, a in enumerate(circle_b):
            b = circle_b[(i + 1) % 4]
            add("wallet.transfer.sent", a, day, {"amount": 30000, "recipient_ref": b})
    # Individual users: low-activity w8..w15, busy w16..w19.
    for u in range(8, 16):
        for day in (4, 19):
            add("wallet.payment.merchant", f"w{u}", day, {"amount": 40000 + u * 1000})
    for u in range(16, 20):
        for day in range(1, 30, 2):
            add("wallet.topup.completed", f"w{u}", day, {"amount": 100000})
    add("wallet.unknown.thing", "w8", 2)  # unmapped vocabulary
    return events


def paylater_events() -> list[dict]:
    events, n = [], 0

    def add(etype, user, days_ago, payload=None):
        nonlocal n
        n += 1
        events.append(_event(f"p{n}", etype, user, NOW - timedelta(days=days_ago), payload,
                             region="ID-JB", cohort="cohort-2"))

    for u in range(12):
        user = f"p{u}"
        add("paylater.loan.disbursed", user, 80, {"principal": 1_500_000})
        add("paylater.checkout.completed", user, 10, {"order_total": 200_000 + u * 5000})
        add("paylater.installment.paid", user, 20, {"amount_paid": 250_000})
    for days in (5, 25):  # p0 is repayment-stressed
        add("paylater.installment.overdue", "p0", days, {"amount_due": 250_000})
    return events


def _mapping(name: str) -> dict:
    return json.loads((FIXTURES / "mappings" / name).read_text(encoding="utf-8"))


def _incentives() -> list[Incentive]:
    data = json.loads((FIXTURES / "incentives.json").read_text(encoding="utf-8"))
    return [Incentive.model_validate(i) for i in data["incentives"]]


def build_store() -> InMemoryStore:
    s = InMemoryStore()
    s.add_tenant(TenantRecord(WALLET_ID, "demo-wallet", "WALLET", _mapping("wallet.json")))
    s.add_tenant(TenantRecord(PAYLATER_ID, "demo-paylater", "LENDING", _mapping("paylater.json")))
    for tenant_id, events in ((WALLET_ID, wallet_events()), (PAYLATER_ID, paylater_events())):
        s.add_raw_events(tenant_id, events)
        s.set_incentives(tenant_id, _incentives())
        s.save_labeled_examples(_labeled(tenant_id, 120, seed=7))
    return s
