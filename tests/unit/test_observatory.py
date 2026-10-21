"""Tests for the Observatory's data layer: regions, community context, drought
maps, rasters and imagery. Pinned to facts the pages state, so a re-fetch that
changed them fails loudly instead of silently changing what the site says."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib import regions

api = TestClient(app)


# --- regions ---------------------------------------------------------------


def test_three_regions_from_the_2020_census():
    names = {f["properties"]["name"] for f in api.get("/api/layers/regions").json()["features"]}
    assert names == {"Pukalani", "Makawao", "Kula"}


def test_study_area_overlap_decides_who_gets_a_vegetation_series():
    """The study area is ~81% Pukalani, ~6% Makawao, 0% Kula."""
    assert 0.78 <= regions.study_area_overlap("Pukalani") <= 0.84
    assert 0.03 <= regions.study_area_overlap("Makawao") <= 0.09
    assert regions.study_area_overlap("Kula") == 0.0
    assert regions.vegetation_coverage("Pukalani")["available"] is True
    assert regions.vegetation_coverage("Makawao")["available"] is False
    assert regions.vegetation_coverage("Kula")["available"] is False


def test_unavailable_regions_explain_why_instead_of_borrowing_data():
    kula = api.get("/api/layers/insights/kula").json()
    assert kula["vegetation"]["available"] is False
    assert "region_timeseries.js" in kula["vegetation"]["reason"]
    assert "ndvi" not in kula["vegetation"]        # no Pukalani series slipped in


def test_dry_season_means_use_may_to_september_and_count_months():
    series = (("2019-04-01", 9.0), ("2019-05-01", 1.0), ("2019-09-01", 3.0), ("2019-10-01", 9.0))
    assert regions.dry_season_means(series) == {"2019": {"mean": 2.0, "months": 2}}


def test_pukalani_dry_season_ndvi_fell_from_2019_to_2022():
    dry = api.get("/api/layers/insights/pukalani").json()["vegetation"]["dry_season_ndvi"]
    assert dry["2019"]["months"] == dry["2022"]["months"] == 5
    assert round(dry["2019"]["mean"], 3) == 0.405
    assert round(dry["2022"]["mean"], 3) == 0.327


def test_drought_is_labelled_county_wide_for_every_region():
    for key in ("pukalani", "makawao", "kula"):
        assert "County" in api.get(f"/api/layers/insights/{key}").json()["drought"]["scope"]


def test_two_regions_contain_2023_burns():
    """Olinda burned inside Makawao, Kula inside Kula; Pukalani is ~0.6 km away."""
    get = lambda k: api.get(f"/api/layers/insights/{k}").json()["fire"]
    assert get("makawao")["overlaps_region"] and get("makawao")["nearest_fire"] == "Olinda"
    assert get("kula")["overlaps_region"] and get("kula")["nearest_fire"] == "Kula"
    puk = get("pukalani")
    assert not puk["overlaps_region"] and 0.3 < puk["distance_km"] < 1.0


def test_unknown_region_is_404():
    assert api.get("/api/layers/insights/atlantis").status_code == 404


# --- community context --------------------------------------------------------


def test_context_layers_carry_counts_and_publisher_currency():
    catalog = {c["id"]: c for c in api.get("/api/layers/context").json()}
    assert catalog["fire_stations"]["count"] == 4
    assert catalog["hospitals"]["names"] == ["Kula Hospital"]
    assert catalog["private_schools"]["currency"] == "as of November 2021"  # old, and shown as such
    assert all(c["currency"] for c in catalog.values())


def test_context_features_have_readable_names():
    for key in ("fire_stations", "ems_stations", "hospitals", "public_schools", "private_schools"):
        features = api.get(f"/api/layers/context/{key}").json()["features"]
        assert features, key
        assert all(f["properties"]["name"] != "Unnamed" for f in features), key


def test_kekaulike_high_is_in_the_public_schools_layer():
    names = {f["properties"]["name"] for f in api.get("/api/layers/context/public_schools").json()["features"]}
    assert "Kekaulike High" in names


def test_unknown_context_layer_is_404():
    assert api.get("/api/layers/context/shelters").status_code == 404   # deliberately not offered


# --- drought maps -----------------------------------------------------------------


def test_one_drought_map_per_year_near_8_august():
    index = api.get("/api/layers/drought-maps").json()
    assert [e["year"] for e in index] == list(range(2018, 2025))
    assert {e["year"]: e["week"] for e in index}[2023] == "2023-08-08"


def test_only_the_2022_early_august_map_shows_exceptional_drought():
    """True of the one map per year shown (week nearest 8 Aug) — NOT of whole years."""
    index = api.get("/api/layers/drought-maps").json()
    assert [e["year"] for e in index if 4 in e["categories"]] == [2022]


def test_d4_occurred_in_several_years_but_most_in_2022():
    """Guards against the earlier claim that 2022 was the only year with D4."""
    from lib import hazards

    weeks = {y: v["weeks"] for y, v in hazards.exceptional_drought_weeks().items()}
    assert weeks == {"2019": 4, "2020": 1, "2021": 8, "2022": 20}
    assert max(weeks, key=weeks.get) == "2022"


# --- rasters, observations, imagery --------------------------------------------


def test_change_rasters_are_served_as_geotiff():
    for name in ("dndvi", "dnbr"):
        r = api.get(f"/api/layers/raster/{name}")
        assert r.status_code == 200 and r.content[:4] == b"II+\x00"   # little-endian BigTIFF
    assert api.get("/api/layers/raster/ndwi").status_code == 404


@pytest.mark.needs_globe_cache
def test_observations_carry_dates_for_the_year_filter():
    obs = api.get("/api/layers/observations").json()
    assert obs and all("date" in o for o in obs)
    assert any(o["date"].startswith("2026") for o in obs)


def test_imagery_reports_what_is_missing_instead_of_failing():
    info = api.get("/api/layers/imagery").json()
    # Every known image is accounted for exactly once: either available or missing.
    available = {a["id"] for a in info["available"]}
    assert available | set(info["missing"]) == {
        "s2_dry_2019", "s2_dry_2022", "s2_dry_2019_cir", "s2_dry_2022_cir", "before_2023", "after_2023"}
    assert not available & set(info["missing"])
    assert "sentinel2_composites.py" in info["how"]
    for key in info["missing"]:
        assert api.get(f"/api/layers/imagery/{key}").status_code == 503
    for a in info["available"]:
        r = api.get(f"/api/layers/imagery/{a['id']}")
        assert r.status_code == 200 and r.headers["content-type"] == {"jpg": "image/jpeg", "tif": "image/tiff"}[a["format"]]
    assert api.get("/api/layers/imagery/nope").status_code == 404


def test_remote_sensing_products_report_provenance():
    info = api.get("/api/layers/remote-sensing").json()
    assert set(info["rasters"]) >= {"dndvi", "s2_aoi_annual", "lidar_aoi", "worldcover_2021"}
    if info["sentinel2"]:
        assert info["sentinel2"]["max_tile_cloud"] == 60
        v = info["sentinel2"]["validation_vs_study_dndvi"]
        assert v["pixels"] > 60000 and v["share_below_-0.10_study"] == 0.4274
    if info["lidar"]:
        assert info["lidar"]["acquired_utc"][0].startswith("202")
    if info["worldcover"]:
        rows = info["worldcover"]["study_area"]
        assert abs(sum(r["share_of_study_area"] for r in rows) - 1) < 0.01
