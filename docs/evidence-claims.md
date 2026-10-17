# What each data source actually shows — and what it doesn't

Written so the demo video, the written answers, and any pointed question from a
judge or from Peder all get the same careful answer. The framing here is
deliberately more conservative than "three independent lines of evidence."

## The sources

| # | Source | Who made it | Imagery | Spatial scale |
|---|---|---|---|---|
| 1 | dNDVI / dNBR browning analysis | This project (NASA SEES Team Terra) | Sentinel-2 SR Harmonized | Pukalani AOI, 1.5 km buffer |
| 2 | LCMS Vegetation Change ("Insect, Disease, or Drought Stress") | USDA Forest Service | Landsat (40+ yr) **+ Sentinel-2** | Maui County |
| 3 | LCMS Land Use (Agriculture → Rangeland) | USDA Forest Service | same as #2 | Maui County |

## How independent are they, really?

**Not three independent lines. Two analyses, and they partly share inputs.**

- **#2 and #3 are the same product.** Both come from LCMS v2024-10. They are two
  different *signals* — a change classification and a land-use classification —
  but one dataset, one team, one processing chain. If LCMS has a systematic
  problem over Maui, both move together.
- **#1 and #2 share an input sensor.** LCMS ingests Sentinel-2 alongside
  Landsat, and this project's analysis is Sentinel-2. They are not sensor-
  independent. What *is* independent: different teams, different algorithms
  (a hand-built dry-season difference vs an ensemble classifier over a 40-year
  Landsat record), and different training data.
- Both are optical remote sensing, so they share failure modes — cloud, sensor
  calibration drift, phenological timing.

**The honest claim:** *two independent analyses, by different teams using
different methods and partly different sensors, agree — and one of them also
supplies a land-use mechanism that explains the fuel.*

That is still a strong claim. It is just not "three independent datasets."

## The scale gap — the most likely pointed question

The browning analysis is a **1.5 km AOI around Pukalani**. The LCMS figures in
the app are **Maui County-wide** (1.17 M acres).

So this statement is NOT supported:

> "LCMS confirms that this site browned."

County-wide drought stress rising does not, on its own, say anything about the
7.12 ha patch a given GLOBE site sits in. What is supported:

> "This site sits inside a patch my own analysis flagged as browned, and across
> Maui County an independent Forest Service product recorded drought-stressed
> vegetation nearly doubling over the same period."

Two true statements at two different scales, joined honestly.

**How to close the gap:** `scripts/gee/lcms_site_sample.js` samples the LCMS
class at each GLOBE site at native 30 m. Once that CSV exists, the per-site
claim becomes available and the scale caveat mostly goes away:

**Running it** (needs you, online): paste the site list from
`python scripts/export_sites_for_gee.py --area pukalani --complete-only` into the
script, run it in the Earth Engine Code Editor, download `lcms_site_classes.csv`
from Drive into `data/research/`, then
`python scripts/crosscheck_lcms.py --csv data/research/lcms_site_classes.csv`.
That compares each GLOBE observation's own label with LCMS at its site and year
and prints every row, including the ones that could not be compared. The class
crosswalk behind it is a judgment (`lib/crosscheck.py`): read it before quoting a
result. Note the script was changed to export `*_name` label columns; the earlier
version exported integer codes only, and the Python side refuses such a CSV.
**The Earth Engine edit has not been run** (no access from the sandbox where it was
written); if it errors in the Code Editor, the failing line will say why.

> "LCMS classified this pixel as drought-stressed in 2022."

That is the single highest-value thing the Earth Engine exports unlock.

## Claim checklist

Safe to say today:

- 42.7% of the Pukalani AOI browned (dNDVI < -0.10), 2019→2022; 879 patches,
  298.6 ha, dominant patch 130.7 ha.
- 16 of the 19 GLOBE observations inside the study area have at least 25% of their
  100 m site footprint browned; the median is 63%, the SEES2026 Pukalani cluster
  runs 52-93%. Say it as "the sites sit in a heavily browned part of the study
  area", and always next to the 42.7% study-area baseline.
