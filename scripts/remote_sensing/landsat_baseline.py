"""Landsat dry-season NDVI for the study area, 2000 onward, from Microsoft's
Planetary Computer (free; no account: an anonymous SAS token signs the reads).

Mirrors section 6 of notebooks/gee_exports.ipynb exactly, so either source can
fill the app's "Was 2022 unusual?" chart (lib/landsat_baseline.py):
  * Landsat 5 TM, 7 ETM+, 8 and 9 OLI, Collection 2 Level-2, Tier 1 only;
  * May-September of each year;
  * per scene: QA_PIXEL bits 1 (dilated cloud), 3 (cloud), 4 (cloud shadow)
    masked, reflectance = DN * 0.0000275 - 0.2, NDVI from NIR and red;
  * per-pixel median NDVI over the year's scenes, then the mean over the
    1.5 km study-area circle at 30 m.

Path 063 is stored in UTM zone 5; scenes are warped (nearest neighbour, so QA
bits are not blended) onto a 30 m EPSG:32604 grid sharing the study raster's
origin. Landsat 7 scan-line gaps after May 2003 are no-data and simply masked.

Products:
  data/research/pukalani_landsat_ndvi_dryseason.csv   year, ndvi_dry_median, n_scenes,
                                                      sensors, clear_pixel_share
  data/research/landsat_aoi_annual.tif                per-pixel dry-season median NDVI,
                                                      one band per year, 30 m
  data/research/landsat_manifest.json                 scenes used per year

Run:  .venv/bin/python scripts/remote_sensing/landsat_baseline.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
import rasterio.errors
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "research"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2"
CENTRE = (-156.344856, 20.838722)              # same as every script here
RADIUS = 1500.0
YEARS = range(2000, 2026)
PLATFORMS = {"landsat-5": ("nir08", "red"), "landsat-7": ("nir08", "red"),
             "landsat-8": ("nir08", "red"), "landsat-9": ("nir08", "red")}
CLOUD_BITS = (1 << 1) | (1 << 3) | (1 << 4)
# 30 m grid on the study raster's origin (774820, 2308080), EPSG:32604, 100 x 100.
ORIGIN, RES, SIZE = (774820.0, 2308080.0), 30.0, 100
CACHE = ROOT / "data" / "cache" / "landsat"          # gitignored

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
if Path("/root/.ccr/ca-bundle.crt").exists():
    os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")

_token = {"value": None, "expires": 0.0}
_lock = threading.Lock()


def _open(req, tries: int = 6) -> bytes:
    """urlopen with back-off: the Planetary Computer rate-limits (HTTP 429)."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 2 ** (attempt + 1)))
    raise AssertionError("unreachable")


def token() -> str:
    """Anonymous SAS token for the landsat-c2 container, shared by all threads
    and refreshed before it expires."""
    with _lock:
        if time.time() > _token["expires"] - 300:
            _token["value"] = json.loads(_open(SAS))["token"]
            _token["expires"] = time.time() + 45 * 60
        return _token["value"]


