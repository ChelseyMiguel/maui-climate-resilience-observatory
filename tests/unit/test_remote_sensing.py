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
