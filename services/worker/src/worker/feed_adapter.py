"""External feed adapter: canned fixture or live source with fallback (requirement 2, §4 resilience).

TODO:
- load_feed(settings) -> list[FeedItem-shaped dict].
- canned: read fixtures/external/*.json.
- live: httpx GET with short timeout; on failure use last snapshot, then canned.
"""
