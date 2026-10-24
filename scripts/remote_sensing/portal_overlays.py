"""Overlay the Hawaii Statewide GIS layers on our whole-island Sentinel-2 results.

Questions, answered on the 60 m island grid (data/research/island_annual.tif):
  1. How much did each moisture zone brown from the 2019 to the 2022 dry season?
  2. Did former sugarcane/pineapple land brown differently from the rest?
  3. How did land inside each DLNR fire-risk rating brown?
  4. Which DLNR fire-risk rating did each 2023 fire burn in?
  5. What are the study area's own moisture zone, fire rating, response zone and history?

"Browned" = dry-season NDVI fell by more than 0.10 from 2019 to 2022, the study's
threshold, here at 60 m (exploratory; the 10 m study raster is unchanged). The fire-risk
polygons cover populated areas only, so most land is "not rated"; that is reported as such,
never as low risk.

Output: data/research/portal_overlays.json
Run:    .venv/bin/python scripts/remote_sensing/portal_overlays.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.warp import transform_geom

ROOT = Path(__file__).resolve().parents[2]
PORTAL = ROOT / "data" / "context" / "hawaii_portal"
RISK_ORDER = {"High": 3, "Medium": 2, "Low": 1}          # where polygons overlap, the higher rating wins
MOISTURE = ["Arid", "Very Dry", "Moderately Dry", "Seasonal Mesic", "Moist Mesic", "Moderately Wet", "Very Wet"]
THRESHOLD = -0.1


def feats(name: str) -> list[dict]:
    return json.loads((PORTAL / f"{name}.geojson").read_text())["features"]


def burn(shapes, shape, transform, default=1):
    """Rasterise (geometry, value) pairs from EPSG:4326 onto the island grid."""
    pairs = [(transform_geom("EPSG:4326", "EPSG:32604", g), v) for g, v in shapes if g]
    return rasterize(pairs, out_shape=shape, transform=transform, fill=0, dtype="uint8") if pairs else np.zeros(shape, "uint8")


def stats(change: np.ndarray, n19: np.ndarray, n22: np.ndarray, mask: np.ndarray) -> dict:
    m = mask & np.isfinite(change)
    if m.sum() < 30:
        return {"pixels": int(m.sum())}
    return {"pixels": int(m.sum()), "area_km2": round(float(m.sum() * 0.0036), 1),
            "ndvi_2019": round(float(np.median(n19[m])), 3), "ndvi_2022": round(float(np.median(n22[m])), 3),
            "median_change": round(float(np.median(change[m])), 4),
            "share_browned": round(float((change[m] < THRESHOLD).mean()), 4)}


def main() -> int:
    with rasterio.open(ROOT / "data" / "research" / "island_annual.tif") as r:
        shape, transform = (r.height, r.width), r.transform
        tags = r.tags()
        years = [int(d.split("_")[1]) for d in r.descriptions if d and d.startswith("ndvi_")]
        bands = {y: r.read(1 + years.index(y)) for y in (2019, 2022)}
    assert "code/125" in tags["encoding"], "island raster encoding changed"

    def dec(a):
        return np.where(a == 255, np.nan, a / 125.0 - 1).astype("float32")

    n19, n22 = dec(bands[2019]), dec(bands[2022])
    change = n22 - n19
    land = np.isfinite(change)

    out: dict = {"threshold": THRESHOLD, "pixel_m": 60, "land_pixels": int(land.sum())}

    zones = burn([(f["geometry"], MOISTURE.index(f["properties"]["moisturezone"]) + 1) for f in feats("moisture_zones")], shape, transform)
    out["moisture_zones"] = [{"zone": name, **stats(change, n19, n22, land & (zones == i + 1))} for i, name in enumerate(MOISTURE)]

    plantation = {}
    for crop in ("sugarcane", "pineapple"):
        files = [p.stem for p in PORTAL.glob(f"{crop}_*.geojson")]
        plantation[crop] = burn([(f["geometry"], 1) for k in files for f in feats(k)], shape, transform) == 1
    ever = plantation["sugarcane"] | plantation["pineapple"]
    out["plantation_history"] = {
        "any_plantation_1900_1937": stats(change, n19, n22, land & ever),
        "sugarcane": stats(change, n19, n22, land & plantation["sugarcane"]),
        "pineapple": stats(change, n19, n22, land & plantation["pineapple"]),
        "never_plantation": stats(change, n19, n22, land & ~ever),
        "share_of_island_land_in_plantation": round(float((land & ever).sum() / land.sum()), 4),
    }
    # Plantation land is mostly dry, so compare like with like: inside each moisture zone.
    out["plantation_within_moisture_zone"] = [
        {"zone": name, "plantation": stats(change, n19, n22, land & ever & (zones == i + 1)),
         "other": stats(change, n19, n22, land & ~ever & (zones == i + 1))} for i, name in enumerate(MOISTURE)]

    risk = burn([(f["geometry"], RISK_ORDER[f["properties"]["risk_rating"]])
                 for f in sorted(feats("fire_risk"), key=lambda f: RISK_ORDER.get(f["properties"]["risk_rating"], 0))
                 if f["properties"]["risk_rating"] in RISK_ORDER], shape, transform)
    out["fire_risk_rating"] = {name: stats(change, n19, n22, land & (risk == v)) for name, v in RISK_ORDER.items()}
    out["fire_risk_rating"]["Not rated"] = stats(change, n19, n22, land & (risk == 0))

    fires = json.loads((ROOT / "data" / "research" / "maui_fire_perimeters.geojson").read_text())["features"]
    out["fires_2023_by_rating"] = []
    for f in fires:
        if f["properties"].get("year") != 2023:
            continue
        m = burn([(f["geometry"], 1)], shape, transform) == 1
        if m.sum() < 5:
            continue
        out["fires_2023_by_rating"].append({
            "fire": f["properties"]["name"], "pixels": int(m.sum()),
            "share_by_rating": {name: round(float((m & (risk == v)).sum() / m.sum()), 3) for name, v in [("High", 3), ("Medium", 2), ("Low", 1), ("Not rated", 0)]}})

    cx, cy = Transformer.from_crs(4326, 32604, always_xy=True).transform(-156.344856, 20.838722)
    rows_, cols_ = np.mgrid[0:shape[0], 0:shape[1]]
    circle = np.hypot(transform.c + (cols_ + 0.5) * transform.a - cx, transform.f + (rows_ + 0.5) * transform.e - cy) <= 1500
    n = int(circle.sum())
    out["study_area"] = {
        "pixels_60m": n,
        "moisture_zone_share": {name: round(float((circle & (zones == i + 1)).sum() / n), 3) for i, name in enumerate(MOISTURE)},
        "fire_risk_share": {name: round(float((circle & (risk == v)).sum() / n), 3) for name, v in [("High", 3), ("Medium", 2), ("Low", 1), ("Not rated", 0)]},
        "former_plantation_share": round(float((circle & ever).sum() / n), 3),
    }
    (ROOT / "data" / "research" / "portal_overlays.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("plantation_within_moisture_zone", "study_area")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
