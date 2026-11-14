"""
HTTP layer. Every route reads from the cache snapshot; none do I/O.
"""
from flask import Blueprint, jsonify

from api.serialize import events_payload, health_payload
from core.cache import Cache

bp = Blueprint("api", __name__, url_prefix="/api")


def init_routes(cache: Cache, feed_meta: dict) -> Blueprint:
    """Attach the cache and feed metadata to the blueprint's view closures."""

    @bp.get("/events")
    def get_events():
        return jsonify(events_payload(cache.snapshot()))

    @bp.get("/health")
    def get_health():
        return jsonify(health_payload(cache.snapshot()))

    @bp.get("/feed/<name>")
    def get_feed(name: str):
        result = cache.get(name)
        if result is None:
            return jsonify({"error": f"feed {name!r} not found or not yet polled"}), 404
        return jsonify(result.to_dict())

    @bp.get("/config")
    def get_config():
        return jsonify({
            "feeds": feed_meta,
            "categories": sorted({m["category"] for m in feed_meta.values()}),
        })

    return bp