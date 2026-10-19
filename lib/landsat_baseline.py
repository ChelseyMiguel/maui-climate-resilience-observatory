"""Was 2022 unusual? Dry-season greenness of the study area over 25 years.

Input: `data/research/pukalani_landsat_ndvi_dryseason.csv` from section 6 of
`notebooks/gee_exports.ipynb`: the May-September median Landsat NDVI over the
project's 1.5 km study area, 2000-2024, with the scene count and sensors per year.

Each year is read against a NORMAL built only from 2000-2018, before the period
the project studies, so 2019-2024 are not compared with themselves. Results are a
z-score (how many standard deviations from normal) and a rank (1 = lowest).

Caveats carried in `notes`: Landsat 8/9 (2013 on) read NDVI slightly differently
from Landsat 5/7; one 1.5 km area; a median of whatever clear scenes each dry
season had, so years with few scenes are flagged.
"""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path

from lib.vegetation import browning

PATH = browning.DATA_DIR / "pukalani_landsat_ndvi_dryseason.csv"
NORMAL_YEARS = range(2000, 2019)
FEW_SCENES = 3
_MISSING = -9999.0

NOTES = (
    (
        "Landsat 8 and 9 (from 2013) measure NDVI slightly differently from Landsat 5 and 7; "
        "the sensors behind each year are listed."
    ),
    "The normal is 2000-2018 only, so the years the project studies are not compared with themselves.",
    "One 1.5 km study area; a dry-season median of the clear scenes available, not a field measurement.",
)


def load(path: Path | str = PATH) -> list[dict]:
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"year", "ndvi_dry_median", "n_scenes", "sensors"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        rows = []
        for r in reader:
            value = float(r["ndvi_dry_median"])
            rows.append({
                "year": int(r["year"]),
                "ndvi": None if value == _MISSING or math.isnan(value) else round(value, 4),
                "n_scenes": int(float(r["n_scenes"])),
                "sensors": r["sensors"],
            })
        return sorted(rows, key=lambda r: r["year"])


def summary(path: Path | str = PATH) -> dict:
    if not Path(path).exists():
        return {"available": False}
    rows = load(path)
    normal = [r["ndvi"] for r in rows if r["year"] in NORMAL_YEARS and r["ndvi"] is not None]
    if len(normal) < 5:
        return {"available": False, "reason": "fewer than 5 normal-period years with data"}
    mean, sd = statistics.fmean(normal), statistics.stdev(normal)
    valued = [r for r in rows if r["ndvi"] is not None]
    order = sorted(valued, key=lambda r: r["ndvi"])
    for r in rows:
        r["z"] = None if r["ndvi"] is None else round((r["ndvi"] - mean) / sd, 2)
        r["rank_lowest"] = None if r["ndvi"] is None else order.index(r) + 1
        r["few_scenes"] = r["n_scenes"] < FEW_SCENES
    return {
        "available": True,
        "normal": {"years": [min(NORMAL_YEARS), max(NORMAL_YEARS)], "mean": round(mean, 4),
                   "sd": round(sd, 4), "n": len(normal)},
        "years_with_data": len(valued),
        "rows": rows,
        "notes": list(NOTES),
    }
