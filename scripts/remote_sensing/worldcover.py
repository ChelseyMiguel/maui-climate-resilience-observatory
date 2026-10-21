"""ESA WorldCover 2021 (v200) land cover for the terrain box, and how the
study's browning splits across land-cover classes.

Source: the public AWS bucket esa-worldcover (CC BY 4.0, ESA WorldCover
project 2021 / Zanaga et al. 2022). 10 m classes from Sentinel-1 + Sentinel-2.

Products:
  data/context/worldcover_2021.tif     uint8 classes, EPSG:4326, terrain box
  data/research/worldcover_browning.json
      for each class inside the study area: pixels, share of the study area,
      and the share of its pixels with study dNDVI < -0.10 (the study raster,
      unchanged; WorldCover resampled to its 10 m UTM grid, nearest)

Run:  .venv/bin/python scripts/remote_sensing/worldcover.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
URL = "/vsicurl/https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N18W159_Map.tif"
BBOX = (-156.45, 20.70, -156.24, 20.88)
CLASSES = {
    10: ("Tree cover", "#006400"), 20: ("Shrubland", "#ffbb22"), 30: ("Grassland", "#ffff4c"),
    40: ("Cropland", "#f096ff"), 50: ("Built-up", "#fa0000"), 60: ("Bare / sparse vegetation", "#b4b4b4"),
    70: ("Snow and ice", "#f0f0f0"), 80: ("Permanent water", "#0064c8"), 90: ("Herbaceous wetland", "#0096a0"),
    95: ("Mangroves", "#00cf75"), 100: ("Moss and lichen", "#fae6a0"),
}

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
if Path("/root/.ccr/ca-bundle.crt").exists():
    os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")


def main() -> int:
    with rasterio.open(URL) as src:
        win = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
        lc = src.read(1, window=win)
        transform = src.window_transform(win)
        crs = src.crs
    out = ROOT / "data" / "context" / "worldcover_2021.tif"
    with rasterio.open(out, "w", driver="GTiff", width=lc.shape[1], height=lc.shape[0], count=1, dtype="uint8",
                       crs=crs, transform=transform, compress="deflate", tiled=True, nodata=0) as dst:
        dst.write(lc, 1)
        dst.write_colormap(1, {k: tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + (255,) for k, (_, c) in CLASSES.items()})
        dst.update_tags(source="ESA WorldCover 10 m 2021 v200 (CC BY 4.0)", classes=json.dumps({k: v[0] for k, v in CLASSES.items()}))

    with rasterio.open(ROOT / "data" / "research" / "dndvi_2019_2022.tif") as r:
        study = r.read(1)
        on_grid = np.zeros(study.shape, dtype="uint8")
        reproject(lc, on_grid, src_transform=transform, src_crs=crs, dst_transform=r.transform, dst_crs=r.crs,
                  resampling=Resampling.nearest)
    valid = ~np.isnan(study)
    rows = []
    for code, (name, colour) in CLASSES.items():
        m = valid & (on_grid == code)
        if m.sum() == 0:
            continue
        rows.append({"code": code, "name": name, "colour": colour, "pixels": int(m.sum()),
                     "share_of_study_area": round(float(m.sum() / valid.sum()), 4),
                     "share_browned_dndvi_lt_-0.10": round(float((study[m] < np.float32(-0.1)).mean()), 4),
                     "median_dndvi": round(float(np.median(study[m])), 4)})
    regional = {CLASSES[int(c)][0]: int(n) for c, n in zip(*np.unique(lc, return_counts=True), strict=True) if int(c) in CLASSES}
    result = {"source": "ESA WorldCover 10 m 2021 v200, tile N18W159 (AWS esa-worldcover), CC BY 4.0",
              "study_area": sorted(rows, key=lambda r: -r["pixels"]), "terrain_box_pixels": regional,
              "classes": {k: {"name": v[0], "colour": v[1]} for k, v in CLASSES.items()}}
    (ROOT / "data" / "research" / "worldcover_browning.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result["study_area"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