- AOI mean NDVI bottoms out August 2022, a year before the fires.
- Maui County: LCMS drought stress 20,716 → 39,709 ac by 2022 (+92%), 49,986 ac
  by 2024 (+141%); Wildfire class 0 → 91 ac in 2023.
- Maui County: agriculture -60% since 2018 while rangeland/pasture gained
  ~11,300 ac — the fallow-fuel mechanism.
- dNBR detects more browning than dNDVI at the -0.10 threshold (median -0.098
  vs -0.084), i.e. the SWIR-based index is more sensitive to this drought.

## The fires and the study area — read this before any fire claim

The August 2023 perimeters (NIFC WFIGS) show that **none of the fires burned
inside the Pukalani study area.** The nearest, Olinda, has its edge ~3 km from the
study-area centre, so ~1.5 km outside the 1.5 km circle; Kula is 6.2 km away and
Pulehu 5.2 km. **No browned-patch polygon lies inside any perimeter.**

So the browning analysis describes ground *near* the fires, not ground that burned.
Supportable: "regional drought preconditioning in the Upcountry area that
burned". Not supportable: "the browned ground burned".

`scripts/gee/fire_perimeter_browning.js` runs the same dNDVI/dNBR method inside
each burned perimeter against a 1 km unburned ring next to it. Until it has been
run, there is no evidence either way about the burned ground itself.

Drought context (U.S. Drought Monitor, Maui County): 2022 had the highest annual
mean DSCI in the record (214); in the week of the fires it was 135 and rising
(106 -> 135 -> 180 over three weeks).

## Drought years — corrected

U.S. Drought Monitor, Maui County, 2018–2024 (weekly category shares):

- **2022 had the highest average drought index (DSCI 214) and 20 weeks of D4
  "exceptional" drought** (August–December, up to 9.3% of the county).
- **D4 also occurred in 2019 (4 weeks), 2020 (1) and 2021 (8).** An earlier
  version of this project said 2022 was "the only year Maui reached D4" — that was
  true only of the single early-August map shown per year, not of whole years.
- "Worst year" means worst of **2018–2024**, the years pulled; the Drought Monitor's
  record goes back to 2000. Don't say "on record".

## Places — Pukalani, Makawao, Kula (2020 Census places)

- The 1.5 km study area is **~81% inside Pukalani, ~6% Makawao, 0% Kula**. Its
  vegetation series can be described as Pukalani's study area, never as Makawao's
  or Kula's.
- **The Olinda fire burned inside the Makawao Census place, and the Kula fire inside
  Kula.** Pukalani's boundary is ~0.6 km from the Olinda perimeter.
- Pukalani study-area dry-season NDVI: 0.405 (2019) → 0.327 (2022), −19%; NBR −42%.
  Both years have all five dry-season months. A two-year comparison, not a trend.

Not safe to say yet:

- ~~"The browned patches burned."~~ — none lie inside a 2023 perimeter.
- ~~"Browning predicted where the fire went."~~ — untested; needs the burned-vs-
  unburned comparison, and even then it is a correlation, not a prediction.
- ~~"2022 was the only year with exceptional (D4) drought."~~ — D4 also occurred in
  2019, 2020 and 2021; 2022 had by far the most weeks.
- ~~"Makawao/Kula browned X%."~~ — no vegetation series exists for either yet.
- ~~"The tool does structure-from-motion / a 3D reconstruction of a site."~~ — SfM
  was attempted and failed on this data (`docs/sfm-experiment.md`).

- ~~"These sites are inside browned patches."~~ — 11 of 31 read as inside, but
  only 1 has a GPS error small enough to say so (the sites sit 5-40 m from the
  edges of fragmented patches). Use the 100 m footprint share instead.
- ~~"GLOBE sites are more browned than the surrounding area."~~ — the median site
  is 63% against a 42.7% study-area baseline, but the sites are clustered in one
  hotspot, not randomly sampled, so this is not a comparison.

