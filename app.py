"""
Entry point. Builds the cache, resolves the feed registry, starts the
scheduler threads, mounts the API blueprint, and serves the static
dashboard. One process, no database, no queue.
"""
import logging

from flask import Flask, send_from_directory

import config
from api.routes import init_routes
from core.cache import Cache
from core.scheduler import Scheduler
from feeds import build_feeds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="")

    cache = Cache()
    feeds = build_feeds()

    if not feeds:
        logging.warning("No feeds resolved; check FEED_REGISTRY and feed modules.")

    feed_meta = {
        entry["name"]: {
            "name": entry["name"],
            "category": entry["category"],
            "label": entry["label"],
            "interval": entry["interval"],
        }
        for entry in config.FEED_REGISTRY
        # Only advertise feeds that actually resolved.
        if any(f.name == entry["name"] for f in feeds)
    }

    scheduler = Scheduler(feeds, cache)
    scheduler.start()

    app.register_blueprint(init_routes(cache, feed_meta))

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # Stash for shutdown handler and debugging.
    app.config["SCHEDULER"] = scheduler
    app.config["CACHE"] = cache
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)