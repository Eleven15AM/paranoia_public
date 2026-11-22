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
                           NEWS_FEED_URLS, NASA_API_KEY, SEVERITY_*,
                           VELOCITY_*, ALERTS_PANEL_LIMIT, GDELT_*, and
                           the two scoring functions score_headline /
                           match_keywords). Single source of truth for feed
                           identity (issue #7).

core/models.py             Event, FeedResult dataclasses. Event is the
                           only shape the frontend ever sees.
core/cache.py              Thread-safe in-memory cache.
core/scheduler.py          One thread per feed; fetch → cache.set → sleep.
core/velocity.py           In-memory rolling window of topic-key hits;
                           emits synthetic VELOCITY surge events (Layer 2).
core/gdelt.py              Best-effort GDELT cross-reference for high
                           severity NEWS/VELOCITY events (Layer 4).

feeds/__init__.py          build_feeds(): resolves FEED_REGISTRY entries and
                           injects name/interval/category; raises on drift.
feeds/base.py              Feed ABC + classify_http_error() (issue #5).
feeds/news.py              RSS/Atom via feedparser. Scores each headline
                           (Layer 1) and seeds velocity (Layer 2).
feeds/flares.py            NASA DONKI FLR. 404 treated as healthy-but-empty.
feeds/quakes.py            USGS GeoJSON. Category from self.category.
feeds/flights.py           adsb.lol /v2/mil, filtered by type.
feeds/neo.py               NASA NeoWs.
feeds/commodities.py       OilPriceAPI demo.
feeds/emergency_squawks.py adsb.lol emergency squawks.

api/routes.py              /api/events, /api/health, /api/feed/<n>, /api/config
api/serialize.py           JSON shaping.

static/index.html          Dashboard shell (three panels + ALERTS panel).
                           Footer slot reserved; no ticker text.
static/css/terminal.css    CRT, glows, tag pills, health rows.
static/js/audio.js         Web Audio synth.
static/js/stream.js        Event cards, filters, dossier, severity tiers,
                           GDELT row. pushTicker() is a null-safe no-op.
static/js/panels.js        Feed health + session stats + ALERTS panel
                           (Layer 3) + [GDELT: N] chip (Layer 4).
static/js/app.js           Poll loop + controls. Only file that talks to server.

.github/workflows/docker-publish.yml
                           Build + push to GHCR on main and v* tags.
docker-compose.prod.yml    Pull-and-run compose for the target machine.
docker-compose.yml         Local development compose (build: .).
Dockerfile                 Single image, used by both compose files.
.env.example               Environment template (NASA_API_KEY, VERSION).
README.md                  Run instructions: local dev and GHCR.
CONTEXT.md                 This file.

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

### Jinja2 templates were considered and rejected

The dashboard is a single page: `index.html` is served once and everything
after that is `fetch('/api/events')` plus DOM rendering in `stream.js`,
`panels.js`, and `app.js`. Jinja2 earns its keep on multi-page sites with
server-rendered forms and shared layouts. This app has none of those. Adding
it would mean a `templates/` directory, a `render_template` call, a template
context, and a second rendering path for content that is already client-rendered
— strictly more surface area for no benefit. The current split (static HTML
shell + JSON + one JS renderer) is coherent and should stay.

If a genuinely server-rendered page appears later — a history view, a settings
form — use Jinja2 for that one route and leave the dashboard SPA untouched.
Do not convert the existing page.

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

Layers 1-4, the feed-handling cleanup (issue #5), the release process
(issue #6), and feed identity (issue #7) are implemented. Scoring, velocity,
and GDELT are news-only; all other feeds emit `severity=0`, `gdelt=null`,
and render unchanged.

Layer 1: `Event.severity: int` (0-100, default 0). `config.score_headline()`
and `config.match_keywords()` live in `config.py` so tuning is a data change.
Only `feeds/news.py` calls them.

Layer 2: `core/velocity.py` keeps an in-memory rolling window of topic-key
hits and emits one synthetic `VELOCITY` event per topic key per cooldown
when the threshold is crossed. Called from `core/scheduler.py` after a
successful news poll. Topic keys are `VELOCITY_TOPICS` plus the positive
Layer 1 crisis keywords; `SEVERITY_CRISIS_EXTRA` is deliberately excluded.
`VELOCITY` events carry `severity=75` and pick up `[PIN]` / red treatment.

Layer 3: a dedicated ALERTS panel above the event stream, rendered by
`panels.js` `updateAlerts()`. Shows only `severity > 70` events, newest
first, capped at `ALERTS_PANEL_LIMIT`. Clicking a row opens the dossier.
The panel is a live view: no ack, no dismissal, no history.

Layer 4: `core/gdelt.py` cross-references each high-severity NEWS/VELOCITY
event against the keyless GDELT 2.0 DOC API. Result is attached as
`Event.gdelt: {"count", "sample_titles", "sample_urls"} | None`. Called from
`core/scheduler.py` after velocity. Best-effort: any failure leaves `gdelt`
as `None` and never fails a poll. A global min-interval
(`GDELT_MIN_INTERVAL_SECONDS`) throttles network calls, including when GDELT
returns 429; an in-memory per-query cache (`GDELT_CACHE_TTL_SECONDS`) avoids
repeats. Titles are sanitized into quoted phrase queries before sending, so
operator characters in headlines are not parsed as GDELT operators.

Issue #5 (feed handling): `feeds/base.py` has `classify_http_error()`,
currently used by `feeds/flares.py` to treat a NASA DONKI 404 as healthy-but-
empty rather than an error. The bottom footer `ALERT: FLASH` marquee and the
scrolling ticker text were removed; the footer slot (`#footer-slot`) is
reserved for future functionality. `stream.js` `pushTicker()` is a null-safe
no-op until that slot is repurposed.

Issue #6 (release process): `.github/workflows/docker-publish.yml` builds
and pushes the image to GHCR (`ghcr.io/eleven15am/paranoia_public`) on push
to `main` and on `v*.*.*` tags. `docker-compose.prod.yml` pulls by
`VERSION` instead of building; the existing `docker-compose.yml` stays for
local development. The published package is public; the workflow sets
`org.opencontainers.image.source` so the package links back to the repo.
Security flags are identical between the two compose files.

Issue #7 (feed identity): `FEED_REGISTRY` is the single source of truth for
`name`, `interval`, `category`, and `label`. `feeds/__init__.py`
`build_feeds()` injects `name`, `interval`, and `category` on each instance
and raises `RuntimeError` if any injected field disagrees with the registry
entry. Feed classes no longer declare `name` (or `category`) as class
attributes. `feeds/quakes.py` builds `Event` with `category=self.category`
rather than a hardcoded string.

Rendering: `stream.js` applies three severity tiers (high >70 red border +
bold + `[PIN]` + sorted to top; medium 41-70 amber border; low <=40
unchanged). News and velocity cards show the full date
(`YYYY-MM-DD HH:MM:SSZ`); other feeds keep `HH:MM:SSZ`. The dossier shows a
`GDELT:` row when present. ALERTS panel rows show `[GDELT: N]` when present.
`panels.js` shows ALERTS (>70) and VELOCITY counts. Thresholds are mirrored
in `stream.js` / `panels.js` — `/api/config` exists and is fetched by
`app.js`, but the frontend does not yet read thresholds from it (see the
accepted review item on the `/api/config` contradiction).

Known limitations from Layers 1-4 and issues #5-#7:
- `SEVERITY_CRISIS_EXTRA` terms are generic (`global`, `millions`, ...) and
  can add +25 to non-crisis headlines. Tune or remove in `config.py`.
- Velocity counts distinct `source_name` as-is, so a syndicated story
  republished under multiple names can look like a surge. Start naive.
- Velocity window and cooldown are in-memory only. Restart = empty window.
- The ALERTS panel has no ack, dismissal, or history. Intentional for Layer 3.
- GDELT is keyless and aggressively rate-limited (HTTP 429 is common). The
  min-interval gate means at most one network attempt per interval; most
  high-severity events will carry `gdelt: None` until GDELT recovers. This
  is expected behavior, not a bug.
- Only `feeds/flares.py` currently uses `classify_http_error()`. Other feeds
  still treat every non-2xx as an error and may need the same treatment.
- `adsb.lol` (flights and squawks) returns HTTP 429 under load. Community-run,
  no SLA; failures are upstream and currently surface as feed errors. See
  accepted review item on ADS-B redundancy.
- The app runs under Flask's development server (`werkzeug` warns on every
  start). Fine for a single-user home deployment; a production WSGI server
  (gunicorn, waitress) would silence the warning and is a candidate
  improvement, not yet scheduled.
- Release images are `linux/amd64` only. If the target machine is ARM, add
  `linux/arm64` to the workflow's `platforms:` and expect a longer build.
- GHCR packages default to private on first push. Visibility is a one-time
  manual toggle in Package settings; see README.

### Accepted from the external review (not yet implemented)

An external code review was performed after issue #6. Item 1 (feed identity
duplication) was implemented as issue #7. The remaining accepted items below
are queued for future work, in rough priority order.

1. ~~**Feed identity duplication.**~~ Implemented in issue #7.

2. **Registry as dataclass.** Replace `FEED_REGISTRY` plain dicts with a small
   dataclass (with defaults) so a typo like `"intervla": 600` fails at import
   time with a clear message, not at first poll with a `KeyError` deep in the
   scheduler. Cheap, makes the registry self-documenting. Note: issue #7 added
   `REQUIRED_KEYS` validation in `build_feeds()`, which catches missing keys
   but not typos that produce a wrong-but-present key.

3. **News coverage and syndication dedup.** Reuters RSS is currently 404ing
   (already a known limitation), so velocity detection runs on two outlets.
   Add one or two more RSS sources (AP, Guardian). Separately, deduplicate
   syndicated stories (same headline, different `source_name`) before they
   reach the velocity window, which fixes the known false-surge limitation
   already recorded in this file.

4. **Resolve the `/api/config` contradiction.** The File map lists
   `/api/config` as exposed and `static/js/app.js` fetches it, so the endpoint
   exists. The frontend does not currently read `SEVERITY_MEDIUM` /
   `SEVERITY_HIGH` from it; `stream.js` and `panels.js` hand-mirror the
   values. Serve the thresholds through `/api/config` (if not already there)
   and read them in the frontend, eliminating the drift risk. Small.

5. **ADS-B redundancy for flights and squawks.** Both feeds depend entirely
   on adsb.lol, a community-run API with no SLA that returns HTTP 429 under
   load. Add a fallback endpoint (adsb.fi or OpenSky) used when adsb.lol
   errors. Medium effort: the payload shapes differ between providers and
   mapping is needed. Its own issue, not a cleanup.

### Rejected from the external review (do not implement)

These were considered and deliberately not adopted. Recording them so a
future reviewer does not re-propose them.

- **Metadata-driven frontend** (serve category color, symbol, and alert flag
  from the registry via an API; build filter buttons and rendering from data).
  Right diagnosis — a genuinely new category currently requires edits to
  `CAT_COLOR`, `index.html`, audio triggers, and the full-date rule — but the
  cost (new endpoint, new rendering-from-data path, migration of four
  hardcoded maps) is only justified when a second genuinely new category
  actually appears. Until then, adding a category to those four places in one
  PR is the smaller, better change. Revisit if and when that second category
  is proposed.

- **`Event.alert: bool`** (feeds set a boolean at parse time; frontend uses it
  instead of hardcoded tag/category rules for audio). Rejected: it duplicates
  what severity already encodes for news, adds a field every feed must
  populate, and introduces a second "is this loud?" concept alongside
  severity. If audio triggers need to change, change the category rules
  directly.

- **Browser notifications for high-severity events.** The premise (the user
  opens the app occasionally) is correct, but browser notifications only fire
  when a tab is open, which weakens the premise. The genuinely useful version
  is a server-side push (email, ntfy, Pushover, webhook), which adds an
  outbound integration and config surface that this file keeps out by design.
  Needs a written proposal before consideration, not a cleanup.

- **`JsonApiFeed` intermediate base class** (own the request/error/packaging
  flow; expose `url(s)` and `parse_item(item)` hooks). Correct diagnosis of
  real duplication across `quakes`, `flares`, `squawks`, `neo`, `commodities`.
  Not rejected on merit, but deferred: it is a refactor of working code with
  regression risk and no visible payoff. Build it lazily when the next
  JSON-shaped feed is added, and migrate existing feeds one at a time with
  verification.

- **Persistence for the velocity window and alert history.** The argument is
  strong, but it is a reversal of this file's "in-memory only, restart = fresh
  poll" decision, not a cleanup. If pursued, it needs its own issue, an
  explicit `CONTEXT.md` update, a volume mount (the read-only container was
  chosen to enforce no disk writes), and a decision between TinyDB (simple,
  document-shaped) and DuckDB (queryable, analytical). Write-behind only:
  feed threads keep writing to the in-memory cache, a separate writer
  persists snapshots. Not now.

- **Jinja2 for the dashboard.** See the new "Decisions" entry above.

### Database, if pursued later

If persistence is revisited, the two candidates worth considering are:

- **TinyDB** — pure Python, single JSON file, document-oriented, no schema,
  trivial to install. Natural shape for `Event` dicts. Recommended if the goal
  is "remember things across restart."
- **DuckDB** — embedded analytical engine with first-class JSON support.
  Recommended if the goal is "query my own history" ("all M5+ quakes near
  this point in six months", "which topics surged this week").

Avoid a separate always-on service (Redis, MongoDB): it adds a second
container to babysit on a home box and breaks the "one container, restart =
fresh state" simplicity for no benefit at single-user scale.

The pattern is write-behind regardless of choice: the in-memory cache remains
the source of truth for the live app; a separate writer persists snapshots on
an interval or on alert-tier events. A database hiccup must never take down a
feed — that per-feed isolation rule is the most important constraint in this
file.

No follow-up layer is currently scheduled. The accepted external-review items
above are queued for future work when you choose to pick them up.

Known limitations from Layers 1-4 and issue #5:
- `SEVERITY_CRISIS_EXTRA` terms are generic (`global`, `millions`, ...) and
  can add +25 to non-crisis headlines. Tune or remove in `config.py`.
- Velocity counts distinct `source_name` as-is, so a syndicated story
  republished under multiple names can look like a surge. Start naive.
- Velocity window and cooldown are in-memory only. Restart = empty window.
- The ALERTS panel has no ack, dismissal, or history. Intentional for Layer 3.
- GDELT is keyless and aggressively rate-limited (HTTP 429 is common). The
  min-interval gate means at most one network attempt per interval; most
  high-severity events will carry `gdelt: None` until GDELT recovers. This
  is expected behavior, not a bug.
- Only `feeds/flares.py` currently uses `classify_http_error()`. Other feeds
  still treat every non-2xx as an error and may need the same treatment.

No planned follow-up layer at present. Open ideas if a next layer is
proposed: none defined beyond what exists above.
  
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