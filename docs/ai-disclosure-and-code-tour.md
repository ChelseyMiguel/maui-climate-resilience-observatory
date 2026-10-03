# AI disclosure + code tour — DRAFT, rewrite in your own words

CAC allows AI use but requires it to be **fully and clearly disclosed**, and it must
not do the entire technical development: judges look for significant personal
contribution *and understanding*. This file has two jobs.

1. **Part A** is a factual disclosure draft. Keep it accurate; edit the wording
   into your own voice, and fill every `[bracket]` yourself. I only wrote down what
   I can actually see in the files and in this session.
2. **Part B** is a code tour for *you*. If a judge asks "how does this work?", you
   should be able to answer from your own understanding. If you can't explain a row
   yet, that is the thing to study, not to paper over.

---

## Part A — Disclosure draft

**AI tool used:** Claude (Anthropic), via Claude Code, as a pair-programming
assistant during development, September–October 2026.

**What the AI did (be specific, this is the honest part):**

- Wrote most of the application code in this repository: the GLOBE API client
  (`lib/globe_api/`), the FastAPI routes (`app/api/routes/sites.py`), the browser
  cube-map viewer (`app/static/js/`), the vegetation-context module
  (`lib/vegetation/`), and the tests.
- Investigated the GLOBE Observer API (authentication, rate limits, data format)
  and reported what it found.
- Found and fixed bugs, including a polygon-hole error that had overcounted
  browned sites and a rendering problem in the 3D viewer.
- Drafted the Earth Engine export scripts in `scripts/gee/`, modelled on the
  existing `gee_export_nbr.js`.

**What I did:** `[fill in — only what is true. Candidates, from the files:]`

- `[Conceived the project and chose to pivot from the coral reef app to GLOBE]`
- `[Designed and ran the NDVI/NBR drought analysis: dNDVI/dNBR maps, the 879-patch
  browning layer, the monthly time series, the NDVI vs NBR comparison, and the
  seasonal-baseline z-score method]` — these predate this tool; the analysis files
  (`gee_export_ndvi.js`, `pukalani_fire_precursor.py`, `gee_export_nbr.js`,
  `pukalani_nbr_comparison.py`) are yours.
- `[Decided what the tool should show, what claims it could honestly make, and
  what to cut]`
- `[Tested it on real sites, verified the 3D view in a browser, directed every change]`
- `[Contacted mentors and collaborators]`
- `[Anything you wrote or edited by hand: list it]`

**Prior work reused:** the vendored JavaScript modules and the overall FastAPI +
no-build-step layout come from your earlier CoralPulse project. CAC counts only
work created after Oct 30, 2025, so say which parts are reused versus new.
`[confirm CoralPulse's own dates and how it was built]`

**Open-source libraries:** FastAPI, Uvicorn, Pydantic, httpx, pypdf, pytest, Ruff
(Python); React, three.js, @react-three/fiber, @react-three/drei, htm (JavaScript,
vendored). Languages: Python, JavaScript, Earth Engine JavaScript.

**Data sources and credit:**

- GLOBE Observer land cover observations: NASA / the GLOBE Program (public API,
  no authentication).
- LCMS v2024-10: USDA Forest Service Landscape Change Monitoring System.
- Sentinel-2 imagery: ESA / Copernicus, processed in Google Earth Engine.
- NASA SEES (Earth System Explorers) and the GLOBE team: guidance and permission to
  be credited. `[exact wording they asked for, if any]` Do not imply they reviewed
  or endorsed the tool.

---

## Part B — Code tour: can you explain each of these?

For each row, try answering the question out loud *without* looking at the code.

| Piece | Plain-language job | The question a judge might ask |
|---|---|---|
| `lib/globe_api/client.py` | Pulls GLOBE land cover observations and turns each into one clean object | **Why is every geographic filter done on your side?** The API silently ignores location parameters, so you fetch by date and clip afterwards |
| `BoundingBox` + cache | Keeps only Hawaii on disk | Why did the cache shrink from 281 MB to under 1 MB? Because the clipping happens *before* it is saved |
| `_clean()` | Turns GLOBE's string `"null"` into real `None` | What would break if you didn't? Empty fields would be treated as real values |
| `app/main.py` | Serves the page, the API, the vendored JS, and the photos | Why is there no template engine? `htm`'s `${{ }}` collides with Jinja's `{{ }}` |
| `cubemap-viewer.mjs` | Puts the six photos on six planes around the camera | **Why isn't this photogrammetry?** One point gives no parallax, so there is no depth to recover |
| The "fill" vs "true field of view" toggle | Stretch photos to fill the cube, or draw them at their real angle | Where does 65° come from? It is an *assumption* (no EXIF), and the toggle says so |
| `view-math.mjs` | The compass/pitch maths, separate so it can be tested | What bug did the tests catch? Sky and Ground labels were swapped |
| `lib/vegetation/browning.py` | Measures how much of a 100 m site browned | **Why the footprint share instead of "is the GPS point in a patch"?** GPS error (3 m to 1 km) is bigger than the distance to patch edges (5–40 m) |
| Polygon holes | Excludes unbrowned islands inside a patch | What went wrong before? Holes were counted as browned, which overcounted 2 sites |
| `AOI_BROWNED_FRACTION` (42.7%) | The yardstick for a site's own browned share | Why does 63% not prove much on its own? The sites cluster in one hotspot of an area that is already 43% browned |
| `lib/vegetation/lcms.py` | County-wide LCMS trends | **Why is it labelled county-wide, not per-site?** Maui County is 1.17 M acres; your analysis is a 1.5 km study area |
| `scripts/gee/*.js` | Per-site LCMS classes and NDVI/NBR curves from Earth Engine | Why not call Earth Engine live? Authentication, and a demo that fails on judging day |
| `mirror_photos()` | Saves photos locally so the demo works offline | Why write to a temp file and rename? An interrupted download would leave a truncated image |

**Two honest claims to be able to defend:**

1. *"Two independent analyses agree"* — yours (Sentinel-2) and LCMS (Landsat +
   Sentinel-2). They differ in team, method and part of the inputs. They are **not**
   three independent datasets: the drought and land-use signals are both LCMS.
2. *"The sites sit in a heavily browned part of the study area"* — **not** "GLOBE
   sites are more browned than elsewhere", and not a validation.

**Question 4 on the form ("what difficulty did you face?")** has real material in
this repo: the GLOBE API has no location filter; GPS error exceeding the size of
what you are measuring; a count that turned out wrong (13 → 11) because polygons
have holes; and then learning that even 11 was too fragile to claim, which led to
the footprint measure. Those are genuine, specific, and yours to tell in your own
words.
