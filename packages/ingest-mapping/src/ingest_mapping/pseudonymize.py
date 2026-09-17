"""THE pseudonymization boundary. Only ingest_mapping may import this.

pseudonym = HMAC_SHA256(PSEUDONYM_HMAC_SECRET, f"{tenant_id}:{raw_ref}").hexdigest()

Keyed per tenant, so the same person in two tenants gets unrelated pseudonyms.
No reverse lookup exists anywhere. Never log raw_ref.
"""
import hashlib
import hmac


def pseudonymize(tenant_id: str, raw_ref: str, secret: bytes) -> str:
    if not secret:
        raise ValueError("pseudonymization secret must not be empty")
    message = f"{tenant_id}:{raw_ref}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()
