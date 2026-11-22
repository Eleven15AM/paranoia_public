"""
NASA NeoWs near-Earth object feed. Free with DEMO_KEY (30 req/hr);
a real key raises the limit to 1000/hr.

NeoWs returns a dict keyed by approach date, each value a list of
asteroid objects. Maximum window is 7 days per the API docs[citation:6].

No terrestrial lat/lon: these are orbital objects. Events carry lat=None,
lon=None, so they appear in the event stream and panels but not on the
radar canvas.
"""
from datetime import timedelta

import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed

BASE_URL = "https://api.nasa.gov/neo/rest/v1/feed"


class NeoFeed(Feed):
    def fetch(self) -> FeedResult:
        try:
            start = utcnow().strftime("%Y-%m-%d")
            end = (utcnow() + timedelta(days=config.NEO_DAYS_AHEAD)).strftime("%Y-%m-%d")
            params = {
                "start_date": start,
                "end_date": end,
                "api_key": config.NASA_API_KEY,
            }
            resp = self._get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return self._empty(error=f"NASA NeoWs request failed: {exc}")

        events = []
        by_date = data.get("near_earth_objects") or {}

        for approach_date, asteroids in by_date.items():
            for neo in asteroids:
                name = neo.get("name") or neo.get("id") or "unknown"
                hazardous = neo.get("is_potentially_hazardous_asteroid", False)

                # Diameter: prefer kilometers (estimated_diameter.kilometers)
                diam = neo.get("estimated_diameter", {}).get("kilometers", {})
                d_min = diam.get("estimated_diameter_min")
                d_max = diam.get("estimated_diameter_max")
                size_str = ""
                if isinstance(d_min, (int, float)) and isinstance(d_max, (int, float)):
                    size_str = f"Diameter {d_min:.2f}–{d_max:.2f} km."

                # First close approach record
                approaches = neo.get("close_approach_data") or []
                miss_km = None
                velocity_kph = None
                if approaches:
                    ca = approaches[0]
                    md = ca.get("miss_distance", {})
                    miss_km = md.get("kilometers")
                    rv = ca.get("relative_velocity", {})
                    velocity_kph = rv.get("kilometers_per_hour")

                desc_parts = [size_str] if size_str else []
                if miss_km:
                    desc_parts.append(f"Miss distance {float(miss_km):,.0f} km.")
                if velocity_kph:
                    desc_parts.append(f"Velocity {float(velocity_kph):,.0f} km/h.")
                if hazardous:
                    desc_parts.append("Potentially hazardous per NASA.")

                tags = []
                if hazardous:
                    tags.append("HAZARD")

                events.append(Event(
                    category="NEO",
                    title=f"NEO {name}" + (" (hazardous)" if hazardous else ""),
                    description=" ".join(desc_parts) or "Source: NASA NeoWs.",
                    timestamp=self._iso_to_dt(approach_date + "T00:00:00Z"),
                    source_name="NASA NeoWs",
                    source_url=neo.get("nasa_jpl_url") or "https://api.nasa.gov/",
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