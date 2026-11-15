"""
Central configuration. The feed registry is the single place to add feeds.

Each entry is a dict because the actual Feed instances are constructed in
feeds/__init__.py (avoids a circular import: feeds import from config,
config imports feeds). The scheduler reads FEED_REGISTRY to know what to
run; the API reads it to advertise categories to the frontend.

Severity scoring (Layer 1), velocity detection (Layer 2), and GDELT
cross-reference (Layer 4) also live here deliberately: retuning keywords,
weights, windows, and endpoints is a data change, not a code change.
"""
import os
import re

# --- NASA API key ---------------------------------------------------------
# DEMO_KEY works immediately with a 30 req/hr limit. That is enough for the
# default intervals below (flares 1800s, NEO 3600s = 3 req/hr combined).
# Drop a real key in .env or the environment to raise the limit to 1000/hr.
NASA_API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")

# --- HTTP behavior --------------------------------------------------------
HTTP_TIMEOUT = 20            # seconds, per request
USER_AGENT = "PARANOIA/1.0 (personal dashboard; contact: local)"

# --- Feed registry --------------------------------------------------------
# name      : unique, used as cache key and URL slug (/api/feed/<name>)
# class     : python dotted path, resolved in feeds/__init__.py
# interval  : seconds between polls (roughly matches source update cadence)
# category  : drives frontend filter buttons and radar symbols
# label     : human-readable, shown in the UI
FEED_REGISTRY = [
    {
        "name": "news",
        "class": "feeds.news.NewsFeed",
        "interval": 600,
        "category": "NEWS",
        "label": "World News",
    },
    {
        "name": "flares",
        "class": "feeds.flares.FlaresFeed",
        "interval": 1800,
        "category": "SPACE",
        "label": "Solar Flares",
    },
    {
        "name": "quakes",
        "class": "feeds.quakes.QuakesFeed",
        "interval": 600,
        "category": "QUAKE",
        "label": "Earthquakes",
    },
    {
        "name": "flights",
        "class": "feeds.flights.FlightsFeed",
        "interval": 180,
        "category": "FLIGHT",
        "label": "Military Flights",
    },
    {
        "name": "neo",
        "class": "feeds.neo.NeoFeed",
        "interval": 3600,
        "category": "NEO",
        "label": "Near-Earth Objects",
    },
    {
        "name": "commodities",
        "class": "feeds.commodities.CommoditiesFeed",
        "interval": 3600,       # 24 req/day, under the 25/day demo limit
        "category": "COMMODITY",
        "label": "Commodities",
    },
    {
        "name": "squawks",
        "class": "feeds.emergency_squawks.EmergencySquawksFeed",
        "interval": 120,       # 2 minutes — emergencies are rare but time-sensitive
        "category": "SQUAWK",
        "label": "Emergency Squawks",
    },
]

# --- Feed-specific settings ----------------------------------------------

# World news: start with a neutral three-source mix. Add or swap freely.
NEWS_FEED_URLS = [
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Axios top 100", "https://api.axios.com/feed/top/"),
    ("Sky Strange and Odd News Stories","https://feeds.skynews.com/feeds/rss/strange.xml"),
    ("Sky Business","https://feeds.skynews.com/feeds/rss/business.xml"),
    ("Deutsche Welle", "https://rss.dw.com/rdf/rss-en-world"),
    ("Reuters World", "https://news.google.com/rss/search?q=source:Reuters+world&hl=en-US&gl=US&ceid=US:en"),
]

# USGS: minimum magnitude to show. 4.5 keeps the list readable.
QUAKE_MIN_MAGNITUDE = 4.5
QUAKE_WINDOW = "day"          # one of: hour, day, week

# adsb.lol: the military endpoint returns aircraft with mil=true in coverage
# areas that have volunteer receivers. Empty result = no coverage, not
# "no flights". The UI labels this explicitly.
FLIGHTS_URL = "https://api.adsb.lol/v2/mil"

# NASA NEO: how many days ahead to query (max 7 per NeoWs docs).
NEO_DAYS_AHEAD = 7

# Aircraft type designators (ICAO) considered interesting for this dashboard.
# Leave the set empty to disable filtering and show all military aircraft.
FLIGHT_INTERESTING_TYPES = {
    # Fighters
    "F16", "F15", "F35", "F22", "A10", "F18", "EF18", "F14", "MIG29", "SU27",
    # Bombers
    "B52", "B1", "B2", "B21",
    # Tankers / AWACS / ISR
    "KC135", "KC46", "KC10", "E3", "E8", "RC135", "U2", "P8", "EP3", "E6",
    # Heavy lift (optional — remove if too noisy)
    "C5", "C17", "C130", "A400", "C40",
}

# --- Severity scoring (Layer 1: news only) --------------------------------
# Tunable in one place. Per-match weights; multi-word keywords match as
# phrases on word boundaries. Case-insensitive over title + " " + description.
SEVERITY_BASE = 10
SEVERITY_MIN, SEVERITY_MAX = 0, 100
SEVERITY_MEDIUM, SEVERITY_HIGH = 40, 70

