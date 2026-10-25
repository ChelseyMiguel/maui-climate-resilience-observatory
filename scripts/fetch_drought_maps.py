from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "context" / "drought_maps"
URL = "https://droughtmonitor.unl.edu/data/json/usdm_{d}.json"
MAUI = (-156.75, 20.45, -155.95, 21.10)
YEARS = range(2018, 2025)
CATEGORY = {0: "D0 Abnormally dry", 1: "D1 Moderate drought", 2: "D2 Severe drought",
            3: "D3 Extreme drought", 4: "D4 Exceptional drought"}


def tuesday_nearest_aug8(year: int) -> date:
    target = date(year, 8, 8)
    back = (target.weekday() - 1) % 7
    prev = target - timedelta(days=back)
    nxt = prev + timedelta(days=7)
    return prev if (target - prev) <= (nxt - target) else nxt


def touches_maui(polygon: list) -> bool:
    xs = [x for x, _ in polygon[0]]
    ys = [y for _, y in polygon[0]]
    w, s, e, n = MAUI
    return not (max(xs) < w or min(xs) > e or max(ys) < s or min(ys) > n)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for year in YEARS:
        week = tuesday_nearest_aug8(year)
        r = httpx.get(URL.format(d=week.strftime("%Y%m%d")), timeout=180)
        r.raise_for_status()
        features = []
        for f in r.json().get("features", []):
            g = f.get("geometry") or {}
            polys = [g["coordinates"]] if g.get("type") == "Polygon" else g.get("coordinates", [])
            kept = [p for p in polys if p and touches_maui(p)]
            if not kept:
                continue
            props = f.get("properties", {})
            dm = props.get("DM", props.get("dm"))
            features.append({"type": "Feature",
                             "geometry": {"type": "MultiPolygon", "coordinates": kept},
                             "properties": {"dm": dm, "label": CATEGORY.get(dm, f"D{dm}")}})
        out = OUT / f"usdm_{week.isoformat()}.geojson"
        out.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        cats = sorted(f["properties"]["dm"] for f in features)
        index.append({"year": year, "week": week.isoformat(), "file": out.name, "categories": cats})
        print(f"  {year}: week {week}  Maui categories present: "
              f"{', '.join(f'D{c}' for c in cats) or 'none (no drought)'}  ({out.stat().st_size // 1024} KB)")
    (OUT / "index.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
