"""Fire, drought and map-layer tests.

Pinned to the facts the project's narrative rests on, so a re-fetch that changed
them would fail loudly rather than silently change what the demo claims.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib import hazards

ROOT = Path(__file__).resolve().parents[2]
api = TestClient(app)


# --- fires -----------------------------------------------------------------


def test_the_2023_upcountry_fires_are_loaded_with_hawaii_dates():
    fires = {f.name: f for f in hazards.load_fires()}
    for name in ("Olinda", "Kula", "Pulehu", "Lahaina"):
        assert fires[name].year == 2023
        # 8 Aug in Hawaii time — the service's UTC timestamps say 9 Aug.
        assert fires[name].discovered == "2023-08-08"


def test_the_study_area_did_not_burn():
    """The single most important caveat in the project."""
    sa = hazards.STUDY_AREA
    ctx = hazards.fire_context(sa["lat"], sa["lon"])
    assert ctx["inside_perimeter"] is False
    assert ctx["nearest_fire"] == "Olinda"
    # Olinda's edge is ~3 km from the centre, i.e. ~1.5 km beyond the 1.5 km circle.
    assert 2.5 < ctx["distance_km"] < 3.5
    assert ctx["distance_km"] - sa["radius_m"] / 1000 > 1.0


def test_no_browned_patch_lies_inside_a_2023_perimeter():
    from lib.vegetation import browning

    burned = [f for f in hazards.load_fires() if f.year == 2023]
    for patch in browning.load_patches():
        for poly in patch.polygons:
            xs = [x for x, _ in poly.outer]
            ys = [y for _, y in poly.outer]
            lon, lat = sum(xs) / len(xs), sum(ys) / len(ys)
            assert not any(f.contains(lat, lon) for f in burned)


def test_inside_a_perimeter_reads_as_zero_distance():
    """Scan Olinda's bounding box for an interior point — a centroid is not
    guaranteed to be inside an irregular perimeter, so don't rely on one."""
    olinda = next(f for f in hazards.load_fires() if f.name == "Olinda")
    xs = [x for x, _ in olinda.polygons[0].outer]
    ys = [y for _, y in olinda.polygons[0].outer]
    inside = next(
        (lat, lon)
        for i in range(1, 40)
        for j in range(1, 40)
        if olinda.contains(
            lat := min(ys) + (max(ys) - min(ys)) * i / 40,
            lon := min(xs) + (max(xs) - min(xs)) * j / 40,
        )
    )
    assert olinda.distance_m(*inside) == 0.0
    assert hazards.fire_context(*inside)["inside_perimeter"] is True


def test_simplified_gee_perimeters_keep_their_area():
    """The Earth Engine script embeds simplified perimeters; area must not drift."""
    import json
    import math

    sys.path.insert(0, str(ROOT / "scripts"))
    from export_fires_for_gee import UPCOUNTRY, polygons, simplify

    def area(ring):
        kx = 111_320 * math.cos(math.radians(ring[0][1]))
        pts = [(x * kx, y * 111_320) for x, y in ring]
        return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2

    for f in json.loads(hazards.FIRES_PATH.read_text())["features"]:
        if f["properties"]["name"] not in UPCOUNTRY or f["properties"]["year"] != 2023:
            continue
        full = simp = 0.0
        for poly in polygons(f["geometry"]):
            for i, ring in enumerate(poly):
                sign = 1 if i == 0 else -1
                full += sign * area(ring)
                simp += sign * area(simplify(ring, ring[0][1]))
        assert abs(simp - full) / full < 0.01, f["properties"]["name"]


# --- drought ---------------------------------------------------------------


def test_2022_was_the_worst_drought_year():
    summary = hazards.drought_summary()
    assert summary["worst_year"] == "2022"
    assert summary["annual_mean"]["2022"] == 214


def test_partial_years_are_left_out_of_annual_means():
    """2017 has a single week in the record; it must not appear as a 'year'."""
    assert "2017" not in hazards.drought_summary()["annual_mean"]