# (weight, [keywords]). Order does not matter: score_headline() evaluates
# crisis groups first, then negatives, so the -10 rule is order-independent.
SEVERITY_WEIGHTS = [
    (40, ["invasion", "airstrike", "missile", "mobilization", "nuclear"]),
    (30, ["killed", "casualties", "massacre", "fatalities", "wounded"]),
    (25, ["outage", "blackout", "collapse", "cyberattack", "breached"]),
    (20, ["emergency", "evacuation", "quarantine", "pandemic"]),
    (20, ["sanctions", "coup", "martial law", "state of emergency"]),
    (-20, ["coach", "transfer", "signing", "contract"]),
    (-20, ["celebrity", "wedding", "divorce", "birthday"]),
    (-10, ["earnings", "stock price", "quarterly"]),
]

# Indices into SEVERITY_WEIGHTS that count as "crisis" for the -10 rule.
SEVERITY_CRISIS_GROUPS = {0, 1, 2, 3, 4}

# Global-scale terms: count as crisis AND add SEVERITY_GLOBAL_WEIGHT per match.
# Remove "millions" if ordinary headlines ("millions raised") get too hot.
# Note: these are intentionally NOT used as velocity topic keys (see below).
SEVERITY_CRISIS_EXTRA = ["global", "millions", "nationwide", "worldwide"]
SEVERITY_GLOBAL_WEIGHT = 25


def _compile_severity():
    out = []
    for gi, (w, kws) in enumerate(SEVERITY_WEIGHTS):
        pats = [
            re.compile(
                r"\b" + r"\s+".join(re.escape(p) for p in kw.split()) + r"\b",
                re.IGNORECASE,
            )
            for kw in kws
        ]
        out.append((gi, w, kws, pats))
    return out


_GLOBAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in SEVERITY_CRISIS_EXTRA) + r")\b",
    re.IGNORECASE,
)
_SEV = _compile_severity()


def match_keywords(title: str, description: str) -> list[str]:
    """Matched keywords for tags/burn-in. De-duped, stable order. Pure."""
    hay = (title or "") + " " + (description or "")
    seen: set[str] = set()
    out: list[str] = []
    for _gi, _w, kws, pats in _SEV:
        for kw, pat in zip(kws, pats):
            key = kw.lower()
            if key not in seen and pat.search(hay):
                seen.add(key)
                out.append(kw)
    for m in _GLOBAL_RE.findall(hay):
        key = m.lower()
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def score_headline(title: str, description: str) -> int:
    """Score a news headline 0-100. Pure; no I/O. Per-match.

    Two-pass so the -10 earnings rule does not depend on list ordering:
    crisis groups + global terms first, then negatives (skipping -10 if any
    crisis term matched).
    """
    hay = (title or "") + " " + (description or "")
    total = SEVERITY_BASE
    crisis = bool(_GLOBAL_RE.search(hay))

    for gi, w, _kw, pats in _SEV:
        if gi in SEVERITY_CRISIS_GROUPS:
            hits = sum(len(p.findall(hay)) for p in pats)
            if hits:
                crisis = True
            total += w * hits

    total += SEVERITY_GLOBAL_WEIGHT * len(_GLOBAL_RE.findall(hay))

    for gi, w, _kw, pats in _SEV:
        if gi in SEVERITY_CRISIS_GROUPS:
            continue
        if w == -10 and crisis:
            continue
        total += w * sum(len(p.findall(hay)) for p in pats)

    return max(SEVERITY_MIN, min(SEVERITY_MAX, total))


# --- Velocity detection (Layer 2: news only) -----------------------------
# A topic key crossing a threshold within a rolling window is itself an event.
# Window state lives in core/velocity.py; everything tunable lives here.
# No persistence: restarting the container starts with an empty window.

# Curated seed topics. Add/remove freely; tuning is a data change.
VELOCITY_TOPICS = [
    "iran", "ukraine", "gaza", "israel", "china", "russia",
    "openai", "election", "europe", "ai", "claude",
]

VELOCITY_WINDOW_SECONDS = 3600
VELOCITY_MIN_SOURCES = 3
VELOCITY_MIN_EVENTS = 3
VELOCITY_COOLDOWN_SECONDS = 3600
VELOCITY_MAX_KEYS = 500
VELOCITY_SEVERITY = 75


def _compile_velocity_topics():
    """Compile VELOCITY_TOPICS plus the positive Layer 1 crisis keywords.

    SEVERITY_CRISIS_EXTRA (global/millions/nationwide/worldwide) is
    deliberately excluded: those are too generic to make a useful surge.
    Returns (sorted_topic_key_list, compiled_regex).
    """
    keys = set(t.lower() for t in VELOCITY_TOPICS)
    for gi, _w, kws, _pats in _SEV:
        if gi in SEVERITY_CRISIS_GROUPS:
            for kw in kws:
                keys.add(kw.lower())
    ordered = sorted(keys)
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in ordered) + r")\b",
        re.IGNORECASE,
    )
    return ordered, pattern


VELOCITY_KEYS, VELOCITY_RE = _compile_velocity_topics()


# --- ALERTS panel (Layer 3) ----------------------------------------------
# How many high-severity events the dedicated ALERTS panel shows at once.
# Overflow is indicated with a "+N more" counter.
ALERTS_PANEL_LIMIT = 5


# --- GDELT cross-reference (Layer 4: news only, high severity only) ------
# Best-effort external signal. Never fails a poll. Keyless GDELT DOC API.
# In-memory cache and min-interval enforced in core/gdelt.py.
GDELT_ENABLED = True
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_TIMESPAN = "1d"
GDELT_MAX_RECORDS = 5
GDELT_MIN_INTERVAL_SECONDS = 300
GDELT_CACHE_TTL_SECONDS = 600
GDELT_TIMEOUT_SECONDS = 10