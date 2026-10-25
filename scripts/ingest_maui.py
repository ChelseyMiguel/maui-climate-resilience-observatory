"""Pull and cache the Maui GLOBE land cover observations the demo runs on.

Run this once before a demo so `data/cache/` is warm and the app never depends
on the GLOBE API being reachable at judging time:

    python scripts/ingest_maui.py
    python scripts/ingest_maui.py --area pukalani --download-photos
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.sites import DEFAULT_END, DEFAULT_START, REGION, STUDY_AREAS
from lib.globe_api import client

PHOTO_DIR = client.PHOTO_DIR


def download_photos(sites: list[client.LandCoverSite]) -> tuple[int, list[str]]:
    saved_total, errors = 0, []
    for index, site in enumerate(sites, 1):
        saved, errs = client.mirror_photos(site)
        saved_total += saved
        errors.extend(errs)
        print(f"    [{index}/{len(sites)}] {site.site_name} {site.land_cover_id}: +{saved}")
    return saved_total, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area", default="pukalani", choices=sorted(STUDY_AREAS))
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--radius-km", type=float, default=None)
    parser.add_argument("--complete-only", action="store_true")
    parser.add_argument("--download-photos", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Bypass the cache.")
    args = parser.parse_args()

    study = STUDY_AREAS[args.area]
    radius = args.radius_km if args.radius_km is not None else study["radius_km"]

    print(f"{study['name']} — {radius:g} km radius, {args.start} to {args.end}")
    sites = client.fetch_near(
        study["lat"],
        study["lon"],
        radius_km=radius,
        start=args.start,
        end=args.end,
        bbox=REGION,
        complete_only=args.complete_only,
        refresh=args.refresh,
    )

    complete = [s for s in sites if s.is_complete]
    grouped = client.group_by_site(sites)
    print(f"  {len(sites)} observations, {len(complete)} complete (6/6)")
    print(f"  {len(grouped)} distinct sites")

    repeats = {k: v for k, v in grouped.items() if len(v) > 1}
    if repeats:
        print(f"  {len(repeats)} sites with repeat visits (before/after candidates):")
        for site_id, observations in sorted(
            repeats.items(), key=lambda kv: -len(kv[1])
        )[:10]:
            dates = sorted(
                {o.measured_at.date().isoformat() for o in observations if o.measured_at}
            )
            print(f"    {observations[0].site_name}  n={len(observations)}  {dates}")

    index_path = PHOTO_DIR.parent / f"sites_{args.area}.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps([s.to_dict() for s in sites], indent=2))
    print(f"  wrote {index_path.relative_to(Path.cwd())}")

    if args.download_photos:
        print("  downloading photos…")
        saved, errors = download_photos(sites)
        print(f"  saved {saved} new files under {PHOTO_DIR}")
        for line in errors:
            print(f"    ! {line}")
        if errors:
            print(f"  {len(errors)} photo(s) failed; re-run to retry just those.")


if __name__ == "__main__":
    main()
