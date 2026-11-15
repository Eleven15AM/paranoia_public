"""
NASA DONKI Solar Flare (FLR) endpoint. Free with DEMO_KEY (30 req/hr);
a real key from api.nasa.gov raises the limit to 1000/hr.
Docs: https://api.nasa.gov/
"""
from datetime import timedelta

import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed, classify_http_error

BASE_URL = "https://api.nasa.gov/DONKI/FLR"


class FlaresFeed(Feed):
    name = "flares"

    def fetch(self) -> FeedResult:
        try:
            # Last 3 days is enough for a 30-minute poll interval; overlap
            # is fine because the frontend dedupes by source_url.
            start = (utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
            params = {
                "startDate": start,
                "api_key": config.NASA_API_KEY,
            }
            resp = self._get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            # A 404 from DONKI means "no flares in this window", not a
            # failure. Report it as healthy-but-empty so FEED HEALTH is
            # honest. Other errors still surface.
            if classify_http_error(exc) == "empty":
                return self._empty(error=None)
            return self._empty(error=f"NASA DONKI request failed: {exc}")

        events = []
        for item in data or []:
            class_type = item.get("classType") or "?"
            begin = item.get("beginTime") or ""
            peak = item.get("peakTime") or begin
            source_loc = item.get("sourceLocation") or "unknown"
            flare_id = item.get("flrID") or ""

            # classType is like "M4.2" or "X1.0"; the first letter is the
            # severity class, the rest is the magnitude.
            tags = []
            if class_type and class_type[0] in "MX":
                tags.append(class_type)

            events.append(Event(
                category="SPACE",
                title=f"Solar flare {class_type} — source {source_loc}",
                description=f"Begin {begin}. Peak {peak}. Source: NASA DONKI.",
                timestamp=self._iso_to_dt(peak or begin),
                source_name="NASA DONKI",
                source_url=f"https://kauai.ccmc.gsfc.nasa.gov/DONKI/view/FLR/{flare_id}" if flare_id else "https://api.nasa.gov/",
                lat=None,
                lon=None,
                symbol="●",
                tags=tags,
            ))

        return FeedResult(
            feed_name=self.name,
            events=events,
            fetched_at=utcnow(),
            ok=True,
        )