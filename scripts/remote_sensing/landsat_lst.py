from __future__ import annotations

import csv
import importlib.util
import json
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
import rasterio.errors
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

_spec = importlib.util.spec_from_file_location("ls", Path(__file__).with_name("landsat_baseline.py"))
ls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ls)

YEARS = range(2013, 2026)


def scene_lst(item: dict, transform) -> np.ndarray | None:
    try:
        out = {}
        for key in ("lwir11", "qa_pixel"):
            href = item["assets"][key]["href"] + "?" + ls.token()
            with rasterio.open("/vsicurl/" + href) as src, WarpedVRT(
                    src, crs="EPSG:32604", transform=transform, width=ls.SIZE, height=ls.SIZE,
                    resampling=Resampling.nearest, src_nodata=src.nodata) as vrt:
                out[key] = vrt.read(1)
    except (rasterio.errors.RasterioIOError, KeyError) as e:
        print(f"  skipped {item['id']}: {str(e)[:100]}", flush=True)
        return None
    qa = out["qa_pixel"].astype("uint16")
    bad = ((qa & ls.CLOUD_BITS) != 0) | (out["lwir11"] == 0) | (qa == 1)
    c = out["lwir11"].astype("float32") * 0.00341802 + 149.0 - 273.15
    c[bad] = np.nan
    return c


def main() -> int:
    transform, circle = ls.grid()
    rows, bands, used = [], [], {}
    for year in YEARS:
        items = [i for i in ls.search(year) if i["properties"]["platform"] in ("landsat-8", "landsat-9")]
        with ThreadPoolExecutor(max_workers=4) as pool:
            got = [g for g in pool.map(lambda it: scene_lst(it, transform), items) if g is not None]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(np.stack(got), axis=0).astype("float32") if got else np.full((ls.SIZE, ls.SIZE), np.nan, "float32")
        med[~circle] = np.nan
        inside = med[circle]
        rows.append({"year": year, "lst_c_median": round(float(np.nanmean(inside)), 3) if np.isfinite(inside).any() else None,
                     "n_scenes": len(got), "sensors": "+".join(sorted({i["properties"]["platform"] for i in items}))})
        bands.append(med)
        used[str(year)] = [i["id"] for i in items]
        print(rows[-1], flush=True)
    out = ls.OUT
    with (out / "landsat_lst_dryseason.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    profile = {"driver": "GTiff", "width": ls.SIZE, "height": ls.SIZE, "count": len(bands), "dtype": "float32",
               "crs": "EPSG:32604", "transform": transform, "compress": "deflate", "predictor": 3, "nodata": np.nan}
    with rasterio.open(out / "landsat_lst_annual.tif", "w", **profile) as dst:
        for i, (b, y) in enumerate(zip(bands, YEARS, strict=True), 1):
            dst.write(b, i)
            dst.set_band_description(i, f"lst_c_{y}")
        dst.update_tags(description="Landsat 8/9 C2 L2 surface temperature, dry-season (May-Sep) median, degC, 30 m",
                        years=",".join(map(str, YEARS)))
    (out / "landsat_lst_manifest.json").write_text(json.dumps({"years": used}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
