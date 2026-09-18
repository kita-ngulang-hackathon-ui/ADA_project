# ADA Solutions

**Intelligent real-time solutions** — a retention and loyalty recommendation engine for Indonesian fintechs.

Built for Hackathon UI 2026 (Universitas Indonesia), BNI Ventures challenge track: customer retention and transaction loyalty.

---

## The problem

Indonesian digital wallets lose customers quietly. Someone does not announce they are leaving — they simply transact less, then stop. By the time a monthly churn report flags them, the relationship is over.

The usual answer is a churn model plus a blast campaign. That fails in three specific ways:

1. **It pays people who were never going to leave.** A high-risk score does not mean an incentive will change the outcome.
2. **It misreads social churn as individual churn.** In a wallet, people transact *with each other*. When someone's circle goes quiet, their own numbers look fine right up until they leave too.
3. **It cannot tell a market dip from a customer problem.** When an entire cohort slows down because the sector slowed down, spending retention budget on them is wasted.

ADA is built around those three failures.

## What ADA does

A client fintech sends us events as they happen. We return **ranked, budget-allocated, individually-explained retention recommendations** — and a human at the client approves every one before anything reaches a customer.

```
client events ──► ingest ──► churn risk ──► circle graph ──► uplift ──► policy ──► rank ──► budget
                     │                                                                        │
              market signals ──────────────────────────────────────────────────────┘          ▼
                (cohort level)                                                    human approval gate
                                                                                              │
                                                                          approved offers ────┘
                                                                                              │
                                                              measured against a held-out control
```

## See it running

Requires Docker, `make`, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
cp .env.example .env     # fill in secrets
make demo                # postgres + api + worker + console, migrated and seeded
```

| Surface | URL |
|---|---|
| Ops console | http://localhost:3000 |
| API docs (OpenAPI) | http://localhost:8000/docs |

To drive real traffic through it, run the companion **`bank_demo`** repository — a working retail bank (desktop internet-banking portal + `wndr` mobile superapp). Every button press there becomes a real HTTP event into this engine. Nothing between the two is faked.

```bash
make test              # 183 tests
make test-invariants   # the guarantees that must never break
make lint-imports      # architectural layer contracts
```

## What makes it different

**Circle churn, not just individual churn.** We build a transaction graph from who actually pays whom, then compute `delta_stability` — how much a person's *neighbours'* activity has changed versus 30 days ago. A customer whose own activity is flat but whose circle has gone quiet is flagged before their own numbers move. The engine tags this `CIRCLE_SPECIFIC` and distinguishes it from `MARKET_DRIVEN`, where a whole cohort dipped together and a negative market signal corroborates it. Churn risk and circle stability are stored and shown **separately, never blended** — the divergence between them is the signal.

**Uplift, not risk.** Every candidate goes through a two-model counterfactual that sorts customers into four segments: `PERSUADABLE`, `SURE_THING`, `LOST_CAUSE`, `SLEEPING_DOG`. Only persuadables get an offer. Sure things would have stayed anyway; lost causes will not be saved; **sleeping dogs get worse if you contact them**. A pure risk model cannot make that distinction and will spend budget on all four.

**A human approves everything.** The worker that generates recommendations has no code path to approve one, and the `app_worker` database role has no grant that permits it. Approval requires a named reviewer, enforced independently at four layers: application code, a domain state machine, database `CHECK` constraints, and Postgres role grants. Deleting every line of the approval check in the API would still not let an unapproved recommendation reach a customer.

**Market signals never touch an individual.** External market and sentiment data is scoped to client, region, or cohort only. The `external_signals` table *has no user column*, and an invariant test asserts it never gains one. Personalisation happens entirely on the client's own first-party transaction data.

**The LLM may only narrate facts it was given.** Explanations are generated from a computed fact sheet. A validator rejects any number that does not match the fact sheet, and any rejection falls back to a deterministic template. The model cannot invent a reason, a figure, or a justification.

**Budget is allocated, not sprayed.** A 0-1 knapsack picks the highest-priority set that fits the budget, records runner-ups, and writes down an explicit exclusion reason for every candidate it did not pick — `POLICY_FREQUENCY_CAP`, `SEGMENT_SLEEPING_DOG`, `CONTROL_HOLDOUT` and so on. Every decision is auditable.

**Results are measured, not asserted.** Customers are assigned to `ENGINE`, `CONTROL` and `NAIVE` arms. Lift is computed against a held-out control and a naive risk-only baseline, and measured outcomes feed back as labeled examples for the next cycle.

## Proven end-to-end

The numbers below are from a full live run of this stack, not projections:

| | |
|---|---|
| Real events ingested over HTTP from `bank_demo` | **24,206** accepted, 0 rejected |
| Customers scored | **120** |
| Canonical events after mapping | **17,816** |
| Recommendations produced | **169**, every one `PENDING_APPROVAL` |
| Of those, group offers to whole transaction circles | **9 circles** |
| Narrations generated by a self-hosted Qwen3-8B | **73** |
| Backend tests / invariants / layer contracts | **183 passed** / 4 passed / 6 kept |

The ops console reads this same data live — the dashboard's risk bands are computed from real churn scores, and its segment split from real transaction volume.

## Architecture

Strict layering, enforced by `.importlinter` in CI (`make lint-imports`):

```
packages/                 Python libraries (uv workspace)
  core-contracts/         L0  domain types, enums, state machine
  ingest-mapping/         L1  client vocabulary -> canonical events, pseudonymization
  external-signals/       L1  feed items -> cohort-scoped signals
  graph-signal/           L1  relationship graph, delta_stability, pattern tag
  churn-risk/             L1  TabPFN churn classifier + signal attribution
  impact/                 L1  uplift engine, four segments
  policy-guard/           L1  hard constraint enforcement
  ranker/                 L1  TabPFN priority scoring
  allocator/              L1  budget-constrained knapsack
  explain/                L1  fact sheet, prompt, validator, template
  measurement/            L1  arm assignment + incremental lift
  feedback/               L1  outcomes -> labeled examples
  persistence/            L2  SQLAlchemy models, repositories, RLS
