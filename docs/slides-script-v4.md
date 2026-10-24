# Slides + script v4 — 5 slides, 3:00 max

Same five slides as v3, updated with what the app does now. **On slide** = the short text to put on the slide.
**Say** = the words to read. **✂** = cut this sentence first if you run long. Read it aloud once with a timer:
core ≈ 2:34, with every ✂ kept ≈ 2:57 (counted at 150 words a minute; real speed varies, so time yourself). Use your own words where you can; keep the numbers.
**Plan to cut at least two ✂ sentences: 2:57 leaves no margin, and 3:00 is a hard limit.**

The app name is still the working title (Rural Hawaiʻi Climate Resilience Observatory). When you pick a name, change it
in slide 1 and slide 4 and the title card.

---

## Slide 1 — Why it matters: drought, then fire (0:00–0:30)

**On slide**
- Title: *[App name]* · Chelsey Miguel, King Kekaulike High School
- NASA SEES Team Terra: Peder Nelson · Dr. Russanne Low · Cassie Soeffing
- 2022: 20 weeks of exceptional drought, Maui County (most since 2000)
- Aug 8, 2023: fires in Upcountry Maui and Lahaina
- Photo: Pukalani, or the burn scar from space (Sentinel-2, after the fires)

**Say**
> Hello, my name is Chelsey Miguel from King Kekaulike High School on Maui. I built the Rural Hawaiʻi Climate Resilience
> Observatory, a web app that shows Upcountry communities how drought, vegetation and wildfire connect. It grew out of my
> NASA SEES research with Peder Nelson, Dr. Russanne Low and Cassie Soeffing.
>
> In 2022, Maui County had twenty weeks of exceptional drought, more than any year since 2000. The next summer, on August
> 8, 2023, wildfires burned in Upcountry Maui and Lahaina. ✂ *Much of Upcountry's old plantation land is now dry grass.*

## Slide 2 — My NASA SEES research (0:30–1:03)

**On slide**
- Question: did the 2022 drought brown the land before the fires?
- Sentinel-2 satellite, dry seasons 2019 vs 2022, Pukalani Park (10 m)
- 42.7% of 70,280 pixels browned · biggest patch 130.7 ha
- Drought and greenness anomalies move together: r = −0.47
- Browning ≠ burning: the study area did not burn
- Figure: the browning map (red = browned)

**Say**
> My research asked: did the 2022 drought brown the vegetation before the fires? With Sentinel-2 imagery in Google Earth
> Engine, I compared the 2019 and 2022 dry seasons around Pukalani Park. Of 70,280 ten-meter pixels, 42.7 percent
> browned; the largest patch covered 130.7 hectares. Drought and greenness anomalies were correlated, r equals minus
> 0.47. ✂ *A USDA Forest Service map partly agreed.* That doesn't show the browned land burned. It shows the land was
> drying before the fires.

## Slide 3 — What exists, and the gap (1:03–1:25)

**On slide**
- Drought Monitor: county-wide, not a place
- Land-cover maps: expert tools; they disagree at park scale
- NASA GLOBE photos: six flat pictures per site
- Fire-risk map (state): covers communities only
- Gap: nowhere a community can see it all and check the source

**Say**
> The data exists, but it's scattered. The Drought Monitor covers a whole county. Satellite land-cover maps are built
> for experts, and at the scale of a park they disagree. ✂ *The state's fire-risk map covers communities, so the largest
> Upcountry fire burned 99 percent outside any rated area.* My results lived in a poster and in code, so no one place let
> a community see them, or check them.

## Slide 4 — How it grew into an app (1:25–1:57)

**On slide**
- For residents, teachers, GLOBE observers, planners
- All of Maui, 2017–2025 · 26 years of Landsat · lidar · state fire and land-use maps
- Checked: my rebuild from raw satellite data matches the study (r = 0.85)
- Every layer shows its source, date and limits
- Python + FastAPI · JavaScript + Svelte · Google Earth Engine
- Not a forecast, not an alert

