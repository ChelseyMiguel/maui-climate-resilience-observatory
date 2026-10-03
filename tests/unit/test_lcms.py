"""Tests for the LCMS county-context layer.

Values are asserted against the LCMS Dashboard PDF reports for Maui County
(v2024-10) so a re-parse cannot silently change the numbers quoted in the demo.
"""

from __future__ import annotations

from lib.vegetation import lcms


def test_all_three_sections_parsed_for_all_years():
    data = lcms.load()
    assert set(data) == {"Vegetation Change", "Land Cover", "Land Use"}
    years = {y for rows in data.values() for r in rows.values() for y in r}
    assert years == {"2018", "2022", "2023", "2024"}


def test_drought_stress_nearly_doubles_by_2022():
    """The fuel-loading signal, in the year before the fires."""
    rows = lcms.load()["Vegetation Change"]["Insect, Disease, or Drought Stress"]
    assert rows["2018"]["acres"] == 20716
    assert rows["2022"]["acres"] == 39709
    assert rows["2024"]["acres"] == 49986


def test_wildfire_class_appears_in_2023():
    rows = lcms.load()["Vegetation Change"]["Wildfire"]
    assert rows["2018"]["acres"] == 0
    assert rows["2023"]["acres"] == 91


def test_agriculture_declines_as_rangeland_grows():
    """Former plantation land going fallow — the documented fire-risk driver."""
    use = lcms.load()["Land Use"]
    assert use["Agriculture"]["2018"]["acres"] == 22980
    assert use["Agriculture"]["2024"]["acres"] == 9102
    assert use["Rangeland or Pasture"]["2024"]["acres"] > use["Rangeland or Pasture"]["2018"]["acres"]


def test_summary_reports_change_against_baseline():
    highlights = {h["class_name"]: h for h in lcms.summary()["highlights"]}
    drought = highlights["Insect, Disease, or Drought Stress"]
    assert drought["baseline_year"] == "2018"
    assert drought["latest_year"] == "2024"
    assert round(drought["change_pct_vs_baseline"]) == 141
    assert highlights["Agriculture"]["change_pct_vs_baseline"] < 0


def test_zero_baseline_gives_no_percentage():
    """Wildfire starts at 0 acres — a percent change from zero is meaningless."""
    highlights = {h["class_name"]: h for h in lcms.summary()["highlights"]}
    wildfire = highlights["Wildfire"]
    assert wildfire["change_pct_vs_baseline"] is None
    assert wildfire["change_acres_vs_baseline"] == 71


def test_summary_flags_itself_as_county_wide():
    """The UI must not present these as a per-site measurement."""
    assert lcms.summary()["county_wide"] is True
