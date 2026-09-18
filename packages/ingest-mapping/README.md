# ingest-mapping (L1)

Turns each client fintech's own event vocabulary into `CanonicalEvent`.
Onboarding a new client is a config change, not a code change (requirement 1).
This is the **only** package allowed to see raw user identifiers.

## Layer rules
- Imports: `core_contracts` only. No I/O. The HMAC secret is passed in by the caller.
- No other package may import `pseudonymize` (enforced by `.importlinter`).

## Files

| File | What to implement |
|---|---|
| `mapping_config.py` | `EventTypeMapping` model: `client_event_type`, `canonical_event_type`, `amount_field_path`, `counterparty_field_path`, `occurred_at_field_path`, `active`. `TenantMappingConfig` = list of mappings for one tenant. Loader from a dict (the API reads JSON from DB/fixtures and passes it in). Validate that no two rows map the same `client_event_type`. |
| `normalize.py` | `normalize(payload: dict, mapping: TenantMappingConfig, pseudonymizer) -> CanonicalEvent`. Resolve dotted field paths. Convert amount to int IDR. Drop attributes not whitelisted. Raise `MappingError` for unknown event types (the worker marks the raw row `unmapped`, it does not crash). |
| `pseudonymize.py` | `pseudonymize(tenant_id, raw_ref, secret) -> str` = `HMAC_SHA256(secret, f"{tenant_id}:{raw_ref}")`, hex. Keyed per tenant so the same person in two tenants gets unrelated pseudonyms. No reverse lookup exists anywhere. |

## Inputs / outputs
- In: raw client JSON (`client_event_id`, `event_type`, `occurred_at`, `user_ref`, `payload`, `user_attributes`).
- Out: `CanonicalEvent`.

## Tests to write
- Wallet and paylater configs map their own vocabularies to the same canonical types.
- Unknown event type raises `MappingError`.
- Same `raw_ref` under two tenants gives different pseudonyms.
- Output never contains the raw `user_ref`.

## Related
Requirement 1, §4 data protection. Fixtures: `fixtures/mappings/*.json`.
