"""Tests for photo mirroring, cache hardening, and the API's failure paths.

The network is mocked throughout, so these never touch the GLOBE API.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib.globe_api import client

JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


class FakeResponse:
    def __init__(self, content=JPEG, content_type="image/jpeg", status=200):
        self.content = content
        self.headers = {"content-type": content_type}
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            request = httpx.Request("GET", "https://data.globe.gov/x.jpg")
            raise httpx.HTTPStatusError(
                "boom", request=request, response=httpx.Response(self._status, request=request)
            )


def _site(land_cover_id="9001", missing=()):
    props = {
        "landcoversLandCoverId": land_cover_id,
        "siteId": "1",
        "siteName": "04QGJ000000",
        "landcoversMeasuredAt": "2026-07-06T04:02:00",
        "landcoversMeasurementLatitude": "20.838",
        "landcoversMeasurementLongitude": "-156.344",
    }
    for d in client.DIRECTIONS:
        props[f"landcovers{d}PhotoUrl"] = (
            "null" if d in missing else f"https://data.globe.gov/{land_cover_id}/{d}.jpg"
        )
    return client.parse_feature({"properties": props, "geometry": {"coordinates": [-156.344, 20.838]}})


@pytest.fixture
def photo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "PHOTO_DIR", tmp_path / "photos")
    return client.PHOTO_DIR


# --- mirroring -------------------------------------------------------------


def test_mirror_saves_all_six_and_skips_on_rerun(photo_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(client.httpx, "get", lambda url, **kw: calls.append(url) or FakeResponse())

    saved, errors = client.mirror_photos(_site())
    assert (saved, errors) == (6, [])
    assert len(calls) == 6
    assert (photo_dir / "9001" / "north.jpg").read_bytes() == JPEG

    saved_again, _ = client.mirror_photos(_site())
    assert saved_again == 0
    assert len(calls) == 6  # nothing re-downloaded


def test_mirror_skips_directions_the_observer_skipped(photo_dir, monkeypatch):
    monkeypatch.setattr(client.httpx, "get", lambda url, **kw: FakeResponse())
    saved, _ = client.mirror_photos(_site(missing=("Upward",)))
    assert saved == 5
    assert not (photo_dir / "9001" / "upward.jpg").exists()


def test_mirror_rejects_non_image_responses(photo_dir, monkeypatch):
    """An HTML error page served with 200 must not be saved as a JPEG."""
    monkeypatch.setattr(
        client.httpx, "get", lambda url, **kw: FakeResponse(b"<html>nope</html>", "text/html")
    )
    saved, errors = client.mirror_photos(_site())
    assert saved == 0
    assert len(errors) == 6 and "not an image" in errors[0]
    assert not list(photo_dir.rglob("*.jpg"))


def test_one_failed_photo_does_not_abort_the_rest(photo_dir, monkeypatch):
    def flaky(url, **kw):
        return FakeResponse(status=500) if url.endswith("East.jpg") else FakeResponse()

    monkeypatch.setattr(client.httpx, "get", flaky)
    saved, errors = client.mirror_photos(_site())
    assert saved == 5
    assert len(errors) == 1 and "East" in errors[0]


def test_interrupted_download_leaves_no_truncated_file(photo_dir, monkeypatch):
    """A temp file is renamed into place, so a failure never leaves a partial JPEG."""
    original = client.Path.replace

    def explode(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(client.Path, "replace", explode)
    monkeypatch.setattr(client.httpx, "get", lambda url, **kw: FakeResponse())
    saved, errors = client.mirror_photos(_site())
    monkeypatch.setattr(client.Path, "replace", original)

    assert saved == 0 and len(errors) == 6
    assert not list(photo_dir.rglob("north.jpg"))  # final name never appeared


# --- cache hardening -------------------------------------------------------


def test_corrupt_cache_is_discarded_and_refetched(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "CACHE_DIR", tmp_path)
    path = client._cache_path("2024-01-01", "2024-01-31", "hawaii")
    path.write_text('{"type": "FeatureCollection", "features": [')  # truncated write

    monkeypatch.setattr(client, "_fetch_chunk", lambda s, e, t: [])
    payload = client.fetch_raw("2024-01-01", "2024-01-31", bbox=client.HAWAII)
    assert payload["features"] == []
    assert json.loads(path.read_text())["features"] == []  # healed on disk


def test_cache_write_is_atomic(tmp_path):
    target = tmp_path / "sub" / "c.geojson"
    client._write_atomic(target, '{"ok": true}')
    assert json.loads(target.read_text()) == {"ok": True}
    assert not list(tmp_path.rglob("*.tmp"))


def test_network_failure_raises_a_clear_error(monkeypatch):
    def down(*a, **kw):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(client.httpx, "get", down)
    with pytest.raises(client.GlobeUnavailableError, match="2024-01-01"):
        client._fetch_chunk("2024-01-01", "2024-01-31", 5.0)


# --- API -------------------------------------------------------------------

api = TestClient(app)


def test_503_with_actionable_message_when_globe_unreachable_and_uncached(monkeypatch):
    def boom(*a, **kw):
        raise client.GlobeUnavailableError("connection refused")

    monkeypatch.setattr(client, "fetch_near", boom)
    response = api.get("/api/sites/search?area=pukalani")
    assert response.status_code == 503
    assert "unavailable and not cached" in response.json()["detail"]


def test_observation_serves_local_photo_when_mirrored(photo_dir):
    obs = api.get("/api/sites/observation/93191").json()
    # Nothing mirrored yet: remote URLs, flagged as such.
    assert obs["photos"]["North"]["mirrored"] is False
    assert obs["photos"]["North"]["photo_url"].startswith("https://data.globe.gov/")

    (photo_dir / "93191").mkdir(parents=True)
    (photo_dir / "93191" / "north.jpg").write_bytes(JPEG)

    obs = api.get("/api/sites/observation/93191").json()
    north, south = obs["photos"]["North"], obs["photos"]["South"]
    assert north["mirrored"] is True
    assert north["photo_url"] == "/photos/93191/north.jpg"
    assert north["source_url"].startswith("https://data.globe.gov/")  # provenance kept
    assert south["mirrored"] is False  # partial mirror: per-photo fallback


def test_empty_photo_file_is_not_treated_as_mirrored(photo_dir):
    (photo_dir / "93191").mkdir(parents=True)
    (photo_dir / "93191" / "north.jpg").write_bytes(b"")  # zero-byte leftover
    obs = api.get("/api/sites/observation/93191").json()
    assert obs["photos"]["North"]["mirrored"] is False


def test_unknown_observation_and_area_are_404():
    assert api.get("/api/sites/observation/nope").status_code == 404
    assert api.get("/api/sites/search?area=atlantis").status_code == 404


def test_search_requires_a_location():
    assert api.get("/api/sites/search").status_code == 400


def test_out_of_area_vegetation_context_is_not_measured_not_false():
    """Honolulu is outside the Pukalani analysis: None, not False."""
    from app.api.routes.sites import _detail

    site = _site()
    site = client.LandCoverSite(**{**site.__dict__, "latitude": 21.3069, "longitude": -157.8583})
    veg = _detail(site).vegetation
    assert veg.in_analysis_area is False
    assert veg.inside_browning_patch is None
