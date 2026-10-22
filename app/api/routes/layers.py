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
from lib import hazards, landsat_baseline, rainfall, relationships
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


@router.get("/drought-greenness")
def drought_greenness() -> dict:
    """County drought against Pukalani NDVI/NBR: scatter points, lag profile and
    dry-season means, all computed in `lib.relationships`."""
    data = relationships.drought_greenness()
    if not data["available"]:
        raise HTTPException(
            status_code=503,
            detail="drought-greenness series missing: need data/research/pukalani_ndvi_monthly.csv "
                   "and maui_dsci_weekly.csv (see scripts/fetch_drought.py)",
        )
    return data


@router.get("/rainfall")
def rainfall_summary() -> dict:
    """Monthly rain at the study area from four products, how well they agree, and
    how rain over the last 1-12 months relates to greenness (lib/rainfall.py)."""
    data = rainfall.summary(rainfall.RAIN_PATH)
    if not data["available"]:
        raise HTTPException(
            status_code=503,
            detail="rainfall missing: export data/research/pukalani_rainfall_monthly.csv with "
                   "notebooks/gee_exports.ipynb or scripts/gee/rainfall_monthly.js",
        )
    return data


@router.get("/drought-weeks")
def drought_weeks() -> list[dict]:
    """Weekly Maui County drought, 2017-12 to 2024-12: DSCI plus the cumulative share
    of the county in D0..D4, for the week-by-week drought calendar."""
    weeks = hazards.drought_weeks()
    if not weeks:
        raise HTTPException(status_code=503,
                            detail="drought categories missing: data/research/maui_drought_categories_weekly.csv")
    return list(weeks)


@router.get("/ndvi-baseline")
def ndvi_baseline() -> dict:
    """25 years of dry-season Landsat NDVI for the study area, each year against the
    2000-2018 normal (lib/landsat_baseline.py)."""
    # Optional analysis: "not produced yet" is a normal answer (200), not an error,
    # so the page that asks for it never logs a failed request.
    data = landsat_baseline.summary(landsat_baseline.PATH)
    if not data["available"]:
        data["how"] = ("run section 6 of notebooks/gee_exports.ipynb and save "
                       "data/research/pukalani_landsat_ndvi_dryseason.csv")
    return data


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


# ---------------------------------------------------------------------------
# Observatory layers: regions, community context, drought maps, rasters
# ---------------------------------------------------------------------------

CONTEXT = DATA / "context"
CONTEXT_KEYS = ("fire_stations", "ems_stations", "hospitals", "public_schools", "private_schools")
RASTERS = {
    "dndvi": browning.DATA_DIR / "dndvi_2019_2022.tif",
    "dnbr": browning.DATA_DIR / "dnbr_2019_2022.tif",
    # Remote-sensing products from scripts/remote_sensing/ (public AWS archives).
    "s2_aoi_annual": browning.DATA_DIR / "s2_aoi_annual.tif",
    "s2_regional_change": browning.DATA_DIR / "s2_regional_change.tif",
    "lidar_aoi": browning.DATA_DIR / "lidar_aoi.tif",
    "worldcover_2021": DATA / "context" / "worldcover_2021.tif",
    "landsat_aoi_annual": browning.DATA_DIR / "landsat_aoi_annual.tif",
    "landsat_lst_annual": browning.DATA_DIR / "landsat_lst_annual.tif",
    "s2_burn_severity_2023": browning.DATA_DIR / "s2_burn_severity_2023.tif",
}
MANIFESTS = {
    "sentinel2": browning.DATA_DIR / "s2_manifest.json",
    "lidar": browning.DATA_DIR / "lidar_manifest.json",
    "worldcover": browning.DATA_DIR / "worldcover_browning.json",
    "landsat": browning.DATA_DIR / "landsat_manifest.json",
    "burn_severity": browning.DATA_DIR / "burn_severity_2023.json",
}
LST_CSV = browning.DATA_DIR / "landsat_lst_dryseason.csv"


