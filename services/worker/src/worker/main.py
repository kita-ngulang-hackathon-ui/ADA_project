"""Worker entry point (python -m worker.main).

For now this runs one pipeline pass over an InMemoryStore seeded from the
fixtures and an optional raw-events JSON file, then prints the stage summary.

TODO (needs the Postgres PipelineStore): poll loop that claims raw events and
queued runs with FOR UPDATE SKIP LOCKED, retries up to WORKER_MAX_RETRIES,
reclaims stale claims, and handles SIGTERM.
"""
import argparse
import json
import sys
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from core_contracts import Incentive

from worker.llm_narrator import narrator_from_settings
from worker.memory_store import InMemoryStore
from worker.pipeline import run_pipeline
from worker.settings import WorkerSettings
from worker.store import TenantRecord


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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run one pipeline pass (in-memory store).")
    parser.add_argument("--tenant-slug", default="demo-wallet")
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    parser.add_argument("--events", type=Path, help="JSON list of raw client events")
    parser.add_argument("--now", help="RFC 3339 timestamp to run 'as of'")
    args = parser.parse_args(argv)

    settings = WorkerSettings()
    store, tenant_id = seed_store(args.fixtures, args.tenant_slug, args.events)
    now = datetime.fromisoformat(args.now) if args.now else None
    result = run_pipeline(tenant_id, f"run-{uuid.uuid4().hex[:12]}", store=store, settings=settings,
                          now=now, narrator=narrator_from_settings(settings))
    json.dump(asdict(result), sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    if result.status != "DONE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