**Say**
> So I turned it into the Observatory. It started with one park; now it covers all of Maui, with nine years of Sentinel-2,
> twenty-six years of Landsat, lidar, and the state's fire and land-use maps. Every layer shows its source and limits. I rebuilt my own result from the raw satellite archive, and it matches the original. I built it with
> Python and FastAPI, JavaScript and Svelte, and Google Earth Engine. ✂ *It has nearly three hundred automated tests.*
> It's for learning, not fire alerts.

## Slide 5 — Demo (1:57–2:52)

**On slide** (mostly screen recording; small captions)
- Map Explorer: island NDVI 2017→2025 (press play) · caption "2022 least green since 2017"
- Landsat chart · caption "2022: lowest of 26 years"
- State layers: moisture zone + former plantation land · caption "Study area: dry zone, 76% old plantation"
- 360° GLOBE site · caption "Citizen photos check the satellites"

**Say**
> *(Map Explorer, whole island; press play on the years)* This is all of Maui, dry season by dry season. Watch 2022:
> it's the least green year since 2017, and Upcountry browns the most.
>
> *(Analysis, the 26-year Landsat chart)* Across twenty-six years of Landsat, the 2022 dry season is the lowest.
> ✂ *Because newer Landsat satellites read slightly greener, that comparison is conservative.*
>
> *(Map Explorer, state layers: moisture zones, former plantation land)* The state's maps show my study area sits in the
> dry zones, and about three quarters of it was sugarcane or pineapple land. ✂ *Where it's dry, that land browned more.*
>
> *(Site Viewer: drag the 360° view)* And this is a real GLOBE site rebuilt in 360 degrees. Citizen photos can check what
> satellite maps disagree on.
>
> ✂ *(Closing, over the Overview page)* Forecasters expect a strong El Niño this winter, which tends to bring a drier
> Hawaiʻi. A record of what drought did to this land matters again.

---

## Where each number comes from (so you can answer a judge)

| Say | Source |
|---|---|
| 20 weeks of exceptional drought, most since 2000 | U.S. Drought Monitor, Maui County; 2010 had 9, 2021 had 8 (docs/evidence-claims.md, "Hawaii state data") |
| Do **not** say "worst drought on record" | By annual drought index 2022 ranks 3rd since 2000 (2010 and 2025 higher) |
| 42.7% of 70,280 pixels, 130.7 ha, r = −0.47 | Manuscript (Miguel et al. 2026); r = −0.47 is the monthly anomaly method |
| 2022 least green since 2017 across Maui | Sentinel-2, island median NDVI 0.470 vs 0.557 in 2019 |
| Lowest of 26 years of Landsat | Landsat 2000–2025, study area, z = −1.6 vs 2000–2018 |
| Rebuilt result matches, r = 0.85 | Independent Sentinel-2 rebuild vs the study raster, 70,280 pixels |
| ~three quarters old plantation land | 76% of the study circle in sugarcane/pineapple land 1900–1937 (state maps) |
| Largest fire 99% outside rated areas | NIFC Pulehu perimeter vs DLNR fire-risk areas (rated 2007, populated areas only) |
| Nearly 300 tests | 258 Python + 40 JavaScript |
| Strong El Niño, drier winter | NOAA CPC ENSO discussion, 8 Oct 2026 (greater than 83% chance of strong-to-very strong); El Niño winters tend dry: Kodama, Mauka Showers, 23 Oct 2026 |

**About the El Niño line:** it is a forecast by NOAA, not your result. Keep it hedged ("expect", "tends to"). NOAA's own
drought outlook through January 2027 shows Hawaiʻi drought-free, so don't say a drought is coming.

## Slide design notes
- Dark background to match the app; orange for the one number you want people to see per slide; no gradients, no round frames.
- One idea per slide, five bullets at most, numbers in a large type size.
- Screenshots: Map Explorer (island, play), Analysis (26-year Landsat), state layers, Site Viewer. Re-take them from your
  own computer after `git pull`, so the slides match what judges will see.
