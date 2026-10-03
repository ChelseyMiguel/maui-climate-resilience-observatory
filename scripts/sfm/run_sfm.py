"""Structure-from-motion experiment on a GLOBE site with repeat visits.

WHY THIS IS AN EXPERIMENT, NOT A FEATURE
One GLOBE observation is six photos from ONE standing point. With no change of
viewpoint there is no parallax, so no depth can be recovered — that is why the
main viewer is a cube map, not a 3D model. SfM needs the same scene from
several positions.

Site 04QGJ763065 is the one place in the Pukalani data where that exists: eight
visits over two days, standing up to ~92 m apart, each facing N/E/S/W. That is a
real (if small) baseline. This script tries to reconstruct it and reports
honestly how much it recovers.

Optional dependency — NOT in requirements.txt (large, native):
    python -m venv .sfmenv && .sfmenv/bin/pip install pycolmap
    .sfmenv/bin/python scripts/sfm/run_sfm.py --site 04QGJ763065

Outputs under data/sfm/<site>/ : the COLMAP model and points.ply (sparse cloud).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HORIZONTAL = ("North", "East", "South", "West")


def collect_images(site_name: str, work: Path) -> list[dict]:
    """Copy the mirrored horizontal photos for every visit to `site_name`."""
    from lib.globe_api import client  # stdlib + httpx only

    sites = client.fetch_sites("2017-01-01", "2026-12-31", bbox=client.HAWAII)
    visits = [s for s in sites if s.site_name == site_name]
    images = work / "images"
    images.mkdir(parents=True, exist_ok=True)
    manifest = []
    for v in visits:
        for d in HORIZONTAL:
            src = client.local_photo_path(v.land_cover_id, d)
            if not src.exists():
                continue
            name = f"{v.land_cover_id}_{d.lower()}.jpg"
            shutil.copy(src, images / name)
            manifest.append({"image": name, "land_cover_id": v.land_cover_id,
                             "direction": d, "lat": v.latitude, "lon": v.longitude,
                             "accuracy_m": v.location_accuracy_m,
                             "measured_at": v.measured_at.isoformat() if v.measured_at else None})
    return manifest


def write_ply(points: list[tuple], path: Path) -> None:
    with path.open("w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for x, y, z, r, g, b in points:
            f.write(f"{x:.4f} {y:.4f} {z:.4f} {r} {g} {b}\n")


def main() -> None:
    import pycolmap

    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="04QGJ763065")
    ap.add_argument(
        "--relaxed", action="store_true",
        help="Lower COLMAP's match thresholds. Grassy GLOBE sites are repetitive "
             "texture, so few pairs reach the default 100-inlier starting pair; "
             "relaxing lets a small model form, at the cost of reliability.",
    )
    args = ap.parse_args()

    work = ROOT / "data" / "sfm" / args.site
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    manifest = collect_images(args.site, work)
    print(f"{args.site}: {len(manifest)} horizontal photos from "
          f"{len({m['land_cover_id'] for m in manifest})} visits")
    if len(manifest) < 3:
        raise SystemExit("not enough mirrored photos — run ingest_maui.py --download-photos")

    db = work / "database.db"
    pycolmap.extract_features(db, work / "images")
    pycolmap.match_exhaustive(db)
    options = pycolmap.IncrementalPipelineOptions()
    if args.relaxed:
        options.min_model_size = 3
        options.mapper.init_min_num_inliers = 30
        options.mapper.abs_pose_min_num_inliers = 15
    maps = pycolmap.incremental_mapping(
        db, work / "images", work / "sparse", options=options
    )

    report = {"site": args.site, "photos": len(manifest), "models": len(maps),
              "relaxed": args.relaxed}
    if not maps:
        report["result"] = "no reconstruction: photos did not share enough matched features"
    else:
        best = max(maps.values(), key=lambda r: r.num_reg_images())
        registered = sorted(img.name for img in best.images.values())
        pts = [(*p.xyz, *p.color) for p in best.points3D.values()]
        write_ply(pts, work / "points.ply")
        report.update({
            "registered_images": best.num_reg_images(),
            "registered": registered,
            "points3d": len(pts),
            "mean_reprojection_error_px": round(best.compute_mean_reprojection_error(), 3),
            "result": "sparse reconstruction",
        })

    (work / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (work / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "registered"}, indent=2))
    if "registered" in report:
        print("registered:", ", ".join(report["registered"]))


if __name__ == "__main__":
    main()