- ~~"LCMS confirms this site browned."~~ — scale mismatch; needs the per-site sample.
- ~~"Three independent datasets agree."~~ — two analyses, partly shared sensors.
- ~~"This site got drier between two GLOBE visits."~~ — no Maui site has
  observations in more than one year. Needs the re-shoot or archived coverage.
- ~~"The browning caused the fire."~~ — the analysis establishes fuel
  preconditioning, not ignition or causation.

## OPEN ITEM — the drought–greenness correlation has two different numbers

The brief and manuscript cite a DSCI–NDVI correlation of **r = −0.47**. The
Region Insights page ("Drought and greenness, month by month") computes its own
figure from the files in `data/research/` (`lib/relationships.py`, pinned in
`tests/unit/test_relationships.py`):

| Method on the shipped files | r | n |
|---|---|---|
| Monthly mean county DSCI vs. monthly NDVI, same month (**what the page shows**) | −0.69 | 61 months |
| Same, NBR instead of NDVI | −0.77 | 61 |
| Month-of-year cycle removed from both (exploratory, not in the app) | −0.64 | 61 |
| May–September months only (exploratory, not in the app) | −0.76 | 25 |

**None of these reproduces −0.47**, so the manuscript used a different pipeline
(different time resolution, window, composite or spatial unit — not recorded in
this repo). The page deliberately states only what it computes and never quotes
−0.47.

**Before the video or written answers:** find out how −0.47 was produced, then
either (a) show that number with its own method, or (b) say the page's figure
and the manuscript's differ because of X. Quoting both without a reason is the
easiest way to lose a judge's trust. Either way this is a correlation of two
coarse, autocorrelated series at different scales (county drought vs. a 1.5 km
area) — not a cause, and not a forecast.

What the data does support without a caveat about methods: in the May–September
means, 2022 has both the highest county DSCI (249) and the lowest NDVI (0.327) of
the five years, and 2023 is back to 122 / 0.421. The same-month link is gone by
about three months apart (r ≈ −0.03 for NDVI), so this data shows drought and
greenness moving together in the same month, not a lagged "preconditioning"
effect; that claim would need a different test.

## Rainfall (exported 2026-10, `data/research/pukalani_rainfall_monthly.csv`)

Source: `notebooks/gee_exports.ipynb` / `scripts/gee/rainfall_monthly.js` — CHIRPS,
TerraClimate, IMERG V07, ERA5-Land, each the one pixel (~4.6–11 km) containing
the study-area centre, Jan 2018 – Dec 2024, all 84 months present. Computed by
`lib/rainfall.py`, pinned in `tests/unit/test_rainfall.py`.

Supported, with method attached:

- The four products move together: r = 0.67–0.82 for every pair (monthly). They
  disagree on amounts (IMERG highest), so **no product's millimetres are quoted**.
- Rain summed over the **last 2–3 months** matches the study area's monthly NDVI
  best: median r ≈ +0.66 across products, vs. ≈ +0.43 for one month.
- The county drought index behaves like 3-month rain: r ≈ −0.67 (median) vs.
  ≈ −0.3 for one month. That is why DSCI tracks greenness better than one
  month's rain does.
