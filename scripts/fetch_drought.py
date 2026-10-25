from __future__ import annotations

import csv
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "research" / "maui_dsci_weekly.csv"
OUT_CATEGORIES = OUT.with_name("maui_drought_categories_weekly.csv")
URL = "https://usdmdataservices.unl.edu/api/CountyStatistics/GetDSCI"
URL_CATEGORIES = ("https://usdmdataservices.unl.edu/api/CountyStatistics/"
                  "GetDroughtSeverityStatisticsByAreaPercent")
MAUI_COUNTY_FIPS = "15009"


def main(start: str = "1/1/2018", end: str = "12/31/2024") -> None:
    response = httpx.get(
        URL,
        params={"aoi": MAUI_COUNTY_FIPS, "startdate": start, "enddate": end,
                "statisticsType": 1},
        headers={"Accept": "application/json"},
        timeout=60.0,
    )
    response.raise_for_status()
    rows = sorted(
        ({"date": r["mapDate"][:10], "dsci": int(r["dsci"])} for r in response.json()),
        key=lambda r: r["date"],
    )
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "dsci"])
        writer.writeheader()
        writer.writerows(rows)


    cats = httpx.get(
        URL_CATEGORIES,
        params={"aoi": MAUI_COUNTY_FIPS, "startdate": start, "enddate": end, "statisticsType": 1},
        headers={"Accept": "application/json"},
        timeout=60.0,
    )
    cats.raise_for_status()
    cat_rows = sorted(
        ({"date": r["mapDate"][:10], **{k: float(r[k] or 0) for k in ("d0", "d1", "d2", "d3", "d4")}}
         for r in cats.json()),
        key=lambda r: r["date"],
    )
    with OUT_CATEGORIES.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "d0", "d1", "d2", "d3", "d4"])
        writer.writeheader()
        writer.writerows(cat_rows)
    print(f"wrote {OUT_CATEGORIES.relative_to(Path.cwd())}: {len(cat_rows)} weeks")

    peak = max(rows, key=lambda r: r["dsci"])
    print(f"wrote {OUT.relative_to(Path.cwd())}: {len(rows)} weeks, "
          f"{rows[0]['date']} to {rows[-1]['date']}")
    print(f"  peak DSCI {peak['dsci']} on {peak['date']}")


if __name__ == "__main__":
    main()
