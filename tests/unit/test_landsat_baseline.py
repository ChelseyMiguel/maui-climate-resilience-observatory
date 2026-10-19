"""25-year Landsat dry-season baseline (lib/landsat_baseline.py), on synthetic CSVs."""

from __future__ import annotations

import pytest

from lib import landsat_baseline as lb

HEADER = "year,ndvi_dry_median,n_scenes,sensors\n"


def _csv(tmp_path, rows):
    path = tmp_path / "ls.csv"
    path.write_text(HEADER + "".join(rows))
    return path


def _normal_years(value_of):
    return [f"{y},{value_of(y)},8,LANDSAT_7\n" for y in range(2000, 2019)]


def test_missing_file_is_unavailable(tmp_path):
    assert lb.summary(tmp_path / "nope.csv") == {"available": False}


def test_bad_columns_are_refused(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("year,ndvi\n2000,0.5\n")
    with pytest.raises(ValueError, match="ndvi_dry_median"):
        lb.load(p)


def test_a_low_year_gets_a_negative_z_and_rank_one(tmp_path):
    rows = _normal_years(lambda y: 0.50 + (0.02 if y % 2 else -0.02))
    rows += ["2022,0.30,6,LANDSAT_8+LANDSAT_9\n", "2023,0.52,7,LANDSAT_8+LANDSAT_9\n"]
    s = lb.summary(_csv(tmp_path, rows))
    by = {r["year"]: r for r in s["rows"]}
    assert s["normal"]["n"] == 19 and s["normal"]["mean"] == pytest.approx(0.499, abs=0.002)
    assert by[2022]["rank_lowest"] == 1 and by[2022]["z"] < -5
    assert by[2023]["z"] > 0


def test_study_years_are_not_part_of_the_normal(tmp_path):
    rows = _normal_years(lambda y: 0.5 + (y % 3) * 0.01) + ["2022,0.1,6,LANDSAT_8\n"]
    with_low = lb.summary(_csv(tmp_path, rows))["normal"]
    without = lb.summary(_csv(tmp_path, _normal_years(lambda y: 0.5 + (y % 3) * 0.01)))["normal"]
    assert with_low == without


def test_missing_years_and_few_scenes_are_flagged_not_dropped(tmp_path):
    rows = _normal_years(lambda y: 0.5 + (y % 4) * 0.01) + ["2012,-9999,0,\n", "2021,0.45,2,LANDSAT_8\n"]
    by = {r["year"]: r for r in lb.summary(_csv(tmp_path, rows))["rows"]}
    assert by[2012]["ndvi"] is None and by[2012]["z"] is None
    assert by[2021]["few_scenes"] is True


def test_too_little_normal_data_is_unavailable(tmp_path):
    s = lb.summary(_csv(tmp_path, ["2000,0.5,5,L7\n", "2001,0.5,5,L7\n", "2022,0.3,5,L8\n"]))
    assert s["available"] is False


def test_endpoint_reports_missing_as_data_not_an_error(tmp_path, monkeypatch):
    """No CSV yet is a normal state: 200 with available=False and how to make it,
    so the Insights page never logs a failed request."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(lb, "PATH", tmp_path / "nope.csv")
    r = TestClient(app).get("/api/layers/ndvi-baseline")
    assert r.status_code == 200
    assert r.json()["available"] is False and "gee_exports.ipynb" in r.json()["how"]