@router.get("/regions")
def region_boundaries() -> FileResponse:
    """Pukalani, Makawao and Kula as 2020 Census Designated Places."""
    return FileResponse(_require(CONTEXT / "regions.geojson", "scripts/fetch_context_layers.py"),
                        media_type="application/geo+json")


@router.get("/context")
def context_catalog() -> list[dict]:
    """What community-context layers exist, how many features, and how current
    each is in its publisher's own words."""
    path = _require(CONTEXT / "catalog.json", "scripts/fetch_context_layers.py")
    return json.loads(path.read_text())


@router.get("/context/{key}")
def context_layer(key: str) -> FileResponse:
    if key not in CONTEXT_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown context layer '{key}'")
    return FileResponse(_require(CONTEXT / f"{key}.geojson", "scripts/fetch_context_layers.py"),
                        media_type="application/geo+json")


@router.get("/drought-maps")
def drought_map_index() -> list[dict]:
    """One U.S. Drought Monitor map per year, for the week nearest 8 August."""
    path = _require(CONTEXT / "drought_maps" / "index.json", "scripts/fetch_drought_maps.py")
    return json.loads(path.read_text())


@router.get("/drought-maps/{year}")
def drought_map(year: int) -> FileResponse:
    for entry in drought_map_index():
        if entry["year"] == year:
            return FileResponse(CONTEXT / "drought_maps" / entry["file"],
                                media_type="application/geo+json")
    raise HTTPException(status_code=404, detail=f"No drought map for {year}")


@router.get("/raster/{name}")
def raster(name: str) -> FileResponse:
    """GeoTIFF rasters: the project's own change rasters (dndvi, dnbr: EPSG:32604,
    10 m, dry season 2022 minus 2019) and the remote-sensing products built by
    scripts/remote_sensing/ (annual Sentinel-2 composites, regional change,
    lidar terrain/canopy, WorldCover land cover)."""
    path = RASTERS.get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown raster '{name}'")
    return FileResponse(_require(path, "scripts/remote_sensing/ or the browning analysis"), media_type="image/tiff")


@router.get("/remote-sensing")
def remote_sensing() -> dict:
    """Provenance and validation for the remote-sensing products: scenes used,
    lidar acquisition dates and density, land-cover breakdown of browning.
    A missing product is reported as null, not an error."""
    out = {k: json.loads(p.read_text()) if p.exists() else None for k, p in MANIFESTS.items()}
    out["rasters"] = {k: p.exists() for k, p in RASTERS.items()}
    # Dry-season land surface temperature per year (scripts/remote_sensing/landsat_lst.py).
    if LST_CSV.exists():
        import csv
        with LST_CSV.open(newline="") as f:
            out["lst"] = [{"year": int(r["year"]), "lst_c": float(r["lst_c_median"]) if r["lst_c_median"] else None,
                           "n_scenes": int(r["n_scenes"]), "sensors": r["sensors"]} for r in csv.DictReader(f)]
    else:
        out["lst"] = None
    return out


@router.get("/inset.png")
def inset() -> FileResponse:
    """Maui shaded relief for the Map Explorer's locator inset (Copernicus DEM GLO-90)."""
    return FileResponse(_require(DATA / "context" / "maui_inset.png", "scripts/remote_sensing/maui_inset.py"),
                        media_type="image/png")


@router.get("/lidar-points")
def lidar_points() -> FileResponse:
    """Thinned lidar points over the study area (see scripts/remote_sensing/lidar_canopy.py
    for the binary layout)."""
    return FileResponse(_require(browning.DATA_DIR / "lidar_points.bin", "scripts/remote_sensing/lidar_canopy.py"),
                        media_type="application/octet-stream")


