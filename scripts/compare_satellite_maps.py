"""How often do the satellite land-cover maps agree with each other at the GLOBE sites?

Uses the same coarse classes as lib/crosscheck.py. No GLOBE data needed.

    python scripts/compare_satellite_maps.py
"""

from __future__ import annotations

import itertools
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import crosscheck

DATA = Path(__file__).resolve().parents[1] / "data" / "research"


def maps() -> dict[str, dict[tuple[str, int], str]]:
    out = dict(crosscheck.load_landcover_csv(DATA / "landcover_site_classes.csv"))
    out["lcms"] = crosscheck.load_lcms_csv(DATA / "lcms_site_classes.csv")
    return out


def compare(a: dict, b: dict) -> Counter:
    tally = Counter()
    for key in sorted(set(a) & set(b)):
        x, y = crosscheck.satellite_classes(a[key]), crosscheck.satellite_classes(b[key])
        tally["unmapped" if x is None or y is None else "agree" if x == y else "partial" if x & y else "disagree"] += 1
    return tally


def main() -> None:
    m = maps()
    for p, q in itertools.combinations(sorted(m), 2):
        for year in sorted({y for _, y in m[p]} & {y for _, y in m[q]}):
            a = {k: v for k, v in m[p].items() if k[1] == year}
            b = {k: v for k, v in m[q].items() if k[1] == year}
            t = compare(a, b)
            print(f"{p:>12} vs {q:<12} {year}: {sum(t.values())} sites -> {dict(t)}")


if __name__ == "__main__":
    main()
