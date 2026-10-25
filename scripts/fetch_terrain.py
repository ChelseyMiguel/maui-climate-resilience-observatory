from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TILE_DIR = ROOT / "data" / "terrain" / "tiles"
OUT_BIN = ROOT / "data" / "terrain" / "upcountry_dem.i16"
OUT_META = ROOT / "data" / "terrain" / "upcountry_dem.json"

URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 13

BBOX = (-156.45, 20.70, -156.24, 20.88)
GRID_MAX = 320


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def decode_png_rgb(data: bytes) -> tuple[int, int, bytes]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat, width = 8, b"", None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            assert depth == 8 and colour in (2, 6) and interlace == 0, "unsupported PNG"
            bpp = 3 if colour == 2 else 4
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + length

    raw = zlib.decompress(idat)
    stride = width * bpp
    out = bytearray(height * stride)
    prev = bytearray(stride)
    i = 0
    for row in range(height):
        ftype = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for k in range(stride):
            a = line[k - bpp] if k >= bpp else 0
            b = prev[k]
            c = prev[k - bpp] if k >= bpp else 0
            if ftype == 1:
                line[k] = (line[k] + a) & 0xFF
            elif ftype == 2:
                line[k] = (line[k] + b) & 0xFF
            elif ftype == 3:
                line[k] = (line[k] + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[k] = (line[k] + pred) & 0xFF
        out[row * stride:(row + 1) * stride] = line
        prev = line
    if bpp == 4:
        out = bytearray(b for j, b in enumerate(out) if j % 4 != 3)
    return width, height, bytes(out)


def get_tile(z, x, y) -> bytes:
    path = TILE_DIR / str(z) / str(x) / f"{y}.png"
    if not path.exists():
        r = httpx.get(URL.format(z=z, x=x, y=y), timeout=60.0)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path.read_bytes()


def main() -> None:
    west, south, east, north = BBOX
    x0f, y0f = lonlat_to_tile(west, north, ZOOM)
    x1f, y1f = lonlat_to_tile(east, south, ZOOM)
    tx0, ty0, tx1, ty1 = int(x0f), int(y0f), int(x1f), int(y1f)
    print(f"tiles x {tx0}..{tx1}, y {ty0}..{ty1} at z{ZOOM} "
          f"({(tx1 - tx0 + 1) * (ty1 - ty0 + 1)} tiles)")


    tiles_w, tiles_h = tx1 - tx0 + 1, ty1 - ty0 + 1
    W, H = tiles_w * 256, tiles_h * 256
    mosaic = [0.0] * (W * H)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            w, h, rgb = decode_png_rgb(get_tile(ZOOM, tx, ty))
            ox, oy = (tx - tx0) * 256, (ty - ty0) * 256
            for r in range(h):
                base = (oy + r) * W + ox
                for c in range(w):
                    j = (r * w + c) * 3
                    mosaic[base + c] = rgb[j] * 256 + rgb[j + 1] + rgb[j + 2] / 256 - 32768


    px0, py0 = (x0f - tx0) * 256, (y0f - ty0) * 256
    px1, py1 = (x1f - tx0) * 256, (y1f - ty0) * 256
    span_x, span_y = px1 - px0, py1 - py0
    scale = GRID_MAX / max(span_x, span_y)
    gw, gh = max(2, round(span_x * scale)), max(2, round(span_y * scale))


    grid = []
    for gy in range(gh):
        lat = north - gy * (north - south) / (gh - 1)
        sy = lonlat_to_tile(west, lat, ZOOM)[1] * 256 - ty0 * 256
        for gx in range(gw):
            lon = west + gx * (east - west) / (gw - 1)
            sx = lonlat_to_tile(lon, lat, ZOOM)[0] * 256 - tx0 * 256
            ix, iy = min(int(sx), W - 2), min(int(sy), H - 2)
            fx, fy = sx - ix, sy - iy
            a, b = mosaic[iy * W + ix], mosaic[iy * W + ix + 1]
            c, d = mosaic[(iy + 1) * W + ix], mosaic[(iy + 1) * W + ix + 1]
            z = a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy
            grid.append(max(-32768, min(32767, round(z))))

    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(struct.pack(f"<{len(grid)}h", *grid))
    meta = {
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "width": gw, "height": gh,
        "min_m": min(grid), "max_m": max(grid),
        "row_order": "north_to_south",
        "spacing": "linear in latitude and longitude",
        "encoding": "int16 little-endian metres",
        "source": f"AWS Terrain Tiles (Tilezen), Terrarium, z{ZOOM}",
    }
    OUT_META.write_text(json.dumps(meta, indent=2))
    print(f"grid {gw}x{gh}, elevation {meta['min_m']}..{meta['max_m']} m "
          f"-> {OUT_BIN.relative_to(ROOT)} ({OUT_BIN.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
