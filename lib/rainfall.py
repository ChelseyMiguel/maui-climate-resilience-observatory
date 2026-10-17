"""Measured rainfall at the Pukalani study area, from four gridded products.

The drought index the Observatory uses (DSCI) is county-wide and expert-blended.
Rainfall is a measurement, so it is the natural check on it: does greenness
follow rain, and over what delay? Four independent products are used because
Upcountry Maui rainfall changes over a few km and every global product is coarser
than that. Agreement between them says the signal is real at this spot;
disagreement says no single product should be trusted here.

Input: `data/research/pukalani_rainfall_monthly.csv`, exported by
`scripts/gee/rainfall_monthly.js`. Missing months carry -9999 and are dropped;
CHIRPS months with fewer days than the calendar month are dropped too, because a
part-month sum looks like a dry month.

    python -m lib.rainfall            # prints the summary as JSON
"""

from __future__ import annotations

import calendar
import csv
import itertools
import json
import statistics
from functools import lru_cache
from pathlib import Path

from lib import relationships
from lib.vegetation import browning

RAIN_PATH = browning.DATA_DIR / "pukalani_rainfall_monthly.csv"
PRODUCTS = ("chirps", "terraclimate", "imerg", "era5land")
_COLUMNS = ("date", "chirps_mm", "chirps_days", "terraclimate_mm", "imerg_mm", "era5land_mm")
_MISSING = -9999.0
# Rain summed over the last k months, compared with this month's greenness.
WINDOWS = (1, 2, 3, 6, 12)

NOTES = (
    (
        "Each product's value is the one grid pixel (about 4.6 to 11 km) containing the "
        "study-area centre, not a gauge reading at Pukalani."
    ),
    (
        "A lag of k months pairs greenness with rain k months earlier. A correlation is "
        "not a cause, and neighbouring months are not independent."
    ),
    (
        "Rain and greenness share a wet-winter, dry-summer cycle, which inflates their "
        "correlation; the version with the seasonal cycle removed is the stricter test."
    ),
)


def load(path: Path | str = RAIN_PATH) -> dict[str, dict[str, float]]:
    """product -> {YYYY-MM: mm}, with missing and part months removed."""
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in _COLUMNS if c not in (reader.fieldnames or ())]
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(missing)}")
        out: dict[str, dict[str, float]] = {p: {} for p in PRODUCTS}
        for row in reader:
            month = row["date"][:7]
            year, mon = int(month[:4]), int(month[5:7])
            for product in PRODUCTS:
                value = float(row[f"{product}_mm"])
                if value == _MISSING:
                    continue
                if product == "chirps" and float(row["chirps_days"]) < calendar.monthrange(year, mon)[1]:
                    continue
                out[product][month] = value
        return out


def accumulate(series: dict[str, float], months: int) -> dict[str, float]:
    """Each month's total over it and the `months - 1` before it.

    Only months whose whole window is present get a value, so a gap never
    produces a short, falsely dry total.
    """
    out = {}
    for month in series:
        window = [relationships._shift(month, back) for back in range(months)]
        if all(m in series for m in window):
            out[month] = sum(series[m] for m in window)
    return out


def anomalies(series: dict[str, float]) -> dict[str, float]:
    """Departure from that calendar month's mean: removes the shared seasonal cycle."""
    by_month: dict[str, list[float]] = {}
    for month, value in series.items():
        by_month.setdefault(month[5:], []).append(value)
    means = {k: statistics.fmean(v) for k, v in by_month.items()}
    return {month: value - means[month[5:]] for month, value in series.items()}


def _r(x: dict[str, float], y: dict[str, float]) -> dict:
    fit = relationships.correlation(relationships.pair_months(x, y))
    return {"r": fit["r"], "n": fit["n"]}


def _windows(data: dict[str, dict[str, float]], target: dict[str, float], seasonal: bool) -> list[dict]:
    """r of accumulated rain with `target`, per window and product."""
    rows = []
    for k in WINDOWS:
        per = {}
        for product in PRODUCTS:
            rain = accumulate(data[product], k)
            if not seasonal:
                rain = anomalies(rain)
            per[product] = _r(rain, target if seasonal else anomalies(target))
        rows.append({"months": k, "products": per})
    return rows


def _lags(rain: dict[str, float], greenness: dict[str, float]) -> list[dict]:
    return [
        {"lag": k, **{key: val for key, val in relationships.correlation(
            relationships.pair_months(rain, greenness, k)).items() if key in ("r", "n")}}
        for k in range(relationships.MAX_LAG + 1)
    ]


@lru_cache(maxsize=4)
def summary(path: Path | str = RAIN_PATH) -> dict:
    """Product agreement, rain-vs-greenness by window and lag, and rain vs. county DSCI."""
    if not Path(path).exists():
        return {"available": False}
    data = load(path)
    ndvi = {d[:7]: v for d, v in browning.ndvi_series()}
    dsci = relationships.monthly_dsci()
    agreement = []
    for a, b in itertools.combinations(PRODUCTS, 2):
        fit = relationships.correlation(relationships.pair_months(data[a], data[b]))
        agreement.append({"a": a, "b": b, "r": fit["r"], "n": fit["n"]})
    return {
        "available": True,
        "months": {p: len(data[p]) for p in PRODUCTS},
        "agreement": agreement,
        "vs_ndvi": {p: _lags(data[p], ndvi) for p in PRODUCTS},
        # Rain over the last k months against this month's greenness, as measured
        # and with each series' seasonal cycle removed (the stricter test).
        "windows_ndvi": _windows(data, ndvi, seasonal=True),
        "windows_ndvi_deseasonalised": _windows(data, ndvi, seasonal=False),
        "windows_dsci": _windows(data, dsci, seasonal=True),
        "monthly": [
            {"month": m, **{p: data[p].get(m) for p in PRODUCTS}}
            for m in sorted(set().union(*(data[p] for p in PRODUCTS)))
        ],
        # Same-month rain against the county drought index: a sanity check that
        # the two describe the same dry spells, not a result in itself.
        "vs_dsci": {
            p: {k: v for k, v in relationships.correlation(
                relationships.pair_months(data[p], dsci)).items() if k in ("r", "n")}
            for p in PRODUCTS
        },
        "notes": list(NOTES),
    }


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
