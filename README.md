<img src="docs/logo/browning-viewer-logo.png" alt="Browning Viewer" width="220">

# Browning Viewer

**See environmental change. Understand community vulnerability.**

An interactive GIS research dashboard for Upcountry Maui — Pukalani, Makawao and
Kula — that puts historical vegetation change, drought, the August 2023 fires and
community context side by side, with every source and caveat in view. At its
centre is a **GLOBE site viewer** that rebuilds a NASA GLOBE Observer citizen
scientist's six land-cover photos into a 360° view.

Built for the Congressional App Challenge 2026 from NASA SEES research on whether
the 2022 drought left Upcountry vegetation browned ahead of the 2023 fires.

> **Research and education only.** Not an emergency alert, evacuation routing or
> fire-risk service, and not for emergency decision-making. For alerts use
> [MEMA Alerts](https://www.mauicounty.gov/983/MEMA-Alerts).

## Run it

Quickest: `./run.sh` (sets everything up on first run), then open http://localhost:8000.


Needs Python 3.11+. Node.js is only needed to *change* the front end — the built
site is committed, so the app runs without it.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

Open http://localhost:8000. Optionally mirror the site photos for fully offline use
(~100 MB):

```bash
.venv/bin/python scripts/ingest_maui.py --download-photos
```

### Working on the front end

```bash
cd web && npm install
```

```bash
npm run dev
```

`npm run dev` serves the Observatory with hot reload on http://localhost:5173 and
forwards data requests to the FastAPI server on :8000 (start that first).
`npm run build` writes the production site into `app/static/site/`.

### Checks

```bash
.venv/bin/python -m pytest tests/unit -q
```

```bash
cd web && npm run check && npm test && npm run build
```

`npm run check` is the typecheck (svelte-check + TypeScript); Python is linted with
`ruff check lib app tests scripts`.

## Pages

| Path | Page | What it shows |
|---|---|---|
| `/` | Overview | The mission, why Upcountry, sourced key facts, what this is and isn't |
| `/explore` | Map Explorer | MapLibre map: vegetation change, drought by year, fires, facilities, places, GLOBE sites; year filter; inspectable feature cards |
| `/insights` | Region Insights | Pukalani / Makawao / Kula: vegetation and drought time series, date filter, dry-season comparison, CSV export |
| `/map` | 3D View | three.js terrain with layers draped on it, a guided tour, and a slot for before/after satellite imagery |
| `/viewer` | Site Viewer | 360° reconstruction of a GLOBE land cover site, compass, mini-map |
| `/methods` | Methods | Formulas, cloud masking, baselines, caveats, hazard vs. exposure vs. vulnerability vs. preparedness |
| `/sources` | Sources | Provenance table: provider, resolution, coverage, period, currency, licence, link |
| `/about` | About | Independent student project; acknowledgements without implied endorsement |

## Data — all real, nothing simulated

There is **no synthetic or demo data** anywhere. Where a layer doesn't exist for a
place or year, the app shows an empty state instead.

| Layer | Source | Notes |
|---|---|---|
| dNDVI / dNBR change rasters, 879 browning patches, monthly NDVI/NBR | Author's Sentinel-2 analysis (Google Earth Engine) | 10 m, 1.5 km study area, dry season 2022 minus 2019. The raster reproduces the manuscript's 42.7% browned exactly. |
| GLOBE land cover observations | NASA GLOBE Observer public API | Citizen science; GPS accuracy 3 m to over 1 km |
| Fire perimeters | National Interagency Fire Center (WFIGS) | Olinda, Kula, Pulehu, Lahaina (2023); Central Maui (2019); Crater (2024). Dates in Hawaiʻi time |
| Drought maps and index | U.S. Drought Monitor | One category map per year (week nearest 8 Aug); weekly county DSCI and category shares |
| LCMS land change | USDA Forest Service | Maui County totals, 2018–2024 |
| Fire & EMS stations, hospital, schools | Hawaiʻi Statewide GIS Program | Locations only, with each publisher's currency (e.g. private schools "as of November 2021") |
| Pukalani, Makawao, Kula boundaries | U.S. Census 2020 (via Hawaiʻi GIS) | Statistical areas, not legal town limits |
| Terrain | AWS Terrain Tiles / USGS 3DEP | Matches GLOBE recorded elevations to a 1 m median at 30 sites |

Refresh any public layer with the matching `scripts/fetch_*.py`.

### Remote-sensing products (public AWS archives, no accounts)

Built by `scripts/remote_sensing/` (`.venv/bin/pip install -r requirements-data.txt` first);
the outputs are committed, so the app needs none of this to run.

| Script | Source | Products |
|---|---|---|
| `sentinel2_composites.py` | Sentinel-2 L2A COGs (`sentinel-cogs`, tile 4QGJ) | Dry-season NDVI/NBR 2017–2025 on the study grid; true-colour and colour-infrared images for 2019, 2022 and before/after the 2023 fires; regional 2019→2022 change; an independent check of the study raster (r = 0.854) |
| `lidar_canopy.py` | USGS 3DEP lidar 2022–23 (`usgs-lidar-public`) | 2 m ground model, height above ground, hillshade; 300k points for the 3D view |
| `worldcover.py` | ESA WorldCover 2021 (`esa-worldcover`) | 10 m land cover; browning share per class |
| `maui_inset.py` | Copernicus DEM GLO-90 | Locator inset |

## Key findings — and their limits

Stated carefully; `docs/evidence-claims.md` lists what can and cannot be claimed.

- **2022 was Maui County's worst drought year of 2018–2024**: the highest average
  drought index, and 20 weeks of D4 "exceptional" drought. D4 also occurred in
  2019, 2020 and 2021, but far less (1–8 weeks).
- **42.7% of the 1.5 km Pukalani study area browned** between the 2019 and 2022 dry
  seasons. Dry-season NDVI fell 19% (0.405 → 0.327) and NBR 42% — the moisture-
  sensitive index responds more strongly.
- **The study area did not burn.** The nearest 2023 perimeter (Olinda) starts ~1.5 km
  outside it, and no browned patch lies inside any perimeter. The Olinda fire did
  burn inside the Makawao Census place, and the Kula fire inside Kula.
- **The study area is ~81% inside Pukalani, ~6% Makawao, 0% Kula**, so only Pukalani
  is shown with a vegetation series. Makawao and Kula show an empty state rather
  than borrowed numbers.
- **GLOBE sites near Pukalani sit in a heavily browned part of the study area**
  (median 63% of the 100 m footprint, against 42.7% study-wide). They are clustered,
  so this is not a validation.
- **Structure-from-motion does not work on GLOBE photos** (12 of 496 pairs matched).
  See `docs/sfm-experiment.md`, and `docs/capture-protocol.md` for a capture that
  should.

## Architecture

```
app/main.py                    FastAPI: API, static files, Observatory + /viewer routes
app/api/routes/sites.py        GLOBE observations, site detail, LCMS, NDVI series
app/api/routes/layers.py       map layers, region insights, drought maps, rasters, imagery
app/templates/index.html       the 360° viewer page (no build step)
app/static/js/                 viewer modules: cubemap-viewer.mjs, view-math.mjs
app/static/site/               the built Observatory (committed)
web/                           Observatory source: Svelte 5, TypeScript data layer
  src/lib/types.ts             Region, DatasetMetadata, RasterLayerMetadata, TimeseriesPoint, InfrastructureFeature
  src/lib/adapters.ts          the only code that knows API shapes
  src/lib/utm.ts, raster.ts    UTM <-> WGS84; GeoTIFF rasters on the map (2.7 m placement error)
  src/pages/                   Overview, Explore, Insights, Map3D, Methods, Sources, About
lib/globe_api/client.py        GLOBE API client, cache, photo mirror
lib/vegetation/                browning patches + footprint measure, LCMS
lib/hazards.py                 fire perimeters, drought record
lib/regions.py                 region insights; who gets a vegetation series and why
scripts/fetch_*.py             public-data fetchers
scripts/gee/                   Earth Engine scripts (run in the Code Editor)
scripts/sfm/run_sfm.py         structure-from-motion (optional pycolmap)
tests/unit/                    Python tests (pytest)
tests/js/                      JS/TS tests (node --test)
```

Presentation never fetches directly: pages use `web/src/lib/adapters.ts`, which maps
API responses onto the typed interfaces in `types.ts`. A new source means a new
adapter, not page changes.

## Next three steps to connect more real data

1. **Run `scripts/gee/region_timeseries.js`** in Earth Engine and save its CSV. It
   gives Makawao and Kula their own monthly NDVI/NBR, replacing their empty states.
2. **Run `scripts/gee/imagery_before_after.js`** and save the two exports as
   `data/imagery/before_2023.tif` and `after_2023.tif`. The 3D view picks them up
   automatically and shows the burn scars on the terrain.
3. **Run `scripts/gee/fire_perimeter_browning.js`.** It runs the browning method
   inside each 2023 perimeter against a 1 km unburned ring — the direct test of the
   research question, which nothing in the app can answer yet.

## Scientific and public-safety limitations

- **Historical, not live.** Nothing is a forecast, real-time warning or alert.
- **No fire-risk score.** No validated model exists here, so none is computed.
- **No routing, shelters or road status.** Not shown: no authoritative, current
  source has been verified. Facility points are locations only.
- **Greenness is not fuel.** NDVI change can reflect drought, grazing, mowing or land
  use, and is not a measure of fuel load.
- **Scale.** Vegetation: a 1.5 km circle. Drought: county-wide. LCMS: county
  totals. They are never presented as the same place.
- **Correlation, not causation.** Nothing here shows that browning caused or
  predicts any fire.

## Credits and AI use

Data from NASA GLOBE Observer citizen scientists, NIFC, the U.S. Drought Monitor,
the USDA Forest Service, the Hawaiʻi Statewide GIS Program, the U.S. Census Bureau
and Copernicus Sentinel-2. Thanks to the NASA SEES and GLOBE team for guidance and
permission to be credited; no endorsement is implied.

Built with substantial help from an AI coding assistant (Claude). See
`docs/ai-disclosure-and-code-tour.md`.

Open-source libraries: FastAPI, Uvicorn, Pydantic, httpx, pypdf, pytest, Ruff;
Svelte, Vite, TypeScript, MapLibre GL JS, three.js, geotiff.js; React,
@react-three/fiber, @react-three/drei and htm (vendored, viewer); COLMAP via
pycolmap (SfM experiment only).
