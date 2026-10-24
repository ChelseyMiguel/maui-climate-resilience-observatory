"""Fire, drought-climate and land-history layers from the Hawaii Statewide GIS
Program (geodata.hawaii.gov), clipped to Maui.

Every layer is the publisher's own, saved with its source, its date in the
publisher's words, and its licence note. Nothing is derived or re-scored here.

  fire_risk       DLNR-DOFAW "Fire Risk Areas": a 2007 rating of wildland-fire risk
                  for populated areas, boundaries reconfirmed 2017 and 2022.
  fire_response   DLNR-DOFAW Fire Response Zones: who responds first (as of April 2026).
  moisture_zones  Seven moisture zones (Arid ... Very Wet), from a species-range model.
  rainfall_mm     Mean annual rainfall isohyets (mm), Rainfall Atlas of Hawaii 2011
                  (base period 1978-2007), as 20 m-simplified lines.
  rain_gauges     Gauges used in the Atlas with mean monthly/annual rainfall.
  sugarcane_*     Lands in sugarcane in 1900, 1920 and 1937 (digitised from historical maps).
  pineapple_*     Lands in pineapple in 1920 and 1937 (none on Maui in 1900).

Output: data/context/hawaii_portal/<key>.geojson and data/context/hawaii_portal.json
Run:    .venv/bin/python scripts/fetch_hawaii_portal.py
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "context"
BASE = "https://geodata.hawaii.gov/arcgis/rest/services"
MAUI = "-156.72,20.55,-155.95,21.05"          # all of Maui, with a margin

# key: (service, layer, title, group, extra where-clause or None)
LAYERS = {
    "fire_risk": ("Hazards", 7, "Fire risk areas (DLNR rating)", "fire", "island = 'Maui'"),
    "fire_response": ("EmergMgmtPubSafety", 6, "Fire response zones", "fire", "island = 'Maui'"),
    "moisture_zones": ("LandUseLandCover", 6, "Moisture zones", "climate", None),
    "rainfall_mm": ("Climate", 26, "Mean annual rainfall (isohyets, mm)", "climate", None),
    "rain_gauges": ("Climate", 27, "Rain gauges (Rainfall Atlas)", "climate", None),
    "sugarcane_1900": ("LandUseLandCover", 23, "Sugarcane lands, 1900", "history", None),
    "sugarcane_1920": ("LandUseLandCover", 24, "Sugarcane lands, 1920", "history", None),
    "sugarcane_1937": ("LandUseLandCover", 25, "Sugarcane lands, 1937", "history", None),
    "pineapple_1920": ("LandUseLandCover", 21, "Pineapple lands, 1920", "history", None),
    "pineapple_1937": ("LandUseLandCover", 22, "Pineapple lands, 1937", "history", None),
}
GAUGE_KEEP = ["skn", "name", "elevm", "minyear", "maxyear", "nummoswith", "annavgmm", "annsd_mm",
              "janavgmm", "febavgmm", "maravgmm", "apravgmm", "mayavgmm", "junavgmm", "julavgmm",
              "augavgmm", "sepavgmm", "octavgmm", "novavgmm", "decavgmm"]


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def fetch(service: str, layer: int, where: str | None) -> tuple[dict, list[dict]]:
    meta = httpx.get(f"{BASE}/{service}/MapServer/{layer}", params={"f": "json"}, timeout=60).json()
    params = {"where": where or "1=1", "geometry": MAUI, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
              "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "outSR": 4326, "returnGeometry": "true",
              "f": "geojson", "geometryPrecision": 5}
    if meta.get("geometryType") != "esriGeometryPoint":
        params["maxAllowableOffset"] = 0.0002          # ~20 m: far below the map's resolution
    feats, offset = [], 0
    while True:                                         # page, in case a layer has more than maxRecordCount
        r = httpx.get(f"{BASE}/{service}/MapServer/{layer}/query", params={**params, "resultOffset": offset}, timeout=120)
        r.raise_for_status()
        page = r.json().get("features", [])
        feats += page
        if len(page) < int(meta.get("maxRecordCount") or 1000):
            break
        offset += len(page)
    return meta, feats


def main() -> None:
    folder = OUT / "hawaii_portal"
    folder.mkdir(parents=True, exist_ok=True)
    catalog = []
    for key, (service, layer, title, group, where) in LAYERS.items():
        meta, feats = fetch(service, layer, where)
        feats = [f for f in feats if f.get("geometry")]
        if key == "rain_gauges":
            feats = [{"type": "Feature", "geometry": f["geometry"],
                      "properties": {k: f["properties"].get(k) for k in GAUGE_KEEP}} for f in feats
                     if f["properties"].get("annavgmm") not in (None, 0)]
            # Maui Nui's neighbours share the box; keep Maui island (east of Lanai/Molokai).
            feats = [f for f in feats if -156.72 < f["geometry"]["coordinates"][0] < -155.95 and 20.55 < f["geometry"]["coordinates"][1] < 21.05]
        for f in feats:
            f["properties"].pop("shape", None)
            for k in [k for k in f["properties"] if k.startswith("st_")]:
                f["properties"].pop(k)
        (folder / f"{key}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
        ms = (meta.get("editingInfo") or {}).get("lastEditDate")
        catalog.append({
            "id": key, "title": title, "group": group, "count": len(feats), "geometry": meta.get("geometryType", "").replace("esriGeometry", ""),
            "source": f"{BASE}/{service}/MapServer/{layer}",
            "publisher": clean(meta.get("copyrightText")) or "Hawaii Statewide GIS Program",
            "description": clean(meta.get("description"))[:700],
            "last_edit": datetime.fromtimestamp(ms / 1000, tz=UTC).date().isoformat() if ms else None,
            "fetched": datetime.now(UTC).date().isoformat(),
        })
        print(f"  {key:<16} {len(feats):>4}  {(folder / f'{key}.geojson').stat().st_size / 1e3:>7.0f} kB  {title}")
    (OUT / "hawaii_portal.json").write_text(json.dumps(catalog, indent=2))


if __name__ == "__main__":
    main()
