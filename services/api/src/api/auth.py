"""Authentication dependencies.

TODO:
- require_tenant_api_key(): Bearer token -> tenant (hmac.compare_digest).
- require_console_reviewer(): session -> reviewer_id in CONSOLE_DEMO_REVIEWERS.
  Never default the reviewer id (requirement 8).
"""


def require_tenant_api_key():
    raise NotImplementedError


def require_console_reviewer():
    raise NotImplementedError
