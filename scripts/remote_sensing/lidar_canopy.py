from __future__ import annotations

import datetime as dt
import http.client
import io
import json
import sys
import time
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import laspy
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "research"
EPT = "https://usgs-lidar-public.s3.amazonaws.com/HI_NOAAMauiOahu_2_B20"
MAX_DEPTH = 11
RES = 2.0
NOISE = (7, 18)
GROUND = 2


CACHE = ROOT / "data" / "cache" / "lidar"


def _get(url: str, tries: int = 5) -> bytes:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except (OSError, http.client.HTTPException):
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def _json(url: str):
    return json.loads(_get(url))


def study_bounds() -> tuple[float, float, float, float]:
    with rasterio.open(OUT / "dndvi_2019_2022.tif") as r:
        return tuple(r.bounds)


def nodes(aoi3857, bounds) -> dict[str, int]:
    def node_box(key):
        d, x, y, _ = map(int, key.split("-"))
        w = (bounds[3] - bounds[0]) / 2 ** d
        return bounds[0] + x * w, bounds[1] + y * w, bounds[0] + (x + 1) * w, bounds[1] + (y + 1) * w

    def hits(key):
        x0, y0, x1, y1 = node_box(key)
        return x1 > aoi3857[0] and x0 < aoi3857[2] and y1 > aoi3857[1] and y0 < aoi3857[3]

    found: dict[str, int] = {}

    def load(key):
        for k, v in _json(f"{EPT}/ept-hierarchy/{key}.json").items():
            if int(k.split("-")[0]) > MAX_DEPTH or not hits(k):
                continue
            if v == -1 and k != key:
                load(k)
            elif v > 0:
                found[k] = v
    load("0-0-0-0")
    return found


def fetch(key: str) -> np.ndarray:
    path = CACHE / f"{key}.laz"
    if not path.exists():
        data = _get(f"{EPT}/ept-data/{key}.laz")
        path.with_suffix(".part").write_bytes(data)
        path.with_suffix(".part").rename(path)
    las = laspy.read(io.BytesIO(path.read_bytes()))
    return np.column_stack([np.asarray(las.x), np.asarray(las.y), np.asarray(las.z),
                            np.asarray(las.classification).astype("float64"), np.asarray(las.gps_time)])


def grid_stat(ix, iy, values, shape, how):
    out = np.full(shape, np.nan)
    flat = iy * shape[1] + ix
    if how == "max":
        order = np.argsort(values)
        out.flat[flat[order]] = values[order]
    else:
        s = np.bincount(flat, weights=values, minlength=out.size)
        n = np.bincount(flat, minlength=out.size)
        with np.errstate(all="ignore"):
            out = (s / n).reshape(shape)
    return out


