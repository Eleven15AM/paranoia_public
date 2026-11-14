"""
Central configuration. The feed registry is the single place to add feeds.

Each entry is a dict because the actual Feed instances are constructed in
feeds/__init__.py (avoids a circular import: feeds import from config,
config imports feeds). The scheduler reads FEED_REGISTRY to know what to
run; the API reads it to advertise categories to the frontend.
"""
import os

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