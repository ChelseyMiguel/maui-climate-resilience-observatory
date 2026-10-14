"""Tests for the vegetation-health context layer.

Ray casting and CSV handling are tested against synthetic shapes; the spatial
join is then checked against the real Pukalani analysis outputs shipped in
`data/research/`, since those numbers are quoted in the manuscript and should
not drift silently.
"""

from __future__ import annotations

import pytest

from lib.vegetation import browning

# --- ray casting -----------------------------------------------------------

SQUARE = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]


def test_point_in_ring_inside_and_outside():
    assert browning._point_in_ring(0.5, 0.5, SQUARE)
    assert not browning._point_in_ring(1.5, 0.5, SQUARE)
    assert not browning._point_in_ring(-0.5, 0.5, SQUARE)
    assert not browning._point_in_ring(0.5, 1.5, SQUARE)


def test_point_in_ring_handles_concave_shape():
    """A U shape: the notch between the arms must read as outside."""
    u = [(0, 0), (0, 3), (1, 3), (1, 1), (2, 1), (2, 3), (3, 3), (3, 0)]
    assert browning._point_in_ring(0.5, 2.0, u)  # left arm
    assert browning._point_in_ring(2.5, 2.0, u)  # right arm
    assert not browning._point_in_ring(1.5, 2.0, u)  # the notch


# --- geometry normalization ------------------------------------------------

BIG = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
HOLE = [(4.0, 4.0), (4.0, 6.0), (6.0, 6.0), (6.0, 4.0)]


def test_polygons_of_polygon_and_multipolygon():
    poly = {"type": "Polygon", "coordinates": [SQUARE]}
    multi = {"type": "MultiPolygon", "coordinates": [[SQUARE], [SQUARE]]}
    assert len(browning._polygons_of(poly)) == 1
    assert len(browning._polygons_of(multi)) == 2
    assert browning._polygons_of({"type": "Point", "coordinates": [0, 0]}) == []


def test_first_ring_is_outer_and_the_rest_are_holes():
    (polygon,) = browning._polygons_of({"type": "Polygon", "coordinates": [BIG, HOLE]})
    assert polygon.outer == [(float(x), float(y)) for x, y in BIG]
    assert len(polygon.holes) == 1


def test_point_in_a_hole_is_not_inside_the_polygon():
    """The bug this guards: holes were once treated as extra outer rings.

    50 of the 879 real patches have holes (the 130.7 ha dominant patch has 256),
    each an unbrowned island. A site standing in one must not read as browned.
    """
    (polygon,) = browning._polygons_of({"type": "Polygon", "coordinates": [BIG, HOLE]})
    assert polygon.contains(2.0, 2.0)  # solid ground
    assert not polygon.contains(5.0, 5.0)  # inside the hole
    assert not polygon.contains(11.0, 5.0)  # outside entirely


def test_multipolygon_holes_stay_attached_to_their_own_polygon():
    """A hole in the first polygon must not carve into the second one."""
    far = [(20.0, 0.0), (20.0, 10.0), (30.0, 10.0), (30.0, 0.0)]
    polygons = browning._polygons_of(
        {"type": "MultiPolygon", "coordinates": [[BIG, HOLE], [far]]}
    )
    patch = browning.BrowningPatch(
        patch_id="t", area_ha=1.0, polygons=polygons,
        min_lon=0, min_lat=0, max_lon=30, max_lat=10,
    )
    assert patch.contains(lat=5.0, lon=25.0)  # inside the second polygon
    assert not patch.contains(lat=5.0, lon=5.0)  # in the first polygon's hole


def test_real_patches_with_holes_load_with_their_holes():
    patches = browning.load_patches()
    with_holes = [p for p in patches if any(poly.holes for poly in p.polygons)]
    assert len(with_holes) == 50
    biggest = max(patches, key=lambda p: p.area_ha)
    assert sum(len(poly.holes) for poly in biggest.polygons) == 256


def test_known_hole_in_the_real_data_reads_as_not_browned():
    """Pick a real hole centre from the data and check it is excluded."""
    for patch in browning.load_patches():
        for polygon in patch.polygons:
            for hole in polygon.holes:
                xs = [x for x, _ in hole]
                ys = [y for _, y in hole]
                lon, lat = sum(xs) / len(xs), sum(ys) / len(ys)
                # The centroid of a hole can sit outside a concave hole, so only
                # assert on one that genuinely contains its own centroid.
                if browning._point_in_ring(lon, lat, hole):
                    assert not patch.contains(lat, lon)
                    return
    raise AssertionError("no usable hole found in the real data")


# --- real analysis outputs -------------------------------------------------


