"""Sentinel-2 L2A composites for the Observatory, from the public AWS archive.

No account or Earth Engine needed: the Element 84 / AWS "sentinel-cogs" bucket
holds every Level-2A scene as Cloud-Optimised GeoTIFFs, and only the pixels
inside our windows are read (HTTP range requests).

Method (mirrors scripts/gee/imagery_before_after.js and the study):
  * tile 4QGJ (UTM 4N, EPSG:32604 -- the same grid as the study rasters);
  * scenes with tile cloud cover < 60 % (GEE: CLOUDY_PIXEL_PERCENTAGE < 60);
  * per-pixel mask from the Scene Classification Layer: SCL 0 (no data),
    1 (saturated/defective), 3 (cloud shadow), 8/9 (cloud), 10 (cirrus);
  * reflectance = DN * 0.0001. From processing baseline 04.00 ESA adds +1000 to
    the DNs; this archive has already removed it when the item says
    earthsearch:boa_offset_applied (checked: open-ocean NIR DNs are ~700 under
    baselines 03.00, 04.00 and 05.09 alike), so the raster:bands offset is NOT
    applied again. Same harmonisation as GEE's S2_SR_HARMONIZED;
  * one scene per acquisition: where a date was reprocessed (_0_/_1_ items),
    only the highest processing baseline is kept;
  * per-band median of the clear observations, then indices from the medians.

Products (all written under data/):
  research/s2_aoi_annual.tif        dry-season (May-Sep) NDVI for 2017-2025 at
                                    10 m on the study raster's exact grid, plus
                                    NBR and clear-observation counts per year
  research/s2_regional_change.tif   2019 -> 2022 dry-season dNDVI and dNBR, 20 m,
                                    for the whole terrain box (exploratory)
  imagery/<id>.jpg + <id>.json      true-colour and colour-infrared images on the
                                    terrain box's EPSG:4326 grid (2048 x 1877), for
                                    the Map Explorer and the 3D view
  research/s2_manifest.json         every scene used, filters and validation

Run:  .venv/bin/pip install -r requirements-data.txt
      .venv/bin/python scripts/remote_sensing/sentinel2_composites.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUCKET = "https://sentinel-cogs.s3.us-west-2.amazonaws.com"
TILE = "sentinel-s2-l2a-cogs/4/Q/GJ"
UTM = "EPSG:32604"
MAX_CLOUD = 60
BAD_SCL = (0, 1, 3, 8, 9, 10)
# The terrain box (data/terrain/upcountry_dem.json) and the 3D view's image grid.
BBOX = (-156.45, 20.70, -156.24, 20.88)
IMAGE_SIZE = (2048, 1877)
DRY = (5, 9)                       # May..September, the study's dry season
YEARS = range(2017, 2026)

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
if Path("/root/.ccr/ca-bundle.crt").exists():          # sandbox proxy CA
    os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def scene_items(year: int, months: range) -> list[dict]:
    """STAC items for tile 4QGJ in the given months, cloud < MAX_CLOUD."""
    out = []
    for m in months:
        xml = _get(f"{BUCKET}/?list-type=2&prefix={TILE}/{year}/{m}/&delimiter=/").decode()
        for prefix in re.findall(r"<Prefix>([^<]+/)</Prefix>", xml)[1:]:
            name = prefix.rstrip("/").split("/")[-1]
            item = json.loads(_get(f"{BUCKET}/{prefix}{name}.json"))
            if item["properties"].get("eo:cloud_cover", 100) < MAX_CLOUD:
                out.append(item)
    return latest_per_acquisition(out)


def latest_per_acquisition(items: list[dict]) -> list[dict]:
    """One item per acquisition time: where a date was reprocessed (_0_/_1_
    items), keep the highest processing baseline. Sorted by time."""
    best: dict[str, dict] = {}
    for it in items:
        key = it["properties"]["datetime"][:19]
        if key not in best or it["properties"].get("s2:processing_baseline", "") > best[key]["properties"].get("s2:processing_baseline", ""):
            best[key] = it
    return sorted(best.values(), key=lambda i: i["properties"]["datetime"])


def reflectance_offset(item: dict, asset: dict) -> float:
    """The additive reflectance offset still to apply: none when the archive has
    already removed ESA's +1000 DN offset (earthsearch:boa_offset_applied)."""
    if item["properties"].get("earthsearch:boa_offset_applied"):
        return 0.0
    return (asset.get("raster:bands") or [{}])[0].get("offset", 0.0)


def _read(item: dict, asset: str, bounds, res: float) -> np.ndarray:
    """One asset over UTM `bounds` at `res` metres, as reflectance (or SCL codes)."""
    a = item["assets"][asset]
    w = round((bounds[2] - bounds[0]) / res)
    h = round((bounds[3] - bounds[1]) / res)
    with rasterio.open("/vsicurl/" + a["href"]) as src:
        win = from_bounds(*bounds, src.transform)
        arr = src.read(1, window=win, out_shape=(h, w), boundless=True, fill_value=0,
                       resampling=Resampling.nearest if asset == "scl" else Resampling.average)
    if asset == "scl":
        return arr
    band = (a.get("raster:bands") or [{}])[0]
    refl = arr.astype("float32") * band.get("scale", 1e-4) + reflectance_offset(item, a)
    refl[arr == 0] = np.nan
    return refl