services/
  api/                    L3  FastAPI: ingestion API + console API
  worker/                 L3  pipeline runner, feed adapter, LLM narrator
apps/web/                 L4  Next.js ops console
```

L0 depends on nothing. L1 packages are mutually independent and perform **no I/O** — they are pure functions over data, which is why they are testable without a database. L2 is the only layer that touches Postgres. Every tenant query runs under row-level security.

**Onboarding a new client fintech is inserting mapping rows, not writing code.** Each client's own event vocabulary (`wallet.transfer.sent`, `paylater.installment.paid`, …) maps to a canonical model through per-tenant config.

## What is real and what is synthetic

All demo customers and their transactions are **synthetic**. No real customer data is used anywhere.

What is genuinely real in the demo:

- Events travel over real HTTP from a separate application into the ingestion API — no fixtures, no shortcuts.
- Churn scoring runs on TabPFN, a real in-context tabular model, with no per-tenant training loop.
- Explanations are generated by a real self-hosted Qwen3-8B, validated per narration.
- The approval gate, RLS, role separation and audit log are real and enforced.

The external market feed is a canned snapshot committed to `fixtures/` so the demo runs without internet.

## Known limits

Stated plainly, because they matter for judging what is built versus planned:

- Five console routes are still stubs: `/allocation`, `/measurement`, `/client-surface`, `/ops/recommendations`, `/users/[pseudonym]`. The dashboard, suggested-actions and actions-overview screens are fully wired to live data.
- `tools/synthetic/generate.py` and `load_fixture.py` are unimplemented; demo data is seeded from hand-authored `fixtures/` plus the `bank_demo` event stream.
- The ops console's segment view maps real churn risk and real transaction volume onto RFM-style segment cards. Those cards are a presentation layer — the pipeline itself reasons in churn risk and the four uplift segments, not RFM clusters.
- Outcome reporting needs an `experiment_id` that the recommendations endpoint does not yet return, so lift measurement is not yet closed end-to-end in the UI.
- A small fraction of LLM narrations come back truncated; the console filters those and falls back to template text.

## Decisions (REQUIREMENTS §6 — resolved)

- Project name and branding: **ADA Solutions**.
- Demo tenant: single tenant, branded **BNI**, digital wallet / superapp profile.
- Incentive catalog: three wallet incentives (cashback, transfer-fee waiver, group split-bill reward).
- Frequency cap: 2 contacts per 30 days.
- Relationship-graph signal: enabled, no tenant carve-out.
- External signals: cohort/region level only, never per user; canned feed source.
- LLM: self-hosted **Qwen3-8B** (OpenAI-compatible endpoint), with deterministic template fallback.

## Team

| | |
|---|---|
| Muhammad Kaila Aidam Riyan | Backend |
| Randuichi Touya | Backend |
| Abdurrahman Ammar Abqary | Frontend |
| Darryl Ahmad Muaz | Design / UIUX |
| Arsy Atrisya Dewi | Business |
