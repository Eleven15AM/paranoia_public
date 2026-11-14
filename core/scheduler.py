"""
One daemon thread per feed. Each thread loops: fetch → cache.set →
sleep(interval). Exceptions inside a fetch are converted to a
FeedResult(ok=False) by the feed itself; the scheduler only guards
against unexpected crashes and keeps the thread alive.
"""
import logging
import threading
import time

from core.cache import Cache
from feeds.base import Feed

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, feeds: list[Feed], cache: Cache) -> None:
        self._feeds = feeds
        self._cache = cache
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for feed in self._feeds:
            t = threading.Thread(
                target=self._run_feed,
                args=(feed,),
                name=f"feed-{feed.name}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)
            log.info("Started feed %s every %ss", feed.name, feed.interval)

    def stop(self) -> None:
        self._stop.set()

    def _run_feed(self, feed: Feed) -> None:
        # First poll immediately, then sleep the interval.
        while not self._stop.is_set():
            try:
                result = feed.fetch()

                # Layer 2: velocity detection runs on real news events only.
                # Synthetic VELOCITY events are appended before caching, so
                # they flow through the same API and frontend path as every
                # other event. Other feeds are untouched.
                if feed.name == "news" and result.ok:
                    from core.velocity import check as _velocity_check
                    try:
                        surges = _velocity_check(result.events)
                        if surges:
                            result.events.extend(surges)
                    except Exception:
                        log.exception("Velocity check failed; continuing without surges")

                self._cache.set(result)
                log.info(
                    "Feed %s: %d events (ok=%s)%s",
                    feed.name,
                    len(result.events),
                    result.ok,
                    f" error={result.error}" if result.error else "",
                )
            except Exception:
                log.exception("Feed %s crashed; thread continues", feed.name)
            # Wait with a timeout so stop() is responsive.
            self._stop.wait(feed.interval)