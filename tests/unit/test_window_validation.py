"""The date window on the sites API: validated, and never a reason to fetch.

Synthetic observations stand in for GLOBE; nothing here touches the network or
the on-disk cache.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import sites as routes
from app.main import app
from lib.globe_api import client

api = TestClient(app, raise_server_exceptions=False)


def _obs(land_cover_id: str, measured_at: str | None, lat=20.83, lon=-156.34):
    props = {
        "landcoversLandCoverId": land_cover_id,
        "siteId": "s1",
        "siteName": "04QGJ000000",
        "landcoversMeasuredAt": measured_at or "null",
        "landcoversMeasurementLatitude": str(lat),
        "landcoversMeasurementLongitude": str(lon),
    }
    return client.parse_feature({"properties": props, "geometry": {"coordinates": [lon, lat]}})


@pytest.fixture
def fetches(monkeypatch):
    """Stub the client; record every window it is asked for."""
    calls: list[tuple[str, str]] = []
    data = [
        _obs("old", "2020-03-01T10:00:00"),
        _obs("new", "2026-07-06T04:02:00"),
        _obs("undated", None),
    ]

    def fake_fetch_sites(start, end, **_):
        calls.append((start, end))
        return data

    monkeypatch.setattr(client, "fetch_sites", fake_fetch_sites)
    return calls


def _ids(response):
    assert response.status_code == 200, response.text
    return {row["land_cover_id"] for row in response.json()}


@pytest.mark.parametrize(
    "query",
    [
        "start=garbage",
        "end=2026-13-45",
        "start=2026-01-01&end=2020-01-01",  # inverted
    ],
)
def test_bad_windows_are_422_not_500(fetches, query):
    for path in (
        f"/api/sites/search?area=pukalani&{query}",
        f"/api/sites/observation/old?{query}",
        f"/api/sites/s1/history?{query}",
    ):
        assert api.get(path).status_code == 422, path
    assert fetches == []  # rejected before any lookup


def test_any_window_reads_only_the_one_cached_window(fetches):
    api.get("/api/sites/search?area=pukalani&start=0001-01-01&end=9999-12-31")
    api.get("/api/sites/search?area=pukalani&start=2024-01-01&end=2024-02-01")
    api.get("/api/sites/s1/history?start=1999-01-01&end=2001-01-01")
    assert fetches
    assert set(fetches) == {(routes.DEFAULT_START, routes.DEFAULT_END)}


def test_window_narrows_results_locally(fetches):
    narrow = api.get("/api/sites/search?area=pukalani&start=2025-01-01&end=2026-12-31")
    assert _ids(narrow) == {"new"}
    older = api.get("/api/sites/search?area=pukalani&start=2020-01-01&end=2020-12-31")
    assert _ids(older) == {"old"}


def test_default_window_keeps_every_observation_including_undated(fetches):
    assert _ids(api.get("/api/sites/search?area=pukalani")) == {"old", "new", "undated"}


def test_observation_outside_the_window_is_a_404(fetches):
    assert api.get("/api/sites/observation/old?start=2025-01-01&end=2026-12-31").status_code == 404
    assert api.get("/api/sites/observation/old").status_code == 200
