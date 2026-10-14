"""Drought-vs-greenness statistics (lib/relationships.py).

Maths is checked on synthetic series; the real-data tests pin the values the
shipped CSVs produce, so a changed file or method cannot move a figure on the
site unnoticed. None of them depend on the gitignored GLOBE cache.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lib import relationships
from lib.vegetation import browning

api = TestClient(app)


# --- pairing ---------------------------------------------------------------


def test_pair_months_drops_unmatched_months():
    x = {"2020-01": 1.0, "2020-02": 2.0, "2020-03": 3.0}
    y = {"2020-02": 20.0, "2020-03": 30.0, "2020-04": 40.0}
    assert relationships.pair_months(x, y) == [("2020-02", 2.0, 20.0), ("2020-03", 3.0, 30.0)]


def test_pair_months_lag_pairs_earlier_x_with_later_y():
    x = {"2020-01": 1.0, "2020-02": 2.0}
    y = {"2020-02": 20.0, "2020-03": 30.0}
    # y of Feb pairs with x of Jan; y of Mar with x of Feb; nothing before Jan.
    assert relationships.pair_months(x, y, lag=1) == [("2020-02", 1.0, 20.0), ("2020-03", 2.0, 30.0)]


def test_pair_months_lag_crosses_a_year_boundary():
    assert relationships.pair_months({"2019-12": 5.0}, {"2020-01": 9.0}, lag=1) == [("2020-01", 5.0, 9.0)]


# --- correlation -----------------------------------------------------------


def test_correlation_of_a_perfect_line():
    pairs = [(f"2020-0{i}", float(i), 2.0 * i + 1) for i in range(1, 6)]
    fit = relationships.correlation(pairs)
    assert fit["n"] == 5
    assert fit["r"] == pytest.approx(1.0)
    assert fit["slope"] == pytest.approx(2.0)
    assert fit["intercept"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "pairs",
    [
        [],
        [("2020-01", 1.0, 1.0), ("2020-02", 2.0, 2.0)],  # too few
        [(f"2020-0{i}", float(i), 7.0) for i in range(1, 6)],  # y never varies
        [(f"2020-0{i}", 3.0, float(i)) for i in range(1, 6)],  # x never varies
    ],
)
def test_correlation_that_cannot_be_computed_is_none_not_nan(pairs):
    fit = relationships.correlation(pairs)
    assert fit["r"] is None and fit["slope"] is None and fit["intercept"] is None
    assert fit["n"] == len(pairs)


# --- DSCI by month ---------------------------------------------------------


def test_monthly_dsci_is_the_mean_of_that_months_weeks(monkeypatch):
    weeks = (("2020-01-07", 100), ("2020-01-14", 200), ("2020-02-04", 50))
    monkeypatch.setattr(relationships.hazards, "drought_series", lambda: weeks)
    assert relationships.monthly_dsci() == {"2020-01": 150.0, "2020-02": 50.0}


# --- the real, shipped series ----------------------------------------------


@pytest.fixture(scope="module")
def result():
    return relationships.drought_greenness()


def test_real_data_is_available(result):
    assert result["available"] is True
    assert set(result["indices"]) == {"ndvi", "nbr"}


def test_ndvi_scatter_uses_every_month_with_imagery(result):
    ndvi = result["indices"]["ndvi"]
    assert len(ndvi["points"]) == ndvi["fit"]["n"] == len(browning.ndvi_series()) == 61
    first = ndvi["points"][0]
    assert set(first) == {"month", "year", "dsci", "value"}
    assert first["month"] == "2018-12" and first["year"] == 2018


def test_pinned_same_month_correlations(result):
    assert result["indices"]["ndvi"]["fit"]["r"] == pytest.approx(-0.690, abs=0.002)
    assert result["indices"]["nbr"]["fit"]["r"] == pytest.approx(-0.767, abs=0.002)


def test_lag_profile_covers_zero_to_six_and_fades(result):
    lags = result["indices"]["ndvi"]["lags"]
    assert [row["lag"] for row in lags] == list(range(7))
    assert lags[0]["r"] == pytest.approx(-0.690, abs=0.002)
    assert abs(lags[3]["r"]) < 0.05  # the same-month link is gone by three months


def test_dry_season_2022_is_the_driest_and_least_green(result):
    rows = {row["year"]: row for row in result["dry_season"]}
    assert set(rows) == {2019, 2020, 2021, 2022, 2023}
    assert max(rows, key=lambda y: rows[y]["dsci"]) == 2022
    assert min(rows, key=lambda y: rows[y]["ndvi"]) == 2022
    assert all(1 <= row["months"] <= 5 for row in rows.values())


def test_caveats_travel_with_the_numbers(result):
    text = " ".join(result["notes"]).lower()
    assert "correlation" in text and "county" in text


def test_no_series_means_unavailable_not_an_empty_chart(monkeypatch):
    monkeypatch.setattr(relationships.browning, "ndvi_series", lambda: ())
    relationships.drought_greenness.cache_clear()
    try:
        assert relationships.drought_greenness()["available"] is False
    finally:
        monkeypatch.undo()
        relationships.drought_greenness.cache_clear()


# --- endpoint --------------------------------------------------------------


def test_endpoint_serves_the_module_payload(result):
    response = api.get("/api/layers/drought-greenness")
    assert response.status_code == 200
    assert response.json() == result


def test_endpoint_is_503_with_the_fix_when_data_is_missing(monkeypatch):
    monkeypatch.setattr(relationships.browning, "ndvi_series", lambda: ())
    relationships.drought_greenness.cache_clear()
    try:
        response = api.get("/api/layers/drought-greenness")
        assert response.status_code == 503
        assert "pukalani_ndvi_monthly" in response.json()["detail"]
    finally:
        monkeypatch.undo()
        relationships.drought_greenness.cache_clear()
