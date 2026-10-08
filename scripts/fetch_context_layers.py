"""Download community-context and boundary layers from the Hawaii Statewide GIS
Program (geodata.hawaii.gov), clipped to Upcountry Maui.

Only authoritative, published layers are used, each saved with the publisher's
own last-edit date so the app can show how current it is. Locations only: none
of these layers says anything about current status (open, staffed, in use as a
shelter), and the app must not imply it does.

    python scripts/fetch_context_layers.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "context"
BASE = "https://geodata.hawaii.gov/arcgis/rest/services"
# Upcountry Maui with margin: Pukalani, Makawao, Kula, and the 2023 fires.
BBOX = "-156.45,20.62,-156.22,20.92"

# key: (service, layer id, title, the field that holds a readable name)
# Each publisher names things differently, so the name field is per layer rather
# than guessed.
LAYERS = {
    "fire_stations": ("EmergMgmtPubSafety", 7, "Fire stations", "alt_name"),
    "ems_stations": ("EmergMgmtPubSafety", 8, "EMS stations", "unit_name"),
    "hospitals": ("Infrastructure", 5, "Hospitals", "name"),
    "public_schools": ("Infrastructure", 7, "Public schools", "sch_name"),
    "private_schools": ("Infrastructure", 8, "Private schools", "school"),
}
PLACES = ("Census", 28, "2020 Census Designated Places")
REGION_NAMES = ("Pukalani", "Makawao", "Kula")


def layer_meta(service: str, layer: int) -> dict:
    r = httpx.get(f"{BASE}/{service}/MapServer/{layer}", params={"f": "json"}, timeout=60)
    r.raise_for_status()
    return r.json()


def query(service: str, layer: int, **params) -> list[dict]:
    base = {"outFields": "*", "outSR": 4326, "f": "geojson", "returnGeometry": "true"}
    r = httpx.get(f"{BASE}/{service}/MapServer/{layer}/query", params={**base, **params}, timeout=60)
    r.raise_for_status()
    return r.json().get("features", [])


def currency(meta: dict) -> str | None:
    """How current the layer is, in the publisher's own words.

    These services carry no machine-readable edit date; the description says it
    instead ("as of December 2025"). Quote that rather than invent a date.
    """
    ms = (meta.get("editingInfo") or {}).get("lastEditDate")
    if ms:
        return "edited " + datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
    text = re.sub(r"<[^>]+>", " ", meta.get("description") or "")
    match = re.search(r"(as of [A-Z][a-z]+ \d{4}|current as of [^.;]{3,30})", text)
    return match.group(1) if match else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []

    # Region boundaries: 2020 Census Designated Places.
    service, layer, title = PLACES
    meta = layer_meta(service, layer)
    names = ",".join(f"'{n}'" for n in REGION_NAMES)
    feats = query(service, layer, where=f"name20 IN ({names})")
    regions = []
    for f in feats:
        p = f["properties"]
        regions.append({"type": "Feature", "geometry": f["geometry"],
                        "properties": {"name": p["name20"], "kind": "2020 Census Designated Place",
                                       "geoid": p.get("geoid20"),
                                       "land_km2": round(float(p.get("aland20") or 0) / 1e6, 2)}})
    (OUT / "regions.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": regions}))
    catalog.append({"id": "regions", "title": title, "count": len(regions),
                    "source": f"{BASE}/{service}/MapServer/{layer}",
                    "currency": "2020 Census (decennial boundaries)",
                    "names": sorted(r["properties"]["name"] for r in regions)})

    # Community context points.
    for key, (service, layer, title, name_field) in LAYERS.items():
        meta = layer_meta(service, layer)
        feats = query(service, layer, geometry=BBOX, geometryType="esriGeometryEnvelope",
                      inSR=4326, spatialRel="esriSpatialRelIntersects", where="1=1")
        cleaned = [{"type": "Feature", "geometry": f["geometry"],
                    "properties": {"name": str(f["properties"].get(name_field) or "Unnamed").strip(),
                                   "layer": key, "attributes": f["properties"]}}
                   for f in feats if f.get("geometry")]
        (OUT / f"{key}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": cleaned}))
        catalog.append({"id": key, "title": title, "count": len(cleaned),
                        "source": f"{BASE}/{service}/MapServer/{layer}",
                        "currency": currency(meta),
                        "names": sorted(c["properties"]["name"] for c in cleaned)})

    (OUT / "catalog.json").write_text(json.dumps(catalog, indent=2))
    for c in catalog:
        print(f"  {c['title']:<30} {c['count']:>3}  {c['currency']!s:<34} {c['names'][:5]}")


if __name__ == "__main__":
    main()
