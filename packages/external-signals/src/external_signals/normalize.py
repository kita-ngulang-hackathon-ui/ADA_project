"""FeedItem -> ExternalSignal. Pure."""
import hashlib

from core_contracts import ExternalSignal, ScopeType, SignalType

from external_signals.feed_models import FeedItem

_ALLOWED_SCOPES = {s.value for s in ScopeType}


def to_signal(item):
    """Clamp value to [-1, 1]; reject any scope that is not CLIENT/REGION/COHORT (§4)."""
    if isinstance(item, dict):
        item = FeedItem.model_validate(item)
    scope = item.scope_type.upper()
    if scope not in _ALLOWED_SCOPES:
        raise ValueError(f"scope {item.scope_type!r} is not allowed; signals never attach to a user")
    signal_type = SignalType(item.signal_type.upper())
    if item.observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    value = max(-1.0, min(1.0, float(item.value)))
    key = f"{item.source}|{scope}|{item.scope_key}|{signal_type.value}|{item.observed_at.isoformat()}"
    return ExternalSignal(
        signal_id=hashlib.sha256(key.encode()).hexdigest()[:16],
        source=item.source,
        scope_type=ScopeType(scope),
        scope_key=item.scope_key,
        signal_type=signal_type,
        value=value,
        observed_at=item.observed_at,
    )
