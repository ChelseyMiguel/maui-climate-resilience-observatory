"""Burn severity of the August 2023 Upcountry fires (Sentinel-2 dNBR), and
whether ground that browned 2019 -> 2022 burned more severely.

dNBR = NBR(before) - NBR(after), NBR = (NIR - SWIR2) / (NIR + SWIR2), from the
same cloud-masked median composites as sentinel2_composites.py (20 m):
  before = 1 May - 7 Aug 2023, after = 15 Aug - 31 Oct 2023.
Severity classes are the USGS FIREMON ranges (Key & Benson 2006):
  < 0.10 unburned/regrowth, 0.10-0.27 low, 0.27-0.44 moderate-low,
  0.44-0.66 moderate-high, >= 0.66 high.
These are ranges calibrated for forests; on Maui's grass and shrub they are a
guide, not a field-verified severity.

Seasonal drying between the two windows raises dNBR everywhere, burned or not.
As Key & Benson recommend, the dNBR of unburned ground is subtracted: the
median over every pixel at least 500 m outside all 2023 perimeters in the box
(the "offset", recorded in the report). Without it, most unburned grassland
reads as "low" severity. The raster keeps offset-corrected values everywhere;
the app shows them only inside the perimeters.

Inside each 2023 perimeter (NIFC) in the terrain box, the script reports the
area per class and the mean dNBR by 2019 -> 2022 regional dNDVI bin
(exploratory: regional Sentinel-2 change, not the study raster).

Products: data/research/s2_burn_severity_2023.tif (dnbr, 20 m, EPSG:32604)
          data/research/burn_severity_2023.json
Run:  .venv/bin/python scripts/remote_sensing/burn_severity.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds, transform_geom

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("s2", Path(__file__).with_name("sentinel2_composites.py"))
s2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s2)

CLASSES = [(-9.0, 0.10, "Unburned / regrowth"), (0.10, 0.27, "Low"), (0.27, 0.44, "Moderate-low"),
           (0.44, 0.66, "Moderate-high"), (0.66, 9.0, "High")]
DNDVI_BINS = [(-9.0, -0.2), (-0.2, -0.1), (-0.1, 0.0), (0.0, 9.0)]


def severity_class(v: np.ndarray) -> np.ndarray:
    """Index into CLASSES for each dNBR value (-1 for NaN)."""
    out = np.full(v.shape, -1, dtype=np.int8)
    for k, (lo, hi, _) in enumerate(CLASSES):
        out[(v >= lo) & (v < hi)] = k
    return out


def main() -> int:
    b = transform_bounds("EPSG:4326", s2.UTM, *s2.BBOX, densify_pts=21)
    bounds = tuple(float(np.floor(v / 20) * 20) if i < 2 else float(np.ceil(v / 20) * 20) for i, v in enumerate(b))
    before_items = [i for i in s2.scene_items(2023, range(5, 9)) if i["properties"]["datetime"][:10] <= "2023-08-07"]
    after_items = [i for i in s2.scene_items(2023, range(8, 11)) if i["properties"]["datetime"][:10] >= "2023-08-15"]
    before, _, used_b = s2.composite(before_items, bounds, 20, ["nir", "swir22"])
    after, _, used_a = s2.composite(after_items, bounds, 20, ["nir", "swir22"])
    raw = s2.nd(before["nir"], before["swir22"]) - s2.nd(after["nir"], after["swir22"])
    h, w = raw.shape
    transform = from_bounds(*bounds, w, h)
    fires = json.loads((ROOT / "data" / "research" / "maui_fire_perimeters.geojson").read_text())
    fires2023 = [transform_geom("EPSG:4326", s2.UTM, f["geometry"]) for f in fires["features"] if f["properties"].get("year") == 2023]
    burned = ~geometry_mask(fires2023, out_shape=(h, w), transform=transform)
    near = burned.copy()                                   # grow the burned mask by 500 m (25 px)
    for _ in range(25):
        near[1:] |= near[:-1]; near[:-1] |= near[1:]; near[:, 1:] |= near[:, :-1]; near[:, :-1] |= near[:, 1:]
    offset = float(np.nanmedian(raw[~near]))
    dnbr = (raw - offset).astype("float32")
    s2.write_tif(ROOT / "data" / "research" / "s2_burn_severity_2023.tif", [dnbr], bounds, s2.UTM, ["dnbr"],
                 {"description": "Sentinel-2 dNBR minus the unburned offset, before (1 May-7 Aug 2023) minus after "
                                 f"(15 Aug-31 Oct 2023), 20 m; offset {offset:.4f}"})
    with rasterio.open(ROOT / "data" / "research" / "s2_regional_change.tif") as r:
        prior = r.read(1)                                  # 2019 -> 2022 dNDVI, same 20 m grid
    assert prior.shape == dnbr.shape, "regional change and burn severity grids differ"
    report = {"unburned_offset": round(offset, 4), "unburned_pixels_used": int(np.isfinite(raw[~near]).sum()),
              "method": __doc__.split("\n\n")[1].strip(), "scenes_before": used_b, "scenes_after": used_a,
              "pixel_m": 20, "classes": [c[2] for c in CLASSES], "fires": []}
    for f in fires["features"]:
        if f["properties"].get("year") != 2023:
            continue
        geom = transform_geom("EPSG:4326", s2.UTM, f["geometry"])
        inside = ~geometry_mask([geom], out_shape=(h, w), transform=transform) & np.isfinite(dnbr)
        if inside.sum() < 25:
            continue                                       # outside the terrain box (Lahaina)
        v, cls = dnbr[inside], severity_class(dnbr[inside])
        ha = 20 * 20 / 10000
        by_prior = []
        for lo, hi in DNDVI_BINS:
            m = (prior[inside] >= lo) & (prior[inside] < hi)
            by_prior.append({"dndvi_2019_2022": [lo, hi], "pixels": int(m.sum()),
                             "mean_dnbr": round(float(np.mean(v[m])), 4) if m.sum() else None,
                             "share_moderate_or_high": round(float((v[m] >= 0.27).mean()), 4) if m.sum() else None})
        report["fires"].append({
            "name": f["properties"]["name"], "pixels": int(inside.sum()), "area_ha": round(inside.sum() * ha, 1),
            "mean_dnbr": round(float(np.mean(v)), 4), "median_dnbr": round(float(np.median(v)), 4),
            "class_ha": {CLASSES[k][2]: round(float((cls == k).sum() * ha), 1) for k in range(len(CLASSES))},
            "by_prior_browning": by_prior,
        })
    (ROOT / "data" / "research" / "burn_severity_2023.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["fires"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
