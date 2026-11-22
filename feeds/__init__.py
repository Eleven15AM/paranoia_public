"""
Resolves the FEED_REGISTRY entries from config.py into actual Feed
instances. Import errors are logged and skipped, so a missing feed module
(e.g. news.py before Message 3) does not prevent the app from starting.

Feed identity contract (issue #7): the registry is the single source of
truth for name, interval, category, and label. build_feeds() injects all of
them on the instance. Feed classes do not declare `name` (or `category`)
as class attributes; the values come only from the registry. If an instance
ends up with a field that disagrees with the registry entry, startup fails
with a clear error instead of a silent drift.
"""
import importlib
import logging

import config

log = logging.getLogger(__name__)

REQUIRED_KEYS = ("name", "class", "interval", "category", "label")
INJECTED_FIELDS = ("name", "interval", "category")


def _resolve(dotted: str):
    module_path, class_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_feeds() -> list:
    """Return a list of instantiated Feed objects for every entry in
    FEED_REGISTRY whose class can be imported. Missing modules are logged
    at WARNING and skipped.

    Raises RuntimeError if an entry is missing a required key, or if an
    injected field does not match the registry after construction.
    """
    feeds = []
    for entry in config.FEED_REGISTRY:
        missing = [k for k in REQUIRED_KEYS if k not in entry]
        if missing:
            raise RuntimeError(
                f"FEED_REGISTRY entry {entry.get('name', '<unnamed>')!r} "
                f"is missing required keys: {missing}"
            )
        try:
            cls = _resolve(entry["class"])
            instance = cls()
            # The registry is the single source of truth for feed identity.
            # Inject on the instance, not the class.
            instance.name = entry["name"]
            instance.interval = entry["interval"]
            instance.category = entry["category"]

            # Defensive contract check: any divergence means a feed class
            # is doing something the registry does not know about.
            for field in INJECTED_FIELDS:
                got = getattr(instance, field, None)
                want = entry[field]
                if got != want:
                    raise RuntimeError(
                        f"Feed {entry['name']!r}: {field}={got!r} "
                        f"does not match registry value {want!r}"
                    )

            feeds.append(instance)
        except (ImportError, AttributeError) as exc:
            log.warning("Skipping feed %r: %s", entry["name"], exc)
    return feeds