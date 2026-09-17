"""Integration test for the worker poll loop against a real, migrated
Postgres. Covers claim -> execute -> SUCCEEDED, the retry budget, stale-claim
reclaim, and shutdown. Skips (never silently) without Postgres.
"""
from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from persistence.repositories import pipeline as pipeline_repo
from persistence.session import make_engine, tenant_session
from test_postgres_store import _env  # shared env/skip helpers (conftest puts tests/ on sys.path)
from worker.main import poll_forever, poll_tenant
from worker.settings import WorkerSettings


@pytest.fixture(scope="module")
def urls() -> dict[str, str]:
    host, port = _env("POSTGRES_HOST") or "localhost", _env("POSTGRES_PORT") or "5432"
    db = _env("POSTGRES_DB") or "retention"
    superuser_pw, worker_pw = _env("POSTGRES_PASSWORD"), _env("APP_WORKER_DB_PASSWORD")
    if not (superuser_pw and worker_pw):
        pytest.skip("Postgres credentials not available -- see tests/invariants/README.md")
    urls = {
        "superuser": f"postgresql+psycopg://postgres:{superuser_pw}@{host}:{port}/{db}",
        "worker": f"postgresql+psycopg://app_worker:{worker_pw}@{host}:{port}/{db}",
    }
    try:
        engine = sa.create_engine(urls["superuser"], pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        engine.dispose()
    except Exception:  # noqa: BLE001 -- connection failures vary by driver/OS; any of them means "skip"
        pytest.skip(f"cannot reach Postgres at {host}:{port}")
    return urls


@pytest.fixture
def superuser_engine(urls):
    engine = sa.create_engine(urls["superuser"])
    yield engine
    engine.dispose()


@pytest.fixture
def worker_engine(urls):
    engine = make_engine(urls["worker"])
    yield engine
    engine.dispose()


@pytest.fixture
def settings(urls) -> WorkerSettings:
    return WorkerSettings(
        pseudonym_hmac_secret="test-pseudonym-secret",
        measurement_hmac_secret="test-measurement-secret",
        database_url=urls["worker"],
        worker_poll_interval_seconds=0,
        worker_max_retries=2,
        worker_stale_claim_seconds=60,
        tabpfn_enabled=False,
        explain_llm_enabled=False,
        external_signal_fixture_dir="does-not-exist",
    )


@pytest.fixture
def tenant_id(superuser_engine) -> str:
    """A WALLET tenant a pipeline run can actually complete against."""
    tid = str(uuid.uuid4())
    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, display_name, profile_type) "
                "VALUES (:id, :slug, 'Poll Loop Tenant', 'WALLET')"
            ),
            {"id": tid, "slug": f"poll-test-{tid[:8]}"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO event_type_mappings (id, tenant_id, client_event_type, "
                " canonical_event_type, amount_field_path, occurred_at_field_path, active) "
                "VALUES (gen_random_uuid(), :tid, 'txn.payment', 'PAYMENT', 'amount', 'created_at', true)"
            ),
            {"tid": tid},
        )
    yield tid
    with superuser_engine.begin() as conn:
        for table in ("risk_scores", "feature_snapshots", "experiment_assignments", "experiments",
                      "users", "canonical_events", "raw_events", "external_signals", "audit_log",
                      "pipeline_runs", "event_type_mappings", "incentives"):
            conn.execute(sa.text(f"DELETE FROM {table} WHERE tenant_id = :tid"), {"tid": tid})
        conn.execute(sa.text("DELETE FROM tenants WHERE id = :tid"), {"tid": tid})


def queue_run(superuser_engine, tenant_id: str, **overrides) -> str:
    run_id = str(uuid.uuid4())
    values = {"id": run_id, "tid": tenant_id, "status": "QUEUED", "attempts": 0, "started_at": None}
    values.update(overrides)
    with superuser_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO pipeline_runs (id, tenant_id, status, attempts, started_at, stages, "
                " reason_source_counts) "
                "VALUES (:id, :tid, :status, :attempts, :started_at, '{}'::jsonb, '{}'::jsonb)"
            ),
            values,
        )
    return run_id


