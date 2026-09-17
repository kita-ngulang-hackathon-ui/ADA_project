"""Recommendation persistence (requirement 8).

TODO:
- create_pending(): worker path, status PENDING_APPROVAL only.
- approve()/reject()/mark_delivered(): console path, require reviewer_id.
- list_pending(), get().
Worker code must never call approve/mark_delivered; the DB role enforces it too.
"""
