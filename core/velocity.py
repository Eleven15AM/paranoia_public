"""
Velocity detection (Layer 2, news only).

An in-memory rolling window of topic-key hits. When a topic is reported by
enough distinct sources within the window, emit one synthetic Event
(category VELOCITY). One surge per topic per cooldown, independent of window
pruning.

No I/O, no persistence: a container restart starts with an empty window.
Thread-safe: the news feed's scheduler thread is the only writer, but the
lock is cheap insurance if a later layer polls other feeds into the same
window.
"""
import logging
import threading
import time

import config
from core.models import Event, utcnow

log = logging.getLogger(__name__)

# (timestamp_epoch, key, source_name, title, source_url)
_window: list[tuple[float, str, str, str, str]] = []
# key -> last_emitted_epoch
_cooldown: dict[str, float] = {}
_lock = threading.Lock()


def extract_keys(title: str, description: str) -> list[str]:
    """Return the velocity topic keys matched in a headline. De-duped."""
    hay = (title or "") + " " + (description or "")
    return sorted({m.lower() for m in config.VELOCITY_RE.findall(hay)})


def _prune_window(now: float) -> None:
    cutoff = now - config.VELOCITY_WINDOW_SECONDS
    # Keep only recent hits. Stable in-place filter.
    _window[:] = [h for h in _window if h[0] >= cutoff]
    # Defensive cap: if too many distinct keys, drop the oldest hits.
    if len(_window) > config.VELOCITY_MAX_KEYS * 10:
        _window[:] = _window[-config.VELOCITY_MAX_KEYS * 10:]


def _prune_cooldown(now: float) -> None:
    cutoff = now - config.VELOCITY_COOLDOWN_SECONDS
    for k in [k for k, ts in _cooldown.items() if ts < cutoff]:
        del _cooldown[k]


def _build_event(key: str, hits: list[tuple[float, str, str, str, str]]) -> Event:
    """One synthetic VELOCITY event from a list of contributing hits."""
    sources = sorted({h[2] for h in hits})
    lines = [f"[{h[2]}] {h[3]}" for h in hits[:8]]
    if len(hits) > 8:
        lines.append(f"... and {len(hits) - 8} more")
    n_src = len(sources)
    n_evt = len(hits)

    # Unique source_url per emission so the client-side dedup in stream.js
    # does not swallow a re-surge after cooldown. The fragment is inert.
    base_url = hits[0][4]
    unique_url = f"{base_url}#surge-{int(time.time())}"

    return Event(
        category="VELOCITY",
        title=f'SURGE: {n_src} sources reporting "{key}" ({n_evt} events)',
        description=" | ".join(lines)[:400],
        timestamp=utcnow(),
        source_name=f"{n_src} sources",
        source_url=unique_url,
        lat=None,
        lon=None,
        symbol="!",
        tags=[key, "SURGE"],
        severity=config.VELOCITY_SEVERITY,
    )


def check(events: list[Event]) -> list[Event]:
    """Feed a batch of real news events; return any new VELOCITY events.

    Safe to call with an empty list (still prunes the window and cooldown).
    """
    now = time.time()
    with _lock:
        _prune_window(now)
        _prune_cooldown(now)

        # Record hits for each topic key in each event.
        for e in events:
            keys = extract_keys(e.title, e.description)
            for k in keys:
                _window.append((now, k, e.source_name, e.title, e.source_url))

        # Group the window by key.
        by_key: dict[str, list[tuple[float, str, str, str, str]]] = {}
        for hit in _window:
            by_key.setdefault(hit[1], []).append(hit)

        emitted: list[Event] = []
        for key, hits in by_key.items():
            n_sources = len({h[2] for h in hits})
            if n_sources < config.VELOCITY_MIN_SOURCES:
                continue
            if len(hits) < config.VELOCITY_MIN_EVENTS:
                continue
            if key in _cooldown:
                continue
            ev = _build_event(key, hits)
            _cooldown[key] = now
            emitted.append(ev)
            log.info(
                "Velocity surge: key=%s sources=%d events=%d",
                key, n_sources, len(hits),
            )

        return emitted