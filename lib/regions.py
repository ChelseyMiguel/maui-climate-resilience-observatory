"""Region insights for Pukalani, Makawao and Kula (2020 Census places).

The honest core of this module is `vegetation_coverage`: the project's NDVI/NBR
series come from ONE 1.5 km study-area circle, which is ~81% inside the Pukalani
Census place, ~6% inside Makawao and 0% inside Kula. So:

* Pukalani gets the series, labelled with that overlap.
* Makawao and Kula get an explicit "not available" with the reason — not the
  Pukalani numbers relabelled. `scripts/gee/region_timeseries.js` computes real
  per-region series when run.

Drought is county-level (U.S. Drought Monitor DSCI for Maui County) and is shown
for every region labelled as such, never as a region-specific value.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from lib import hazards
from lib.vegetation import browning
from lib.vegetation.browning import Polygon, _polygons_of

CONTEXT = Path(__file__).resolve().parents[1] / "data" / "context"
REGIONS_PATH = CONTEXT / "regions.geojson"
REGION_KEYS = {"pukalani": "Pukalani", "makawao": "Makawao", "kula": "Kula"}

# Below this share of the study area inside a region, the study-area series is
# not presented as that region's series.
MIN_COVERAGE = 0.5

# The dry season used throughout the project's analysis (May through September),
# matching DRY_MONTHS in pukalani_fire_precursor.py and the GEE composites.
DRY_MONTHS = (5, 6, 7, 8, 9)


@lru_cache(maxsize=1)
def load_regions() -> dict[str, dict]:
    if not REGIONS_PATH.exists():
        return {}
    out = {}
    for f in json.loads(REGIONS_PATH.read_text())["features"]:
        name = f["properties"]["name"]
        out[name] = {"properties": f["properties"], "polygons": _polygons_of(f["geometry"])}
    return out


def _inside(polygons: list[Polygon], lat: float, lon: float) -> bool:
    return any(p.contains(lon, lat) for p in polygons)


@lru_cache(maxsize=8)
def study_area_overlap(name: str, step_m: float = 25.0) -> float:
    """Share of the 1.5 km study-area circle that lies inside a region."""
    region = load_regions().get(name)
    if not region:
        return 0.0
    sa = hazards.STUDY_AREA
    r = sa["radius_m"]
    kx = 111_320 * math.cos(math.radians(sa["lat"]))
    n = hits = 0
    steps = int(r // step_m)
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            dx, dy = j * step_m, i * step_m
            if dx * dx + dy * dy > r * r:
                continue
            n += 1
            if _inside(region["polygons"], sa["lat"] + dy / 111_320, sa["lon"] + dx / kx):
                hits += 1
    return round(hits / n, 3) if n else 0.0


def dry_season_means(series: tuple[tuple[str, float], ...]) -> dict[str, dict]:
    """Mean of the May-September monthly values per year, with how many months fed it.

    Months with no usable imagery are already absent from the series, so `months`
    shows how complete each year's dry season is — a year built from two months
    is not as trustworthy as one built from five.
    """
    by_year: dict[str, list[float]] = {}
    for date, value in series:
        if int(date[5:7]) in DRY_MONTHS:
            by_year.setdefault(date[:4], []).append(value)
    return {y: {"mean": round(sum(v) / len(v), 4), "months": len(v)}
            for y, v in sorted(by_year.items())}


def vegetation_coverage(name: str) -> dict:
    overlap = study_area_overlap(name)
    if overlap >= MIN_COVERAGE:
        return {
            "available": True,
            "analysis_area": "1.5 km study-area circle (Sentinel-2, 10 m)",
            "overlap": overlap,
            "note": (f"{round(overlap * 100)}% of the study-area circle lies inside the "
                     f"{name} Census place; the rest falls outside it. This is the study "
                     "area's series, not a measurement of the whole place."),
        }
    return {
        "available": False,
        "overlap": overlap,
        "reason": (f"Only {round(overlap * 100)}% of the project's study area lies in {name}, "
                   "so its series would not represent this place. A per-place series needs "
                   "scripts/gee/region_timeseries.js to be run."),
    }


@lru_cache(maxsize=8)
def region_fire_context(name: str) -> dict:
    """Nearest 2023 fire to a region: inside it, or distance from its edge."""
    region = load_regions().get(name)
    fires = [f for f in hazards.load_fires() if f.year == 2023]
    if not region or not fires:
        return {"available": False}
    best = None
    for fire in fires:
        overlaps = any(
            fire.contains(lat, lon)
            for poly in region["polygons"]
            for lon, lat in poly.outer[:: max(1, len(poly.outer) // 200)]
        ) or any(
            _inside(region["polygons"], lat, lon)
            for poly in fire.polygons
            for lon, lat in poly.outer[:: max(1, len(poly.outer) // 200)]
        )
        if overlaps:
            dist = 0.0
        else:
            dist = min(
                fire.distance_m(lat, lon)
                for poly in region["polygons"]
                for lon, lat in poly.outer[:: max(1, len(poly.outer) // 300)]
            )
        if best is None or dist < best[1]:
            best = (fire, dist)
    fire, dist = best
    return {"available": True, "nearest_fire": fire.name, "acres": fire.acres,
            "overlaps_region": dist == 0.0, "distance_km": round(dist / 1000, 2)}


@lru_cache(maxsize=8)
def insights(key: str) -> dict | None:
    """Everything the Region Insights page shows for one place.

    Cached: none of it changes while the server runs, and the fire-distance step
    is a few seconds of geometry per region. `warm()` fills the cache at startup.
    """
    return _insights(key)


def warm() -> None:
    """Compute every region up front (called in a background thread at startup)."""
    for key in REGION_KEYS:
        insights(key)


def _insights(key: str) -> dict | None:
    name = REGION_KEYS.get(key)
    if not name or name not in load_regions():
        return None
    props = load_regions()[name]["properties"]
    veg = vegetation_coverage(name)
    if veg["available"]:
        veg["ndvi"] = [{"date": d, "value": round(v, 4)} for d, v in browning.ndvi_series()]
        veg["nbr"] = [{"date": d, "value": round(v, 4)} for d, v in browning.nbr_series()]
        veg["dry_season_ndvi"] = dry_season_means(browning.ndvi_series())
        veg["dry_season_nbr"] = dry_season_means(browning.nbr_series())
    return {
        "key": key,
        "name": name,
        "kind": props.get("kind"),
        "geoid": props.get("geoid"),
        "land_km2": props.get("land_km2"),
        "vegetation": veg,
        "drought": {
            "scope": "Maui County as a whole — not specific to this place",
            "source": "U.S. Drought Monitor DSCI (weekly, 0-500)",
            "weekly": [{"date": d, "dsci": v} for d, v in hazards.drought_series()],
        },
        "fire": region_fire_context(name),
    }
