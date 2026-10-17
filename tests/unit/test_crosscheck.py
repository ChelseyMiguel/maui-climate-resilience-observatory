"""GLOBE citizen labels vs. LCMS land cover at the same site (lib/crosscheck.py).

All inputs here are synthetic and only exercise the logic; they say nothing about
how well the real labels agree. That needs the real LCMS sample CSV
(scripts/gee/lcms_site_sample.js) and the GLOBE cache.
"""

from __future__ import annotations

import pytest

from lib import crosscheck
from lib.globe_api import client

# --- GLOBE label -> coarse classes ------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Herbaceous/Grassland, Short Grass", {"grass"}),
        ("Shrubs, Loosely Spaced", {"shrub"}),
        ("Cultivated, Crops or Pastures", {"grass"}),
        ("Urban, Roads and Parking", {"built_barren"}),
        ("Closed Forest, Evergreen", {"tree"}),
        ("Wooded Grassland, Medium Tall", {"tree", "grass"}),
        ("Water, Fresh", {"water"}),
    ],
)
def test_globe_labels_map_to_coarse_classes(label, expected):
    assert crosscheck.globe_classes(label) == frozenset(expected)


@pytest.mark.parametrize("label", [None, "", "Something Entirely New"])
def test_unknown_globe_labels_are_unmapped_not_guessed(label):
    assert crosscheck.globe_classes(label) is None


# --- LCMS Land_Cover name -> coarse classes ---------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Trees", {"tree"}),
        ("Shrubs", {"shrub"}),
        ("Grass/Forb/Herb", {"grass"}),
        ("Shrubs & Trees Mix", {"shrub", "tree"}),
        ("Grass/Forb/Herb & Shrubs Mix", {"grass", "shrub"}),
        ("Barren & Grass/Forb/Herb Mix", {"built_barren", "grass"}),
        ("Barren or Impervious", {"built_barren"}),
        ("Water", {"water"}),
    ],
)
def test_lcms_names_map_to_coarse_classes(name, expected):
    assert crosscheck.lcms_classes(name) == frozenset(expected)


@pytest.mark.parametrize("name", [None, "", "Non-Processing Area Mask", "Snow or Ice"])
def test_lcms_names_outside_the_scheme_are_unmapped(name):
    assert crosscheck.lcms_classes(name) is None


# --- verdict ---------------------------------------------------------------


def test_verdict_agree_partial_disagree_unmapped():
    assert crosscheck.verdict("Herbaceous/Grassland, Short Grass", "Grass/Forb/Herb") == "agree"
    assert crosscheck.verdict("Herbaceous/Grassland, Short Grass", "Grass/Forb/Herb & Shrubs Mix") == "partial"
    assert crosscheck.verdict("Urban, Roads and Parking", "Trees") == "disagree"
    assert crosscheck.verdict("Mystery", "Trees") == "unmapped"
    assert crosscheck.verdict("Closed Forest", "Non-Processing Area Mask") == "unmapped"


# --- CSV -------------------------------------------------------------------


def _write(tmp_path, text):
    path = tmp_path / "lcms.csv"
    path.write_text(text)
    return path


def test_csv_with_labels_loads(tmp_path):
    path = _write(
        tmp_path,
        "site,year,Change,Change_name,Land_Cover,Land_Cover_name,Land_Use,Land_Use_name\n"
        "04QGJ764065,2022,3,Stable,9,Grass/Forb/Herb,3,Rangeland or Pasture\n",
    )
    assert crosscheck.load_lcms_csv(path) == {("04QGJ764065", 2022): "Grass/Forb/Herb"}


def test_csv_with_only_integer_codes_is_refused_with_the_fix(tmp_path):
    """The first version of the Earth Engine script exported codes, not names."""
    path = _write(tmp_path, "site,year,Change,Land_Cover,Land_Use\n04QGJ764065,2022,3,9,3\n")
    with pytest.raises(ValueError, match="Land_Cover_name") as err:
        crosscheck.load_lcms_csv(path)
    assert "lcms_site_sample.js" in str(err.value)


def test_csv_missing_columns_is_refused(tmp_path):
    with pytest.raises(ValueError, match="site"):
        crosscheck.load_lcms_csv(_write(tmp_path, "year,Land_Cover_name\n2022,Trees\n"))


# --- end to end ------------------------------------------------------------


def _obs(land_cover_id, site_name, date, label):
    props = {
        "landcoversLandCoverId": land_cover_id,
        "siteId": site_name,
        "siteName": site_name,
        "landcoversMeasuredAt": date,
        "landcoversMeasurementLatitude": "20.83",
        "landcoversMeasurementLongitude": "-156.34",
        "landcoversMucDescription": label,
    }
    return client.parse_feature({"properties": props, "geometry": {"coordinates": [-156.34, 20.83]}})


