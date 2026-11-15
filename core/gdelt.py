"""
GDELT cross-reference (Layer 4, news only, high severity only).

Best-effort external signal. For each event with severity > SEVERITY_HIGH,
query the keyless GDELT 2.0 DOC API with the event's title and attach a
small summary to Event.gdelt:

    {"count": int, "sample_titles": [str], "sample_urls": [str]}

Failure is never fatal: a timeout, HTTP error, rate limit, or malformed
response leaves Event.gdelt as None and the poll proceeds. No disk I/O.
In-memory cache and min-interval gate only; a restart begins empty.
"""
import json
import logging
import threading
import time
import urllib.parse
import urllib.request

import config

log = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}   # query -> (expiry_epoch, result)
_last_call_ts: float = 0.0


def _build_url(query: str) -> str:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "timespan": config.GDELT_TIMESPAN,
        "maxrecords": str(config.GDELT_MAX_RECORDS),
        "sort": "datedesc",
    }
    return config.GDELT_API_URL + "?" + urllib.parse.urlencode(params)


def _fetch(query: str) -> dict | None:
    """One network call. Returns the summary dict or None on any failure."""
    url = _build_url(query)
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=config.GDELT_TIMEOUT_SECONDS) as resp:
            raw = resp.read()
    except Exception as exc:
        log.debug("GDELT fetch failed for %r: %s", query, exc)
        return None

    try:
        data = json.loads(raw)
    except Exception as exc:
        log.debug("GDELT JSON parse failed for %r: %s", query, exc)
        return None

    articles = data.get("articles") or []
    if not isinstance(articles, list):
        return None

    titles = []
    urls = []
    for a in articles[: config.GDELT_MAX_RECORDS]:
        if not isinstance(a, dict):
            continue
        t = a.get("title") or ""
        u = a.get("url") or ""
        if t:
            titles.append(t[:200])
        if u:
            urls.append(u)

    return {
        "count": len(articles),
        "sample_titles": titles,
        "sample_urls": urls,
    }


def _lookup(query: str, now: float) -> dict | None:
    """Cache-aware, min-interval-gated lookup. Caller holds _lock."""
    global _last_call_ts

    cached = _cache.get(query)
    if cached and cached[0] > now:
        return cached[1]

    if now - _last_call_ts < config.GDELT_MIN_INTERVAL_SECONDS:
        # Rate limited. Return a stale cache entry if we have one, else None.
        return cached[1] if cached else None

    # Claim the next slot BEFORE the call so a failure (including 429) also
    # throttles subsequent events in this batch. One attempt per interval.
    _last_call_ts = now

    result = _fetch(query)
    if result is not None:
        _cache[query] = (now + config.GDELT_CACHE_TTL_SECONDS, result)
    # Opportunistic prune; keep the cache small.
    for k in [k for k, (exp, _) in _cache.items() if exp <= now]:
        del _cache[k]
    return result


def enrich(events: list) -> None:
    """Attach a GDELT summary to each high-severity event, in place.

    Events below SEVERITY_HIGH, or of any category other than NEWS or
    VELOCITY, are left untouched (gdelt stays None). Never raises.
    """
    if not config.GDELT_ENABLED or not events:
        return

    try:
        with _lock:
            now = time.time()
            for e in events:
                if getattr(e, "category", None) not in ("NEWS", "VELOCITY"):
                    continue
                if (getattr(e, "severity", 0) or 0) <= config.SEVERITY_HIGH:
                    continue
                query = (getattr(e, "title", "") or "").strip()
                if not query:
                    continue
                summary = _lookup(query, now)
                if summary is not None:
                    e.gdelt = summary
    except Exception:
        # Best-effort. A bug here must not fail the poll.
        log.exception("GDELT enrich failed; continuing without enrichment")