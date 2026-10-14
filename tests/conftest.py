"""Shared pytest setup.

`needs_globe_cache` marks tests that assert against the real, cached GLOBE
observations. That cache (`data/cache/`) is gitignored and built by
`scripts/ingest_maui.py` while online, so on a fresh clone or in CI these are
skipped with the reason below rather than failing on a network call. Where the
cache exists they run exactly as before.
"""

from __future__ import annotations

import pytest

from lib.globe_api import client


def _cache_present() -> bool:
    # The window every API route and analysis test reads (see routes.sites).
    return client._cache_path("2017-01-01", "2026-12-31", client.HAWAII.name).exists()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "needs_globe_cache: needs the cached GLOBE observations in data/cache/"
    )


def pytest_collection_modifyitems(config, items):
    if _cache_present():
        return
    skip = pytest.mark.skip(
        reason="no data/cache/ — run scripts/ingest_maui.py once while online"
    )
    for item in items:
        if "needs_globe_cache" in item.keywords:
            item.add_marker(skip)
