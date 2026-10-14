"""Compression, caching and header policy (app/middleware.py)."""

from __future__ import annotations

import asyncio
import gzip

import pytest
from fastapi.testclient import TestClient

from app import middleware
from app.main import app

api = TestClient(app)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/static/site/assets/Explore-qcL3YR8E.js", middleware.IMMUTABLE),
        ("/static/vendor/esm/8c8916b936ecb538064af82801c55a66230510b6.mjs", middleware.IMMUTABLE),
        ("/", middleware.REVALIDATE),
        ("/map", middleware.REVALIDATE),
        ("/viewer", middleware.REVALIDATE),
        ("/photos/9001/north.jpg", middleware.PHOTO),
        ("/api/layers/browning", middleware.DATASET),
        ("/api/sites/search", None),  # computed per request: no lifetime of its own
        ("/static/js/cubemap-viewer.mjs", None),  # not content-hashed
        ("/health", None),
    ],
)
def test_cache_policy_by_path(path, expected):
    assert middleware.cache_control_for(path) == expected


def test_hashed_build_assets_are_immutable_and_gzipped():
    from pathlib import Path

    asset = next(Path("app/static/site/assets").glob("Explore-*.js"))
    r = api.get(f"/static/site/assets/{asset.name}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == middleware.IMMUTABLE
    assert r.headers["content-encoding"] == "gzip"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_geojson_is_compressed_and_smaller_on_the_wire():
    plain = api.get("/api/layers/browning", headers={"Accept-Encoding": "identity"})
    zipped = api.get("/api/layers/browning", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in plain.headers
    assert zipped.headers["content-encoding"] == "gzip"
    assert zipped.headers["cache-control"] == middleware.DATASET
    assert zipped.content == plain.content  # httpx decodes; the bytes are the same data
    wire = len(gzip.compress(plain.content))
    assert wire < len(plain.content) / 2


def test_page_is_revalidated_so_rebuilds_are_picked_up():
    assert api.get("/").headers["cache-control"] == middleware.REVALIDATE


def _gzip_header_for(path: str) -> bytes | None:
    """Run SelectiveGZip around a stub app that returns 5 KB of body for any path."""

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"x" * 5000})

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request"}

    scope = {"type": "http", "method": "GET", "path": path, "headers": [(b"accept-encoding", b"gzip")]}
    asyncio.run(middleware.SelectiveGZip(inner)(scope, receive, send))
    return dict(sent[0]["headers"]).get(b"content-encoding")


@pytest.mark.parametrize(
    "path",
    [
        "/photos/9001/north.jpg",
        "/api/layers/raster/dndvi",  # the real raster routes carry no extension
        "/api/layers/imagery/before_2023",
        "/static/anything.png",
    ],
)
def test_already_compressed_content_is_not_gzipped_again(path):
    assert _gzip_header_for(path) is None


@pytest.mark.parametrize("path", ["/api/layers/browning", "/api/layers/terrain.bin", "/static/site/assets/a.js"])
def test_everything_else_is_gzipped(path):
    assert _gzip_header_for(path) == b"gzip"


def test_errors_are_never_given_a_cache_lifetime(monkeypatch):
    """A 503 for a missing data file must not be remembered after the file appears."""
    from app.api.routes import layers

    monkeypatch.setattr(layers, "TERRAIN_META", layers.DATA / "terrain" / "nope.json")
    r = api.get("/api/layers/terrain")
    assert r.status_code == 503
    assert "cache-control" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("path", ["/", "/viewer"])
def test_pages_declare_an_icon_so_browsers_do_not_request_a_missing_favicon(path):
    """No <link rel=icon> makes every browser fetch /favicon.ico, which is a 404
    and a red console error on the first page a visitor sees."""
    assert 'rel="icon"' in api.get(path).text
