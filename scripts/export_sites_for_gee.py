"""Emit the GLOBE site list as an Earth Engine FeatureCollection literal.

The GEE Code Editor has no access to this machine, so site coordinates have to
be pasted into the scripts under `scripts/gee/`. Generating that block keeps it
in sync with the cached GLOBE data instead of being hand-maintained.

    python scripts/export_sites_for_gee.py --area pukalani
    python scripts/export_sites_for_gee.py --area pukalani --complete-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.sites import DEFAULT_END, DEFAULT_START, REGION, STUDY_AREAS
from lib.globe_api import client


def _clean_note(note: str, limit: int = 60) -> str:
    flat = " ".join(note.split())
    return flat[: limit - 1] + "…" if len(flat) > limit else flat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area", default="pukalani", choices=sorted(STUDY_AREAS))
    parser.add_argument("--complete-only", action="store_true")
    parser.add_argument("--radius-km", type=float, default=None)
    args = parser.parse_args()

    study = STUDY_AREAS[args.area]
    radius = args.radius_km if args.radius_km is not None else study["radius_km"]

    sites = client.fetch_near(
        study["lat"],
        study["lon"],
        radius_km=radius,
        start=DEFAULT_START,
        end=DEFAULT_END,
        bbox=REGION,
        complete_only=args.complete_only,
    )


    by_site: dict[str, list] = {}
    for site in sites:
        by_site.setdefault(site.site_name, []).append(site)

    print(f"// {len(by_site)} sites near {study['name']} ({radius:g} km)")
    print("var sites = ee.FeatureCollection([")

    entries = sorted(by_site.items())
    for index, (name, observations) in enumerate(entries):
        lat = sum(o.latitude for o in observations) / len(observations)
        lon = sum(o.longitude for o in observations) / len(observations)


        separator = "," if index < len(entries) - 1 else ""
        note = observations[0].field_notes
        comment = f"  // {_clean_note(note)}" if note else ""
        print(
            f"  ee.Feature(ee.Geometry.Point([{lon:.5f}, {lat:.5f}]), "
            f"{{site: '{name}'}}){separator}{comment}"
        )

    print("]);")


if __name__ == "__main__":
    main()