def composite(items: list[dict], bounds, res: float, assets: list[str]) -> tuple[dict, np.ndarray, list[str]]:
    """Median of clear observations per asset, the clear count, and the scenes used."""
    def scene(item):
        scl = _read(item, "scl", bounds, res)
        clear = ~np.isin(scl, BAD_SCL)
        if not clear.any():
            return None
        bands = {}
        for asset in assets:
            b = _read(item, asset, bounds, res)
            b[~clear] = np.nan
            bands[asset] = b
        return item["id"], clear, bands

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [r for r in pool.map(scene, items) if r is not None]
    if not results:
        raise RuntimeError("no clear observations")
    count = np.sum([r[1] for r in results], axis=0).astype("uint8")
    med = {}
    for asset in assets:
        stack = np.stack([r[2][asset] for r in results])
        with np.errstate(all="ignore"):
            med[asset] = np.nanmedian(stack, axis=0).astype("float32")
    return med, count, [r[0] for r in results]


def _date(scene_id: str) -> str:
    """S2A_4QGJ_20190705_0_L2A -> 2019-07-05."""
    d = scene_id.split("_")[2]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def nd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        return ((a - b) / (a + b)).astype("float32")


def study_grid() -> tuple[tuple, int, int, np.ndarray]:
    with rasterio.open(DATA / "research" / "dndvi_2019_2022.tif") as r:
        return tuple(r.bounds), r.width, r.height, r.read(1)


def write_tif(path: Path, bands: list[np.ndarray], bounds, crs: str, names: list[str], tags: dict) -> None:
    h, w = bands[0].shape
    profile = {"driver": "GTiff", "width": w, "height": h, "count": len(bands), "dtype": bands[0].dtype,
               "crs": crs, "transform": transform_from_bounds(*bounds, w, h), "compress": "deflate",
               "predictor": 3 if bands[0].dtype == np.float32 else 2, "tiled": True,
               "nodata": np.nan if bands[0].dtype == np.float32 else None}
    with rasterio.open(path, "w", **profile) as dst:
        for i, (b, n) in enumerate(zip(bands, names, strict=True), 1):
            dst.write(b, i)
            dst.set_band_description(i, n)
        dst.update_tags(**tags)


def to_image(rgb: list[np.ndarray], src_bounds, out: Path, meta: dict, lo=0.0, hi=0.3, gamma=1.3) -> None:
    """Stretch three reflectance bands (as GEE visualize) and reproject to the terrain
    box's EPSG:4326 grid, saved as a JPEG with a JSON sidecar."""
    from PIL import Image

    W, H = IMAGE_SIZE
    dst_t = transform_from_bounds(*BBOX, W, H)
    channels = []
    for band in rgb:
        h, w = band.shape
        dst = np.full((H, W), np.nan, dtype="float32")
        reproject(band, dst, src_transform=transform_from_bounds(*src_bounds, w, h), src_crs=UTM,
                  dst_transform=dst_t, dst_crs="EPSG:4326", resampling=Resampling.bilinear,
                  src_nodata=np.nan, dst_nodata=np.nan)
        v = np.clip((dst - lo) / (hi - lo), 0, 1) ** (1 / gamma)
        channels.append(np.nan_to_num(v * 255, nan=0).astype("uint8"))
    Image.fromarray(np.dstack(channels)).save(out.with_suffix(".jpg"), quality=88, optimize=True)
    out.with_suffix(".json").write_text(json.dumps({**meta, "bbox": BBOX, "crs": "EPSG:4326", "size": IMAGE_SIZE}, indent=1))