def test_patches_match_the_published_analysis():
    """879 patches / 298.6 ha / 130.7 ha dominant — the manuscript's figures."""
    patches = browning.load_patches()
    assert len(patches) == 879
    assert round(sum(p.area_ha for p in patches), 1) == 298.6
    assert round(max(p.area_ha for p in patches), 1) == 130.7


@pytest.mark.needs_globe_cache
def test_eleven_of_thirty_one_pukalani_observations_are_in_a_browned_patch():
    """The headline count. It was 13 before holes were respected."""
    from lib.globe_api import client

    sites = client.fetch_near(
        20.838, -156.344, radius_km=15,
        start="2017-01-01", end="2026-12-31", bbox=client.HAWAII,
    )
    inside = [
        s for s in sites
        if browning.context_for_point(s.latitude, s.longitude)["inside_browning_patch"]
    ]
    assert len(sites) == 31
    assert len(inside) == 11


def test_sees2026_cluster_is_inside_a_browned_patch():
    """The Pukalani re-shoot target sits on ground the analysis flagged."""
    ctx = browning.context_for_point(20.8380, -156.3440)
    assert ctx["available"] and ctx["in_analysis_area"]
    assert ctx["inside_browning_patch"] is True
    assert ctx["patch_area_ha"] > 0
    assert ctx["distance_to_browning_km"] == 0.0


def test_point_far_outside_reports_not_in_analysis_area():
    ctx = browning.context_for_point(21.3069, -157.8583)  # Honolulu
    assert ctx["available"]
    assert ctx["in_analysis_area"] is False
    # "Not measured" must be distinguishable from "measured, not browned".
    assert ctx["inside_browning_patch"] is None


def test_outside_patch_reports_distance_to_nearest():
    """Somewhere in the AOI but off a patch still gets useful context."""
    ctx = browning.context_for_point(20.8507, -156.3168)
    assert ctx["inside_browning_patch"] is False
    assert ctx["distance_to_browning_km"] > 0
    assert ctx["nearest_patch_area_ha"] > 0


# --- monthly series --------------------------------------------------------


def test_series_drop_the_no_imagery_sentinel():
    ndvi = browning.ndvi_series()
    assert len(ndvi) == 61  # 72 rows, 11 months with no usable imagery
    assert all(v != -9999 for _, v in ndvi)
    assert all(0 < v < 1 for _, v in ndvi)


def test_ndvi_minimum_is_the_2022_drought():
    """The trough should land in Aug 2022, a year before the Aug 2023 fires."""
    ndvi = browning.ndvi_series()
    trough_date, _ = min(ndvi, key=lambda pair: pair[1])
    assert trough_date.startswith("2022-08")


def test_nbr_series_loads_alongside_ndvi():
    assert len(browning.nbr_series()) == len(browning.ndvi_series())


# --- GPS accuracy, edge distance, and the 100 m footprint ------------------


def test_point_to_segment_distance_in_metres():
    # A segment along the equator-ish line; a point ~111 m north of its middle.
    d = browning._point_to_segment_m(
        20.001, 0.0, (-0.001, 20.0), (0.001, 20.0)
    )
    assert 105 < d < 118


def test_point_to_segment_clamps_to_the_endpoint():
    """Past the end of the segment, distance is to the endpoint, not the line."""
    d = browning._point_to_segment_m(20.0, 0.01, (-0.001, 20.0), (0.001, 20.0))
    assert d > 900  # ~0.009 deg of longitude, nowhere near the line's own distance (0)


def test_edge_distance_inside_counts_hole_edges():
    """Just beside the hole, the nearest thing to leave is the hole, not the outer edge."""
    (polygon,) = browning._polygons_of({"type": "Polygon", "coordinates": [BIG, HOLE]})
    patch = browning.BrowningPatch(
        patch_id="t", area_ha=1.0, polygons=[polygon],
        min_lon=0, min_lat=0, max_lon=10, max_lat=10,
    )
    # 0.1 degrees (~11 km) from the hole's west edge, but 3.9 degrees from the
    # outer boundary: only counting the hole's edge gives the small number.
    beside_hole = patch.edge_distance_m(lat=5.0, lon=3.9)
    assert 9_000 < beside_hole < 12_500
    # 0.5 degrees (~55 km) from the outer edge and 3.5 from the hole: now the
    # outer boundary is the nearest thing to leave.
    beside_outer = patch.edge_distance_m(lat=5.0, lon=0.5)
    assert 50_000 < beside_outer < 60_000


def test_confidence_is_floored_at_one_raster_pixel():
    """A 3 m fix next to a 5 m edge is NOT confident: the edge is only good to ~10 m."""
    assert browning._confidence(3.0, 5.2) == "uncertain"
    assert browning._confidence(10.0, 37.4) == "confident"
    assert browning._confidence(212.0, 14.6) == "uncertain"
    assert browning._confidence(None, 100.0) == "unknown"


