"""Vegetation-health context for a GLOBE site, from the Pukalani browning analysis.

This is the layer that turns the viewer from a photo browser into a research
tool: given where a citizen scientist stood, it answers "did this ground brown
between 2019 and 2022, and by how much?"

Two products of the Team Terra drought/wildfire analysis back it:

* `browning_patches.geojson` — 879 contiguous patches where dNDVI < -0.10 over
  2019→2022, totalling 298.6 ha, with one dominant 130.7 ha patch. These are the
  browned areas themselves, as polygons.
* `pukalani_{ndvi,nbr}_monthly.csv` — monthly mean NDVI and NBR across the AOI,
  Dec 2018 to Dec 2023, which brackets both the 2022 drought and the August 2023
  Upcountry fires. Missing months are stored as the sentinel -9999 (no usable
  imagery, typically cloud) and are dropped on load rather than plotted as zero.

Deliberately dependency-free: point-in-polygon is a plain ray cast and the CSVs
go through the stdlib. Reading the companion dNDVI/dNBR GeoTIFFs would pull in
rasterio/GDAL for a per-pixel value the patch polygons already summarize.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "research"
PATCHES_PATH = DATA_DIR / "browning_patches.geojson"
NDVI_PATH = DATA_DIR / "pukalani_ndvi_monthly.csv"
NBR_PATH = DATA_DIR / "pukalani_nbr_monthly.csv"

# The analysis threshold: a pixel counts as browned at dNDVI < -0.10.
BROWNING_THRESHOLD = -0.10

# A GLOBE land cover site is documented as a 100 m square, so "did this site
# brown?" is a question about that footprint, not about one GPS point.
SITE_SIZE_M = 100.0
# Spacing of the grid used to estimate the browned fraction of that footprint.
SITE_SAMPLE_STEP_M = 5.0
# The patches were vectorised from 10 m Sentinel-2 pixels, so a patch edge is
# only good to about a pixel; a location error smaller than that cannot be
# resolved against it either.
PIXEL_M = 10.0

# Share of the whole Pukalani AOI that browned (dNDVI < -0.10, 2019 to 2022), from
# the manuscript. The yardstick for a site's own browned fraction: a site at 60%
# means little if the surrounding area is 43% browned and the sites cluster in
# its worst part.
AOI_BROWNED_FRACTION = 0.427

# Margin around the patch extent that still counts as "in the analysis area".
AOI_MARGIN_DEG = 0.02

# Rows carry -9999 where no usable imagery existed for that month.
_MISSING = -9999.0


Ring = list[tuple[float, float]]


Box = tuple[float, float, float, float]  # min_x, min_y, max_x, max_y


def _ring_box(ring: Ring) -> Box:
    xs = [x for x, _ in ring]
    ys = [y for _, y in ring]
    return (min(xs), min(ys), max(xs), max(ys))


def _in_box(x: float, y: float, box: Box) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


@dataclass(frozen=True)
class Polygon:
    """One outer boundary and the holes cut out of it."""

    outer: Ring
    holes: list[Ring]
    # Bounding boxes, so a point is ray-cast against a ring only when it can
    # possibly be inside it. The dominant browning patch has 256 holes; testing
    # every one for every sample point was most of the cost of a site lookup.
    _outer_box: Box = field(init=False, repr=False, compare=False)
    _hole_boxes: list[Box] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_outer_box", _ring_box(self.outer))
        object.__setattr__(self, "_hole_boxes", [_ring_box(h) for h in self.holes])

    def contains(self, lon: float, lat: float) -> bool:
        if not _in_box(lon, lat, self._outer_box) or not _point_in_ring(lon, lat, self.outer):
            return False
        # A point in a hole is NOT in the polygon. Browning patches are full of
        # these: 50 of 879 have interior holes (the 130.7 ha dominant patch has
        # 256), each an unbrowned island, so skipping this check would report
        # ground that did not brown as browned.
        return not any(
            _in_box(lon, lat, box) and _point_in_ring(lon, lat, hole)
            for box, hole in zip(self._hole_boxes, self.holes)
        )

    def boundary_distance_m(self, lat: float, lon: float) -> float:
        """Metres to the nearest edge of this polygon, outer boundary or hole."""
        return min(
            _ring_distance_m(lat, lon, ring) for ring in (self.outer, *self.holes)
        )


@dataclass(frozen=True)
class BrowningPatch:
    """One contiguous browned area from the 2019→2022 dNDVI analysis.

    A patch is one or more polygons (the file mixes Polygon and MultiPolygon),
    each with its own holes.
    """

    patch_id: str
    area_ha: float
    polygons: list[Polygon]
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def contains(self, lat: float, lon: float) -> bool:
        if not (
            self.min_lon <= lon <= self.max_lon and self.min_lat <= lat <= self.max_lat
        ):
            return False  # cheap bounding-box rejection first
        return any(polygon.contains(lon, lat) for polygon in self.polygons)

    def edge_distance_m(self, lat: float, lon: float) -> float:
        """Metres to the nearest edge: how far a GPS error would have to reach.

        For a point inside, only the polygon containing it counts — crossing its
        boundary is what would change the answer. For a point outside, it is the
        nearest edge of any polygon in the patch.
        """
        for polygon in self.polygons:
            if polygon.contains(lon, lat):
                return polygon.boundary_distance_m(lat, lon)
        return min(p.boundary_distance_m(lat, lon) for p in self.polygons)

    def distance_km(self, lat: float, lon: float) -> float:
        """Approximate distance to the patch: 0 inside, else to the nearest vertex.

        Vertex distance slightly overestimates the true edge distance, which is
        fine for a "how far is the nearest browning" readout. Hole boundaries
        count: from inside an unbrowned island the nearest browning is the
        island's edge.
        """
        if self.contains(lat, lon):
            return 0.0
        return min(
            _haversine_km(lat, lon, y, x)
            for polygon in self.polygons
            for ring in (polygon.outer, *polygon.holes)
            for x, y in ring
        )


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test on a single ring of (lon, lat) points."""
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        # Does the horizontal ray at y cross this edge?
        if (y1 > y) != (y2 > y):
            x_cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_cross:
                inside = not inside
    return inside


