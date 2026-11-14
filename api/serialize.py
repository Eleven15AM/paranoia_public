"""
JSON shaping. Kept separate from routes so the HTTP layer stays thin and
the merge logic is testable in isolation if you ever want that.
"""
from core.models import FeedResult


def health_payload(snapshot: dict[str, FeedResult]) -> dict:
    """Per-feed status for the health panel."""
    out = {}
    for name, result in snapshot.items():
        age = (result.fetched_at.replace(microsecond=0)).isoformat()
        out[name] = {
            "ok": result.ok,
            "error": result.error,
            "fetched_at": age,
            "event_count": len(result.events),
        }
    return out


def events_payload(snapshot: dict[str, FeedResult]) -> dict:
    """Merged, newest-first event list plus per-feed health."""
    merged = []
    for result in snapshot.values():
        for event in result.events:
            merged.append(event.to_dict())
    merged.sort(key=lambda e: e["timestamp"], reverse=True)
    return {
        "events": merged,
        "health": health_payload(snapshot),
    }