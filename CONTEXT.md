# CONTEXT.md

**This file is for whoever is working on PARANOIA — an AI assistant or
a future maintainer.** It answers questions that the code does not
answer on its own: why decisions were made, what was tried and rejected,
what is currently in progress, and where the sharp edges are.

Install, run, and license information are in `README.md`. Do not
duplicate them here; if the two disagree, `README.md` wins on operational
details and this file wins on architecture and design intent.

## If you are an AI assistant

You are about to work on a Flask + static JavaScript dashboard. The user
is one person, on a home network, who opens this app occasionally to see
what the world's public feeds are reporting right now. Everything in this
file is written to save you the effort of reconstructing state that is
not in the code.

Before writing anything:

1. **Read this file fully.** The "Decisions that look odd without context"
   section is the one that will trip you up most often, because the code
   will look wrong if you do not know it was deliberate.
2. **Read the current task issue** (or ask the user to paste its body if
   you cannot reach GitHub). Do not infer the task from the code.
3. **Propose a plan before coding.** The user will tell you if the plan
   is too large, too small, or misses something. Coding first wastes
   their time and yours.

While working:

- **Preserve the security guards.** Every DOM write in `static/js/stream.js`
  that involves user-derived text goes through `escapeHtml`. The earlier
  XSS regression tests matter. Do not shortcut this.
- **Preserve the scheduler's per-feed isolation.** One feed failing must
  not affect any other feed. This is why each feed runs in its own thread
  with its own try/except.
- **Put tunable values in `config.py`, not in the feed or the frontend.**
  Keyword lists, weights, intervals, URLs, filters — all in `config.py`.
  This keeps tuning a data change, not a code change, which is what makes
  the second pass on any feature fast.
- **Do not add dependencies without asking.** The project has three Python
  dependencies (`flask`, `feedparser`, `requests`) and zero JavaScript
  dependencies beyond the Tailwind CDN. That is a deliberate constraint.
- **Do not add a database.** In-memory only, by design. Restarting the
  container is a fresh poll. This is not a bug to fix.
- **Do not re-add the radar canvas.** See "Decisions" below.

## What PARANOIA is

A personal, self-hosted, single-user dashboard that monitors five (soon
six) public data feeds and displays them in a 1990s NCurses/BBS terminal
aesthetic. The name is tongue-in-cheek: the app shows what public feeds
are reporting, not what is true, and it does not forecast or score.

The feeds are:

| Feed | Source | Interval | Notes |
|---|---|---|---|
| `news` | BBC, Al Jazeera, Reuters (RSS) | 600s | Reuters URL is currently broken; see known limitations |
| `flares` | NASA DONKI FLR | 1800s | Uses `NASA_API_KEY`; `DEMO_KEY` works but is shared and rate-limited |
| `quakes` | USGS FDSN | 600s | M4.5+ in the last 24h |
| `flights` | adsb.lol `/v2/mil` | 180s | Filtered to curated type list; see "flights" below |
| `neo` | NASA NeoWs | 3600s | 7-day close-approach window |
| `commodities` | OilPriceAPI demo | 3600s | 6 codes; demo key is 25 req/day per IP |
| `squawks` | adsb.lol `/v2/sqk/{7500,7600,7700}` | 120s | Usually empty; high-signal when not |

