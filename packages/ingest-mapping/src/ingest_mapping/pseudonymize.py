"""THE pseudonymization boundary. Only ingest_mapping may import this.

pseudonym = HMAC_SHA256(PSEUDONYM_HMAC_SECRET, f"{tenant_id}:{raw_ref}").hexdigest()

TODO:
- Implement with hmac + hashlib (stdlib only).
- Never log raw_ref.
"""


def pseudonymize(tenant_id: str, raw_ref: str, secret: bytes) -> str:
    raise NotImplementedError
