"""
Thread-safe in-memory cache. This is the only shared mutable state in the
process. Each background feed thread writes one FeedResult per feed_name;
the HTTP layer reads a snapshot. No persistence: restart = fresh poll.
"""
import threading
from core.models import FeedResult


class Cache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, FeedResult] = {}

    def set(self, result: FeedResult) -> None:
        with self._lock:
            self._data[result.feed_name] = result

    def get(self, feed_name: str) -> FeedResult | None:
        with self._lock:
            return self._data.get(feed_name)

    def snapshot(self) -> dict[str, FeedResult]:
        with self._lock:
            return dict(self._data)