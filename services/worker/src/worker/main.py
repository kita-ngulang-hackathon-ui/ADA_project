"""Worker entry point (python -m worker.main).

Default: poll Postgres forever. Each cycle, per tenant:
reclaim stale claims -> claim one QUEUED pipeline_runs row
(`FOR UPDATE SKIP LOCKED`) -> run the pipeline -> mark SUCCEEDED, or requeue
until WORKER_MAX_RETRIES is spent and the row goes FAILED.

`--offline` keeps the original fixture pass over an InMemoryStore, for
running the pipeline with no database at all.

Two things shape the loop:

- Tenants are enumerated first, then every later query runs inside that
  tenant's `tenant_session`. A single cross-tenant "find queued work" query
  would return zero rows: RLS hides every pipeline_runs row unless
  app.tenant_id matches (ARCHITECTURE.md §11). `tenants` itself carries no
  RLS policy -- there is nothing wider to scope it by -- so that one lookup
  is the only unscoped query here.
- Raw events are not polled separately. They are claimed by the pipeline's
  own INGEST stage, so a run is the only thing that processes them; posting
  events without queueing a run leaves them for the next run.
"""
import argparse
import json
import logging
import signal
import sys
import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from core_contracts import Incentive
from persistence.repositories import pipeline as pipeline_repo
from persistence.repositories import tenants as tenants_repo
from persistence.session import make_engine, tenant_session
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from worker.churn_scorer import ChurnScorerUnavailable, load_scorer
from worker.llm_narrator import narrator_from_settings
from worker.memory_store import InMemoryStore
from worker.pipeline import run_pipeline
from worker.postgres_store import PostgresPipelineStore
from worker.settings import WorkerSettings
from worker.store import TenantRecord

log = logging.getLogger("worker")


# --------------------------------------------------------------------- poll loop


def list_tenant_ids(engine: Engine) -> list[str]:
    with Session(bind=engine) as session:
        return [str(t.id) for t in tenants_repo.list_tenants(session)]


def stage_error(result) -> str | None:
    for stage in result.stages:
        if stage.status == "FAILED":
            return f"{stage.stage}: {stage.detail.get('error', 'failed')}"
    return None


def execute_run(engine: Engine, tenant_id: str, run_id: uuid.UUID, settings, narrator,
                churn_scorer=None) -> bool:
    """Run one claimed pipeline run. PostgresPipelineStore is built fresh per
    run because its cross-call caches are scoped to exactly one run."""
    store = PostgresPipelineStore(engine, tenant_id)
    try:
        result = run_pipeline(tenant_id, str(run_id), store=store, settings=settings, narrator=narrator,
                              churn_scorer=churn_scorer)
        succeeded = result.status == "DONE"
        error = None if succeeded else stage_error(result)
    except Exception as exc:  # one bad run must not kill the worker
        log.exception("run %s raised outside a stage", run_id)
        succeeded, error = False, f"{type(exc).__name__}: {exc}"

    with tenant_session(engine, tenant_id) as session:
        if succeeded:
            pipeline_repo.finish_run(session, tenant_id=tenant_id, run_id=run_id, succeeded=True)
        else:
            row = pipeline_repo.requeue_or_fail(
                session, tenant_id=tenant_id, run_id=run_id,
                max_retries=settings.worker_max_retries, error=error,
            )
            log.warning("run %s %s: %s", run_id, row.status if row else "missing", error)
    return succeeded


def poll_tenant(engine: Engine, tenant_id: str, settings, narrator, churn_scorer=None) -> int:
    """One tenant's share of a cycle. Returns how many runs were executed."""
    with tenant_session(engine, tenant_id) as session:
        stale = pipeline_repo.reclaim_stale(
            session, tenant_id=tenant_id, stale_seconds=settings.worker_stale_claim_seconds,
            max_retries=settings.worker_max_retries,
        )
        for row in stale:
            log.warning("reclaimed stale run %s -> %s (attempt %s)", row.id, row.status, row.attempts)

        claimed = [
            row.id for row in pipeline_repo.claim_queued(session, tenant_id=tenant_id, limit=1)
        ]

    for run_id in claimed:
        execute_run(engine, tenant_id, run_id, settings, narrator, churn_scorer)
    return len(claimed)


