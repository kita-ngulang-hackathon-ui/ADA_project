"""external-signals (L1) — Feed items to canonical cohort/region/client signals."""
from external_signals.attach import resolve_for_user
from external_signals.feed_models import FeedItem
from external_signals.normalize import to_signal

__all__ = ["FeedItem", "resolve_for_user", "to_signal"]
