"""Tiny JSON file cache for retrieval results.

Why: searching the same topic twice (common while demoing/debugging) should not
hit DuckDuckGo/GitHub again; that is how you get rate-limited. One file per
(namespace, key), with a time-to-live from CACHE_TTL_HOURS.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from config import get_settings


def _path(namespace: str, key: str):
    settings = get_settings()
    digest = hashlib.sha1(f"{namespace}:{key}".encode()).hexdigest()[:16]
    return settings.cache_dir / f"{namespace}_{digest}.json"


def get(namespace: str, key: str) -> Any | None:
    ttl = get_settings().cache_ttl_hours
    path = _path(namespace, key)
    if ttl <= 0 or not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - entry.get("saved_at", 0) > ttl * 3600:
        return None
    return entry.get("data")


def put(namespace: str, key: str, data: Any) -> None:
    # Never cache empty results: "no results" is often a temporary block or rate limit,
    # and caching it would hide recovered search engines for the whole TTL.
    if get_settings().cache_ttl_hours <= 0 or not data:
        return
    path = _path(namespace, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"saved_at": time.time(), "data": data}), encoding="utf-8")
    except OSError:
        pass  # caching is best-effort; never fail a research run because of it
