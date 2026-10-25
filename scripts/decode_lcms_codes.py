from __future__ import annotations

import csv
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "research" / "lcms_site_classes.csv"


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
