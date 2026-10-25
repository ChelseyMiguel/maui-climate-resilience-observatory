from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "research" / "maui_fire_perimeters.geojson"
BASE = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services"
MAUI = "-156.75,20.55,-155.95,21.05"


HST = ZoneInfo("Pacific/Honolulu")

SERVICES = {
    "WFIGS_Interagency_Perimeters": {
        "name": "poly_IncidentName",
        "acres": "poly_GISAcres",
        "date": "attr_FireDiscoveryDateTime",
    },
    "InterAgencyFirePerimeterHistory_All_Years_View": {
        "name": "INCIDENT",
        "acres": "GIS_ACRES",
        "date": None,
        "year": "FIRE_YEAR",
    },
}


def fetch(service: str) -> list[dict]:
    response = httpx.get(
        f"{BASE}/{service}/FeatureServer/0/query",
        params={
            "where": "1=1",
            "geometry": MAUI,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json().get("features", [])


def main() -> None:
    features, seen = [], set()
    for service, fields in SERVICES.items():
        for f in fetch(service):
            props = f.get("properties", {})
            name = (props.get(fields["name"]) or "Unknown").strip().title()
            acres = props.get(fields["acres"])
            if fields.get("date") and props.get(fields["date"]):
                when = datetime.fromtimestamp(props[fields["date"]] / 1000, tz=HST)
                date, year = when.date().isoformat(), when.year
            else:
                date, year = None, int(props.get(fields.get("year"), 0) or 0) or None


            key = (name, year)
            if key in seen:
                continue
            seen.add(key)

            features.append(
                {
                    "type": "Feature",
                    "geometry": f.get("geometry"),
                    "properties": {
                        "name": name,
                        "year": year,
                        "discovered": date,
                        "acres": round(float(acres), 1) if acres else None,
                        "source": f"NIFC {service}",
                    },
                }
            )

    features.sort(key=lambda f: (f["properties"]["year"] or 0, f["properties"]["name"]))
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(f"wrote {OUT.relative_to(Path.cwd())}")
    for f in features:
        p = f["properties"]
        print(f"  {p['year']}  {p['name']:<14} {p['acres']:>8} ac  discovered {p['discovered']} (HST)")


if __name__ == "__main__":
    main()
