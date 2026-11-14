"""
Emergency squawk feed. Polls the three dedicated adsb.lol squawk endpoints
(7500 hijack, 7600 radio failure, 7700 general emergency). Emits events
only when aircraft are present. Empty responses are normal and expected.

Endpoint shapes: /v2/sqk/{7500|7600|7700}, same JSON as /v2/mil.
"""
import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed

BASE_URL = "https://api.adsb.lol/v2/sqk"

SQUAWK_LABELS = {
    "7500": "HIJACK",
    "7600": "RADIO FAILURE",
    "7700": "GENERAL EMERGENCY",
}


class EmergencySquawksFeed(Feed):
    name = "squawks"

    def fetch(self) -> FeedResult:
        events = []

        for code, label in SQUAWK_LABELS.items():
            try:
                resp = self._get(f"{BASE_URL}/{code}")
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                # One squawk endpoint failing should not sink the others.
                continue

            aircraft = data.get("ac") or data.get("aircraft") or []
            for ac in aircraft:
                lat = ac.get("lat")
                lon = ac.get("lon")
                if lat is None or lon is None:
                    continue

                callsign = (ac.get("flight") or "").strip() or ac.get("hex") or "unknown"
                alt = ac.get("alt_baro")
                speed = ac.get("gs")

                desc_parts = [f"Squawk {code} ({label})."]
                if isinstance(alt, (int, float)):
                    desc_parts.append(f"Alt {alt:.0f} ft.")
                if isinstance(speed, (int, float)):
                    desc_parts.append(f"GS {speed:.0f} kt.")

                events.append(Event(
                    category="SQUAWK",
                    title=f"EMERGENCY {code}: {callsign}",
                    description=" ".join(desc_parts),
                    timestamp=utcnow(),
                    source_name="adsb.lol",
                    source_url=f"https://globe.adsb.lol/?icao={ac.get('hex', '')}",
                    lat=float(lat),
                    lon=float(lon),
                    symbol="!",
                    tags=[code, label],
                ))

        return FeedResult(
            feed_name=self.name,
            events=events,
            fetched_at=utcnow(),
            ok=True,
        )