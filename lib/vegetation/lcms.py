"""LCMS (Landscape Change Monitoring System) context for Maui County.

LCMS is the USDA Forest Service's annual land-change product. It matters here
because it is *independent* corroboration: the browning analysis in
`browning.py` is the author's own Sentinel-2 work, while LCMS is a published
federal product built by other people from other imagery. When both point the
same way, the claim is much harder to wave off.

What the Maui County numbers show, 2018 baseline:

* "Insect, Disease, or Drought Stress" nearly doubles by 2022 — the year before
  the fires — and keeps climbing to +141% by 2024.
* The "Wildfire" class goes 0 acres (2018) to 91 acres (2023), picking up the
  August 2023 events.
* "Agriculture" land use falls 60% while "Rangeland or Pasture" grows by ~11,300
  acres. Former plantation land going fallow into unmanaged grass is the
  best-documented driver of Maui's fire risk, and LCMS quantifies it.

IMPORTANT SCOPE NOTE: these figures are **county-wide**, not per-site. They are
context for the whole island, not a measurement at any one GLOBE observation.
Per-site LCMS classes need a raster sample from Earth Engine — see
`scripts/gee/lcms_site_sample.js`. The UI must not imply otherwise.

Data is produced by `scripts/extract_lcms.py` from the LCMS Dashboard PDFs.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "research" / "lcms_maui.json"

SUMMARY_AREA = "Maui County, Hawaii"
DATA_VERSION = "LCMS v2024-10"

# The classes worth surfacing, and why each one earns its place in the story.
HIGHLIGHTS: tuple[tuple[str, str, str], ...] = (
    (
        "Vegetation Change",
        "Insect, Disease, or Drought Stress",
        "Drought-stressed vegetation: the fuel-loading signal.",
    ),
    (
        "Vegetation Change",
        "Wildfire",
        "Area LCMS attributes to wildfire.",
    ),
    (
        "Land Use",
        "Agriculture",
        "Active agricultural land; its decline is the fallow-fuel story.",
    ),
    (
        "Land Use",
        "Rangeland or Pasture",
        "Where retired agricultural land tends to end up.",
    ),
)


@lru_cache(maxsize=1)
def load() -> dict:
    """The parsed LCMS tables, or an empty dict when the file is absent."""
    if not DATA_PATH.exists():
        return {}
    return json.loads(DATA_PATH.read_text())


def _trajectory(section: str, class_name: str) -> list[dict]:
    """Per-year acres/percent for one class, oldest first."""
    rows = load().get(section, {}).get(class_name, {})
    return [
        {"year": year, "acres": rows[year]["acres"], "pct": rows[year]["pct"]}
        for year in sorted(rows)
    ]


def summary() -> dict:
    """Headline LCMS trajectories, with change against the 2018 baseline.

    `change_pct_vs_baseline` is None where the baseline is zero — the Wildfire
    class starts at 0 acres, and a percentage change from zero is meaningless
    rather than infinite.
    """
    if not load():
        return {"available": False}

    highlights = []
    for section, class_name, why in HIGHLIGHTS:
        points = _trajectory(section, class_name)
        if not points:
            continue
        first, last = points[0], points[-1]
        change = (
            round((last["acres"] - first["acres"]) / first["acres"] * 100, 1)
            if first["acres"]
            else None
        )
        highlights.append(
            {
                "section": section,
                "class_name": class_name,
                "why": why,
                "points": points,
                "baseline_year": first["year"],
                "latest_year": last["year"],
                "change_pct_vs_baseline": change,
                "change_acres_vs_baseline": last["acres"] - first["acres"],
            }
        )

    return {
        "available": True,
        "summary_area": SUMMARY_AREA,
        "data_version": DATA_VERSION,
        "county_wide": True,  # NOT a per-site measurement
        "highlights": highlights,
    }