_M_PER_DEG_LAT = 111_320.0


def _point_to_segment_m(
    lat: float, lon: float, a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distance in metres from a point to the segment a-b (both as (lon, lat)).

    Uses a local flat projection centred on the point, which is accurate to well
    under a metre at the scale of one patch. A true edge distance matters here:
    distance to the nearest *vertex* overestimates it, and the whole point is to
    decide whether a GPS error could have put the observer on the other side.
    """
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat))
    ax, ay = (a[0] - lon) * m_per_deg_lon, (a[1] - lat) * _M_PER_DEG_LAT
    bx, by = (b[0] - lon) * m_per_deg_lon, (b[1] - lat) * _M_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
    return math.hypot(ax + t * dx, ay + t * dy)


def _ring_distance_m(lat: float, lon: float, ring: Ring) -> float:
    return min(
        _point_to_segment_m(lat, lon, ring[i], ring[(i + 1) % len(ring)])
        for i in range(len(ring))
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _polygons_of(geometry: dict) -> list[Polygon]:
    """Normalize Polygon and MultiPolygon into a list of Polygons.

    The patch file mixes both (658 Polygon, 221 MultiPolygon), which differ by
    one level of nesting. In GeoJSON the first ring of a polygon is its outer
    boundary and any further rings are holes.
    """
    kind, coords = geometry.get("type"), geometry.get("coordinates", [])
    if kind == "Polygon":
        raw_polygons = [coords]
    elif kind == "MultiPolygon":
        raw_polygons = coords
    else:
        return []

    polygons: list[Polygon] = []
    for rings in raw_polygons:
        if not rings:
            continue
        converted = [[(float(x), float(y)) for x, y in ring] for ring in rings]
        polygons.append(Polygon(outer=converted[0], holes=converted[1:]))
    return polygons


@lru_cache(maxsize=1)
def load_patches() -> tuple[BrowningPatch, ...]:
    """Load and index the browning patches (cached for the process lifetime)."""
    if not PATCHES_PATH.exists():
        return ()

    payload = json.loads(PATCHES_PATH.read_text())
    patches: list[BrowningPatch] = []

    for feature in payload.get("features", []):
        polygons = _polygons_of(feature.get("geometry", {}))
        if not polygons:
            continue
        # The bounding box only needs the outer rings; holes sit inside them.
        xs = [x for polygon in polygons for x, _ in polygon.outer]
        ys = [y for polygon in polygons for _, y in polygon.outer]
        props = feature.get("properties", {})
        patches.append(
            BrowningPatch(
                patch_id=str(props.get("patch_id", "")),
                area_ha=float(props.get("area_ha", 0.0)),
                polygons=polygons,
                min_lon=min(xs),
                min_lat=min(ys),
                max_lon=max(xs),
                max_lat=max(ys),
            )
        )

    return tuple(patches)


def _load_series(path: Path, column: str) -> list[tuple[str, float]]:
    """Read one monthly CSV, dropping the -9999 no-imagery months."""
    if not path.exists():
        return []
    out: list[tuple[str, float]] = []
    with path.open() as handle:
        for row in csv.DictReader(handle):
            try:
                value = float(row[column])
            except (KeyError, TypeError, ValueError):
                continue
            if value != _MISSING:
                out.append((row["date"], value))
    return out


@lru_cache(maxsize=1)
def ndvi_series() -> tuple[tuple[str, float], ...]:
    """Monthly mean NDVI across the Pukalani AOI, missing months removed."""
    return tuple(_load_series(NDVI_PATH, "ndvi"))


@lru_cache(maxsize=1)
def nbr_series() -> tuple[tuple[str, float], ...]:
    """Monthly mean NBR across the Pukalani AOI, missing months removed."""
    return tuple(_load_series(NBR_PATH, "nbr"))


@lru_cache(maxsize=1)
def _index() -> dict | None:
    """Per-process derived values that do not depend on the query point.

    Ranking by area and the AOI extent were being recomputed on every call;
    they only depend on the patch file.
    """
    patches = load_patches()
    if not patches:
        return None
    ranked = sorted(patches, key=lambda p: p.area_ha, reverse=True)
    return {
        "rank": {id(p): i + 1 for i, p in enumerate(ranked)},
        "min_lon": min(p.min_lon for p in patches) - AOI_MARGIN_DEG,
        "max_lon": max(p.max_lon for p in patches) + AOI_MARGIN_DEG,
        "min_lat": min(p.min_lat for p in patches) - AOI_MARGIN_DEG,
        "max_lat": max(p.max_lat for p in patches) + AOI_MARGIN_DEG,
        "total_ha": round(sum(p.area_ha for p in patches), 1),
    }


def _box_distance_km_lower_bound(patch: BrowningPatch, lat: float, lon: float) -> float:
    """A distance no greater than the true distance from a point to anything in the
    patch's bounding box. Flat-earth with a deliberately low km-per-degree, so it
    can only underestimate; used to rule patches out without touching their vertices."""
    d_lat = max(patch.min_lat - lat, 0.0, lat - patch.max_lat)
    d_lon = max(patch.min_lon - lon, 0.0, lon - patch.max_lon)
    worst_lat = min(89.0, max(abs(lat), abs(patch.min_lat), abs(patch.max_lat)))
    km_per_deg = 111.0 * 0.999
    return math.hypot(d_lat * km_per_deg, d_lon * km_per_deg * math.cos(math.radians(worst_lat)))


def nearest_patch(lat: float, lon: float) -> BrowningPatch | None:
    """The patch with the smallest `distance_km`, found without scanning them all.

    Patches are visited nearest-bounding-box first and the search stops once the
    next box is already farther than the best patch found. Same answer as
    `min(patches, key=distance_km)` (ties go to the earlier patch), a fraction of
    the vertex distance calculations.
    """
    patches = load_patches()
    order = sorted(
        range(len(patches)), key=lambda i: _box_distance_km_lower_bound(patches[i], lat, lon)
    )
    best: tuple[float, int] | None = None
    for i in order:
        if best is not None and _box_distance_km_lower_bound(patches[i], lat, lon) > best[0]:
            break
        candidate = (patches[i].distance_km(lat, lon), i)
        if best is None or candidate < best:
            best = candidate
    return patches[best[1]] if best else None


# Cap on how far the sensitivity check shifts the footprint. Beyond this the
# range just says "the GPS fix tells you almost nothing", which the accuracy
# figure already says.
MAX_SHIFT_M = 250.0


def fraction_range(
    lat: float, lon: float, accuracy_m: float | None
) -> tuple[float, float] | None:
    """Min/max browned fraction as the footprint slides by the GPS error.

    Re-evaluates the footprint shifted by the recorded accuracy north, east, south
    and west. A narrow range means the browned fraction is a property of the
    place; a wide one means the answer depends on exactly where the phone thought
    it was, and should be reported as a range rather than one number.
    """
    if accuracy_m is None:
        return None
    shift = min(accuracy_m, MAX_SHIFT_M)
    d_lat = shift / _M_PER_DEG_LAT
    d_lon = shift / (_M_PER_DEG_LAT * math.cos(math.radians(lat)))
    values = [_fraction_at(lat, lon)]
    for dy, dx in ((d_lat, 0), (-d_lat, 0), (0, d_lon), (0, -d_lon)):
        values.append(_fraction_at(lat + dy, lon + dx))
    return (min(values), max(values))


def _confidence(accuracy_m: float | None, edge_m: float) -> str:
    """Could the recorded GPS error have flipped the answer?

    `confident`  the fix error is smaller than the distance to the nearest edge,
                 so no point within the error radius would give a different answer.
    `uncertain`  the error radius reaches across an edge — the observer may have
                 been on the other side.
    `unknown`    no accuracy was recorded.

    GLOBE's accuracy is taken as a radius in metres, the usual phone-GPS meaning.
    The error is floored at one raster pixel, since the patch edge itself is only
    that precise.
    """
    if accuracy_m is None:
        return "unknown"
    return "confident" if max(accuracy_m, PIXEL_M) <= edge_m else "uncertain"


def site_browned_fraction(lat: float, lon: float) -> float | None:
    """Cached front for `_site_browned_fraction`, keyed on rounded coordinates."""
    return _site_browned_fraction(round(lat, 6), round(lon, 6))


@lru_cache(maxsize=8192)
def _site_browned_fraction(lat: float, lon: float) -> float | None:
    """Share of a 100 m x 100 m site footprint that falls in browned patches.

    Estimated by sampling a regular grid (5 m spacing, 441 points) centred on the
    observation and testing each against the patches. This answers the question
    a GLOBE site actually poses, and it degrades gracefully: unlike a single
    point, a modest GPS error shifts the footprint rather than flipping the
    answer. Returns None outside the analysed area, where it is not measurable.
    """
    index = _index()
    if index is None:
        return None
    if not (
        index["min_lon"] <= lon <= index["max_lon"]
        and index["min_lat"] <= lat <= index["max_lat"]
    ):
        return None
    return _fraction_at(lat, lon)


def _fraction_at(lat: float, lon: float) -> float:
    """Browned share of the footprint centred here (no area check)."""
    half = SITE_SIZE_M / 2
    d_lat = half / _M_PER_DEG_LAT
    d_lon = half / (_M_PER_DEG_LAT * math.cos(math.radians(lat)))
    candidates = [
        p
        for p in load_patches()
        if p.min_lon <= lon + d_lon
        and p.max_lon >= lon - d_lon
        and p.min_lat <= lat + d_lat
        and p.max_lat >= lat - d_lat
    ]
    if not candidates:
        return 0.0

    steps = int(SITE_SIZE_M / SITE_SAMPLE_STEP_M) + 1
    hits = total = 0
    for i in range(steps):
        y = lat - d_lat + (2 * d_lat) * i / (steps - 1)
        for j in range(steps):
            x = lon - d_lon + (2 * d_lon) * j / (steps - 1)
            total += 1
            if any(p.contains(y, x) for p in candidates):
                hits += 1
    return round(hits / total, 3)


@lru_cache(maxsize=8192)
def _context(lat: float, lon: float, accuracy_m: float | None) -> tuple:
    return tuple(_compute_context(lat, lon, accuracy_m).items())


def context_for_point(
    lat: float, lon: float, accuracy_m: float | None = None
) -> dict:
    """Vegetation-health context for one location.

    Returns whether the point sits inside a mapped browning patch, how large that
    patch is and how it ranks by area, or — when outside — how far the nearest
    browning is. `in_analysis_area` distinguishes "measured, and not browned"
    from "outside the study area entirely", which is a meaningful difference:
    only the first is evidence of anything.

    Pass the observation's recorded GPS accuracy to also get `edge_distance_m`
    and `location_confidence`. Citizen-science fixes range from a few metres to
    over a kilometre, and a 7 ha patch is only ~265 m across, so "inside" is
    only a real statement when the error is smaller than the distance to the
    nearest edge.
    """
    return dict(_context(round(lat, 6), round(lon, 6), accuracy_m))


def _compute_context(lat: float, lon: float, accuracy_m: float | None) -> dict:
    index = _index()
    if index is None:
        return {"available": False}

    patches = load_patches()
    in_area = (
        index["min_lon"] <= lon <= index["max_lon"]
        and index["min_lat"] <= lat <= index["max_lat"]
    )

    result = {
        "available": True,
        "in_analysis_area": in_area,
        "threshold": BROWNING_THRESHOLD,
        "total_patches": len(patches),
        "total_browned_ha": index["total_ha"],
        "location_accuracy_m": accuracy_m,
        "site_browned_fraction": site_browned_fraction(lat, lon),
    }

    if in_area:
        rng = fraction_range(lat, lon, accuracy_m)
        result["site_browned_range"] = list(rng) if rng else None
        result["aoi_browned_fraction"] = AOI_BROWNED_FRACTION
    else:
        result["site_browned_range"] = None
        result["aoi_browned_fraction"] = None

    if not in_area:
        # Outside the analysed area the question has no answer: None means "not
        # measured", which is different from False ("measured, not browned").
        # Skipping the scan also avoids walking every vertex in the file for a
        # far-away point.
        result.update(
            {
                "inside_browning_patch": None,
                "distance_to_browning_km": None,
                "edge_distance_m": None,
                "location_confidence": None,
            }
        )
        return result

    containing = next((p for p in patches if p.contains(lat, lon)), None)
    if containing is not None:
        edge_m = containing.edge_distance_m(lat, lon)
        result.update(
            {
                "inside_browning_patch": True,
                "patch_area_ha": round(containing.area_ha, 2),
                "patch_rank_by_area": index["rank"][id(containing)],
                "distance_to_browning_km": 0.0,
                "edge_distance_m": round(edge_m, 1),
                "location_confidence": _confidence(accuracy_m, edge_m),
            }
        )
    else:
        # Pick the nearest patch by cheap vertex distance, then measure it
        # properly against its edges.
        nearest = nearest_patch(lat, lon)
        edge_m = nearest.edge_distance_m(lat, lon)
        result.update(
            {
                "inside_browning_patch": False,
                "patch_area_ha": None,
                "patch_rank_by_area": None,
                "distance_to_browning_km": round(edge_m / 1000, 3),
                "nearest_patch_area_ha": round(nearest.area_ha, 2),
                "edge_distance_m": round(edge_m, 1),
                "location_confidence": _confidence(accuracy_m, edge_m),
            }
        )
    return result
