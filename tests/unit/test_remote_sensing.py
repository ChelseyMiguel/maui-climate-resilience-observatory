"""Pure helpers of the remote-sensing pipelines (scripts/remote_sensing/).
Skipped where the optional data stack (requirements-data.txt) isn't installed."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("laspy")

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "remote_sensing" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s2 = _load("sentinel2_composites")
lidar = _load("lidar_canopy")


def _item(when, pb, applied):
    return {"properties": {"datetime": when, "s2:processing_baseline": pb, "earthsearch:boa_offset_applied": applied}}


def test_reprocessed_scenes_count_once_keeping_the_latest_baseline():
    items = [_item("2021-06-04T21:10:00Z", "03.00", False), _item("2021-06-04T21:10:00Z", "05.00", True),
             _item("2021-06-14T21:10:00Z", "03.00", False)]
    kept = s2.latest_per_acquisition(items)
    assert [i["properties"]["s2:processing_baseline"] for i in kept] == ["05.00", "03.00"]


def test_offset_is_not_applied_twice():
    asset = {"raster:bands": [{"scale": 0.0001, "offset": -0.1}]}
    assert s2.reflectance_offset(_item("2022-07-09T00:00:00Z", "04.00", True), asset) == 0.0
    assert s2.reflectance_offset(_item("2022-07-09T00:00:00Z", "04.00", False), asset) == -0.1


def test_scene_dates_and_normalised_difference():
    assert s2._date("S2A_4QGJ_20190705_0_L2A") == "2019-07-05"
    nd = s2.nd(np.array([0.3, 0.0], dtype="float32"), np.array([0.1, 0.0], dtype="float32"))
    assert nd[0] == pytest.approx(0.5) and np.isnan(nd[1])


def test_hillshade_is_lit_from_the_north_west():
    y, x = np.mgrid[0:20, 0:20].astype(float)
    assert lidar.hillshade(x + y, 1.0).mean() > 200      # rises to the SE: faces NW, lit
    assert lidar.hillshade(-(x + y), 1.0).mean() < 10    # faces SE: in shadow
    assert lidar.hillshade(np.zeros((4, 4)), 1.0).mean() == pytest.approx(180, abs=1)  # sin 45 deg


def test_dtm_fill_records_which_pass_filled_each_cell():
    a = np.array([[1, np.nan, 3], [np.nan, np.nan, np.nan], [7, 8, 9.0]])
    filled, when = lidar.fill(a, 3)
    assert not np.isnan(filled).any()
    assert when[0, 0] == 0 and when[0, 1] == 1 and when[1, 1] == 1
    assert filled[0, 1] == pytest.approx(2.0)


def test_committed_products_agree_with_the_study():
    import json
    m = json.loads((ROOT / "data" / "research" / "s2_manifest.json").read_text())
    v = m["validation_vs_study_dndvi"]
    assert v["pixels"] == 70280 and v["share_below_-0.10_study"] == 0.4274
    assert v["pearson_r"] > 0.8 and abs(v["mean_difference"]) < 0.02


def test_landsat_baseline_from_the_planetary_computer():
    from lib import landsat_baseline
    s = landsat_baseline.summary()
    assert s["available"] and s["years_with_data"] == 26
    assert s["normal"]["years"] == [2000, 2018] and s["normal"]["n"] == 19
    y2022 = next(r for r in s["rows"] if r["year"] == 2022)
    assert y2022["rank_lowest"] == 1 and y2022["z"] < -1.5
    # Lower than every OLI-era (Landsat 8+) year before it, so not a sensor artefact.
    assert all(r["ndvi"] > y2022["ndvi"] for r in s["rows"] if 2014 <= r["year"] <= 2021)


def test_landsat_scene_failures_are_recorded_not_filled():
    import json
    m = json.loads((ROOT / "data" / "research" / "landsat_manifest.json").read_text())
    assert m["masked_qa_bits"] == [1, 3, 4]
    assert all(s not in m["years"][y] for y, skipped in m.get("unreadable", {}).items() for s in skipped)


burn = _load("burn_severity")


def test_burn_severity_classes_follow_firemon():
    v = np.array([0.05, 0.1, 0.3, 0.5, 0.7, np.nan])
    assert burn.severity_class(v).tolist() == [0, 1, 2, 3, 4, -1]


def test_burned_area_matches_official_perimeters():
    import json
    d = json.loads((ROOT / "data" / "research" / "burn_severity_2023.json").read_text())
    acres = {"Pulehu": 3238, "Olinda": 1083, "Kula": 207}          # NIFC, as on the 3D view
    for f in d["fires"]:
        assert abs(f["area_ha"] - acres[f["name"]] * 0.404686) / (acres[f["name"]] * 0.404686) < 0.02
    assert 0 < d["unburned_offset"] < 0.1                            # seasonal drying, removed


def test_2022_was_the_hottest_dry_season_since_2013():
    import csv
    rows = list(csv.DictReader((ROOT / "data" / "research" / "landsat_lst_dryseason.csv").open()))
    hottest = max(rows, key=lambda r: float(r["lst_c_median"]))
    assert hottest["year"] == "2022" and len(rows) == 13


island = _load("island_annual")


def test_island_codes_round_trip_within_half_a_step():
    v = np.array([-1.0, -0.1, 0.0, 0.47, 0.8, 1.0, np.nan], dtype="float32")
    c = island.encode(v)
    assert c[-1] == 255 and c.max() <= 255 and c[:-1].max() <= 250
    back = c[:-1] / 125 - 1
    assert np.all(np.abs(back - v[:-1]) <= 0.004 + 1e-6)


def test_island_products_cover_maui():
    import json
    p = ROOT / "data" / "research" / "island_annual.json"
    if not p.exists():
        pytest.skip("island_annual.py not run")
    d = json.loads(p.read_text())
    assert abs(d["land_pixels"] * 0.0036 - 1883) / 1883 < 0.05      # Maui is 1,883 km2; 60 m pixel = 0.0036 km2
    assert d["years"]["2022"]["ndvi"]["median"] < d["years"]["2019"]["ndvi"]["median"]


def test_statements_on_the_analysis_page_match_the_state_data_overlays():
    """The chart notes quote these numbers; fail loudly if the data stops supporting them."""
    import json
    d = json.loads((ROOT / "data" / "research" / "portal_overlays.json").read_text())
    zones = {z["zone"]: z for z in d["moisture_zones"]}
    assert max(zones, key=lambda k: zones[k]["share_browned"]) == "Moderately Dry"          # browned most
    assert d["study_area"]["moisture_zone_share"]["Moderately Dry"] > 0.7                      # "73 %"
    within = {z["zone"]: z for z in d["plantation_within_moisture_zone"]}
    for zone in ("Arid", "Very Dry", "Moderately Dry"):                                       # driest three
        assert within[zone]["plantation"]["share_browned"] > within[zone]["other"]["share_browned"]
    assert within["Seasonal Mesic"]["plantation"]["share_browned"] < within["Seasonal Mesic"]["other"]["share_browned"]
    assert 0.7 < d["study_area"]["former_plantation_share"] < 0.8                              # "76 %"
    r = d["fire_risk_rating"]
    assert r["High"]["share_browned"] < 0.1 and r["Medium"]["share_browned"] > 0.6
    fires = {f["fire"]: f["share_by_rating"] for f in d["fires_2023_by_rating"]}
    assert fires["Pulehu"]["Not rated"] > 0.95 and fires["Lahaina"]["High"] > 0.6


def test_state_drought_record_since_2000():
    from lib import statedrought
    s = statedrought.summary()
    assert s["available"] and s["first"] == "2000-01-04"
    assert s["maui_d4_weeks"][2022] == 20 and max(s["maui_d4_weeks"].values()) == 20
    assert sorted(s["maui_d4_weeks"].values())[-2] == 9                                        # 2010 is next
    assert s["maui_rank_by_annual_dsci"][2022] == 3                                            # 2010 and 2025 were higher
    assert {"hawaii", "honolulu", "kauai", "maui"} <= set(s["annual"][0])


def test_portal_layers_are_complete_and_dated():
    import json
    cat = {c["id"]: c for c in json.loads((ROOT / "data" / "context" / "hawaii_portal.json").read_text())}
    assert set(cat) >= {"fire_risk", "fire_response", "moisture_zones", "rainfall_mm", "rain_gauges", "sugarcane_1937", "pineapple_1937"}
    assert all(c["count"] > 0 and c["source"].startswith("https://geodata.hawaii.gov/") and c["publisher"] for c in cat.values())
    desc = cat["fire_risk"]["description"]
    assert "2007" in desc and "12/18/17" in desc and "10/31/22" in desc          # rated 2007, reconfirmed 2017 and 2022
