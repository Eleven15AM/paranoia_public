"""
USGS Earthquake API. Free, keyless, GeoJSON output.
Docs: https://earthquake.usgs.gov/fdsnws/event/1/
"""
from datetime import timedelta

import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed

BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


class QuakesFeed(Feed):
    def fetch(self) -> FeedResult:
        try:
            start = (utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            params = {
                "format": "geojson",
                "starttime": start,
                "minmagnitude": config.QUAKE_MIN_MAGNITUDE,
                "orderby": "time",
                "limit": 50,
            }
            resp = self._get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return self._empty(error=f"USGS request failed: {exc}")

        events = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates") or [None, None, None]

            mag = props.get("mag")
            place = props.get("place") or "Unknown location"
            # USGS time is epoch milliseconds
            ts_ms = props.get("time")
            timestamp = utcnow()
            if isinstance(ts_ms, (int, float)):
                from datetime import datetime, timezone
                timestamp = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

            title = f"M{mag:.1f} — {place}" if isinstance(mag, (int, float)) else place
            tags = []
            if isinstance(mag, (int, float)):
                tags.append(f"M{mag:.1f}")
            if props.get("tsunami"):
                tags.append("TSUNAMI")

            events.append(Event(
                category=self.category,
                title=title,
                description=f"Depth {coords[2]:.0f} km. Source: USGS." if len(coords) > 2 and coords[2] is not None else "Source: USGS.",
                timestamp=timestamp,
                source_name="USGS",
                source_url=props.get("url") or "https://earthquake.usgs.gov/",
                lat=coords[1],
                lon=coords[0],
                symbol="▲",
                tags=tags,
            ))

        return FeedResult(
            feed_name=self.name,
            events=events,
            fetched_at=utcnow(),
            ok=True,
        )