def test_crosscheck_summarises_and_never_hides_what_it_skipped():
    rows = {
        ("A", 2022): "Grass/Forb/Herb",
        ("B", 2022): "Trees",
        ("C", 2024): "Barren or Impervious",  # 2025 visit uses the latest year LCMS has
        ("E", 2022): "Non-Processing Area Mask",
    }
    observations = [
        _obs("1", "A", "2022-07-01T10:00:00", "Herbaceous/Grassland, Short Grass"),  # agree
        _obs("2", "B", "2022-07-01T10:00:00", "Shrubs, Loosely Spaced"),  # disagree
        _obs("3", "C", "2025-03-01T10:00:00", "Urban, Roads and Parking"),  # agree, year clamped
        _obs("4", "D", "2022-07-01T10:00:00", "Closed Forest"),  # site not in the CSV
        _obs("5", "E", "2022-07-01T10:00:00", "Closed Forest"),  # LCMS class outside the scheme
        _obs("6", "A", "2022-07-02T10:00:00", "Something Entirely New"),  # GLOBE label unmapped
    ]
    result = crosscheck.crosscheck(observations, rows)

    assert result["summary"] == {
        "compared": 5, "agree": 2, "partial": 0, "disagree": 1, "unmapped": 2,
        "no_lcms_row": 1,
    }
    by_id = {r["land_cover_id"]: r for r in result["rows"]}
    assert by_id["3"]["lcms_year"] == 2024 and by_id["3"]["verdict"] == "agree"
    assert by_id["4"]["verdict"] == "no_lcms_row"
    assert "30 m" in " ".join(result["notes"])


def test_undated_observation_is_reported_not_guessed():
    result = crosscheck.crosscheck([_obs("1", "A", "null", "Closed Forest")], {("A", 2022): "Trees"})
    assert result["rows"][0]["verdict"] == "no_lcms_row"


# --- other satellite maps: ESA WorldCover and Dynamic World --------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # ESA WorldCover v100/v200 class names
        ("Tree cover", {"tree"}),
        ("Shrubland", {"shrub"}),
        ("Grassland", {"grass"}),
        ("Cropland", {"grass"}),  # crops read as herbaceous, like GLOBE "Cultivated"
        ("Built-up", {"built_barren"}),
        ("Bare / sparse vegetation", {"built_barren"}),
        ("Permanent water bodies", {"water"}),
        # Dynamic World labels
        ("trees", {"tree"}),
        ("shrub_and_scrub", {"shrub"}),
        ("crops", {"grass"}),
        ("built", {"built_barren"}),
        ("bare", {"built_barren"}),
    ],
)
def test_other_map_names_share_the_same_coarse_scheme(name, expected):
    assert crosscheck.satellite_classes(name) == frozenset(expected)


@pytest.mark.parametrize(
    "name", ["Herbaceous wetland", "Mangroves", "Moss and lichen", "flooded_vegetation", "snow_and_ice"]
)
def test_classes_the_scheme_does_not_cover_stay_unmapped(name):
    assert crosscheck.satellite_classes(name) is None


def test_landcover_csv_loads_by_product(tmp_path):
    path = _write(
        tmp_path,
        "site,product,year,class_value,class_name\n"
        "A,worldcover,2021,30,Grassland\n"
        "A,dynamicworld,2022,2,grass\n",
    )
    assert crosscheck.load_landcover_csv(path) == {
        "worldcover": {("A", 2021): "Grassland"},
        "dynamicworld": {("A", 2022): "grass"},
    }


def test_landcover_csv_missing_columns_is_refused(tmp_path):
    with pytest.raises(ValueError, match="class_name"):
        crosscheck.load_landcover_csv(_write(tmp_path, "site,product,year\nA,worldcover,2021\n"))


def test_years_are_held_to_what_each_product_has():
    """WorldCover only exists for 2020 and 2021, so a 2023 visit is read against 2021."""
    obs = [_obs("1", "A", "2023-07-01T10:00:00", "Herbaceous/Grassland, Short Grass")]
    result = crosscheck.crosscheck(obs, {("A", 2020): "Tree cover", ("A", 2021): "Grassland"})
    assert result["rows"][0]["lcms_year"] == 2021
    assert result["rows"][0]["verdict"] == "agree"


def test_crosscheck_products_runs_each_map_separately():
    obs = [_obs("1", "A", "2021-07-01T10:00:00", "Herbaceous/Grassland, Short Grass")]
    table = {"worldcover": {("A", 2021): "Grassland"}, "dynamicworld": {("A", 2021): "trees"}}
    out = crosscheck.crosscheck_products(obs, table)
    assert out["worldcover"]["summary"]["agree"] == 1
    assert out["dynamicworld"]["summary"]["disagree"] == 1