@router.get("/observations")
def all_observations() -> list[dict]:
    """Every GLOBE land cover observation in the Upcountry extent, with its date,
    so the map's year filter can show what was actually observed that year."""
    meta = json.loads(_require(TERRAIN_META, "scripts/fetch_terrain.py").read_text())
    box = meta["bbox"]
    try:
        observations = client.fetch_sites(DEFAULT_START, DEFAULT_END, bbox=REGION)
    except client.GlobeUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        {"land_cover_id": o.land_cover_id, "site_name": o.site_name,
         "label": client.meaningful_note(o.field_notes) or o.muc_description or "Land cover site",
         "lat": o.latitude, "lon": o.longitude,
         "date": o.measured_at.date().isoformat() if o.measured_at else None,
         "complete": o.is_complete, "teams": o.globe_teams}
        for o in observations
        if box["west"] <= o.longitude <= box["east"] and box["south"] <= o.latitude <= box["north"]
    ]


@router.get("/insights/{key}")
def region_insights(key: str) -> dict:
    from lib import regions

    data = regions.insights(key)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Unknown region '{key}'")
    return data


# ---------------------------------------------------------------------------
# Satellite imagery for the 3D map (exported by scripts/gee/imagery_before_after.js)
# ---------------------------------------------------------------------------

IMAGERY_DIR = DATA / "imagery"
# key -> (label, period). Each is either a JPEG + JSON sidecar from
# scripts/remote_sensing/sentinel2_composites.py, or a GeoTIFF exported by
# scripts/gee/imagery_before_after.js; both cover the terrain box in EPSG:4326.
IMAGERY = {
    "s2_dry_2019": ("Dry season 2019", "Sentinel-2 true colour, May – Sep 2019 median"),
    "s2_dry_2022": ("Dry season 2022", "Sentinel-2 true colour, May – Sep 2022 median"),
    "s2_dry_2019_cir": ("Dry season 2019 · colour infrared", "Sentinel-2 NIR-red-green, May – Sep 2019"),
    "s2_dry_2022_cir": ("Dry season 2022 · colour infrared", "Sentinel-2 NIR-red-green, May – Sep 2022"),
    "before_2023": ("Before the fires", "Sentinel-2 true colour, 1 May – 7 Aug 2023"),
    "after_2023": ("After the fires", "Sentinel-2 true colour, 15 Aug – 31 Oct 2023"),
}
_IMAGE_TYPES = {".jpg": "image/jpeg", ".tif": "image/tiff"}


def _image_file(key: str) -> Path | None:
    for suffix in _IMAGE_TYPES:
        if (path := IMAGERY_DIR / f"{key}{suffix}").exists():
            return path
    return None


@router.get("/imagery")
def imagery_index() -> dict:
    """Which images exist, in which format, with their provenance. Missing ones
    are listed with how to make them, rather than failing."""
    available = []
    for k, (label, period) in IMAGERY.items():
        path = _image_file(k)
        if path is None:
            continue
        sidecar = path.with_suffix(".json")
        meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
        available.append({"id": k, "label": label, "period": period, "format": path.suffix[1:],
                          "scenes": meta.get("scenes"), "dates": meta.get("dates"), "source": meta.get("source"),
                          "bands": meta.get("bands")})
    return {
        "available": available,
        "missing": [k for k in IMAGERY if _image_file(k) is None],
        "how": "Run scripts/remote_sensing/sentinel2_composites.py (public AWS Sentinel-2 archive), or "
               "scripts/gee/imagery_before_after.js in the Earth Engine Code Editor for the 2023 pair.",
    }


@router.get("/imagery/{key}")
def imagery_file(key: str) -> FileResponse:
    if key not in IMAGERY:
        raise HTTPException(status_code=404, detail=f"Unknown imagery '{key}'")
    path = _image_file(key)
    if path is None:
        raise HTTPException(status_code=503, detail=f"{key} missing — run scripts/remote_sensing/sentinel2_composites.py")
    return FileResponse(path, media_type=_IMAGE_TYPES[path.suffix])