- **Strict version** (each series' month-of-year cycle removed): one month of
  rain says almost nothing (median r ≈ +0.06); a **12-month** total is best
  (≈ +0.49). Once ordinary seasons are subtracted, a wetter- or drier-than-usual
  year is what shows in the vegetation.

What this means for the −0.47 question: on the same data, reasonable method
choices give drought/rain–greenness correlations anywhere from ≈ 0.06 to 0.70.
A correlation is not quotable without its method.

Not supported: any statement about rain *at Pukalani* in mm, and any causal or
predictive claim.

## Satellite land cover at the GLOBE sites (`data/research/landcover_site_classes.csv`)

ESA WorldCover and Dynamic World, sampled at the 15 Pukalani-area sites:

- The two maps agree on the coarse class at **8 of 15 sites in 2020 and 6 of 15
  in 2021**. WorldCover calls 13 of 15 sites grassland in 2021; Dynamic World
  calls 9 of them built-up. Dynamic World's yearly class changes at 8 of 15 sites.
- Reading: these sites are parks, fields and roadsides, mixed at the 10 m pixel
  scale, so satellite land cover is not a dependable ground truth here. That is
  an argument *for* ground photos like GLOBE's, not against them.
- The GLOBE-label comparison itself needs the local GLOBE cache:
  `python scripts/crosscheck_lcms.py --landcover data/research/landcover_site_classes.csv`.
- LCMS at the sites: the first export failed (`USFS/GTAC/LCMS/v2024-10`
  filtered to `study_area == 'HI'` returned no images; the asset is superseded).
  The notebook and `lcms_site_sample.js` now use the newer asset and filter by
  location; not yet re-run.

### LCMS at the sites (`data/research/lcms_site_classes.csv`, 2025-11 asset)

105 rows = 15 sites x 2018-2024. The asset has no class-name tables, so codes were
decoded from its own `*_Raw_Probability_*` band order and that decoding was
**tested** (notebook cell 4c): each site-year's code equalled its most probable
class in **105/105** for Land_Cover, so Land_Cover is decoded
(`scripts/decode_lcms_codes.py`). Land_Use passed only **83%**, below the 95% bar,
so it is **not decoded** and must not be described ("Developed" is plausible for
code 2 but unproven). Change is not decoded.

LCMS calls every site Grass/Forb/Herb in every year.

### Do the three satellite maps agree? (`scripts/compare_satellite_maps.py`)

| Pair | Agree (of 15 sites) |
|---|---|
| LCMS vs ESA WorldCover | 13 in 2020, 13 in 2021 |
| Dynamic World vs WorldCover | 8 in 2020, 6 in 2021 |
| Dynamic World vs LCMS | 4-10 per year, 2018-2024 |

Two maps (30 m LCMS, 10 m WorldCover) agree these are grassland sites; Dynamic
World, the near-real-time 10 m product, often calls them built-up. These are
parks, fields and roadsides, where a pixel mixes grass with pavement. Satellite
land cover is not a dependable ground truth at this scale, which is the case for
ground photos such as GLOBE's. The GLOBE-label check itself runs on the author's
machine (it needs the GLOBE cache):
`python scripts/crosscheck_lcms.py --csv data/research/lcms_site_classes.csv --landcover data/research/landcover_site_classes.csv`.

## DECISION NEEDED — which drought–greenness correlation to quote

Same two series (county DSCI, study-area NDVI, Dec 2018–Dec 2023), different
methods. Computed from `data/research/` on 2026-10-17:

| Method | r | n | Use it? |
|---|---|---|---|
| Annual dry-season means | −0.99 | 5 | **No.** Five points; looks perfect, means little; a judge will rightly attack it |
| Annual means | −0.92 | 5 | **No**, same reason |
| NBR instead of NDVI, same month | −0.77 | 61 | Only if the claim is about NBR |
| **Monthly, same month, Pearson** | **−0.69** | **61** | **Recommended**: what the site shows, tested, reproducible from the downloadable CSV |
| Monthly, rank (Spearman) | −0.67 | 61 | Fine as a robustness check |
| Weekly DSCI vs. that month's NDVI | −0.66 | 265 weeks | Inflates n (weeks share one NDVI value) |
| Monthly, seasonal cycle removed | −0.63 | 61 | The strict version; good to mention |
| Monthly, DSCI one month earlier | −0.42 | 61 | Closest to −0.47, but not it |
| Manuscript | −0.47 | ? | Method not recorded in this repo |

**Recommendation:** quote **r = −0.69 (monthly, same month, 61 months)** in the app,
video and written answers, and add "−0.63 once the seasonal cycle is removed".
Do not quote −0.47 next to it unless you can name its method. If the manuscript
keeps −0.47, its methods section must say how it was computed.

**Draft question for Dr. Low / Peder** (for you to send, in your words):
> "The app recomputes the DSCI–NDVI correlation from our exported series and gets
> r = −0.69 (monthly means, same month, n = 61), or −0.63 with the seasonal cycle
> removed. The manuscript has −0.47. Do you remember how that one was computed
> (which months, time step, lag, or spatial unit), so I can report them
> consistently?"
