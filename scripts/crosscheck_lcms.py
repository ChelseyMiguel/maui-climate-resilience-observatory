"""Compare GLOBE observation labels with LCMS land cover at the same sites.

    python scripts/crosscheck_lcms.py --csv data/research/lcms_site_classes.csv
    python scripts/crosscheck_lcms.py --csv ... --area pukalani --json report.json

Needs the GLOBE cache (`scripts/ingest_maui.py`, once, online) and the CSV exported
by `scripts/gee/lcms_site_sample.js` (run in the Earth Engine Code Editor). Prints
every row, including the ones that could not be compared, then the summary.
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
    parser.add_argument("--csv", required=True, type=Path, help="lcms_site_classes.csv from Earth Engine")
    parser.add_argument("--area", default="pukalani", choices=sorted(STUDY_AREAS))
    parser.add_argument("--json", type=Path, help="also write the full result here")
    args = parser.parse_args()

    try:
        lcms = crosscheck.load_lcms_csv(args.csv)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: {exc}")

    study = STUDY_AREAS[args.area]
    observations = client.fetch_near(
        study["lat"], study["lon"], radius_km=study["radius_km"],
        start=DEFAULT_START, end=DEFAULT_END, bbox=REGION,
    )
    # The CSV only covers the sites that were pasted into the Earth Engine script;
    # observations elsewhere in the area show up as no_lcms_row, not as errors.
    result = crosscheck.crosscheck(observations, lcms)

    for row in result["rows"]:
        print(f"{row['verdict']:<12} {row['site']:<13} {row['date'] or '—':<11} "
              f"GLOBE: {row['globe_label'] or '—'}  |  LCMS {row['lcms_year'] or '—'}: {row['lcms_class'] or '—'}")
    s = result["summary"]
    print(f"\n{s['compared']} compared: {s['agree']} agree, {s['partial']} partial, "
          f"{s['disagree']} disagree, {s['unmapped']} unmapped; {s['no_lcms_row']} not in the LCMS sample.")
    for note in result["notes"]:
        print(f"  - {note}")
    if args.json:
        args.json.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
