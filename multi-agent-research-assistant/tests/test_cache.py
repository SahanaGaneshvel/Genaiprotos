"""JSON file cache tests (uses a temporary directory, never the real cache)."""

import dataclasses

import pytest

from config import get_settings
from services import cache


@pytest.fixture
def temp_cache(monkeypatch, tmp_path):
    settings = dataclasses.replace(get_settings(), cache_dir=tmp_path, cache_ttl_hours=1)
    monkeypatch.setattr(cache, "get_settings", lambda: settings)
    return tmp_path


def test_round_trip(temp_cache):
    cache.put("web", "query", [{"title": "x"}])
    assert cache.get("web", "query") == [{"title": "x"}]


def test_empty_results_are_never_cached(temp_cache):
    # real bug: a temporary "no results" (rate limit) was cached for 24 h
    cache.put("web", "query", [])
    assert cache.get("web", "query") is None
    assert list(temp_cache.iterdir()) == []


def test_expired_entries_are_ignored(temp_cache, monkeypatch):
    cache.put("web", "query", [{"title": "x"}])
    monkeypatch.setattr(cache.time, "time", lambda: 10**12)  # far in the future
    assert cache.get("web", "query") is None
