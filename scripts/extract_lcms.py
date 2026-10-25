"""Parse LCMS Dashboard PDF reports into a single JSON the app can serve.

LCMS (Landscape Change Monitoring System) is the USFS annual land-change
product. Its dashboard exports a per-county PDF with three tables — Vegetation
Change, Land Cover, and Land Use — each giving acres and area-% for a baseline
year and a comparison year.

Parsing them rather than transcribing by hand keeps the numbers auditable and
lets new report years be added by dropping in another PDF.

    python scripts/extract_lcms.py ~/Downloads/lcmsReport_Maui_County_*.pdf
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "research" / "lcms_maui.json"

SECTIONS = ("Vegetation Change", "Land Cover", "Land Use")


_HEADER_RE = re.compile(r"^(\d{4})\(Acres\)$")
_NUMBER_RE = re.compile(r"^[\d,]+$")
_PERCENT_RE = re.compile(r"^[\d.]+%$")


def _parse_section(lines: list[str], start: int) -> tuple[dict, int]:
    i = start
    years: list[str] = []
    while i < len(lines):
        m = _HEADER_RE.match(lines[i])
        if m:
            years.append(m.group(1))
            i += 1
            continue
        if lines[i].endswith("(Area %)"):
            i += 1
            continue
        break

    rows: dict[str, dict] = {}
    name_parts: list[str] = []
    while i < len(lines):
        line = lines[i]
        if line.startswith("Figure ") or line in SECTIONS:
            break
        if _NUMBER_RE.match(line) and name_parts:


            acres = []
            for _ in range(len(years)):
                if i < len(lines) and _NUMBER_RE.match(lines[i]):
                    acres.append(int(lines[i].replace(",", "")))
                    i += 1
            pcts = []
            for _ in range(len(years)):
                if i < len(lines) and _PERCENT_RE.match(lines[i]):
                    pcts.append(float(lines[i].rstrip("%")))
                    i += 1
            name = " ".join(name_parts).strip()
            rows[name] = {
                year: {"acres": a, "pct": p}
                for year, a, p in zip(years, acres, pcts)
            }
            name_parts = []
            continue
        name_parts.append(line)
        i += 1

    return rows, i


def parse_report(path: Path) -> dict:
    reader = PdfReader(str(path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    out: dict[str, dict] = {}
    for idx, line in enumerate(lines):
        if line in SECTIONS and idx + 1 < len(lines):

            for probe in range(idx, min(idx + 4, len(lines))):
                if lines[probe] == "Class":
                    rows, _ = _parse_section(lines, probe + 1)
                    if rows:
                        out.setdefault(line, {}).update(
                            {k: v for k, v in rows.items()}
                        )
                    break
    return out


def merge(reports: list[dict]) -> dict:
    merged: dict[str, dict] = {}
    for report in reports:
        for section, rows in report.items():
            for name, by_year in rows.items():
                merged.setdefault(section, {}).setdefault(name, {}).update(by_year)
    return merged


def main() -> None:
    paths = [Path(p).expanduser() for p in sys.argv[1:]]
    if not paths:
        print(__doc__)
        raise SystemExit(1)

    merged = merge([parse_report(p) for p in paths])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True))

    print(f"wrote {OUT_PATH.relative_to(Path.cwd())}")
    for section, rows in merged.items():
        years = sorted({y for by_year in rows.values() for y in by_year})
        print(f"  {section}: {len(rows)} classes, years {years}")


if __name__ == "__main__":
    main()
