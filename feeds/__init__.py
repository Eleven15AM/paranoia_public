"""
Resolves the FEED_REGISTRY entries from config.py into actual Feed
instances. Import errors are logged and skipped, so a missing feed module
(e.g. news.py before Message 3) does not prevent the app from starting.
"""
import importlib
import logging

import config

log = logging.getLogger(__name__)


def _resolve(dotted: str):
    module_path, class_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_feeds() -> list:
    """Return a list of instantiated Feed objects for every entry in
    FEED_REGISTRY whose class can be imported. Missing modules are logged
    at WARNING and skipped."""
    feeds = []
    for entry in config.FEED_REGISTRY:
        try:
            cls = _resolve(entry["class"])
            instance = cls()
            # The registry is the source of truth for interval/category;
            # the class may define defaults, but config overrides.
            instance.interval = entry["interval"]
            instance.category = entry["category"]
            feeds.append(instance)
        except (ImportError, AttributeError) as exc:
            log.warning("Skipping feed %r: %s", entry["name"], exc)
    return feeds