def search(year: int) -> list[dict]:
    body = {"collections": ["landsat-c2-l2"], "intersects": {"type": "Point", "coordinates": list(CENTRE)},
            "datetime": f"{year}-05-01T00:00:00Z/{year}-09-30T23:59:59Z", "limit": 100,
            "query": {"landsat:collection_category": {"eq": "T1"}, "platform": {"in": list(PLATFORMS)}}}
    req = urllib.request.Request(STAC, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    feats = json.loads(_open(req))["features"]
    return sorted(feats, key=lambda f: f["properties"]["datetime"])


def grid():
    transform = from_origin(*ORIGIN, RES, RES)
    rows, cols = np.mgrid[0:SIZE, 0:SIZE]
    e = ORIGIN[0] + (cols + 0.5) * RES
    n = ORIGIN[1] - (rows + 0.5) * RES
    from pyproj import Transformer
    ce, cn = Transformer.from_crs(4326, 32604, always_xy=True).transform(*CENTRE)
    return transform, np.hypot(e - ce, n - cn) <= RADIUS


def scene_ndvi(item: dict, transform) -> np.ndarray | None:
    """One scene's NDVI on the 30 m study grid (NaN = masked or no data), or
    None if a file can't be read (recorded in the manifest, never filled)."""
    try:
        return _scene_ndvi(item, transform)
    except rasterio.errors.RasterioIOError as e:
        print(f"  skipped {item['id']}: {str(e)[:120]}", flush=True)
        return None


def _scene_ndvi(item: dict, transform) -> np.ndarray:
    nir_key, red_key = PLATFORMS[item["properties"]["platform"]]
    out = {}
    for key in (nir_key, red_key, "qa_pixel"):
        href = item["assets"][key]["href"] + "?" + token()
        with rasterio.open("/vsicurl/" + href) as src, WarpedVRT(
                src, crs="EPSG:32604", transform=transform, width=SIZE, height=SIZE,
                resampling=Resampling.nearest, src_nodata=src.nodata) as vrt:
            out[key] = vrt.read(1)
    qa = out["qa_pixel"].astype("uint16")
    bad = ((qa & CLOUD_BITS) != 0) | (out[nir_key] == 0) | (out[red_key] == 0) | (qa == 1)   # QA bit 0 = fill
    nir = out[nir_key].astype("float32") * 0.0000275 - 0.2
    red = out[red_key].astype("float32") * 0.0000275 - 0.2
    with np.errstate(all="ignore"):
        ndvi = (nir - red) / (nir + red)
    ndvi[bad] = np.nan
    return ndvi


def main() -> int:
    transform, circle = grid()
    CACHE.mkdir(parents=True, exist_ok=True)
    rows, bands, manifest = [], [], {"source": "Microsoft Planetary Computer, landsat-c2-l2 (Tier 1)",
                                     "season": "May-Sep", "masked_qa_bits": [1, 3, 4], "years": {}}
    for year in YEARS:
        items = search(year)
        cached = CACHE / f"{year}.npz"
        if cached.exists():                                     # resumable reruns
            z = np.load(cached, allow_pickle=False)
            stack, skipped = list(z["stack"]), list(z["skipped"])
        else:
            with ThreadPoolExecutor(max_workers=4) as pool:
                got = list(pool.map(lambda it: scene_ndvi(it, transform), items))
            stack = [g for g in got if g is not None]
            skipped = [it["id"] for it, g in zip(items, got, strict=True) if g is None]
            np.savez_compressed(cached, stack=np.array(stack, dtype="float32").reshape(-1, SIZE, SIZE), skipped=np.array(skipped, dtype=str))
        if stack:
            with np.errstate(all="ignore"):
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    med = np.nanmedian(np.stack(stack), axis=0).astype("float32")
        else:
            med = np.full((SIZE, SIZE), np.nan, dtype="float32")
        med[~circle] = np.nan
        inside = med[circle]
        clear = float(np.isfinite(inside).mean())
        value = float(np.nanmean(inside)) if np.isfinite(inside).any() else -9999.0
        sensors = "+".join(sorted({it["properties"]["platform"].replace("landsat-", "LANDSAT_") for it in items if it["id"] not in skipped}))
        rows.append({"year": year, "ndvi_dry_median": round(value, 6), "n_scenes": len(stack),
                     "sensors": sensors, "clear_pixel_share": round(clear, 4)})
        bands.append(med)
        manifest["years"][str(year)] = [it["id"] for it in items if it["id"] not in skipped]
        if skipped:
            manifest.setdefault("unreadable", {})[str(year)] = skipped
        print(year, rows[-1], flush=True)

    with (OUT / "pukalani_landsat_ndvi_dryseason.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    profile = {"driver": "GTiff", "width": SIZE, "height": SIZE, "count": len(bands), "dtype": "float32",
               "crs": "EPSG:32604", "transform": transform, "compress": "deflate", "predictor": 3, "nodata": np.nan}
    with rasterio.open(OUT / "landsat_aoi_annual.tif", "w", **profile) as dst:
        for i, (b, y) in enumerate(zip(bands, YEARS, strict=True), 1):
            dst.write(b, i)
            dst.set_band_description(i, f"ndvi_{y}")
        dst.update_tags(description="Landsat C2 L2 dry-season (May-Sep) median NDVI, 30 m, study AOI",
                        years=",".join(map(str, YEARS)))
    (OUT / "landsat_manifest.json").write_text(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
