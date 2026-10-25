# CLAUDE.md

Browning Viewer — Congressional App Challenge 2026 (due Oct 26, 2026, 12:00 PM EDT).

## Stack
Python 3.11+ / FastAPI (`app/`, `lib/`), Svelte 5 in legacy syntax + Vite + TypeScript + MapLibre + three.js (`web/`, builds to `app/static/site/`), vendored ESM 360° viewer (`app/templates/index.html`, `app/static/js/`), Google Earth Engine scripts (`scripts/gee/`). JSON/GeoJSON files, no database.

## How to work
- Read the relevant code before changing it; match existing style, naming, structure.
- Be efficient and brief. Talk only when needed.
- Fix bugs, edge cases and security issues you find, even unasked.
- If intent is unclear, ask one specific question instead of guessing.
- Every change ships with a verification: a test or a quick sanity check, and run it.
- No fabricated data. Every number must trace to `docs/evidence-claims.md` or a source in `/sources`.

## Commands
- Run: `./run.sh` → http://localhost:8000
- Python tests: `.venv/bin/python -m pytest tests/unit -q`; lint: `ruff check lib app tests scripts`
- Front end: `cd web && npm run check && npm test && npm run build` (commit the rebuilt `app/static/site/`)

## Never
- Use the `coralpulse-maui` service-account key.
- Send emails or push/publish without explicit approval.
