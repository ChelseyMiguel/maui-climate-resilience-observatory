# GLOBE Site Reconstruction

Turns a NASA GLOBE Observer land cover observation — six photos taken from one
standing point (N/S/E/W, straight up, straight down) — into an explorable
look-around reconstruction of that site in the browser.

Built for the Congressional App Challenge 2026, grounded in NASA SEES Team Terra
research on whether the 2022 Maui drought preconditioned vegetation fuels ahead
of the August 2023 Upcountry Maui wildfires.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python scripts/ingest_maui.py --download-photos
```

The `--download-photos` flag mirrors every photo to `data/photos/` (about 100 MB
for the 166 Pukalani-area photos), so the viewer works with **no network**. It is safe to
re-run: existing files are skipped and a failed photo is retried. Without it
everything still works, loading photos from `data.globe.gov` on demand.

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

Then open http://localhost:8000.

## What works today

- Pulls real land cover observations from the public GLOBE API and caches them.
- Finds observations near a study area (Pukalani/Upcountry Maui by default).
- Reconstructs any observation as a six-faced cube map you can look around in.
- Flags observations missing one or more of the six protocol photos.
- Tracks repeat visits to the same site — the basis for before/after comparison.
- **Places each site against the 2019→2022 browning analysis** — whether the
  observer stood inside a mapped browned patch, how big it is, and how it ranks.
- Shows AOI mean NDVI (Dec 2018 – Dec 2023) with the Aug 2022 drought trough and
  the Aug 2023 Upcountry fires marked.
- Corroborates the browning story with **LCMS**, the USDA Forest Service annual
  land-change product — an independent federal dataset, not the author's own.

## The GLOBE API, as confirmed against the live service

```
GET https://api.globe.gov/search/v1/measurement/protocol/measureddate/
    ?protocols=land_covers&startdate=YYYY-MM-DD&enddate=YYYY-MM-DD
    &geojson=TRUE&sample=FALSE
