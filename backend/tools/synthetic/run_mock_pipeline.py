"""Run one full pipeline pass over the in-memory mock world. No database.

    uv run python -m tools.synthetic.run_mock_pipeline
    make mock-run

Settings come from .env, so this exercises the configured narrator: with
EXPLAIN_LLM_ENABLED=true every recommendation is sent to the LLM, and the
printed reason source says LLM or TEMPLATE per narration. A narration that
invents a number is rejected by the validator and falls back to the template,
which is a pass, not a failure.

All data is synthetic (§4). Nothing is written to Postgres or to fixtures.
"""
import argparse
import sys

from worker.llm_narrator import narrator_from_settings
from worker.pipeline import run_pipeline
from worker.settings import WorkerSettings

from tools.synthetic.mock_world import PAYLATER_ID, WALLET_ID, build_store

TENANTS = {"demo-wallet": WALLET_ID, "demo-paylater": PAYLATER_ID}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant-slug", choices=sorted(TENANTS), default="demo-wallet")
    parser.add_argument("--show", type=int, default=3, help="how many narrations to print in full")
    args = parser.parse_args(argv)

    settings = WorkerSettings()
    narrator = narrator_from_settings(settings)
    store, now = build_store(settings)
    tenant_id = TENANTS[args.tenant_slug]

    print(f"tenant     {args.tenant_slug}")
    if narrator is None:
        print("narrator   none -- template narration only "
              "(set EXPLAIN_LLM_ENABLED/BASE_URL/MODEL in .env)")
    else:
        print(f"narrator   {narrator.model} at {narrator.base_url}")
    print()

    result = run_pipeline(tenant_id, "mock-run", store=store, settings=settings, now=now,
                          narrator=narrator)

    for outcome in result.stages:
        print(f"{outcome.stage:<9} {outcome.status:<7} {outcome.detail}")

    narrations = store.narrations.get(tenant_id, [])
    print(f"\n{len(narrations)} narration(s)")
    for row in narrations[: args.show]:
        print(f"\n[{row['source']}] {row['text']}")

    if result.status != "DONE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