def main() -> int:
    manifest: dict = {"source": f"{BUCKET}/{TILE}", "max_tile_cloud": MAX_CLOUD, "masked_scl": BAD_SCL,
                      "season": "May-Sep", "products": {}}
    imagery = DATA / "imagery"
    imagery.mkdir(exist_ok=True)

    # 1. Study area, every dry season, on the study raster's exact 10 m grid.
    sbounds, _, _, study = study_grid()
    ndvi, nbr, counts, names = [], [], [], []
    for year in YEARS:
        items = scene_items(year, range(DRY[0], DRY[1] + 1))
        med, count, used = composite(items, sbounds, 10, ["red", "nir", "swir22"])
        ndvi.append(nd(med["nir"], med["red"]))
        nbr.append(nd(med["nir"], med["swir22"]))
        counts.append(count)
        names.append(str(year))
        manifest["products"][f"aoi_{year}"] = {"scenes": used, "candidates": len(items),
                                               "median_clear_obs": int(np.median(count))}
        print(f"AOI {year}: {len(used)} scenes, median {int(np.median(count))} clear obs/pixel", flush=True)
    mask = np.isnan(study)
    for arrs in (ndvi, nbr):
        for a in arrs:
            a[mask] = np.nan                                  # same AOI circle as the study
    write_tif(DATA / "research" / "s2_aoi_annual.tif",
              ndvi + nbr + [c.astype("float32") for c in counts], sbounds, UTM,
              [f"ndvi_{n}" for n in names] + [f"nbr_{n}" for n in names] + [f"clear_obs_{n}" for n in names],
              {"description": "Sentinel-2 L2A dry-season (May-Sep) median composites, study AOI, 10 m",
               "years": ",".join(names)})

    # Validation against the study's own dNDVI (same grid, same period).
    mine = ndvi[names.index("2022")] - ndvi[names.index("2019")]
    ok = ~np.isnan(mine) & ~np.isnan(study)
    r = float(np.corrcoef(mine[ok], study[ok])[0, 1])
    both = (mine[ok] < -0.1) == (study[ok] < -0.1)
    manifest["validation_vs_study_dndvi"] = {
        "pixels": int(ok.sum()), "pearson_r": round(r, 4),
        "mean_difference": round(float(np.mean(mine[ok] - study[ok])), 4),
        "rmse": round(float(np.sqrt(np.mean((mine[ok] - study[ok]) ** 2))), 4),
        "class_agreement_at_-0.10": round(float(both.mean()), 4),
        "share_below_-0.10_this_pipeline": round(float((mine[ok] < -0.1).mean()), 4),
        "share_below_-0.10_study": round(float((study[ok] < -0.1).mean()), 4),
    }
    print("validation:", manifest["validation_vs_study_dndvi"], flush=True)

    # 2. Regional composites on the terrain box (20 m): imagery and exploratory change.
    rbounds = transform_bounds("EPSG:4326", UTM, *BBOX, densify_pts=21)
    rbounds = tuple(float(np.floor(v / 20) * 20) if i < 2 else float(np.ceil(v / 20) * 20) for i, v in enumerate(rbounds))
    periods = {
        "s2_dry_2019": ("Dry season 2019 (May–Sep)", [(2019, range(5, 10))]),
        "s2_dry_2022": ("Dry season 2022 (May–Sep)", [(2022, range(5, 10))]),
        "before_2023": ("Before the fires: 1 May – 7 Aug 2023", [(2023, range(5, 9))]),
        "after_2023": ("After the fires: 15 Aug – 31 Oct 2023", [(2023, range(8, 11))]),
    }
    regional = {}
    for key, (label, spans) in periods.items():
        items = [i for y, ms in spans for i in scene_items(y, ms)]
        if key == "before_2023":
            items = [i for i in items if i["properties"]["datetime"][:10] <= "2023-08-07"]
        if key == "after_2023":
            items = [i for i in items if i["properties"]["datetime"][:10] >= "2023-08-15"]
        med, count, used = composite(items, rbounds, 20, ["red", "green", "blue", "nir", "swir22"])
        regional[key] = med
        meta = {"label": label, "source": "Sentinel-2 L2A (AWS sentinel-cogs), tile 4QGJ, 20 m median of cloud-masked scenes",
                "scenes": len(used), "dates": [_date(used[0]), _date(used[-1])]}
        to_image([med["red"], med["green"], med["blue"]], rbounds, imagery / key, {**meta, "bands": "B4-B3-B2 (true colour)"})
        if key.startswith("s2_dry"):
            to_image([med["nir"], med["red"], med["green"]], rbounds, imagery / f"{key}_cir",
                     {**meta, "label": label + " · colour infrared", "bands": "B8-B4-B3 (colour infrared: vegetation red)"},
                     hi=0.45, gamma=1.0)
        manifest["products"][key] = {"scenes": used, "candidates": len(items),
                                     "median_clear_obs": int(np.median(count))}
        print(f"{key}: {len(used)} scenes", flush=True)

    d_ndvi = nd(regional["s2_dry_2022"]["nir"], regional["s2_dry_2022"]["red"]) - nd(regional["s2_dry_2019"]["nir"], regional["s2_dry_2019"]["red"])
    d_nbr = nd(regional["s2_dry_2022"]["nir"], regional["s2_dry_2022"]["swir22"]) - nd(regional["s2_dry_2019"]["nir"], regional["s2_dry_2019"]["swir22"])
    write_tif(DATA / "research" / "s2_regional_change.tif", [d_ndvi, d_nbr], rbounds, UTM, ["dndvi", "dnbr"],
              {"description": "Exploratory: Sentinel-2 L2A dry-season 2022 minus 2019, 20 m, terrain box. Not the study raster."})
    manifest["regional_bounds_utm"] = rbounds
    (DATA / "research" / "s2_manifest.json").write_text(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