```

| | |
|---|---|
| **Auth** | **None.** Public read API — no developer key, no access code. |
| **Rate limits** | None documented or observed. Single-query cap of 1M records. |
| **Volume** | ~16k land cover observations/year worldwide — a decade is one request. |
| **Geo filter** | **Not supported.** `countrycode` and bbox params are silently ignored; all geographic filtering happens client-side, and only the clipped region is cached. |
| **Photos** | `data.globe.gov`, public, CORS-enabled, ~300 KB JPEGs. |

Two gotchas that cost real debugging time: the **trailing slash is required**
(404 without it) and the booleans must be **uppercase** `TRUE`/`FALSE` (406
otherwise).

The developer-key/access-code scheme documented at `api.globe.gov/docs` applies
only to the separate *submission* API for POSTing new sensor data — it does not
support the land cover protocol and is not used here.

### Response quirks handled in `lib/globe_api/client.py`

- Empty fields come back as the **string** `"null"`, not JSON `null`.
- Free-text fields use `"(none)"` for empty.
- Timestamps come in two shapes, with and without microseconds, always naive.
- Classification strings look like
  `"80% MUC 43 [Herbaceous/Grassland, Short Grass]; 20% MUC 93 [Urban, Roads and Parking]"`,
  sometimes with a parenthesised variant (`MUC 81 (1)`). Percentages are eyeball
  estimates and do **not** reliably sum to 100.

## Data found near the study area

A search within 25 km of Pukalani returns **34 observations, 23 of them complete
6/6 sets, across 23 distinct sites**. Three GLOBE teams are active on Maui:
`[SEES2026]` (16), `[Hawaii Wing Civil Air Patrol]` (11), and
`[Oregon State University GEOGRAPHY]` (8 — Peder Nelson's institution, including
`04QGH777957` / "Rice Park Maui", 2023-10-08).

**Important limitation for the before/after story:** across all of Maui, **no
site has observations in more than one year.** The five "repeat visit" sites all
repeat within days (2026-07-03 and 07-06), not across seasons. The 2023 / 2025 /
2026 observations near Pukalani are *different site IDs by different teams* —
the closest near-miss is a 2025 CAP site 172 m from Rice Park. So a genuine
same-site before/after does not exist in the public data yet, and would need
either archived non-public coverage or a fresh re-shoot of an existing site.

## Vegetation context (Phase 3)

`lib/vegetation/browning.py` joins each GLOBE observation to the Team Terra
drought/wildfire analysis outputs in `data/research/`:

- `browning_patches.geojson` — 879 patches where dNDVI < -0.10 over 2019→2022,
  totalling 298.6 ha, dominant patch 130.7 ha.
- `pukalani_{ndvi,nbr}_monthly.csv` — monthly AOI means, Dec 2018 – Dec 2023.
  Months with no usable imagery are stored as -9999 and dropped on load.

**The measure is the browned share of a site's 100 m footprint**, not whether one
GPS point lands in a patch. A GLOBE site is documented as a 100 m square, and
citizen-science GPS is good to anywhere from 3 m to over 1 km, against patches
that are fragmented and only ~265 m across. A single point flips with the phone's
error; the footprint share barely does. Each result also carries the range the
share spans as the footprint slides by the recorded GPS error, and is read
against the whole study area, which is 42.7% browned.

Of the 19 observations inside the study area:

- **16 have at least 25% of their footprint browned; the median is 63%.**
- The SEES2026 Pukalani cluster runs **52–93%**, and stays at least 26% browned
  even at the worst end of each site's GPS error.
- 2 sites (Civil Air Patrol, ~1.7 km east) have no browned pixels at all.

**Read that against the baseline.** The study area as a whole is 42.7% browned, so
a 63% median is above it but not dramatically, and these sites are clustered in
one part of the area, not sampled at random. The supportable claim is that the
sites sit in a heavily browned part of the study area. It is *not* that GLOBE
sites are more browned than the area around them, and it is not a validation.

**The point-in-patch reading is kept as a secondary line, with a confidence flag.**
11 of the 31 nearby observations read as "inside a patch" (an earlier version said
13; it ignored interior holes). But only **1** of those 11 has a GPS error small
enough to say so, because the sites sit 5–40 m from patch edges: 9 are uncertain
and 1 has no accuracy recorded. Confidence also floors the error at one 10 m
Sentinel-2 pixel, since the patch edge is only that precise.

AOI mean NDVI bottoms out in **August 2022 at 0.289**, one year before the
Upcountry fires.

Deliberately dependency-free: point-in-polygon is a plain ray cast and the CSVs
go through the stdlib. Reading the companion dNDVI/dNBR GeoTIFFs would pull in
rasterio/GDAL for a per-pixel value the patch polygons already summarize.

## LCMS corroboration

`lib/vegetation/lcms.py` serves Maui County trajectories parsed from the LCMS
Dashboard reports (v2024-10) by `scripts/extract_lcms.py`. It matters because it
is *independent*: the browning analysis is the author's own Sentinel-2 work,
while LCMS is built by other people from other imagery.

| LCMS class | 2018 | 2022 | 2023 | 2024 | change |
|---|---|---|---|---|---|
| Insect, Disease, or Drought Stress | 20,716 ac | **39,709** | 38,271 | 49,986 | **+141%** |
| Wildfire | 0 ac | 6 | **91** | 71 | +71 ac |
| Agriculture (land use) | 22,980 ac | 11,884 | 11,213 | 9,102 | **-60%** |
| Rangeland or Pasture | 419,062 ac | 430,856 | 430,352 | 430,391 | +3% |

Drought stress nearly doubles by 2022 — the year *before* the fires — and the
Wildfire class picks up the August 2023 events. Meanwhile agriculture falls 60%
while rangeland gains ~11,300 acres: former plantation land going fallow into
unmanaged grass, which is the best-documented driver of Maui's fire risk.

**These are county-wide figures, not per-site measurements**, and the UI says so.
Per-site LCMS classes need `scripts/gee/lcms_site_sample.js`.

## Earth Engine

GEE is used the way the rest of this analysis already uses it: scripts pasted
into the Code Editor that export to Drive, with the app consuming the static
outputs. No live GEE call, no service-account key, and nothing to authenticate
on judging day.

- `scripts/gee/lcms_site_sample.js` — LCMS Change / Land Cover / Land Use class
  sampled **at each GLOBE site**, 2018-2024, at LCMS's native 30 m.
- `scripts/gee/site_timeseries.js` — NDVI **and** NBR per site (30 m buffer),
  Dec 2018 to present, replacing the single AOI-wide curve and extending past
  the existing series' Dec 2023 end so the 2025/2026 observations are covered.
- `scripts/export_sites_for_gee.py` — regenerates the site list both scripts
  embed, so coordinates stay in sync with the cached GLOBE data.

Both scripts reuse the masking, band pairing and `-9999` sentinel from
`gee_export_nbr.js`, so their CSVs drop into the existing loaders unchanged.

## Layout

```
app/
  main.py                    FastAPI app — static mount, index, routers
  api/routes/sites.py        search / observation detail / site history
  static/js/cubemap-viewer.mjs   the cube-map viewer (vendored ESM, no build step)
  static/vendor/esm/         react, three, r3f, drei, htm — served locally
  templates/index.html       the page; import map + sidebar + viewer
