"""Raw and canonical event persistence.

TODO:
- insert_raw_event(): ON CONFLICT (tenant_id, client_event_id) DO NOTHING; return duplicate flag.
- claim_unprocessed(batch_size): SELECT ... FOR UPDATE SKIP LOCKED.
- mark_processed / mark_unmapped.
- insert_canonical_events().
"""
