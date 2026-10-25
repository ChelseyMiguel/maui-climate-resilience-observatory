"""Compare GLOBE observation labels with LCMS land cover at the same sites.

    python scripts/crosscheck_lcms.py --csv data/research/lcms_site_classes.csv
    python scripts/crosscheck_lcms.py --landcover data/research/landcover_site_classes.csv
    python scripts/crosscheck_lcms.py --csv ... --landcover ... --json report.json

Needs the GLOBE cache (`scripts/ingest_maui.py`, once, online) and the CSV exported
by `scripts/gee/lcms_site_sample.js` and/or `scripts/gee/landcover_site_sample.js`
(ESA WorldCover + Dynamic World), run in the Earth Engine Code Editor or the Colab
notebook. Prints every row per map, including the ones that could not be
compared, then each map's summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.sites import DEFAULT_END, DEFAULT_START, REGION, STUDY_AREAS
from lib import crosscheck
from lib.globe_api import client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="lcms_site_classes.csv from Earth Engine")
    parser.add_argument("--landcover", type=Path, help="landcover_site_classes.csv (WorldCover, Dynamic World)")
    parser.add_argument("--area", default="pukalani", choices=sorted(STUDY_AREAS))
    parser.add_argument("--json", type=Path, help="also write the full result here")
    args = parser.parse_args()

    if not (args.csv or args.landcover):
        parser.error("give --csv (LCMS) and/or --landcover (WorldCover, Dynamic World)")
    table: dict[str, dict] = {}
    try:
        if args.csv:
            table["lcms"] = crosscheck.load_lcms_csv(args.csv)
        if args.landcover:
            table.update(crosscheck.load_landcover_csv(args.landcover))
    except (OSError, ValueError) as exc:
        sys.exit(f"error: {exc}")

    study = STUDY_AREAS[args.area]
    try:
        observations = client.fetch_near(
            study["lat"], study["lon"], radius_km=study["radius_km"],
            start=DEFAULT_START, end=DEFAULT_END, bbox=REGION,
        )
    except client.GlobeUnavailableError as exc:
        sys.exit(f"error: no cached GLOBE observations ({exc}). "
                 "Run scripts/ingest_maui.py once while online, then try again.")


    results = crosscheck.crosscheck_products(observations, table)

    for product, result in results.items():
        print(f"\n=== {product} ===")
        for row in result["rows"]:
            if row["verdict"] == "no_lcms_row":
                continue
            print(f"{row['verdict']:<10} {row['site']:<13} {row['date'] or '—':<11} "
                  f"GLOBE: {row['globe_label'] or '—'}  |  {row['lcms_year']}: {row['lcms_class']}")
        s = result["summary"]
        print(f"{s['compared']} compared: {s['agree']} agree, {s['partial']} partial, "
              f"{s['disagree']} disagree, {s['unmapped']} unmapped; {s['no_lcms_row']} not in the sample.")
    for note in crosscheck.NOTES:
        print(f"  - {note}")
    if args.json:
        args.json.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
