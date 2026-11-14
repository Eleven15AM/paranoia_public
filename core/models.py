"""
Normalized event shape. Every feed, no matter its source format, produces
a list[Event]. Nothing downstream (cache, API, frontend) needs to know the
original source structure.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Event:
    category: str                 # NEWS | SPACE | QUAKE | FLIGHT | NEO
    title: str
    description: str
    timestamp: datetime           # when the event happened (best available)
    source_name: str              # "USGS", "BBC World", "NASA DONKI", ...
    source_url: str               # deep link to the original
    lat: Optional[float] = None   # None if not geolocatable
    lon: Optional[float] = None
    symbol: str = "●"             # radar marker; set by each feed
    tags: list[str] = field(default_factory=list)  # burn-in keywords
    severity: int = 0             # 0-100; Layer 1 scores NEWS only, others stay 0

    def to_dict(self) -> dict:
        d = asdict(self)
        # datetimes → ISO 8601 strings; naive JSON elsewhere in the app
        d["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        return d


@dataclass
class FeedResult:
    """What a Feed.fetch() returns, and what the cache stores."""
    feed_name: str
    events: list[Event]
    fetched_at: datetime
    ok: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "feed_name": self.feed_name,
            "fetched_at": self.fetched_at.astimezone(timezone.utc).isoformat(),
            "ok": self.ok,
            "error": self.error,
            "events": [e.to_dict() for e in self.events],
        }