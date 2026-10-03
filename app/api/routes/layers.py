"""Map layers for the 3D GIS view: terrain, browning, fires, drought, sites.

Kept separate from `sites.py` because none of these are GLOBE observations — they
are the context the observations are read against. Everything is served from
files produced by the `scripts/fetch_*.py` and analysis outputs, so the map works
offline exactly like the viewer.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.routes.sites import DEFAULT_END, DEFAULT_START, REGION
from lib import hazards
from lib.globe_api import client
from lib.vegetation import browning

router = APIRouter()

DATA = Path(__file__).resolve().parents[3] / "data"
TERRAIN_META = DATA / "terrain" / "upcountry_dem.json"
TERRAIN_BIN = DATA / "terrain" / "upcountry_dem.i16"


def _require(path: Path, how: str) -> Path:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"{path.name} missing — run {how}")
    return path


@router.get("/terrain")
def terrain_meta() -> dict:
    """Grid size, bounding box and elevation range for the terrain mesh."""
    return json.loads(_require(TERRAIN_META, "scripts/fetch_terrain.py").read_text())


@router.get("/terrain.bin")
def terrain_grid() -> FileResponse:
    """The elevation grid itself: Int16 little-endian metres, rows north to south,
    spaced linearly in latitude and longitude (see /terrain for the shape)."""
    return FileResponse(_require(TERRAIN_BIN, "scripts/fetch_terrain.py"),
                        media_type="application/octet-stream")


@router.get("/browning")
def browning_patches() -> FileResponse:
    """The 879 browning patches (dNDVI < -0.10, 2019 -> 2022) as GeoJSON."""
    return FileResponse(_require(browning.PATCHES_PATH, "the browning analysis"),
                        media_type="application/geo+json")


@router.get("/fires")
def fire_perimeters() -> FileResponse:
    """Maui fire perimeters from NIFC, including the 8 Aug 2023 fires."""
    return FileResponse(_require(hazards.FIRES_PATH, "scripts/fetch_fire_perimeters.py"),
                        media_type="application/geo+json")


@router.get("/drought")
def drought() -> dict:
    """Weekly Maui County drought index plus annual means and the fire weeks."""
    series = hazards.drought_series()
    if not series:
        raise HTTPException(status_code=503, detail="drought data missing — run scripts/fetch_drought.py")
    return {
        "series": [{"date": d, "dsci": v} for d, v in series],
        "ndvi": [{"date": d, "value": v} for d, v in browning.ndvi_series()],
        **hazards.drought_summary(),
    }


@router.get("/study-area")
def study_area() -> dict:
    """The 1.5 km circle every browning analysis in this project covers."""
    return {**hazards.STUDY_AREA,
            "browned_fraction": browning.AOI_BROWNED_FRACTION,
            "fire": hazards.fire_context(hazards.STUDY_AREA["lat"], hazards.STUDY_AREA["lon"])}


@router.get("/sites")
def site_pins() -> list[dict]:
    """One pin per GLOBE site inside the terrain extent.

    Each pin opens the site's latest complete observation (falling back to the
    latest of any kind), matching what the viewer's sidebar card shows.
    """
    meta = json.loads(_require(TERRAIN_META, "scripts/fetch_terrain.py").read_text())
    box = meta["bbox"]
    try:
        observations = client.fetch_sites(DEFAULT_START, DEFAULT_END, bbox=REGION)
    except client.GlobeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    by_site: dict[str, list] = {}
    for o in observations:
        if box["west"] <= o.longitude <= box["east"] and box["south"] <= o.latitude <= box["north"]:
            by_site.setdefault(o.site_id, []).append(o)

    pins = []
    for visits in by_site.values():
        visits.sort(key=lambda o: o.measured_at.isoformat() if o.measured_at else "", reverse=True)
        best = next((o for o in visits if o.is_complete), visits[0])
        pins.append({
            "site_id": best.site_id,
            "site_name": best.site_name,
            "land_cover_id": best.land_cover_id,
            "label": client.meaningful_note(best.field_notes) or best.muc_description or "Land cover site",
            "lat": best.latitude,
            "lon": best.longitude,
            "elevation_m": best.elevation_m,
            "visits": len(visits),
            "latest": best.measured_at.date().isoformat() if best.measured_at else None,
            "teams": best.globe_teams,
            "browned_fraction": browning.site_browned_fraction(best.latitude, best.longitude),
            "fire": hazards.fire_context(best.latitude, best.longitude),
        })
    pins.sort(key=lambda p: p["site_name"])
    return pins