lib/globe_api/client.py      GLOBE API client, parsing, caching, geo filtering
lib/vegetation/browning.py   spatial join to the browning patches + NDVI/NBR series
lib/vegetation/lcms.py       LCMS county land-change trajectories
scripts/gee/                 Earth Engine export scripts (run in the Code Editor)
scripts/extract_lcms.py      LCMS Dashboard PDFs -> data/research/lcms_maui.json
data/research/               browning patches + monthly NDVI/NBR (committed)
scripts/ingest_maui.py       warm the cache before a demo
tests/unit/                  parsing tests built from real API responses
data/cache/                  cached raw GeoJSON (gitignored, regenerable)
```

## Design notes

**No build step.** React, three.js, react-three-fiber, drei and htm are vendored
as ES modules under `app/static/vendor/esm/` and wired up with an import map, so
there is no npm, bundler, or JSX transform anywhere. Components are written with
`htm` tagged templates. This is carried over from the CoralPulse project.

**Not photogrammetry, deliberately.** Six photos from a single point have no
parallax, so no depth is recoverable. The viewer reprojects the photos onto the
six faces of a cube and puts the camera inside. Seams between faces are real and
expected — a phone's field of view is narrower than the 90° a true cube face
needs. Being straight about that limit is part of the project's story.

**Offline photos.** The API serves a local copy of each photo when one exists in
`data/photos/` and falls back to GLOBE per photo, so a partial mirror still works.
The original `data.globe.gov` URL is always kept as `source_url` for attribution.
Downloads go through a temp file and are checked to be actual images, so an
interrupted run or an HTML error page can't leave a broken cube face behind.

**Caching.** Because the API cannot filter geographically, the client clips
results to a named `BoundingBox` before writing them, and caches per (area, date
range) under `data/cache/`. A decade of land cover worldwide is ~200 MB and takes
~2 s to parse; the same window clipped to Hawaii is **776 KB** and loads in
0.04 s. Parsed results are additionally memoized in process (~1 ms warm). The
cache is regenerable and gitignored, and the app never needs the network at demo
time. Widening the region writes a separate cache file rather than silently
reusing a narrower one.

## Roadmap

- **Phase 3** — ✅ browning-patch join and NDVI/NBR series shipped. Still open:
  a before/after view, which needs a site with two dates (see the limitation
  above) — the mechanism is blocked on data, not code.
- **Phase 4** — a 2-servo pan/tilt capture rig (ESP32/Arduino) that automates the
  six-shot sequence, turning a manual protocol into a repeatable station.

## Credits

GLOBE Observer land cover data is collected by citizen scientists worldwide and
published by NASA/GLOBE. Vendored libraries: React, three.js,
@react-three/fiber, @react-three/drei, htm.
