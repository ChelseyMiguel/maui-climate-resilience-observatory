"""Weekly drought across the whole state of Hawaii, 2000 to now.

The U.S. Drought Monitor's DSCI (0-500: 0 none, 500 all of the county in D4) for each
Hawaii county, plus Maui County's share of land in each category D0-D4, so Maui's
2022 drought can be read against the other islands and against 25 years.

Source: USDM data services, University of Nebraska-Lincoln (public, no key).
County values are county-wide: they do not describe any single place within it.

    python scripts/fetch_hawaii_drought.py
Output: data/research/hawaii_dsci_weekly.csv  (date, hawaii, honolulu, kauai, maui, kalawao)
        data/research/maui_categories_2000.csv (date, d0..d4)
"""
from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "research"
BASE = "https://usdmdataservices.unl.edu/api/CountyStatistics"
COUNTIES = {"hawaii": "15001", "honolulu": "15003", "kalawao": "15005", "kauai": "15007", "maui": "15009"}


def get(endpoint: str, fips: str, start: str, end: str) -> list[dict]:
    r = httpx.get(f"{BASE}/{endpoint}", params={"aoi": fips, "startdate": start, "enddate": end, "statisticsType": 1},
                  headers={"Accept": "application/json"}, timeout=120.0)
    r.raise_for_status()
    return r.json()


def main(start: str = "1/1/2000") -> None:
    end = datetime.now(UTC).strftime("%m/%d/%Y").lstrip("0")
    table: dict[str, dict[str, int]] = {}
    for name, fips in COUNTIES.items():
        for r in get("GetDSCI", fips, start, end):
            table.setdefault(r["mapDate"][:10], {})[name] = int(r["dsci"])
    dates = sorted(table)
    with (OUT / "hawaii_dsci_weekly.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", *COUNTIES])
        for d in dates:
            w.writerow([d, *(table[d].get(k, "") for k in COUNTIES)])
    cats = sorted(({"date": r["mapDate"][:10], **{k: float(r[k] or 0) for k in ("d0", "d1", "d2", "d3", "d4")}}
                   for r in get("GetDroughtSeverityStatisticsByAreaPercent", COUNTIES["maui"], start, end)), key=lambda r: r["date"])
    with (OUT / "maui_categories_2000.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "d0", "d1", "d2", "d3", "d4"])
        w.writeheader()
        w.writerows(cats)
    print(f"{len(dates)} weeks {dates[0]} to {dates[-1]}; Maui categories {len(cats)} weeks")


if __name__ == "__main__":
    main()
