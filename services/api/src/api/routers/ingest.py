"""Client ingestion API (requirement 1).

POST /v1/events        single event  -> 202 {raw_event_id, duplicate}
POST /v1/events:batch  up to 500     -> 202 {accepted, duplicates, rejected[]}

TODO:
- Validate request shape only; do not map or score inline.
- Insert raw row idempotently on (tenant_id, client_event_id).
- Must stay fast; client transaction must never depend on this call.
"""