## Architecture

    Browser (static HTML/JS)
        │  fetch /api/events every 20s
        ▼
    Flask (app.py)
        │  reads from
        ▼
    Cache (core/cache.py)         ← in-memory dict, thread-safe
        │  written by
        ▼
    Scheduler (core/scheduler.py) ← one daemon thread per feed
        │  calls
        ▼
    Feeds (feeds/*.py)            ← each implements fetch() -> FeedResult
        │  HTTP
        ▼
    Public APIs (keyless, or NASA key via .env)

Key consequence: if a feed fails, only that feed's cache entry goes
stale. Everything else keeps working. The health panel shows which feeds
are healthy, stale, or errored, so a silent gap is impossible.

## File map

    app.py                     Flask app factory; starts scheduler; mounts /api
    config.py                  FEED_REGISTRY + all tunables
                               (QUAKE_MIN_MAGNITUDE, FLIGHT_INTERESTING_TYPES,
                               NEWS_FEED_URLS, NASA_API_KEY, etc.)

    core/models.py             Event, FeedResult dataclasses. Event is the
                               only shape the frontend ever sees.
    core/cache.py              Thread-safe in-memory cache.
    core/scheduler.py          One thread per feed; fetch → cache.set → sleep.

    feeds/base.py              Feed ABC. Provides _get() and _iso_to_dt().
    feeds/news.py              RSS/Atom via feedparser.
    feeds/flares.py            NASA DONKI FLR.
    feeds/quakes.py            USGS GeoJSON.
    feeds/flights.py           adsb.lol /v2/mil, filtered by type.
    feeds/neo.py               NASA NeoWs.
    feeds/commodities.py       OilPriceAPI demo.
    feeds/emergency_squawks.py adsb.lol emergency squawks.

    api/routes.py              /api/events, /api/health, /api/feed/<n>, /api/config
    api/serialize.py           JSON shaping.

    static/index.html          Dashboard shell (three panels).
    static/css/terminal.css    CRT, glows, tag pills, health rows.
    static/js/audio.js         Web Audio synth.
    static/js/stream.js        Event cards, filters, dossier, ticker.
    static/js/panels.js        Feed health + session stats.
    static/js/app.js           Poll loop + controls. Only file that talks to server.

## Decisions that look odd without context

### Radar canvas was removed

An earlier version had a canvas radar with a rotating sweep and blips
for quakes and flights. It looked like a map but was not one — no
coastlines, no anchoring, and the rotating sweep implied active scanning
that was not happening. It was replaced with a `lat, lon` chip on each
event card, plus the event stream itself. Do not re-add it without a
real map underneath, and if you do add a real map, remember the flights
feed is filtered, so an empty region on the map does not mean "no
aircraft" — it means "no aircraft matching the current type filter in
covered areas".

### GCP dot, Schumann, panic index were removed

The original prototype had a "GCP coherence dot", a Schumann resonance
gauge, a "panic index", and a "weirdness gauges" panel. None of these
have a reliable free API, so all were simulated. The dashboard is now
real-data-only. What replaced them is the Feed Health panel: every
configured feed is listed with its last-poll age and event count, and
any feed that is down shows as `err:` in red.

### Flights feed is filtered, not complete

`FLIGHT_INTERESTING_TYPES` in `config.py` is a curated set of ICAO type
designators (F16, C17, A400, etc.). Only aircraft matching those types
appear. Type codes are checked against both `t` and `type` in the
payload, and source tags like `MLAT` or `ADSB_ICAO` are rejected — they
look like types but are not. If you add a type and it does not appear,
check `config.py`: several common aircraft have non-obvious designators
(K35R for KC-135, DC10 for KC-10, C5M for C-5, E3TF for E-3).

### Every event has a source and a link

The dossier drawer shows an `[open source]` link to the original URL
returned by the feed. Nothing is paraphrased or aggregated. If you add a
summary feature, the summary must cite the source URL, not replace it.

### In-memory only, no database

Restarting the container is a fresh poll. This is a feature for a
single-user dashboard: no schema migrations, no disk state to corrupt,
no cleanup jobs. Do not add persistence unless the user explicitly asks.

## Design principles

- **No scoring, no threat level, no forecast.** The dashboard shows
  what feeds are reporting now. (This is the constraint the current task
  is reconsidering — see "What is currently in progress".)
- **Every feed is labeled.** No feed is hidden. A feed that is down
  shows as down, not as absent.
- **Coverage is not the world.** Military ADS-B is the clearest
  example: an empty flights list means "no coverage in this region", not
  "no aircraft airborne". The event description carries this caveat. The
  same applies to news (three outlets, not "the news") and flares
  (NASA's catalog, not "all flares").
- **Security guards stay.** Every place `stream.js` writes user-derived
  text to the DOM goes through `escapeHtml`.
- **Three dependencies.** `flask`, `feedparser`, `requests`. No more
  without asking.

## What is currently in progress

Layer 1 (headline severity scoring) is implemented. `Event` now carries a
`severity: int` (0–100, default 0); `config.score_headline()` and
`config.match_keywords()` live in `config.py` so tuning is a data change.
Only `feeds/news.py` calls them — all other feeds emit `severity=0` and
render unchanged.

Rendering: `stream.js` applies three tiers (high >70 red border + bold +
`[PIN]` + sorted to top of stream; medium 41–70 amber border; low ≤40
unchanged). `panels.js` shows an ALERTS count (>70) in session stats.
Thresholds are mirrored in `stream.js` / `panels.js` — `api/routes.py` does
not yet expose `/api/config`, so keep them in sync by hand.

Known limitation from Layer 1: `SEVERITY_CRISIS_EXTRA` terms are generic
(`global`, `millions`, …) and can add +25 to non-crisis headlines
(e.g. "green turtles … global status"). Tune or remove in `config.py`.

Planned follow-up layers (do not implement while working on Layer 1):
- Layer 2: velocity detection — same topic in multiple sources within a
  time window. A surge in mentions is itself an event.
- Layer 3: dedicated ALERTS panel above the stream, populated by
  high-severity events only.
- Layer 4: cross-reference against GDELT conflict events for an external
  objective signal, not just keyword heuristics.

## How to work on this project

1. Read the current task issue. If something is ambiguous or
   contradicts the code, ask before coding.
2. Propose a file-by-file plan. Do not start editing until the plan is
   approved.
3. One logical change at a time. Show how to verify each change before
   the next starts.
4. Preserve existing behavior unless the task explicitly changes it.
5. Put tunable values in `config.py`. Logic goes in the feed or module
   that owns the behavior.
6. When done, summarize what changed, what to verify manually, and what
   remains for the next layer.

## Known limitations

- **Reuters RSS URL is broken.** `https://www.reutersagency.com/feed/`
  returns 404. Candidate replacements are in the news feed config
  comments, or add a fourth source. The feed itself is healthy with
  two sources.
- **`DEMO_KEY` quota.** NASA's demo key is shared globally at 30
  req/hour. A free key from api.nasa.gov raises it to 1000/hour. The
  key goes in `.env`, never in `config.py`.
- **`OilPriceAPI` demo is 25 req/day per IP.** Polling interval is
  3600s, so a 24-hour run uses 24 requests. Frequent container restarts
  will exhaust it before midnight UTC.
- **adsb.lol is community-run.** No SLA. Coverage varies by region and
  time. If flights or squawks go red, it is almost always upstream.
- **`NonXMLContentType` warnings in logs** from BBC, Al Jazeera, Sky
  are harmless — the content parses fine, only the HTTP header is
  missing. Downgrade to `log.debug` if the noise bothers you.
- **No tests.** Deliberate. `curl` against `/api/health` is the
  intended smoke test.

## API shape

`GET /api/events` returns:

    {
      "events": [
        {
          "category": "QUAKE",
          "title": "M5.2 — 43 km SE of Somewhere",
          "description": "Depth 12 km. Source: USGS.",
          "timestamp": "2026-11-01T04:22:13+00:00",
          "source_name": "USGS",
          "source_url": "https://earthquake.usgs.gov/...",
          "lat": 37.2,
          "lon": -115.8,
          "symbol": "▲",
          "tags": ["M5.2"]
        }
      ],
      "health": {
        "quakes": {"ok": true, "error": null, "fetched_at": "...", "event_count": 30}
      }
    }

`lat`/`lon` are `null` for NEWS, SPACE, NEO, and COMMODITY — those
events live in the stream and stats but not on any map. `severity` is
being added by the current task; until it lands, treat missing fields
as `0`.

## How to keep this file current

This file goes stale in one place primarily: "What is currently in
progress". Update it at the start of each new task and at the end of
each completed task. The rest of the document changes rarely — only
when a decision is reversed, a file is added or removed, or a new
limitation is discovered.

If you are an AI assistant updating this file: only update the
sections that are actually stale. Do not rewrite it wholesale. Diffs
are easier to review than rewrites.