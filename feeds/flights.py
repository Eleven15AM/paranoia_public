"""
adsb.lol military aircraft feed. Free, keyless, no registration.
Returns live positions for aircraft broadcasting ADS-B that are flagged
military in the volunteer network's coverage.

Important: empty result means "no coverage in this region", not "no
military flights". The UI must label this, and the description here
carries the caveat per event so it survives into the dossier panel.

Response shape (per observed payloads): a top-level "ac" array of aircraft
objects with fields like hex, flight, lat, lon, alt_baro, gs, track, type.
"""
import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed


class FlightsFeed(Feed):
    def fetch(self) -> FeedResult:
        try:
            resp = self._get(config.FLIGHTS_URL)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return self._empty(error=f"adsb.lol request failed: {exc}")

        aircraft = data.get("ac") or data.get("aircraft") or []
        def interestingness(ac):
            """Lower sort key = more interesting. Sort ascending.

            Heuristic, in order:
              1. dbFlags bit set (military=1, interesting=2) sorts first.
              2. On-ground aircraft sort last (an aircraft parked at a base
                 is less informative than one airborne).
              3. Low altitude sorts before high altitude — low-level military
                 activity is rarer and more notable than a tanker at cruise.
              4. Callsign as a stable tiebreaker so the same aircraft appear
                 across polls instead of the list reshuffling.
            """
            raw_flags = ac.get("dbFlags")
            try:
                flags = int(raw_flags) if raw_flags is not None else 0
            except (TypeError, ValueError):
                flags = 0

            # Bit 1 (military) or bit 2 (interesting) → priority 0
            flagged = 1 if (flags & 3) else 0

            alt = ac.get("alt_baro")
            # "ground" sorts after airborne; missing altitude also last.
            if alt == "ground":
                air_rank = 2
                alt_val = 0
            elif isinstance(alt, (int, float)):
                air_rank = 0
                alt_val = alt
            else:
                air_rank = 2
                alt_val = 0

            callsign = (ac.get("flight") or ac.get("hex") or "").strip()
            return (flagged, air_rank, alt_val, callsign)

        # Only keep aircraft with a position — the rest can't be shown.
        positioned = [ac for ac in aircraft if ac.get("lat") is not None and ac.get("lon") is not None]
        # Filter to a curated set of interesting airframes. If the config
        # set is empty, no filtering is applied (show all military).
        interesting = getattr(config, "FLIGHT_INTERESTING_TYPES", set())

        def type_matches(ac):
            # Check 't' first (ICAO designator), then 'type' as a
            # fallback, but only accept values that look like a
            # designator (no underscores, 2–4 chars). Source tags
            # like 'MLAT' or 'ADSB_ICAO' are not aircraft types.
            for key in ("t", "type"):
                val = ac.get(key)
                if not isinstance(val, str):
                    continue
                val = val.strip().upper()
                if not val or "_" in val or len(val) < 2 or len(val) > 4:
                    continue
                if val in interesting:
                    return True
            return False

        if interesting:
            positioned = [ac for ac in positioned if type_matches(ac)]
        positioned.sort(key=interestingness)
        events = []
        for ac in positioned[:80]:
            try:
                lat = ac.get("lat")
                lon = ac.get("lon")
                if lat is None or lon is None:
                    continue

                callsign = (ac.get("flight") or "").strip() or ac.get("hex") or "unknown"
                ac_type = (ac.get("t") or ac.get("type") or "").strip().upper()
                alt = ac.get("alt_baro")
                speed = ac.get("gs")

                desc_parts = []
                if isinstance(alt, (int, float)):
                    desc_parts.append(f"Alt {alt:.0f} ft")
                if isinstance(speed, (int, float)):
                    desc_parts.append(f"GS {speed:.0f} kt")
                desc_parts.append("Coverage-dependent: empty region ≠ no flights.")

                events.append(Event(
                    category="FLIGHT",
                    title=f"Military aircraft {callsign}" + (f" [{ac_type}]" if ac_type else ""),
                    description=". ".join(desc_parts),
                    timestamp=utcnow(),
                    source_name="adsb.lol",
                    source_url="https://adsb.lol/",
                    lat=float(lat),
                    lon=float(lon),
                    symbol="◆",
                    tags=["MIL"],
                ))
            except Exception:
                # One malformed aircraft must not sink the poll.
                continue

        return FeedResult(
            feed_name=self.name,
            events=events,
            fetched_at=utcnow(),
            ok=True,
        )