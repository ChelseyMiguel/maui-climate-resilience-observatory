"""How county drought and Pukalani vegetation move together.

Everything the "Drought vs. greenness" card shows is computed here, from the
files already in `data/research/`, so the UI draws numbers and never makes them.

What this is and is not. Maui County's weekly drought index (DSCI, U.S. Drought
Monitor) is paired month by month with the monthly NDVI/NBR of the project's
1.5 km Pukalani study area. That is a correlation between two coarse series at
different scales. It is not a causal estimate and not a fire-risk measure, and
adjacent months are not independent, so `n` overstates how much separate
information there is. The `notes` in the payload say so, next to the numbers.

Months without usable imagery are absent from the vegetation series (the loader
drops the -9999 sentinel) and so drop out of every pairing here, never zero.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from functools import lru_cache

from lib import hazards
from lib.vegetation import browning

MAX_LAG = 6
DRY_MONTHS = (5, 6, 7, 8, 9)  # May-September, as in the rest of the project

Pair = tuple[str, float, float]  # (month of the vegetation value, drought, vegetation)

NOTES = (
    (
        "A correlation between two coarse series, not a cause and not a forecast: "
        "county-wide drought against a 1.5 km study area."
    ),
    (
        "Neighbouring months are not independent, so the number of months overstates "
        "how many separate observations there are."
    ),
    (
        "Vegetation indices also respond to rainfall, mowing, grazing and land use, "
        "not only to drought."
    ),
)


def _shift(month: str, back: int) -> str:
    """`YYYY-MM` minus `back` months."""
    total = int(month[:4]) * 12 + int(month[5:7]) - 1 - back
    return f"{total // 12}-{total % 12 + 1:02d}"


def monthly_dsci() -> dict[str, float]:
    """`YYYY-MM` -> mean of that month's weekly county DSCI."""
    weeks: dict[str, list[float]] = {}
    for date, value in hazards.drought_series():
        weeks.setdefault(date[:7], []).append(value)
    return {month: statistics.fmean(values) for month, values in weeks.items()}


def pair_months(
    drought: Mapping[str, float], vegetation: Mapping[str, float], lag: int = 0
) -> list[Pair]:
    """Pair each vegetation month with the drought value `lag` months earlier.

    Only months present on both sides are kept, so a gap in either series
    shrinks `n` instead of being filled.
    """
    return [
        (month, drought[source], vegetation[month])
        for month in sorted(vegetation)
        if (source := _shift(month, lag)) in drought
    ]


def correlation(pairs: Sequence[Pair]) -> dict:
    """Pearson r and the least-squares line, or Nones when they do not exist.

    Fewer than three pairs, or a series that never varies, has no correlation;
    that is reported as None (JSON cannot carry NaN) rather than raised.
    """
    n = len(pairs)
    empty = {"r": None, "n": n, "slope": None, "intercept": None}
    if n < 3:
        return empty
    xs, ys = [p[1] for p in pairs], [p[2] for p in pairs]
    try:
        r = statistics.correlation(xs, ys)
        line = statistics.linear_regression(xs, ys)
    except statistics.StatisticsError:
        return empty
    return {
        "r": round(r, 4),
        "n": n,
        "slope": round(line.slope, 6),
        "intercept": round(line.intercept, 4),
    }


def _index_block(drought: Mapping[str, float], series: Mapping[str, float]) -> dict:
    pairs = pair_months(drought, series)
    return {
        "points": [
            {"month": m, "year": int(m[:4]), "dsci": round(d, 1), "value": round(v, 4)}
            for m, d, v in pairs
        ],
        "fit": correlation(pairs),
        "lags": [
            {"lag": k, **{key: val for key, val in correlation(pair_months(drought, series, k)).items()
                          if key in ("r", "n")}}
            for k in range(MAX_LAG + 1)
        ],
    }


def _dry_season(
    drought: Mapping[str, float], ndvi: Mapping[str, float], nbr: Mapping[str, float]
) -> list[dict]:
    """Per year: May-Sep mean DSCI and index, with how many months fed each.

    DSCI is averaged over the same months as the NDVI it sits beside, so the two
    numbers describe the same weeks. A year built from few months is listed with
    its count so the reader can discount it.
    """
    years = sorted({int(m[:4]) for m in ndvi if int(m[5:7]) in DRY_MONTHS})
    rows = []
    for year in years:
        months = [m for m in sorted(ndvi) if m.startswith(str(year)) and int(m[5:7]) in DRY_MONTHS
                  and m in drought]
        nbr_months = [m for m in nbr if m.startswith(str(year)) and int(m[5:7]) in DRY_MONTHS]
        if not months:
            continue
        rows.append({
            "year": year,
            "months": len(months),
            "dsci": round(statistics.fmean(drought[m] for m in months), 1),
            "ndvi": round(statistics.fmean(ndvi[m] for m in months), 4),
            "nbr_months": len(nbr_months),
            "nbr": round(statistics.fmean(nbr[m] for m in nbr_months), 4) if nbr_months else None,
        })
    return rows


@lru_cache(maxsize=1)
def drought_greenness() -> dict:
    """The whole payload behind the card (cached: the inputs are static files)."""
    drought = monthly_dsci()
    ndvi = {d[:7]: v for d, v in browning.ndvi_series()}
    nbr = {d[:7]: v for d, v in browning.nbr_series()}
    if not (drought and ndvi):
        return {"available": False, "indices": {}, "dry_season": [], "notes": []}
    return {
        "available": True,
        "indices": {"ndvi": _index_block(drought, ndvi), "nbr": _index_block(drought, nbr)},
        "dry_season": _dry_season(drought, ndvi, nbr),
        "notes": list(NOTES),
    }
