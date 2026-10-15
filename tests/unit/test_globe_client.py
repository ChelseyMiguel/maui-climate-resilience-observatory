"""Unit tests for GLOBE land cover parsing.

Fixtures below are trimmed from real API responses, so they carry the quirks
that actually show up: the string "null" for empty fields, classification
strings with parenthesised MUC variants, and observations missing directions.
"""

from __future__ import annotations

import math

from lib.globe_api import client


def _feature(**overrides) -> dict:
    """A complete 6/6 observation, modelled on the real 'Rice Park Maui' record."""
    props = {
        "countryCode": "USA",
        "elevation": "925.5",
        "landcoversDataSource": "GLOBE Observer App",
        "landcoversLandCoverId": "61975",
        "landcoversMeasuredAt": "2023-10-08T23:16:00",
        "landcoversMeasurementLatitude": "20.7412",
        "landcoversMeasurementLongitude": "-156.3328",
        "landcoversMeasurementElevation": "926.4",
        "landcoversLocationAccuracyM": "11",
        "landcoversMucCode": "M43",
        "landcoversMucDescription": "Herbaceous/Grassland, Short Grass",
        "landcoversFieldNotes": "Rice Park Maui",
        "organizationName": "United States of America Citizen Science",
        "siteId": "328395",
        "siteName": "04QGH777957",
        "protocol": "land_covers",
    }
    for d in client.DIRECTIONS:
        props[f"landcovers{d}PhotoUrl"] = f"https://data.globe.gov/photos/{d}.jpg"
        props[f"landcovers{d}Classifications"] = "100% MUC 43 [Herbaceous/Grassland, Short Grass]"
        props[f"landcovers{d}Caption"] = "null"
    props.update(overrides)
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [-156.3328, 20.7412]},
    }


def test_parses_all_six_directions():
    site = client.parse_feature(_feature())
    assert site.is_complete
    assert site.missing_directions == []
    assert set(site.photo_urls()) == set(client.DIRECTIONS)
    assert site.site_name == "04QGH777957"
    assert site.measured_at.year == 2023
    assert site.elevation_m == 926.4


def test_missing_direction_is_detected():
    site = client.parse_feature(_feature(landcoversUpwardPhotoUrl="null"))
    assert not site.is_complete
    assert site.missing_directions == ["Upward"]
    assert "Upward" not in site.photo_urls()
    assert site.photos["Upward"].present is False


def test_null_strings_become_none():
    site = client.parse_feature(
        _feature(landcoversFieldNotes="(none)", landcoversMucDescription="null")
    )
    assert site.field_notes is None
    assert site.muc_description is None
    # Captions come through as the literal string "null" in the raw API payload.
    assert site.photos["North"].caption is None


def test_classification_parsing_multiple_classes():
    parsed = client.parse_classifications(
        "80% MUC 43 [Herbaceous/Grassland, Short Grass]; 20% MUC 93 [Urban, Roads and Parking]"
    )
    assert [(c.percent, c.muc_code) for c in parsed] == [(80, "43"), (20, "93")]
    assert parsed[0].label == "Herbaceous/Grassland, Short Grass"


def test_classification_parsing_handles_muc_variants():
    """Entries like 'MUC 81 (1)' and 'MUC 33 (l)' carry a parenthesised variant."""
    parsed = client.parse_classifications(
        "50% MUC 81 (1) [Cultivated, Crops or Pastures]; 10% MUC 33 (l) [Shrubs, Loosely Spaced]"
    )
    assert [(c.percent, c.muc_code) for c in parsed] == [(50, "81"), (10, "33")]
    assert parsed[1].label == "Shrubs, Loosely Spaced"


def test_classification_parsing_empty():
    assert client.parse_classifications("null") == []
    assert client.parse_classifications(None) == []


def test_falls_back_to_geometry_when_measurement_coords_missing():
    site = client.parse_feature(
        _feature(
            landcoversMeasurementLatitude="null",
            landcoversMeasurementLongitude="null",
        )
    )
    assert site.latitude == 20.7412
    assert site.longitude == -156.3328


def test_measured_at_with_microseconds():
    """Older manual site definitions carry microsecond precision."""
    site = client.parse_feature(
        _feature(landcoversMeasuredAt="2018-02-03T17:39:03.059676")
    )
    assert site.measured_at.year == 2018
    assert site.measured_at.microsecond == 59676


def test_haversine_known_distance():
    # Pukalani to Kahului is roughly 10 km.
    km = client.haversine_km(20.827, -156.336, 20.8893, -156.4729)
    assert 12 < km < 18


