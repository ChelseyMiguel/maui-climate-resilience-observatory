"""Add Land_Cover_name to data/research/lcms_site_classes.csv from the asset's own class order.

The 2025-11 LCMS asset (projects/gtac-data-publish/assets/LCMS/Product_Version/2025-11)
has no class-name tables. Its Land_Cover_Raw_Probability_* bands list the classes, and
notebook cell 4c tested "code n = n-th band" against the data: each site-year's
Land_Cover code equalled its most probable class in 105 of 105 site-years (2026-10
run). So Land_Cover is decoded from that order.

Land_Use is NOT decoded: the same test held in only 83% of site-years, below the 95%
bar, so its names stay blank. Change is not decoded: its probability bands do not
list all its classes.

    python scripts/decode_lcms_codes.py
"""

from __future__ import annotations

import csv
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "research" / "lcms_site_classes.csv"

# Band order of Land_Cover_Raw_Probability_* in the 2025-11 asset, as printed by cell 4c.
LAND_COVER = (
    "Trees", "Tall Shrubs and Trees Mix", "Shrubs and Trees Mix", "Grass Forb Herb and Trees Mix",
    "Barren and Trees Mix", "Tall Shrubs", "Shrubs", "Grass Forb Herb and Shrubs Mix",
    "Barren and Shrubs Mix", "Grass Forb Herb", "Barren and Grass Forb Herb Mix",
    "Barren or Impervious", "Snow or Ice", "Water",
)


def decode(code: str) -> str:
    n = int(code)
    return LAND_COVER[n - 1] if 1 <= n <= len(LAND_COVER) else "unknown"


def main() -> None:
    with PATH.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    columns = ["site", "year", "Change", "Land_Cover", "Land_Cover_name", "Land_Use", "Land_Use_name"]
    with PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "Land_Cover_name": decode(row["Land_Cover"]),
                             "Land_Use_name": row.get("Land_Use_name", "")})
    print(f"decoded {len(rows)} rows in {PATH.name}")


if __name__ == "__main__":
    main()