def poll_forever(settings, *, shutdown: threading.Event, max_cycles: int | None = None,
                 churn_scorer=None) -> int:
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required to poll; use --offline for the fixture pass")

    engine = make_engine(settings.database_url)
    narrator = narrator_from_settings(settings)
    executed = cycles = 0
    try:
        while not shutdown.is_set():
            try:
                worked = sum(
                    poll_tenant(engine, tenant_id, settings, narrator, churn_scorer)
                    for tenant_id in list_tenant_ids(engine)
                )
            except Exception:  # a DB blip must not end the service
                log.exception("poll cycle failed")
                worked = 0

            executed += worked
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            if not worked:  # only sleep when idle, so a backlog drains at full speed
                shutdown.wait(settings.worker_poll_interval_seconds)
    finally:
        engine.dispose()
    return executed


def install_signal_handlers(shutdown: threading.Event) -> None:
    """SIGTERM (docker stop) and SIGINT stop the loop after the run in
    flight finishes, so a claim is never abandoned mid-pipeline."""
    def handle(signum, _frame):
        log.info("signal %s received; finishing current run then exiting", signum)
        shutdown.set()

    for name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, handle)


# --------------------------------------------------------------------- offline pass


def seed_store(fixtures: Path, tenant_slug: str, events_file: Path | None) -> tuple[InMemoryStore, str]:
    store = InMemoryStore()
    mapping = None
    for path in sorted((fixtures / "mappings").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("tenant_slug") == tenant_slug:
            mapping = data
    if mapping is None:
        raise SystemExit(f"no mapping fixture for tenant {tenant_slug!r}")
    tenant_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, tenant_slug))
    store.add_tenant(TenantRecord(tenant_id=tenant_id, slug=tenant_slug,
                                  profile_type=mapping["profile_type"], mapping=mapping))
    catalog = json.loads((fixtures / "incentives.json").read_text(encoding="utf-8"))
    store.set_incentives(tenant_id, [Incentive.model_validate(i) for i in catalog["incentives"]])
    if events_file:
        store.add_raw_events(tenant_id, json.loads(events_file.read_text(encoding="utf-8")))
    return store, tenant_id


def run_offline(args, settings, churn_scorer=None) -> None:
    store, tenant_id = seed_store(args.fixtures, args.tenant_slug, args.events)
    now = datetime.fromisoformat(args.now) if args.now else None
    result = run_pipeline(tenant_id, f"run-{uuid.uuid4().hex[:12]}", store=store, settings=settings,
                          now=now, narrator=narrator_from_settings(settings),
                          churn_scorer=churn_scorer)
    json.dump(asdict(result), sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    if result.status != "DONE":
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Poll Postgres for queued pipeline runs.")
    parser.add_argument("--offline", action="store_true",
                        help="run one pipeline pass over fixtures, no database")
    parser.add_argument("--max-cycles", type=int, help="stop after N poll cycles (testing/demo)")
    parser.add_argument("--tenant-slug", default="demo-wallet", help="--offline only")
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures"), help="--offline only")
    parser.add_argument("--events", type=Path, help="--offline only: JSON list of raw client events")
    parser.add_argument("--now", help="--offline only: RFC 3339 timestamp to run 'as of'")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = WorkerSettings()
    # Load the trained scorer once per process, before any run; it stays resident in memory.
    churn_scorer = None
    if settings.churn_scorer_enabled:
        try:
            churn_scorer = load_scorer(settings)
        except ChurnScorerUnavailable as exc:
            raise SystemExit(f"worker startup failed: {exc}") from exc

    if args.offline:
        run_offline(args, settings, churn_scorer)
        return

    shutdown = threading.Event()
    install_signal_handlers(shutdown)
    log.info("worker polling every %ss", settings.worker_poll_interval_seconds)
    executed = poll_forever(settings, shutdown=shutdown, max_cycles=args.max_cycles,
                            churn_scorer=churn_scorer)
    log.info("worker stopped after %s run(s)", executed)


if __name__ == "__main__":
    main()
