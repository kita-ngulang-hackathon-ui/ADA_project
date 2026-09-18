# fixtures

Committed demo data. Everything here is **synthetic**.

| Path | Contents |
|---|---|
| `external/canned_feed.json` | Canned external market/sentiment feed (requirement 2). Items are scoped to CLIENT / REGION / COHORT only. Used when `EXTERNAL_SIGNAL_SOURCE=canned` and as fallback for the live adapter. Must contain the negative cohort signal that makes planted pattern P2 `MARKET_DRIVEN`. |
| `mappings/wallet.json` | Event type mapping config for the `demo-wallet` tenant. |
| `mappings/paylater.json` | Event type mapping config for a `demo-paylater` tenant. Kept to show that onboarding a second client with a different vocabulary is config, not code; the demo itself runs the single wallet tenant. |
| `incentives.json` | Incentive catalog for the demo. The three `WALLET` entries are the ones seeded. |
| `churn_scorer_mapping.json` | Region/cohort mapping the trained churn scorer expects. |

## Rules
- Regenerate synthetic fixtures only via `make synthetic`; commit the result.
- Never put real user data here.
