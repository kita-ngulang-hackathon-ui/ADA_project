# explain (L1)

Builds everything the one generative step needs (requirement 9). The LLM may
only **narrate** numbers that are already computed. The actual LLM HTTP call
lives in `services/worker` (L1 packages do no I/O); this package defines the
prompt, the validator, and the deterministic template fallback.

## Layer rules
- Imports: `core_contracts` only. No HTTP, no LLM SDK.

## Files

| File | What to implement |
|---|---|
| `fact_sheet.py` | `build_fact_sheet(candidate, risk, impact, circle, policy, allocation) -> FactSheet`. Includes top pick and runner-up, reason factors, external signal (cohort level), and `synthetic_data: true` flag. `fact_sheet_hash = sha256(canonical_json(fact_sheet))`. |
| `prompt.py` | `build_prompt(fact_sheet) -> (system, user)`. System prompt forbids new facts, advice, or numbers not in the sheet. Temperature 0. Max tokens `EXPLAIN_LLM_MAX_TOKENS`. |
| `validator.py` | `validate_narration(text, fact_sheet)`. Reject if any number in the text is not in the fact sheet (after formatting normalization), if it names an unknown user/counterparty, or if it exceeds length. |
| `template.py` | `render_template(fact_sheet) -> str`. Deterministic Bahasa/English sentence built only from the fact sheet. Used when the LLM is disabled, times out, or fails validation (`reason_source="TEMPLATE"`). |
| `narrator_protocol.py` | `Narrator` Protocol (`narrate(system, user) -> str`) that the worker's LLM client implements. |

## Tests to write
- Narration with an invented number is rejected.
- Template output passes the validator for every fact sheet.
- Same fact sheet gives same hash.

## Related
Requirement 9, demo beat 1. Config: `EXPLAIN_LLM_*`.
