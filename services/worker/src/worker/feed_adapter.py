"""External feed adapter: canned fixture or live source with fallback (requirement 2, §4 resilience).

Never raises and never blocks the pipeline for long:
live -> last good live snapshot -> canned fixture -> empty list.
"""
import json
import logging
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

_last_live_snapshot: list[dict] | None = None


def load_canned(fixture_dir: str) -> list[dict]:
    items: list[dict] = []
    directory = Path(fixture_dir)
    if not directory.is_dir():
        log.warning("canned feed directory %s not found", fixture_dir)
        return items
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("skipping unreadable canned feed file %s", path.name)
            continue
        items.extend(data.get("items", []) if isinstance(data, dict) else data)
    return items


def load_live(base_url: str, timeout_s: float) -> list[dict]:
    response = httpx.get(base_url, timeout=timeout_s)
    response.raise_for_status()
    data = response.json()
    return data.get("items", []) if isinstance(data, dict) else list(data)


def load_feed(settings) -> tuple[list[dict], str]:
    """Return (feed items, source used): "canned", "live", "live_snapshot"."""
    global _last_live_snapshot
    if settings.external_signal_source.lower() == "live" and settings.external_signal_live_base_url:
        try:
            items = load_live(settings.external_signal_live_base_url,
                              settings.external_signal_live_timeout_s)
            _last_live_snapshot = items
            return items, "live"
        except Exception as exc:  # timeout, DNS, bad JSON: venue internet must not break the demo
            log.warning("live feed unavailable (%s); falling back", type(exc).__name__)
            if _last_live_snapshot is not None:
                return _last_live_snapshot, "live_snapshot"
    return load_canned(settings.external_signal_fixture_dir), "canned"
