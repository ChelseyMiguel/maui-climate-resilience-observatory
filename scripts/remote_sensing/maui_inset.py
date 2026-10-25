from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.merge import merge

ROOT = Path(__file__).resolve().parents[2]
TILES = [f"/vsicurl/https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{t}_DEM/Copernicus_DSM_COG_30_{t}_DEM.tif"
         for t in ("N20_00_W157_00", "N20_00_W156_00")]
BOUNDS = (-156.72, 20.55, -155.95, 21.05)

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
if Path("/root/.ccr/ca-bundle.crt").exists():
    os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")


def main() -> int:
    sources = [rasterio.open(t) for t in TILES]
    dem, transform = merge(sources, bounds=BOUNDS)
    dem = dem[0].astype("float32")
    land = dem > 0

    lat = (BOUNDS[1] + BOUNDS[3]) / 2
    dx = abs(transform.a) * 111320 * np.cos(np.radians(lat))
    dy = abs(transform.e) * 111320
    d_row, d_col = np.gradient(dem, dy, dx)
    dz_de, dz_dn = d_col, -d_row
    norm = np.sqrt(dz_de ** 2 + dz_dn ** 2 + 1)
    sun = (np.cos(np.radians(45)) * np.sin(np.radians(315)), np.cos(np.radians(45)) * np.cos(np.radians(315)), np.sin(np.radians(45)))
    hs = np.clip((-dz_de * sun[0] - dz_dn * sun[1] + sun[2]) / norm, 0, 1)

    t = np.clip(dem / 3055, 0, 1)
    tint = np.stack([110 + 120 * t, 116 + 100 * t, 92 + 120 * t], axis=-1) * (0.45 + 0.55 * hs[..., None])
    rgba = np.dstack([np.clip(tint, 0, 255).astype("uint8"), np.where(land, 255, 0).astype("uint8")])
    img = Image.fromarray(rgba, "RGBA")
    img = img.resize((img.width // 3, img.height // 3), Image.Resampling.LANCZOS)
    out = ROOT / "data" / "context"
    img.save(out / "maui_inset.png", optimize=True)
    (out / "maui_inset.json").write_text(json.dumps({
        "bounds": BOUNDS, "crs": "EPSG:4326", "size": [img.width, img.height],
        "source": "Copernicus DEM GLO-90 (AWS copernicus-dem-90m), land = elevation > 0"}, indent=1))
    print(img.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
