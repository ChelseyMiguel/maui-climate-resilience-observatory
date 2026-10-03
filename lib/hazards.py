"""Wildfire and drought context: the disaster-awareness layer.

Two published, independent records, each from a different agency than the
project's own satellite analysis:

* Fire perimeters — National Interagency Fire Center (WFIGS + perimeter history),
  fetched by `scripts/fetch_fire_perimeters.py`. Includes the 8 Aug 2023
  Olinda, Kula, Pulehu and Lahaina fires.
* Weekly drought — U.S. Drought Monitor DSCI for Maui County, fetched by
  `scripts/fetch_drought.py`.

Polygon handling reuses `lib.vegetation.browning`, which already treats holes and
MultiPolygons correctly and is covered by tests.

Scope note, same discipline as the browning layer: the Pukalani study area did
NOT burn. The nearest 2023 perimeter (Olinda) is ~1.5 km outside it. Distances
here say how close a place is to where fire actually went; they are not a fire
risk score and must not be presented as one.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lib.vegetation.browning import Polygon, _polygons_of

DATA = Path(__file__).resolve().parents[1] / "data" / "research"
FIRES_PATH = DATA / "maui_fire_perimeters.geojson"
DROUGHT_PATH = DATA / "maui_dsci_weekly.csv"

# The study area used by every Earth Engine script in this project
# (gee_export_ndvi.js / gee_export_nbr.js): a 1.5 km circle around this point.
STUDY_AREA = {"lat": 20.838722, "lon": -156.344856, "radius_m": 1500.0}


@dataclass(frozen=True)
class Fire:
    name: str
    year: int | None
    discovered: str | None  # ISO date, Hawaii time
    acres: float | None
    source: str
    polygons: list[Polygon]

    def contains(self, lat: float, lon: float) -> bool:
        return any(p.contains(lon, lat) for p in self.polygons)

    def distance_m(self, lat: float, lon: float) -> float:
        """0 inside the perimeter, else metres to its nearest edge."""
        if self.contains(lat, lon):
            return 0.0
        return min(p.boundary_distance_m(lat, lon) for p in self.polygons)


@lru_cache(maxsize=1)
def load_fires() -> tuple[Fire, ...]:
    if not FIRES_PATH.exists():
        return ()
    fires = []
    for f in json.loads(FIRES_PATH.read_text()).get("features", []):
        p = f.get("properties", {})
        polys = _polygons_of(f.get("geometry") or {})
        if polys:
            fires.append(Fire(p.get("name", "Unknown"), p.get("year"), p.get("discovered"),
                              p.get("acres"), p.get("source", ""), polys))
    return tuple(fires)


@lru_cache(maxsize=1)
def drought_series() -> tuple[tuple[str, int], ...]:
    """Weekly Maui County DSCI (0 = no drought, 500 = all of it exceptional)."""
    if not DROUGHT_PATH.exists():
        return ()
    with DROUGHT_PATH.open() as handle:
        return tuple((r["date"], int(r["dsci"])) for r in csv.DictReader(handle))


def fire_context(lat: float, lon: float, year: int | None = 2023) -> dict:
    """Nearest fire perimeter (optionally of one year) to a point."""
    fires = [f for f in load_fires() if year is None or f.year == year]
    if not fires:
        return {"available": False}
    nearest = min(fires, key=lambda f: f.distance_m(lat, lon))
    distance = nearest.distance_m(lat, lon)
    return {
        "available": True,
        "year": year,
        "nearest_fire": nearest.name,
        "discovered": nearest.discovered,
        "acres": nearest.acres,
        "inside_perimeter": distance == 0.0,
        "distance_km": round(distance / 1000, 2),
        "source": nearest.source,
    }


def drought_summary() -> dict:
    """Annual means and the week of the 8 Aug 2023 fires, for the timeline."""
    series = drought_series()
    if not series:
        return {"available": False}
    by_year: dict[str, list[int]] = {}
    for date, value in series:
        by_year.setdefault(date[:4], []).append(value)
    annual = {y: round(sum(v) / len(v)) for y, v in sorted(by_year.items()) if len(v) >= 26}
    fire_weeks = [{"date": d, "dsci": v} for d, v in series if "2023-07-25" <= d <= "2023-08-22"]
    worst_year = max(annual, key=annual.get) if annual else None
    return {
        "available": True,
        "annual_mean": annual,  # only years with at least half a year of weeks
        "worst_year": worst_year,
        "weeks_around_fires": fire_weeks,
        "source": "U.S. Drought Monitor (UNL), Maui County DSCI",
    }
