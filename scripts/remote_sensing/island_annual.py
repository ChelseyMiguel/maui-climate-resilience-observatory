"""Whole-island dry-season NDVI and NBR for Maui, 2017-2025 (Sentinel-2, 60 m).

Same method as sentinel2_composites.py (tile cloud < 60 %, SCL mask, one scene
per acquisition, per-band median, indices from the medians), over all of Maui:
tiles 4QGJ, 4QGH and 4QHJ, all UTM zone 4, merged on one 60 m EPSG:32604 grid.
Ocean is masked with Copernicus DEM GLO-90 (land = elevation > 0), which also
gives the elevation for the elevation-zone statistics.

Values are stored as uint8 codes to keep the repository small:
  code = round((value + 1) * 125), value = code / 125 - 1 (step 0.008), 255 = no data.
60 m suits the whole island; the 10 m study-area products stay the reference.

Products:
  data/research/island_annual.tif      bands ndvi_2017..ndvi_2025, nbr_2017..nbr_2025,
                                       then elevation (uint8 = metres / 13, 255 = sea)
  data/research/island_annual.json     per-year island medians and percentiles, per
                                       elevation zone, scenes and clear-observation counts
Run:  .venv/bin/python scripts/remote_sensing/island_annual.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("s2", Path(__file__).with_name("sentinel2_composites.py"))
s2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s2)

TILES = ("GJ", "GH", "HJ")
RES = 60.0
# Maui in UTM 4N, snapped to 60 m: about -156.70..-155.97 E, 20.56..21.04 N.
WEST, SOUTH, EAST, NORTH = 735000.0, 2274000.0, 812040.0, 2328000.0
YEARS = range(2017, 2026)
ZONES = [(0, 300), (300, 600), (600, 1000), (1000, 1500), (1500, 2200), (2200, 3100)]
DEM = [f"/vsicurl/https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{t}_DEM/Copernicus_DSM_COG_30_{t}_DEM.tif"
       for t in ("N20_00_W157_00", "N20_00_W156_00")]


def encode(v: np.ndarray) -> np.ndarray:
    out = np.full(v.shape, 255, dtype="uint8")
    ok = np.isfinite(v)
    out[ok] = np.clip(np.round((np.clip(v[ok], -1, 1) + 1) * 125), 0, 250).astype("uint8")
    return out


def items_for(year: int) -> list[dict]:
    out = []
    for t in TILES:
        s2.TILE = f"sentinel-s2-l2a-cogs/4/Q/{t}"
        out += s2.scene_items(year, range(5, 10))
    return out


def elevation(shape, transform) -> np.ndarray:
    dem = np.full(shape, np.nan, dtype="float32")
    for url in DEM:
        with rasterio.open(url) as src:
            part = np.full(shape, np.nan, dtype="float32")
            reproject(rasterio.band(src, 1), part, dst_transform=transform, dst_crs="EPSG:32604",
                      resampling=Resampling.average, dst_nodata=np.nan)
            dem = np.where(np.isnan(dem), part, dem)
    return dem


def stats(v: np.ndarray) -> dict | None:
    v = v[np.isfinite(v)]
    if v.size < 50:
        return None
    p = np.percentile(v, [10, 25, 50, 75, 90])
    return {"n": int(v.size), "p10": round(float(p[0]), 4), "p25": round(float(p[1]), 4), "median": round(float(p[2]), 4),
            "p75": round(float(p[3]), 4), "p90": round(float(p[4]), 4)}


def main() -> int:
    bounds = (WEST, SOUTH, EAST, NORTH)
    w, h = round((EAST - WEST) / RES), round((NORTH - SOUTH) / RES)
    transform = from_origin(WEST, NORTH, RES, RES)
    dem = elevation((h, w), transform)
    land = np.isfinite(dem) & (dem > 0)
    ndvi, nbr, report = [], [], {"tiles": TILES, "res_m": RES, "years": {}, "zones": [list(z) for z in ZONES]}
    for year in YEARS:
        items = items_for(year)
        med, count, used = s2.composite(items, bounds, RES, ["red", "nir", "swir22"])
        a, b = s2.nd(med["nir"], med["red"]), s2.nd(med["nir"], med["swir22"])
        a[~land] = np.nan
        b[~land] = np.nan
        ndvi.append(a)
        nbr.append(b)
        zones = [{"zone_m": list(z), "ndvi": stats(a[land & (dem >= z[0]) & (dem < z[1])])} for z in ZONES]
        report["years"][str(year)] = {"scenes": len(used), "candidates": len(items), "ndvi": stats(a[land]), "nbr": stats(b[land]),
                                      "clear_obs_median": int(np.median(count[land])), "zones": zones,
                                      "land_pixels_without_data": int((land & ~np.isfinite(a)).sum())}
        print(year, len(used), report["years"][str(year)]["ndvi"], flush=True)

    # Where the island browned most from 2019 to 2022, by elevation zone.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        d = ndvi[list(YEARS).index(2022)] - ndvi[list(YEARS).index(2019)]
    report["change_2019_2022_by_zone"] = [
        {"zone_m": list(z), **(stats(d[land & (dem >= z[0]) & (dem < z[1])]) or {}),
         "share_below_-0.10": round(float((d[land & (dem >= z[0]) & (dem < z[1])] < -0.1).mean()), 4)} for z in ZONES]
    report["land_pixels"] = int(land.sum())

    elev = np.full((h, w), 255, dtype="uint8")
    elev[land] = np.clip(np.round(dem[land] / 13), 0, 254).astype("uint8")
    profile = {"driver": "GTiff", "width": w, "height": h, "count": 2 * len(YEARS) + 1, "dtype": "uint8",
               "crs": "EPSG:32604", "transform": transform, "compress": "deflate", "predictor": 2, "tiled": True, "nodata": 255}
    names = [f"ndvi_{y}" for y in YEARS] + [f"nbr_{y}" for y in YEARS] + ["elevation_13m"]
    with rasterio.open(ROOT / "data" / "research" / "island_annual.tif", "w", **profile) as dst:
        for i, band in enumerate([encode(x) for x in ndvi + nbr] + [elev], 1):
            dst.write(band, i)
            dst.set_band_description(i, names[i - 1])
        dst.update_tags(encoding="value = code/125 - 1 (indices); metres = code*13 (elevation); 255 = no data",
                        description="Sentinel-2 L2A dry-season (May-Sep) median NDVI/NBR, Maui, 60 m")
    (ROOT / "data" / "research" / "island_annual.json").write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
