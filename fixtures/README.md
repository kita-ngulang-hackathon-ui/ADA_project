# fixtures

Committed demo data. Everything here is **synthetic**.

| Path | Contents |
|---|---|
| `external/canned_feed.json` | Canned external market/sentiment feed (requirement 2). Items are scoped to CLIENT / REGION / COHORT only. Used when `EXTERNAL_SIGNAL_SOURCE=canned` and as fallback for the live adapter. Must contain the negative cohort signal that makes planted pattern P2 `MARKET_DRIVEN`. |
| `mappings/wallet.json` | Event type mapping config for the `demo-wallet` tenant. |
| `mappings/paylater.json` | Event type mapping config for the `demo-paylater` tenant. |
| `incentives.json` | Incentive catalog for the demo. Contents are an **open decision** (§6). |
| `synthetic/` | Output of `tools/synthetic/generate.py` (not committed until generated). |

## Rules
- Regenerate synthetic fixtures only via `make synthetic`; commit the result.
- Never put real user data here.
