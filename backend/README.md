# [PROJECT NAME TBD] — backend

Retention and loyalty recommendation engine for Indonesian fintechs.
Built for Hackathon UI 2026 (Universitas Indonesia, 17–18 Sep 2026), BNI Ventures
challenge track: customer retention and transaction loyalty.

Team: Aidam, Randuichi Touya, Abdurrahman Ammar Abqary.

This folder is the complete, self-contained backend: the Python packages, both
services, the migrations and the demo data. It references nothing outside
itself and is hosted on its own. The Next.js console lives in `../frontend` and
reaches this API over `NEXT_PUBLIC_API_BASE_URL`.

> **Status: skeleton.** Directories, stub files, and implementation guides only.
> No logic is implemented yet. Each module's `README.md` describes what to build.
> Source of truth for scope: [`REQUIREMENTS (1).md`](REQUIREMENTS%20(1).md).

## What it does

1. Ingests events from more than one client fintech, each with its own vocabulary, through per-client config.
2. Ingests external market/sentiment signals at client/region/cohort level (never per user).
3. Scores churn risk with TabPFN (in-context, no training loop).
4. Builds the transaction-circle graph, computes `delta_stability`, tags `CIRCLE_SPECIFIC` vs `MARKET_DRIVEN`.
5. Supports group recommendations over transaction circles.
6. Estimates incentive impact with a two-model counterfactual (persuadable, sure thing, lost cause, sleeping dog).
7. Decides: hard policy filters, then TabPFN ranking, then 0-1 knapsack budget allocation with runner-ups.
8. Produces recommendations only. A human reviewer must approve before anything is actionable.
9. Explains each recommendation with an LLM that may only narrate computed facts (template fallback).
10. Measures real lift against a held-out control and a naive baseline.
11. Feeds outcomes back as new in-context labeled examples.

All demo data is **synthetic**.

## Layout

```
packages/                 Python libraries (uv workspace)
  core-contracts/         L0  domain types, enums, state machine
  ingest-mapping/         L1  client vocabulary -> canonical events, pseudonymization
  external-signals/       L1  feed items -> canonical cohort signals
  graph-signal/           L1  relationship graph, delta_stability, pattern tag
  churn-risk/             L1  TabPFN churn classifier + signal attribution
  impact/                 L1  Intervention Impact Engine, four segments
  policy-guard/           L1  hard constraint enforcement
  ranker/                 L1  TabPFN priority scoring (Decision Engine pass 2)
  allocator/              L1  budget-constrained knapsack selection
  explain/                L1  fact sheet, prompt, validator, template
  measurement/            L1  arm assignment + incremental lift
  feedback/               L1  outcomes -> labeled examples
  persistence/            L2  SQLAlchemy models, repositories
services/
  api/                    L3  FastAPI: ingestion API + console API
  worker/                 L3  pipeline runner, feed adapter, LLM narrator
tools/synthetic/          Synthetic dataset generator
fixtures/                 Canned external feed, mappings, incentives
artifacts/                Trained churn-scorer bundle (context parquet + schema)
migrations/               Alembic migrations
tests/invariants/         Non-skippable guarantee tests
deploy/                   systemd units, bootstrap script, DEPLOY.md
```

The L4 console (Next.js) is not here — it is `../frontend`.

## Layer rules

- L0 depends on nothing. L1 packages depend only on L0, are mutually independent, and do no I/O.
- L2 (`persistence`) is the only database access. L3 services wire everything together.
- `.importlinter` enforces these rules (`make lint-imports`).

## Running locally

Requirements: `make`, [uv](https://docs.astral.sh/uv/), and Docker + Docker
Compose if you want Postgres and the services in containers.

```bash
cp .env.example .env     # fill secrets; __TBD__ values are open decisions
make demo                # up + migrate + seed, then prints URLs
make test                # Python tests
make test-invariants     # hard guarantees
```

Every command must run from this directory. Both services load `.env` and
resolve `fixtures/` and `artifacts/` relative to the working directory.

## Deploying

Production is a plain VM with systemd, no Docker. The runbook is
[`deploy/DEPLOY.md`](deploy/DEPLOY.md); `docker-compose.yml` is for local
development only.

```bash
./deploy/bootstrap.sh    # uv sync + alembic upgrade head
```

## Open decisions (REQUIREMENTS §6)

- Project name and branding.
- Incentive catalog (`fixtures/incentives.json`).
- Frequency-cap threshold (`FREQUENCY_CAP_*`).
- Whether the paylater/lending tenant gets the relationship-graph signal.
- External signals: strictly cohort/region-level (default) vs per-user resolution.
- External source: canned feed vs real API (`EXTERNAL_SIGNAL_SOURCE`).
- LLM provider and model (`EXPLAIN_LLM_*`).
- Team role mapping.

## Spec documents

The spec images (`spec_*_of_3.png`) contain `ARCHITECTURE.md`, `API_CONTRACTS.md`,
`PRD.md`, `DECISIONS.md`, `TASKS.md`, `SYNTHETIC_DATA.md`, `DEMO_SCRIPT.md`, and
`CLAUDE.md`. These are still to be added to the repo as text files.
