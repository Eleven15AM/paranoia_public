"""
Feed contract. Every feed subclasses Feed and implements fetch().
The base provides a small HTTP helper so individual feeds stay short.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import requests

import config
from core.models import FeedResult, utcnow


class Feed(ABC):
    name: str          # set by subclass
    interval: int      # set by subclass, seconds
    category: str      # set by subclass

    @abstractmethod
    def fetch(self) -> FeedResult:
        """Perform one poll. Must not raise; wrap errors into FeedResult."""
        ...

    # --- helpers available to subclasses --------------------------------

    def _empty(self, error: str | None = None) -> FeedResult:
        return FeedResult(
            feed_name=self.name,
            events=[],
            fetched_at=utcnow(),
            ok=error is None,
            error=error,
        )

    def _get(self, url: str, **kwargs) -> requests.Response:
        headers = {"User-Agent": config.USER_AGENT}
        headers.update(kwargs.pop("headers", {}))
        return requests.get(
            url,
            headers=headers,
            timeout=config.HTTP_TIMEOUT,
            **kwargs,
        )

    @staticmethod
    def _iso_to_dt(value: str) -> datetime:
        """Parse an ISO 8601 string into an aware UTC datetime.
        Falls back to now() on failure so a bad timestamp never crashes
        the poll loop."""
        try:
            # fromisoformat handles 'Z' only from Python 3.11+, and even
            # then inconsistently across sources; normalize here.
            v = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return utcnow()