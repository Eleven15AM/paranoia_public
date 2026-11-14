"""
World news via RSS/Atom. Uses feedparser for parsing but requests for HTTP
so we keep config.HTTP_TIMEOUT and our User-Agent. Dedupes entries within a
single poll by link; cross-poll dedup happens client-side.

Feedparser note: parsed.bozo is True for malformed feeds. We log it but
still use whatever entries parsed, because partial output beats nothing
for a dashboard.
"""
import logging

import feedparser
from io import BytesIO

import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed

log = logging.getLogger(__name__)


class NewsFeed(Feed):
    name = "news"

    def fetch(self) -> FeedResult:
        events = []
        seen_links = set()

        for source_name, url in config.NEWS_FEED_URLS:
            try:
                resp = self._get(url)
                resp.raise_for_status()
            except Exception as exc:
                log.warning("News source %s failed: %s", source_name, exc)
                continue

            # Parse from bytes we already fetched, supplying content-location
            # so feedparser can resolve relative links correctly.
            headers = dict(resp.headers)
            headers.setdefault("content-location", resp.url)
            parsed = feedparser.parse(BytesIO(resp.content), response_headers=headers)

            if parsed.bozo:
                log.info("News source %s malformed: %r", source_name, parsed.bozo_exception)

            for entry in parsed.entries[:15]:
                link = entry.get("link") or ""
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                title = entry.get("title") or "(untitled)"
                summary = entry.get("summary") or entry.get("description") or ""
                # published_parsed is a time.struct_time in UTC; fall back
                # to updated_parsed, then to now.
                published = None
                for key in ("published_parsed", "updated_parsed"):
                    if entry.get(key):
                        import calendar
                        from datetime import datetime, timezone
                        published = datetime.fromtimestamp(
                            calendar.timegm(entry[key]), tz=timezone.utc
                        )
                        break
                timestamp = published or utcnow()

                events.append(Event(
                    category="NEWS",
                    title=title,
                    description=summary[:400],
                    timestamp=timestamp,
                    source_name=source_name,
                    source_url=link,
                    lat=None,
                    lon=None,
                    symbol="★",
                    tags=[],
                ))

        return FeedResult(
            feed_name=self.name,
            events=events,
            fetched_at=utcnow(),
            ok=True,
        )