def fill(a: np.ndarray, passes: int) -> tuple[np.ndarray, np.ndarray]:
    a = a.copy()
    when = np.where(np.isnan(a), -1, 0)
    for p in range(1, passes + 1):
        hole = np.isnan(a)
        if not hole.any():
            break
        pad = np.pad(a, 1, constant_values=np.nan)
        stack = np.stack([pad[1 + dy:pad.shape[0] - 1 + dy, 1 + dx:pad.shape[1] - 1 + dx]
                          for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(stack, axis=0)
        newly = hole & ~np.isnan(m)
        a[newly] = m[newly]
        when[newly] = p
    return a, when


def hillshade(dem: np.ndarray, res: float, az=315.0, alt=45.0) -> np.ndarray:
    d_row, d_col = np.gradient(dem, res)
    dz_de, dz_dn = d_col, -d_row
    norm = np.sqrt(dz_de ** 2 + dz_dn ** 2 + 1)
    a, h = np.radians(az), np.radians(alt)
    sun = (np.cos(h) * np.sin(a), np.cos(h) * np.cos(a), np.sin(h))
    hs = (-dz_de * sun[0] - dz_dn * sun[1] + sun[2]) / norm
    return np.nan_to_num(np.clip(hs, 0, 1) * 255, nan=0).astype("uint8")


def main() -> int:
    west, south, east, north = study_bounds()
    to3857 = Transformer.from_crs(32604, 3857, always_xy=True)
    to_utm = Transformer.from_crs(3857, 32604, always_xy=True)
    xs, ys = to3857.transform([west, east, west, east], [south, south, north, north])
    aoi3857 = (min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20)
    meta = _json(f"{EPT}/ept.json")
    keys = nodes(aoi3857, meta["bounds"])
    print(f"{len(keys)} nodes, {sum(keys.values()):,} points listed", flush=True)

    CACHE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        pts = np.concatenate(list(pool.map(fetch, sorted(keys))))
    e, n = to_utm.transform(pts[:, 0], pts[:, 1])
    z, cls, gps = pts[:, 2], pts[:, 3].astype("uint8"), pts[:, 4]
    inside = (e >= west) & (e < east) & (n > south) & (n <= north) & ~np.isin(cls, NOISE)
    e, n, z, cls, gps = e[inside], n[inside], z[inside], cls[inside], gps[inside]
    print(f"{inside.sum():,} points in the study box", flush=True)

    width, height = round((east - west) / RES), round((north - south) / RES)
    ix = np.clip(((e - west) / RES).astype(int), 0, width - 1)
    iy = np.clip(((north - n) / RES).astype(int), 0, height - 1)
    g = cls == GROUND
    dtm_raw = grid_stat(ix[g], iy[g], z[g], (height, width), "mean")
    dtm, filled = fill(dtm_raw, 8)
    dsm = grid_stat(ix, iy, z, (height, width), "max")
    dsm = np.where(np.isnan(dsm), dtm, dsm)
    chm = np.clip(dsm - dtm, 0, None)
    chm[(filled > 2) | (filled < 0)] = np.nan
    hs = hillshade(dtm, RES)


    def u16(a, scale):
        out = np.full(a.shape, 65535, dtype="uint16")
        ok = np.isfinite(a)
        out[ok] = np.clip(np.round(a[ok] * scale), 0, 65534).astype("uint16")
        return out
    profile = {"driver": "GTiff", "width": width, "height": height, "count": 3, "dtype": "uint16", "crs": "EPSG:32604",
               "transform": from_origin(west, north, RES, RES), "compress": "deflate", "predictor": 2,
               "tiled": True, "nodata": 65535}
    with rasterio.open(OUT / "lidar_aoi.tif", "w", **profile) as dst:
        for i, (band, name) in enumerate([(u16(dtm, 10), "dtm_dm"), (u16(chm, 100), "chm_cm"), (hs.astype("uint16"), "hillshade")], 1):
            dst.write(band, i)
            dst.set_band_description(i, name)
        dst.update_tags(source="USGS 3DEP / NOAA lidar HI_NOAAMauiOahu_2 (2022-2023, QL1), EPT depth <= 11",
                        units="band 1 DTM decimetres, band 2 CHM centimetres (highest return minus ground), band 3 hillshade")


    hag = z - dtm[iy, ix]
    k = max(1, len(z) // 300_000)
    sel = slice(None, None, k)
    z_min = float(np.floor(z.min()))
    rec = np.zeros(len(z[sel]), dtype=[("e", "<u2"), ("n", "<u2"), ("z", "<u2"), ("hag", "<i2"), ("cls", "u1")])
    rec["e"] = np.round((e[sel] - west) * 10)
    rec["n"] = np.round((n[sel] - south) * 10)
    rec["z"] = np.round((z[sel] - z_min) * 100)
    rec["hag"] = np.clip(np.round(np.nan_to_num(hag[sel]) * 100), -32768, 32767)
    rec["cls"] = cls[sel]
    (OUT / "lidar_points.bin").write_bytes(rec.tobytes())

    gps_dates = [dt.datetime(1980, 1, 6, tzinfo=dt.UTC) + dt.timedelta(seconds=float(s) + 1e9) for s in np.percentile(gps, [0, 50, 100])]
    manifest = {
        "source": EPT, "survey": "2022-2023 NOAA/USGS lidar, Hawaii (Maui, Oahu...), QL1, nominal 8 pts/m2",
        "max_depth": MAX_DEPTH, "nodes": len(keys), "points_in_box": int(inside.sum()),
        "ground_points": int(g.sum()), "density_pts_m2": round(float(inside.sum() / ((east - west) * (north - south))), 2),
        "acquired_utc": [d.strftime("%Y-%m-%d") for d in gps_dates],
        "grid": {"crs": "EPSG:32604", "res_m": RES, "width": width, "height": height, "origin": [west, north]},
        "dtm_cells_measured": int((filled == 0).sum()), "dtm_cells_filled": int((filled > 0).sum()),
        "dtm_cells_empty": int((filled < 0).sum()),
        "chm_m_percentiles_5_50_95": [round(float(v), 2) for v in np.nanpercentile(chm, [5, 50, 95])],
        "points_file": {"count": len(rec), "every_kth": int(k), "origin_utm": [west, south], "z_min_m": z_min,
                        "layout": "u16 (e-west) dm, u16 (n-south) dm, u16 (z - z_min) cm, i16 height above ground cm, u8 class"},
    }
    (OUT / "lidar_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
