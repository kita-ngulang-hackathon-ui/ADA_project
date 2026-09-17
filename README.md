# ADA Solutions

Intelligent real-time solutions — retention and loyalty recommendation engine
for Indonesian fintechs.
Built for Hackathon UI 2026 (Universitas Indonesia, 17–18 Sep 2026), BNI Ventures
challenge track: customer retention and transaction loyalty.

Team:
- Muhammad Kaila Aidam Riyan — Backend
- Randuichi Touya — Backend
- Abdurrahman Ammar Abqary — Frontend
- Darryl Ahmad Muaz — Designer/UIUX
- Arsy Atrisya Dewi — Business specialist

> **Status: implemented, integration in progress.** All L0-L3 packages and services
> have real logic and tests. Remaining gaps: `apps/web/lib/api.ts` is not wired to
> the backend (frontend runs on mock data), and `tools/synthetic/generate.py` is
> unimplemented (demo currently uses hand-authored `fixtures/` data instead).

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

## Repository layout

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
apps/
  web/                    L4  Next.js console + simulated client surface
tools/synthetic/          Synthetic dataset generator
fixtures/                 Canned external feed, mappings, incentives
migrations/               Alembic migrations
tests/invariants/         Non-skippable guarantee tests
```

## Layer rules

- L0 depends on nothing. L1 packages depend only on L0, are mutually independent, and do no I/O.
- L2 (`persistence`) is the only database access. L3 services wire everything together.
- `.importlinter` enforces these rules (`make lint-imports`).

## Running (once implemented)

```bash
cp .env.example .env     # fill secrets; __TBD__ values are open decisions
make demo                # up + migrate + seed, then prints URLs
make test                # Python tests
make test-invariants     # hard guarantees
```

Requirements: Docker + Docker Compose, `make`, [uv](https://docs.astral.sh/uv/), Node 20+ with pnpm.

## Decisions (REQUIREMENTS §6 — resolved)

- Project name and branding: **ADA Solutions**.
- Incentive catalog: single placeholder incentive (prototype scope, no full catalog).
- Frequency-cap threshold: 2 contacts per 30 days (`FREQUENCY_CAP_MAX_CONTACTS=2`, `FREQUENCY_CAP_WINDOW_DAYS=30`).
- Relationship-graph signal: enabled, full feature, no tenant carve-out.
- Demo tenant: single tenant, branded **BNI**, digital wallet/superapp product type (WONDR-style: transfers, split bill, bill autopay, top-up, QR payment).
- External signals: cohort/region-level only, never per-user.
- External source: canned feed (`EXTERNAL_SIGNAL_SOURCE=canned`).
- LLM provider and model: Gemini, `gemini-2.5-flash`.
- Team role mapping: see Team above.


