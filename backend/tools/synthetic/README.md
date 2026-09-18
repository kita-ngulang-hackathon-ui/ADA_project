# tools/synthetic

Deterministic synthetic dataset generator for the demo. All demo data is
synthetic and must be labeled as such wherever performance is shown (§4).

## Rules
- Seeded by `SYNTHETIC_SEED`. Same seed, same bytes. The committed fixture is regenerated only on purpose.
- Output goes to `fixtures/` and is loaded by `make seed`.
- Planted patterns exist so the demo is reproducible; the pipeline must still **discover** them from data, never read the plant labels.

## Files to implement

| File | What to implement |
|---|---|
| `generate.py` | CLI entry (`python -m tools.synthetic.generate`). Builds both tenants, users, counterparty edges, events over `SYNTHETIC_DAYS_HISTORY`, prior campaign outcomes (treated/control) for the impact model context, and writes JSON fixtures. |
| `profiles.py` | Two tenants with different vocabularies: `demo-wallet` (e-wallet: `wallet.transfer.sent`, `wallet.split.created`, `wallet.topup.completed`, ...) and `demo-paylater` (`paylater.installment.paid`, `paylater.installment.overdue`, ...). Region and cohort assignment. |
| `planted_patterns.py` | P1 circle churn preceding individual churn (demo beat 1). P2 cohort-wide market dip matched by a negative canned external signal (`MARKET_DRIVEN`). P3 persuadables. P4 sure-things and lost causes. P5 sleeping dogs. P6 repayment-stressed paylater users (policy guard denies borrowing incentives). P7 frequency-capped users. |
| `load_fixture.py` | Load fixtures through the ingestion API (so the demo exercises the real path) or directly via `persistence` for speed. |

## Related
`SYNTHETIC_DATA.md` in the spec; config `SYNTHETIC_*`.
