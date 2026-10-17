"""Rainfall products vs. each other and vs. greenness (lib/rainfall.py).

Synthetic CSVs only: they test the logic, not Maui's rainfall. Real figures need
data/research/pukalani_rainfall_monthly.csv from scripts/gee/rainfall_monthly.js.
"""

from __future__ import annotations

import pytest

from lib import rainfall

HEADER = "date,chirps_mm,chirps_days,terraclimate_mm,imerg_mm,era5land_mm\n"


def _csv(tmp_path, rows):
    path = tmp_path / "rain.csv"
    path.write_text(HEADER + "".join(r + "\n" for r in rows))
    return path


def test_load_drops_missing_and_part_months(tmp_path):
    path = _csv(tmp_path, [
        "2020-01-01,100,31,90,80,70",
        "2020-02-01,50,10,-9999,40,30",  # CHIRPS has 10 of 29 days: not a real total
    ])
    data = rainfall.load(path)
    assert data["chirps"] == {"2020-01": 100.0}
    assert data["terraclimate"] == {"2020-01": 90.0}
    assert data["imerg"] == {"2020-01": 80.0, "2020-02": 40.0}


def test_load_refuses_a_csv_without_the_expected_columns(tmp_path):
    path = tmp_path / "rain.csv"
    path.write_text("date,chirps_mm\n2020-01-01,5\n")
    with pytest.raises(ValueError, match="terraclimate_mm"):
        rainfall.load(path)


def test_missing_file_is_unavailable_not_an_error(tmp_path):
    assert rainfall.summary(tmp_path / "nope.csv")["available"] is False


def _months(n, f):
    out = []
    for i in range(n):
        y, m = 2019 + i // 12, i % 12 + 1
        out.append(f(i, f"{y}-{m:02d}-01"))
    return out


def test_products_that_move_together_agree(tmp_path):
    rows = _months(24, lambda i, d: f"{d},{(i % 12) * 10 + 5},31,{(i % 12) * 10 + 5},{(i % 12) * 20 + 1},{(i % 12) * 3}")
    result = rainfall.summary(_csv(tmp_path, rows))
    pairs = {(a["a"], a["b"]): a for a in result["agreement"]}
    assert pairs[("chirps", "terraclimate")]["r"] == pytest.approx(1.0)
    assert pairs[("chirps", "imerg")]["r"] == pytest.approx(1.0)
    assert len(pairs) == 6  # every pair of the four products, once


def test_lag_profile_finds_greenness_following_rain(tmp_path, monkeypatch):
    rain = [((i * 7) % 11) * 10.0 + 1 for i in range(36)]
    rows = _months(36, lambda i, d: f"{d},{rain[i]},31,{rain[i]},{rain[i]},{rain[i]}")
    # Greenness = rain two months earlier, so the lag-2 correlation is perfect.
    ndvi = tuple((f"{2019 + (i + 2) // 12}-{(i + 2) % 12 + 1:02d}-01", rain[i] / 100) for i in range(34))
    monkeypatch.setattr(rainfall.browning, "ndvi_series", lambda: ndvi)
    result = rainfall.summary(_csv(tmp_path, rows))
    lags = result["vs_ndvi"]["chirps"]
    assert [row["lag"] for row in lags] == list(range(7))
    assert lags[2]["r"] == pytest.approx(1.0)
    assert abs(lags[0]["r"]) < 0.9


def test_notes_carry_the_scale_caveat(tmp_path):
    result = rainfall.summary(_csv(tmp_path, ["2020-01-01,1,31,1,1,1"]))
    assert "pixel" in " ".join(result["notes"]).lower()