def test_group_by_site_sorts_oldest_first():
    early = client.parse_feature(
        _feature(landcoversMeasuredAt="2023-01-01T10:00:00", landcoversLandCoverId="1")
    )
    late = client.parse_feature(
        _feature(landcoversMeasuredAt="2025-01-01T10:00:00", landcoversLandCoverId="2")
    )
    grouped = client.group_by_site([late, early])
    assert [o.land_cover_id for o in grouped["328395"]] == ["1", "2"]


def test_hawaii_bbox_contains_maui_and_excludes_elsewhere():
    assert client.HAWAII.contains(20.827, -156.336)  # Pukalani
    assert client.HAWAII.contains(19.72, -155.06)  # Hilo
    assert not client.HAWAII.contains(7.28, 5.23)  # Nigeria
    assert not client.HAWAII.contains(-18.90, 47.54)  # Madagascar


def test_bbox_filters_features_by_measurement_coords():
    inside = _feature()  # Maui
    outside = _feature(
        landcoversMeasurementLatitude="29.3447",
        landcoversMeasurementLongitude="47.7538",  # Kuwait
    )
    assert client.HAWAII.contains_feature(inside)
    assert not client.HAWAII.contains_feature(outside)


def test_bbox_falls_back_to_geometry_then_rejects_unplaceable():
    """A feature with no usable position cannot be placed, so it is dropped."""
    geom_only = _feature(
        landcoversMeasurementLatitude="null", landcoversMeasurementLongitude="null"
    )
    assert client.HAWAII.contains_feature(geom_only)  # geometry is still Maui

    nowhere = dict(geom_only)
    nowhere["geometry"] = {"type": "Point", "coordinates": [None, None]}
    assert not client.HAWAII.contains_feature(nowhere)


def test_year_chunks_split_range_on_calendar_years():
    chunks = list(client._iter_year_chunks("2023-06-01", "2025-02-10"))
    assert chunks == [
        ("2023-06-01", "2023-12-31"),
        ("2024-01-01", "2024-12-31"),
        ("2025-01-01", "2025-02-10"),
    ]


def test_year_chunks_single_range_within_one_year():
    assert list(client._iter_year_chunks("2024-03-01", "2024-04-01")) == [
        ("2024-03-01", "2024-04-01")
    ]


def test_to_dict_is_json_safe():
    site = client.parse_feature(_feature())
    d = site.to_dict()
    assert d["is_complete"] is True
    assert d["photos"]["North"]["classifications"][0]["percent"] == 100
    assert not math.isnan(d["latitude"])


def test_non_answer_notes_are_not_used_as_labels():
    assert client.meaningful_note("No") is None
    assert client.meaningful_note("  n/a ") is None
    assert client.meaningful_note("null") is None
    assert client.meaningful_note(None) is None


def test_short_but_real_notes_are_kept():
    """Real Hawaii data has notes like these; a length cut-off would wrongly drop them."""
    for note in ("Park", "Beach", "SOH045", "Hb2", "Rice Park Maui"):
        assert client.meaningful_note(note) == note


def test_viewer_and_api_use_the_same_non_answer_list():
    """The viewer (JS) and the map API (Python) each filter notes; keep them in step."""
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "app" / "templates" / "index.html").read_text()
    js_list = re.search(r"NON_ANSWER_NOTES = new Set\(\[(.*?)\]\)", page).group(1)
    assert set(re.findall(r'"([^"]*)"', js_list)) == set(client.NON_ANSWER_NOTES)


def test_request_matches_the_documented_public_globe_api_contract(monkeypatch):
    """The request shape every working GLOBE API consumer uses.

    Cross-checked against IGES-Geospatial/globe-mosquitoes-notebook (a community
    copy of GLOBE's own Python notebook, `call()` in mosquitoes.py): same base
    path with its trailing slash, `protocols/startdate/enddate/geojson/sample`,
    uppercase TRUE/FALSE, and a bare GET with no key, token or auth header.
    See docs/globe-api-verification.md.
    """
    seen = {}

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": []}

    def fake_get(url, **kwargs):
        seen["url"], seen["kwargs"] = url, kwargs
        return Reply()

    monkeypatch.setattr(client.httpx, "get", fake_get)
    assert client._fetch_chunk("2024-01-01", "2024-12-31", 30.0) == []

    assert seen["url"] == "https://api.globe.gov/search/v1/measurement/protocol/measureddate/"
    assert seen["kwargs"]["params"] == {
        "protocols": "land_covers",
        "startdate": "2024-01-01",
        "enddate": "2024-12-31",
        "geojson": "TRUE",
        "sample": "FALSE",
    }
    # Public read API: nothing identifying or secret goes with the request.
    assert not {"headers", "auth", "cookies"} & set(seen["kwargs"])
