"""Statewide Hawaii drought, 2000 to now: DSCI by county and Maui's category history.

Input: data/research/hawaii_dsci_weekly.csv and maui_categories_2000.csv
(scripts/fetch_hawaii_drought.py; U.S. Drought Monitor, county-wide values).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from lib.vegetation import browning

DSCI = browning.DATA_DIR / "hawaii_dsci_weekly.csv"
CATEGORIES = browning.DATA_DIR / "maui_categories_2000.csv"
COUNTIES = ("hawaii", "maui", "kauai", "honolulu")
MIN_WEEKS = 40                       # a year needs this many weeks to count (partial years are dropped)


def load(dsci: Path = DSCI, categories: Path = CATEGORIES) -> dict:
    with Path(dsci).open(newline="") as f:
        rows = list(csv.DictReader(f))
    weekly = [{"date": r["date"], **{c: int(r[c]) if r.get(c, "") != "" else None for c in COUNTIES}} for r in rows]
    by_year: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in weekly:
        for c in COUNTIES:
            if r[c] is not None:
                by_year[r["date"][:4]][c].append(r[c])
    annual = []
    for y in sorted(by_year):
        if all(len(by_year[y][c]) >= MIN_WEEKS for c in COUNTIES):
            annual.append({"year": int(y), **{c: round(fmean(by_year[y][c])) for c in COUNTIES}})
    with Path(categories).open(newline="") as f:
        cats = list(csv.DictReader(f))
    d4 = defaultdict(int)
    for r in cats:
        if float(r["d4"]) > 0:
            d4[int(r["date"][:4])] += 1
    maui = sorted(annual, key=lambda a: -a["maui"])
    return {
        "available": True, "weeks": len(weekly), "first": weekly[0]["date"], "last": weekly[-1]["date"],
        "annual": annual,
        "maui_d4_weeks": {y: d4.get(y, 0) for y in range(annual[0]["year"], annual[-1]["year"] + 1)},
        "maui_rank_by_annual_dsci": {a["year"]: i + 1 for i, a in enumerate(maui)},
        "notes": [
            "County-wide Drought Monitor values: they describe the whole county, not any place within it.",
            "Annual values are the mean of the weekly DSCI; years with under 40 weeks are left out.",
        ],
    }


def summary() -> dict:
    if not Path(DSCI).exists() or not Path(CATEGORIES).exists():
        return {"available": False, "how": "run scripts/fetch_hawaii_drought.py"}
    return load()
