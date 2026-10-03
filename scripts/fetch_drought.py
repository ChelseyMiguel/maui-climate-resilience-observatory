"""Download the U.S. Drought Monitor's weekly drought index for Maui County.

DSCI (Drought Severity and Coverage Index) weights the share of the county in
each drought category D0-D4 into one 0-500 number: 0 means no drought anywhere,
500 means the whole county in D4 (exceptional). It is the series the manuscript
correlates against NDVI (r = -0.47).

Source: USDM data services, University of Nebraska-Lincoln (public, no key).

    python scripts/fetch_drought.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "research" / "maui_dsci_weekly.csv"
URL = "https://usdmdataservices.unl.edu/api/CountyStatistics/GetDSCI"
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

    peak = max(rows, key=lambda r: r["dsci"])
    print(f"wrote {OUT.relative_to(Path.cwd())}: {len(rows)} weeks, "
          f"{rows[0]['date']} to {rows[-1]['date']}")
    print(f"  peak DSCI {peak['dsci']} on {peak['date']}")


if __name__ == "__main__":
    main()