@pytest.mark.needs_globe_cache
def test_most_inside_observations_cannot_be_trusted_on_gps_alone():
    """The finding that retired the point-in-patch headline.

    11 observations read as 'inside' a patch, but only 1 has a GPS error small
    enough to say so — the sites sit 5-40 m from edges of fragmented patches.
    """
    from collections import Counter

    from lib.globe_api import client

    sites = client.fetch_near(
        20.838, -156.344, radius_km=15,
        start="2017-01-01", end="2026-12-31", bbox=client.HAWAII,
    )
    tally = Counter()
    for s in sites:
        ctx = browning.context_for_point(s.latitude, s.longitude, s.location_accuracy_m)
        if ctx["inside_browning_patch"]:
            tally[ctx["location_confidence"]] += 1
    assert dict(tally) == {"uncertain": 9, "confident": 1, "unknown": 1}


def test_footprint_fraction_is_none_outside_the_study_area():
    assert browning.site_browned_fraction(21.3069, -157.8583) is None  # Honolulu


def test_footprint_fraction_inside_the_sees2026_cluster():
    fraction = browning.site_browned_fraction(20.8380, -156.3440)
    assert 0.4 <= fraction <= 0.7


def test_footprint_fraction_is_zero_away_from_any_browning():
    """The CAP sites ~1.7 km east of the cluster have no browned pixels at all."""
    assert browning.site_browned_fraction(20.85070, -156.31680) == 0.0


@pytest.mark.needs_globe_cache
def test_footprint_headline_across_pukalani_observations():
    """16 of 19 in-area observations have >=25% of their footprint browned."""
    import statistics

    from lib.globe_api import client

    sites = client.fetch_near(
        20.838, -156.344, radius_km=15,
        start="2017-01-01", end="2026-12-31", bbox=client.HAWAII,
    )
    fractions = [
        f for s in sites
        if (f := browning.site_browned_fraction(s.latitude, s.longitude)) is not None
    ]
    assert len(fractions) == 19
    assert sum(f >= 0.25 for f in fractions) == 16
    assert sum(f == 0 for f in fractions) == 2
    assert round(statistics.median(fractions), 2) == 0.63


def test_fraction_range_brackets_the_centre_value_and_needs_accuracy():
    centre = browning.site_browned_fraction(20.8380, -156.3440)
    low, high = browning.fraction_range(20.8380, -156.3440, 58.0)
    assert low <= centre <= high
    assert browning.fraction_range(20.8380, -156.3440, None) is None


def test_zero_gps_error_gives_a_zero_width_range():
    low, high = browning.fraction_range(20.8380, -156.3440, 0.0)
    assert low == high


def test_aoi_baseline_matches_the_manuscript():
    """A site's fraction only means something read against this."""
    assert browning.AOI_BROWNED_FRACTION == 0.427


# --- spatial-index shortcuts must not change any answer ---------------------


def _brute_force_contains(polygon, lon, lat):
    """The original definition, with no bounding-box shortcuts."""
    if not browning._point_in_ring(lon, lat, polygon.outer):
        return False
    return not any(browning._point_in_ring(lon, lat, hole) for hole in polygon.holes)


def _sample_points(n=300, seed=7):
    import random

    index = browning._index()
    rng = random.Random(seed)
    return [
        (
            rng.uniform(index["min_lat"], index["max_lat"]),
            rng.uniform(index["min_lon"], index["max_lon"]),
        )
        for _ in range(n)
    ]


def test_bounding_box_shortcut_agrees_with_brute_force_on_real_patches():
    patches = browning.load_patches()
    assert patches, "browning patches missing from data/research"
    holey = [pg for p in patches for pg in p.polygons if pg.holes]
    assert holey, "expected real patches with holes"
    checked = 0
    for lat, lon in _sample_points():
        for polygon in holey[:40]:
            assert polygon.contains(lon, lat) == _brute_force_contains(polygon, lon, lat)
            checked += 1
    # Points inside the dominant patch's holes are the case the shortcut could break.
    big = max((pg for p in patches for pg in p.polygons), key=lambda pg: len(pg.holes))
    for hole in big.holes[:50]:
        lon = sum(x for x, _ in hole) / len(hole)
        lat = sum(y for _, y in hole) / len(hole)
        assert big.contains(lon, lat) == _brute_force_contains(big, lon, lat)
    assert checked > 1000


def test_nearest_patch_matches_exhaustive_search():
    patches = browning.load_patches()
    for lat, lon in _sample_points(n=40, seed=11):
        expected = min(patches, key=lambda p: p.distance_km(lat, lon))
        assert browning.nearest_patch(lat, lon) is expected


def test_nearest_patch_is_none_without_patches(monkeypatch):
    monkeypatch.setattr(browning, "load_patches", lambda: ())
    assert browning.nearest_patch(20.8, -156.3) is None
