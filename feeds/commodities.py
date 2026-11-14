"""
OilPriceAPI demo endpoint. No API key, 25 requests/day per IP (keyless).
Response shape: {"status":"success","data":{"prices":[...],"meta":{...}}}
"""
import config
from core.models import Event, FeedResult, utcnow
from feeds.base import Feed

BASE_URL = "https://api.oilpriceapi.com/v1/demo/prices"

CODES = "WTI_USD,GOLD_USD,SILVER_USD,NATURAL_GAS_USD,BRENT_CRUDE_USD,PLATINUM_USD"

LABELS = {
    "WTI_USD": "WTI Crude",
    "BRENT_CRUDE_USD": "Brent Crude",
    "GOLD_USD": "Gold",
    "SILVER_USD": "Silver",
    "NATURAL_GAS_USD": "Natural Gas",
    "PLATINUM_USD": "Platinum",
}


class CommoditiesFeed(Feed):
    name = "commodities"

    def fetch(self) -> FeedResult:
        try:
            resp = self._get(BASE_URL, params={"codes": CODES})
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return self._empty(error=f"OilPriceAPI request failed: {exc}")

        # The real shape is data["data"]["prices"] — not data["data"].
        # Keep the older-path fallbacks in case the API changes again.
        prices = (
            (data.get("data") or {}).get("prices")
            or data.get("prices")
            or []
        )
        if not isinstance(prices, list):
            return self._empty(error="OilPriceAPI response: unexpected prices shape")

        events = []
        for item in prices:
            code = item.get("code")
            price = item.get("price")
            if not code or price is None:
                continue

            label = LABELS.get(code, item.get("name") or code)
            try:
                price_str = f"${float(price):,.2f}"
            except (TypeError, ValueError):
                price_str = str(price)

            # Optional extra context from the payload
            stale = item.get("stale", False)
            tags = [code]
            if stale:
                tags.append("STALE")

            events.append(Event(
                category="COMMODITY",
                title=f"{label}: {price_str}",
                description=(
                    f"{item.get('name', label)} in {item.get('currency', 'USD')}. "
                    f"Source: OilPriceAPI"
                    + (" (marked stale by source)." if stale else ".")
                ),
                timestamp=self._iso_to_dt(item.get("updated_at", "")) if item.get("updated_at") else utcnow(),
                source_name="OilPriceAPI",
                source_url="https://oilpriceapi.com/",
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