def read_run(superuser_engine, run_id: str):
    with superuser_engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT status, attempts, error, finished_at FROM pipeline_runs WHERE id = :id"),
            {"id": run_id},
        ).one()


def test_queued_run_is_claimed_executed_and_marked_succeeded(
    superuser_engine, settings, tenant_id
) -> None:
    run_id = queue_run(superuser_engine, tenant_id)

    executed = poll_forever(settings, shutdown=threading.Event(), max_cycles=1)

    assert executed == 1
    row = read_run(superuser_engine, run_id)
    assert row.status == "SUCCEEDED"
    assert row.attempts == 1
    assert row.finished_at is not None


def test_shutdown_before_first_cycle_does_no_work(superuser_engine, settings, tenant_id) -> None:
    run_id = queue_run(superuser_engine, tenant_id)
    shutdown = threading.Event()
    shutdown.set()

    assert poll_forever(settings, shutdown=shutdown, max_cycles=5) == 0
    assert read_run(superuser_engine, run_id).status == "QUEUED"


def test_failed_run_requeues_until_retry_budget_is_spent(
    worker_engine, superuser_engine, settings, tenant_id
) -> None:
    run_id = queue_run(superuser_engine, tenant_id, attempts=1)

    with tenant_session(worker_engine, tenant_id) as session:
        pipeline_repo.requeue_or_fail(
            session, tenant_id=tenant_id, run_id=uuid.UUID(run_id),
            max_retries=settings.worker_max_retries, error="RISK: boom",
        )
    assert read_run(superuser_engine, run_id).status == "QUEUED"

    with superuser_engine.begin() as conn:
        conn.execute(sa.text("UPDATE pipeline_runs SET attempts = 2 WHERE id = :id"), {"id": run_id})
    with tenant_session(worker_engine, tenant_id) as session:
        pipeline_repo.requeue_or_fail(
            session, tenant_id=tenant_id, run_id=uuid.UUID(run_id),
            max_retries=settings.worker_max_retries, error="RISK: boom",
        )

    row = read_run(superuser_engine, run_id)
    assert row.status == "FAILED"
    assert row.error == "RISK: boom"
    assert row.finished_at is not None


def test_stale_claim_is_reclaimed_then_failed_once_budget_is_gone(
    worker_engine, superuser_engine, settings, tenant_id
) -> None:
    abandoned = datetime.now(UTC) - timedelta(seconds=settings.worker_stale_claim_seconds + 60)
    retryable = queue_run(superuser_engine, tenant_id, status="RUNNING", attempts=1,
                          started_at=abandoned)
    exhausted = queue_run(superuser_engine, tenant_id, status="RUNNING", attempts=2,
                          started_at=abandoned)
    fresh = queue_run(superuser_engine, tenant_id, status="RUNNING", attempts=1,
                      started_at=datetime.now(UTC))

    with tenant_session(worker_engine, tenant_id) as session:
        reclaimed = pipeline_repo.reclaim_stale(
            session, tenant_id=tenant_id, stale_seconds=settings.worker_stale_claim_seconds,
            max_retries=settings.worker_max_retries,
        )

    assert {str(r.id) for r in reclaimed} == {retryable, exhausted}
    assert read_run(superuser_engine, retryable).status == "QUEUED"
    assert read_run(superuser_engine, exhausted).status == "FAILED"
    assert read_run(superuser_engine, fresh).status == "RUNNING"


def test_claim_skips_runs_another_worker_already_holds(
    worker_engine, superuser_engine, settings, tenant_id
) -> None:
    """FOR UPDATE SKIP LOCKED: a second replica polling the same tenant while
    the first holds the row takes no work rather than double-running it."""
    queue_run(superuser_engine, tenant_id)
    other = make_engine(settings.database_url)
    try:
        with tenant_session(other, tenant_id) as holding:
            held = pipeline_repo.claim_queued(holding, tenant_id=tenant_id, limit=1)
            assert len(held) == 1
            # Same transaction still open, row still locked.
            assert poll_tenant(worker_engine, tenant_id, settings, None) == 0
    finally:
        other.dispose()
