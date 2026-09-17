"""THE pseudonymization boundary. Only ingest_mapping may import this
(enforced by .importlinter's pseudonymization-boundary contract).

pseudonym = HMAC_SHA256(PSEUDONYM_HMAC_SECRET, f"{tenant_id}:{raw_ref}").hexdigest()

Tenant ID is mixed into the HMAC input, so the same real-world person
appearing at two tenants produces two unrelated pseudonyms -- cross-client
correlation is cryptographically impossible, not merely forbidden (ADR-009).
"""
import hashlib
import hmac


def pseudonymize(tenant_id: str, raw_ref: str, secret: bytes) -> str:
    message = f"{tenant_id}:{raw_ref}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()
