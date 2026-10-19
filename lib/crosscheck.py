"""Do GLOBE citizen labels agree with independent satellite land-cover maps?

Each GLOBE observation carries the observer's own land-cover label (a MUC class,
e.g. "Herbaceous/Grassland, Short Grass"). LCMS, a USDA Forest Service product
built from satellite imagery, gives a class for the 30 m pixel at the same
place and year (`scripts/gee/lcms_site_sample.js` exports it). This module lines
the two up. It is a sanity check on the citizen data, not a validation of
either source.

**The crosswalk is a judgment.** Both schemes are reduced to a few coarse
components (tree, shrub, grass, built_barren, water) and a pair counts as
`agree` when the component sets are equal, `partial` when they overlap (LCMS
"Grass/Forb/Herb & Shrubs Mix" against a GLOBE grassland), and `disagree` when
they share nothing. Anything either scheme calls something this table does not
know is `unmapped`, counted and shown, never guessed. Review `_GLOBE_RULES` and
`_LCMS_RULES` before quoting a result.

Scale caveat that travels with every result: an LCMS pixel is 30 m, a GLOBE
site is a 100 m square, and the observer's GPS fix can be tens of metres off.
A mismatch can be the pixel, not the label.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from lib.globe_api.client import LandCoverSite

LCMS_FIRST_YEAR, LCMS_LAST_YEAR = 2018, 2024  # years the sampling script exports

# (substring of the lower-cased GLOBE label, components). First match wins, so
# the mixed class is listed before the single classes it contains.
_GLOBE_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("wooded grassland", frozenset({"tree", "grass"})),
    ("forest", frozenset({"tree"})),
    ("woodland", frozenset({"tree"})),
    ("shrub", frozenset({"shrub"})),
    ("herbaceous", frozenset({"grass"})),
    ("grassland", frozenset({"grass"})),
    # Crops and pasture are grass/forb/herb in LCMS Land Cover (it has no
    # cropland class), so "cultivated" can only ever agree through grass.
    ("cultivated", frozenset({"grass"})),
    ("urban", frozenset({"built_barren"})),
    ("barren", frozenset({"built_barren"})),
    ("water", frozenset({"water"})),
)

# Satellite class names: LCMS Land_Cover ("Shrubs & Trees Mix"), ESA WorldCover
# ("Tree cover", "Built-up") and Dynamic World ("shrub_and_scrub"). Names can be
# combinations, so each component keyword found adds to the set. Cropland reads
# as grass: GLOBE "Cultivated" does too, and LCMS has no crop class at all.
_SATELLITE_RULES: tuple[tuple[str, str], ...] = (
    ("tree", "tree"),
    ("shrub", "shrub"),
    ("grass", "grass"),
    ("crop", "grass"),
    ("barren", "built_barren"),
    ("bare", "built_barren"),
    ("impervious", "built_barren"),
    ("built", "built_barren"),
    ("water", "water"),
)
# Classes outside the coarse scheme (wetlands, mangroves, moss, snow and masks
# carry no keyword above, or are excluded here) come back as None: unmapped.
_SATELLITE_OUTSIDE_SCHEME = ("non-processing", "snow", "wetland", "flooded", "mangrove", "moss")

NOTES = (
    (
        "An LCMS pixel is 30 m and a GLOBE site is a 100 m square with a phone-GPS "
        "fix, so a mismatch can reflect the pixel, not the observer's label."
    ),
    (
        "The class crosswalk is a judgment (lib/crosscheck.py); `partial` means the "
        "two schemes overlap, not that they match."
    ),
    "Agreement between two sources is a sanity check, not proof that either is right.",
)


def globe_classes(label: str | None) -> frozenset[str] | None:
    """Coarse components of a GLOBE MUC label, or None if it is not in the table."""
    text = (label or "").lower()
    for needle, components in _GLOBE_RULES:
        if needle in text:
            return components
    return None


def satellite_classes(name: str | None) -> frozenset[str] | None:
    """Coarse components of an LCMS, WorldCover or Dynamic World class name, or
    None if it is outside the scheme."""
    text = (name or "").lower()
    if not text or any(word in text for word in _SATELLITE_OUTSIDE_SCHEME):
        return None
    found = frozenset(component for needle, component in _SATELLITE_RULES if needle in text)
    return found or None


lcms_classes = satellite_classes  # the name the LCMS-only version used


def verdict(globe_label: str | None, lcms_name: str | None) -> str:
    """`agree`, `partial`, `disagree`, or `unmapped` when either side is unknown."""
    globe, lcms = globe_classes(globe_label), satellite_classes(lcms_name)
    if globe is None or lcms is None:
        return "unmapped"
    if globe == lcms:
        return "agree"
    return "partial" if globe & lcms else "disagree"


def load_lcms_csv(path: Path | str) -> dict[tuple[str, int], str]:
    """(site, year) -> LCMS Land_Cover name, from `lcms_site_classes.csv`.

    The sampling script must export the `Land_Cover_name` label column. A CSV
    with only integer codes cannot be compared and is refused with the fix,
    rather than being matched against code numbers by accident.
    """
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = {"site", "year"} - fields
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        if "Land_Cover_name" not in fields:
            raise ValueError(
                f"{path} has no Land_Cover_name column"
                + (" (only the integer Land_Cover codes)" if "Land_Cover" in fields else "")
                + ": re-run the updated scripts/gee/lcms_site_sample.js, which exports label columns; "
                "if the asset has no class-name tables, run cell 4b of notebooks/gee_exports.ipynb "
                "and build the lookup from what it prints."
            )
        return {
            (row["site"].strip(), int(row["year"])): row["Land_Cover_name"].strip()
            for row in reader
        }


def load_landcover_csv(path: Path | str) -> dict[str, dict[tuple[str, int], str]]:
    """product -> {(site, year): class name}, from `landcover_site_classes.csv`
    (exported by scripts/gee/landcover_site_sample.js or the Colab notebook)."""
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"site", "product", "year", "class_name"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        out: dict[str, dict[tuple[str, int], str]] = {}
        for row in reader:
            out.setdefault(row["product"].strip(), {})[(row["site"].strip(), int(row["year"]))] = (
                row["class_name"].strip()
            )
        return out


def crosscheck(
    observations: Iterable[LandCoverSite], lcms: Mapping[tuple[str, int], str]
) -> dict:
    """Compare each observation's label with a satellite map at its site in its year.

    The map year is the observation's year, held to the years the map has
    (WorldCover exists only for 2020-2021, so a 2023 visit is read against
    2021; LCMS was sampled 2018-2024). Observations with no date, or whose
    site/year is not in the sample, are listed as `no_lcms_row`, never dropped.
    """
    years = {year for _, year in lcms}
    first, last = (min(years), max(years)) if years else (LCMS_FIRST_YEAR, LCMS_LAST_YEAR)
    rows = []
    for obs in observations:
        year = obs.measured_at.year if obs.measured_at else None
        lcms_year = None if year is None else min(max(year, first), last)
        lcms_name = lcms.get((obs.site_name, lcms_year)) if lcms_year else None
        rows.append({
            "land_cover_id": obs.land_cover_id,
            "site": obs.site_name,
            "date": obs.measured_at.date().isoformat() if obs.measured_at else None,
            "lcms_year": lcms_year,
            "globe_label": obs.muc_description,
            "lcms_class": lcms_name,
            "verdict": "no_lcms_row" if lcms_name is None else verdict(obs.muc_description, lcms_name),
        })
    counts = {key: sum(r["verdict"] == key for r in rows)
              for key in ("agree", "partial", "disagree", "unmapped", "no_lcms_row")}
    return {
        "summary": {"compared": len(rows) - counts["no_lcms_row"], **counts},
        "rows": rows,
        "notes": list(NOTES),
    }


def crosscheck_products(
    observations: Iterable[LandCoverSite], table: Mapping[str, Mapping[tuple[str, int], str]]
) -> dict[str, dict]:
    """`crosscheck` against each satellite map separately, keyed by product."""
    observations = list(observations)
    return {product: crosscheck(observations, rows) for product, rows in table.items()}


# ---------------------------------------------------------------------------
# One site, all maps: what the Site Viewer shows next to the photos
# ---------------------------------------------------------------------------

RESEARCH = Path(__file__).resolve().parents[1] / "data" / "research"
MAPS = (
    ("lcms", "LCMS (USDA Forest Service)", "30 m"),
    ("worldcover", "ESA WorldCover", "10 m"),
    ("dynamicworld", "Dynamic World (Google)", "10 m"),
)


@lru_cache(maxsize=1)
def _site_tables() -> dict[str, dict[tuple[str, int], str]]:
    """Every satellite map sampled at the GLOBE sites, from the committed CSVs."""
    tables: dict[str, dict[tuple[str, int], str]] = {}
    landcover = RESEARCH / "landcover_site_classes.csv"
    if landcover.exists():
        tables.update(load_landcover_csv(landcover))
    lcms = RESEARCH / "lcms_site_classes.csv"
    if lcms.exists():
        try:
            tables["lcms"] = load_lcms_csv(lcms)
        except ValueError:
            pass  # a codes-only export cannot be compared; leave LCMS out
    return tables


def site_satellite_classes(site: str, year: int | None, observer_label: str | None) -> dict:
    """What each satellite map calls this GLOBE site, nearest the visit year.

    Each map is read in the year closest to the observation (WorldCover only has
    2020 and 2021), and each class is compared with the observer's own label.
    Sites outside the sampled set return `available: False`.
    """
    tables = _site_tables()
    rows = []
    for key, name, resolution in MAPS:
        years = sorted(y for s, y in tables.get(key, {}) if s == site)
        if not years:
            continue
        chosen = years[-1] if year is None else min(years, key=lambda y: (abs(y - year), -y))
        class_name = tables[key][(site, chosen)]
        rows.append({
            "product": key, "name": name, "resolution": resolution, "year": chosen,
            "class_name": class_name, "verdict": verdict(observer_label, class_name),
        })
    coarse = {satellite_classes(r["class_name"]) for r in rows}
    return {
        "available": bool(rows),
        "site": site,
        "observer_label": observer_label,
        "maps": rows,
        # Do the satellite maps even agree with each other here?
        "maps_agree": (len(coarse) == 1 and None not in coarse) if rows else None,
    }
