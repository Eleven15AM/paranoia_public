# paranoia_public

A personal, self-hosted, single-user dashboard that monitors public data
feeds (news, solar flares, earthquakes, military flights, near-earth
objects, commodities, emergency squawks) and displays them in a 1990s
NCurses/BBS terminal aesthetic. Flask + static JavaScript. No database;
the cache is in-memory and rebuilds on restart.

Architecture and design intent are documented in `CONTEXT.md`. This
README covers only how to run it.

## Run locally (development)

Requires Docker.

```bash
cp .env.example .env      # set NASA_API_KEY if you have one; DEMO_KEY otherwise
docker compose up --build -d
Open http://localhost:8080. 
Logs: docker compose logs -f.
Stop: docker compose down
```
## Run from GHCR (target machine)

The published image lives at
```ghcr.io/eleven15am/paranoia_public.```
The package is public, so no registry login is required to pull.

Requires Docker and Docker Compose v2 on the target machine.
```bash
    Copy the two files you need next to each other:
    bash

    cp .env.example .env
    # edit .env: set NASA_API_KEY and VERSION (e.g. VERSION=1.0.0)

    docker-compose.prod.yml is in this repo; copy it alongside .env,
    or clone the repo and use it in place.

    Pull and start:
    bash

    docker compose -f docker-compose.prod.yml pull
    docker compose -f docker-compose.prod.yml up -d

    Open http://<host>:8080. The app binds to 8080 on all interfaces,
    so it is reachable on your local network but not exposed to the
    internet unless you forward the port.
```
## Updating

Change VERSION in .env (or pass it inline), then:
``` bash
VERSION=1.0.1 docker compose -f docker-compose.prod.yml pull
VERSION=1.0.1 docker compose -f docker-compose.prod.yml up -d
```
latest is also published on every v*.*.* tag, but pinning a version
is recommended so restarts do not silently change behavior.

## Security flags

docker-compose.prod.yml runs the container with read_only: true,
tmpfs: /tmp, and cap_drop: ALL. The app writes nothing to disk; if
you add a feature that needs scratch space, mount a tmpfs rather than
removing read_only.

## Publishing a release (maintainer)

The image is built and pushed by .github/workflows/docker-publish.yml:

    Push to main → tags edge and sha-<short>.

    Push a v*.*.* git tag → tags X.Y.Z, X.Y, X, and latest.

To cut a release:
``` bash

git tag v1.0.0
git push origin v1.0.0
```
## Two one-time setup notes:

    Pushing the workflow file requires a personal access token with
    the workflow scope (classic) or Workflows: write (fine-grained).
    This is a push-time requirement only; the workflow itself uses the
    built-in GITHUB_TOKEN at runtime.

    First publish visibility. GHCR packages default to private even
    for public repos. After the first successful push, open the repo's
    Packages sidebar entry for paranoia_public → Package
    settings → Change visibility → Public. The workflow sets
    org.opencontainers.image.source automatically, which is what makes
    the package appear under the repo.

## Configuration

All tunables live in config.py (feed intervals, scoring keywords and
weights, velocity thresholds, GDELT settings, ALERTS panel limit). The
only environment variables are:
```
    NASA_API_KEY — optional; DEMO_KEY works but is rate-limited.

    VERSION — the GHCR image tag to run (production compose only).
```
.env.example lists them with comments.