def test_fire_week_drought_is_moderate_and_rising():
    weeks = {w["date"]: w["dsci"] for w in hazards.drought_summary()["weeks_around_fires"]}
    assert weeks["2023-08-01"] < weeks["2023-08-08"] < weeks["2023-08-15"]


# --- map layers API ---------------------------------------------------------


def test_terrain_binary_matches_its_metadata():
    meta = api.get("/api/layers/terrain").json()
    raw = api.get("/api/layers/terrain.bin").content
    assert len(raw) == meta["width"] * meta["height"] * 2
    grid = struct.unpack(f"<{meta['width'] * meta['height']}h", raw)
    assert min(grid) == meta["min_m"] and max(grid) == meta["max_m"]
    # Haleakala's summit (3,055 m) is inside the box.
    assert 3000 < meta["max_m"] <= 3055
    assert meta["spacing"] == "linear in latitude and longitude"


@pytest.mark.needs_globe_cache
def test_site_pins_carry_browning_and_fire_context():
    pins = api.get("/api/layers/sites").json()
    assert len(pins) == 19
    assert all(p["fire"]["available"] for p in pins)
    assert all(p["label"] != "No" for p in pins)  # non-answer notes never become titles
    sees = [p for p in pins if p["site_name"] == "04QGJ763065"]
    assert sees and sees[0]["browned_fraction"] > 0.5


def test_study_area_endpoint_states_the_fire_distance():
    sa = api.get("/api/layers/study-area").json()
    assert sa["fire"]["inside_perimeter"] is False
    assert sa["browned_fraction"] == 0.427


def test_other_layers_serve():
    for path in ("/api/layers/browning", "/api/layers/fires", "/api/layers/drought"):
        assert api.get(path).status_code == 200, path


@pytest.mark.needs_globe_cache
def test_observation_detail_includes_nearest_fire():
    obs = api.get("/api/sites/observation/93353").json()
    assert obs["fire"]["nearest_fire"] in {"Olinda", "Kula", "Pulehu"}
    assert obs["fire"]["inside_perimeter"] is False


def test_observatory_pages_are_served_once_built():
    built = (ROOT / "app" / "static" / "site" / "index.html").exists()
    for path in ("/", "/explore", "/insights", "/map", "/methods", "/sources", "/about"):
        response = api.get(path)
        if built:
            assert response.status_code == 200, path
            assert "/static/site/assets/" in response.text, path
        else:
            assert response.status_code == 503 and "npm run build" in response.json()["detail"]


def test_viewer_moved_to_its_own_path():
    response = api.get("/viewer")
    assert response.status_code == 200
    assert "cubemap-viewer.mjs" in response.text


def test_old_viewer_deep_links_redirect():
    """Links from before the Observatory pointed at /?obs=<id>."""
    response = api.get("/?obs=93353", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/viewer?obs=93353"


def test_redirect_encodes_the_observation_id():
    response = api.get("/?obs=a b&c", follow_redirects=False)
    assert response.headers["location"] == "/viewer?obs=a%20b"


# --- drought calendar ------------------------------------------------------


def test_drought_weeks_are_cumulative_and_sum_to_the_official_dsci():
    from lib import hazards

    weeks = hazards.drought_weeks()
    assert len(weeks) == 367
    official = dict(hazards.drought_series())
    for w in weeks:
        assert w["d0"] >= w["d1"] >= w["d2"] >= w["d3"] >= w["d4"]
        assert abs(w["dsci"] - official[w["date"]]) <= 1


def test_drought_weeks_2022_has_twenty_exceptional_weeks():
    from lib import hazards

    assert sum(1 for w in hazards.drought_weeks() if w["date"].startswith("2022") and w["d4"] > 0) == 20


def test_drought_weeks_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    rows = TestClient(app).get("/api/layers/drought-weeks").json()
    assert len(rows) == 367 and set(rows[0]) == {"date", "dsci", "d0", "d1", "d2", "d3", "d4"}
