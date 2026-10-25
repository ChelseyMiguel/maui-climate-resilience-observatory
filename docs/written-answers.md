# Browning Viewer: CAC form answers (draft)

The form limits each answer to 400 words. `[Brackets]` are details only you know. Rewrite in your own voice and keep the AI answer honest about what you did yourself. Every number traces to `docs/evidence-claims.md`.

## Please briefly describe what your app does?

Browning Viewer shows Upcountry Maui residents, teachers, NASA GLOBE observers and planners how drought, vegetation and wildfire connect, and lets them check the evidence themselves. It maps where land turned brown between the 2019 and 2022 dry seasons: 42.7% of my 1.5 km study area around Pukalani (30,037 of 70,280 pixels), using Sentinel-2 satellite images. A threshold slider recounts the browned pixels live. The Map Explorer layers that change with Maui County drought records, 2023 fire perimeters, rainfall, 26 years of Landsat, surface temperature, lidar height, state fire-risk zones and a view of all of Maui. A 3D view drapes the data on real terrain. NASA GLOBE Observer photos open as 360 degree sites, each showing how much of its footprint browned. An Analysis page has charts you can export as CSV or PNG. Every layer shows its source and its limits. It is for research and education, not fire-risk prediction or emergency alerts.

*(154 words)*

## What inspired you to create this app?

[One personal sentence: where you were or what you saw during the August 2023 fires.] In 2022 Maui County had 20 weeks of exceptional drought, the most since 2000. The next summer, on August 8, 2023, fires burned in Upcountry Maui and Lahaina. In my NASA SEES research I asked whether the drought browned the land before the fires. My answer lived in a poster and in code, so the people living there could not see it or check it. Satellite maps are built for experts, drought maps cover a whole county, and GLOBE photos are flat pictures. I wanted one place where anyone in Upcountry could see the change at their own spot and see exactly where each number comes from. [Add why this place matters to you.]

*(129 words)*

## What technical difficulties did you face programming your app?

The hardest problems were about getting correct numbers from messy public data.

1. **3D from photos failed.** Structure-from-motion on the one GLOBE site with 8 visits matched only 12 of 496 photo pairs (repetitive grass, changing light), so no 3D model was possible. I turned it into a 360 degree cube-map viewer.
2. **My rebuild disagreed with my study.** Rebuilding the 2022 minus 2019 change from public Sentinel-2 data first gave r = 0.10. The archive had already removed a reflectance offset I was subtracting again, and reprocessed scenes were counted twice. Fixing both gave r = 0.85, with 77% of pixels in the same class.
3. **One exact number everywhere.** The browned count (30,037 of 70,280 pixels, 42.7%) had to be identical in Python, in the browser's slider and in the charts. The browser compares 32-bit floats exactly as stored in the GeoTIFF, and a test checks it against the real raster.
4. **Public servers push back.** A satellite service rate-limited me (HTTP 429), so I added back-off and fewer parallel reads. One unreadable Landsat file is skipped and listed, never filled in.
5. **A false signal.** Burn severity showed "low severity" on unburned grass because grass dries in summer. I subtracted the typical change on unburned land and clipped the map to the fire perimeters.
6. **No fabricated data.** Services that needed a login (a rainfall API) were left out instead of faked, and the 3D view shows terrain height only, never greenness as height.

*(247 words)*

## What improvements would you make if you were to create a 2.0 version of your app?

The biggest limit is that the 3D views come from terrain and lidar, not from the GLOBE sites themselves. In 2.0 I would use a drone survey, after FAA and airspace checks, to build a real 3D model and measure vegetation height at a GLOBE site. I would run my Earth Engine script for Makawao and Kula, which have no vegetation series yet. I would ask GLOBE observers to repeat photos at the same sites so the app can show change over time. I would also add live monthly updates so the maps keep up with new satellite images, and test the app with Upcountry teachers and residents.

*(108 words)*

## Did you use AI in the creation, development, or functionality of your app?

Yes. I used Claude (Anthropic) through Claude Code as a coding assistant from September to October 2026. The app itself uses no AI when it runs.

**What the AI did.** Claude wrote most of the application code from my directions:
- The Python and FastAPI back end, and the NASA GLOBE API client.
- The Svelte, TypeScript, MapLibre and three.js front end: Map Explorer, 3D view, Analysis charts and the logo header.
- The 360 degree viewer.
- Data scripts for Sentinel-2, Landsat, lidar, burn severity, Drought Monitor and Hawaii state GIS data.
- Earth Engine scripts, the Render deploy file, and 258 Python and 40 JavaScript tests.
- Bug fixes, and drafts of documentation and these answers.

**What I did.** I did the NASA SEES research and wrote the original Earth Engine analysis (NDVI and NBR, 2019 versus 2022), which every result comes from. I ran the Earth Engine exports and uploaded the rainfall, land-cover and LCMS data. I chose the name, logo and design direction, decided which features and data to add, required that every number trace to a source with nothing fabricated, ran the app, checked it against my study, and asked for fixes. [Add anything else you did.]

*(202 words)*

## What did you learn or take away from participating in the Congressional App Challenge?

Building a real tool taught me that how you show data matters as much as the data. I learned that scale and method change the answer: county drought, a 1.5 km study area, a 100 m GLOBE site and a 10 m pixel answer different questions, so each layer says what it is. Satellite maps disagree about the ground, and photos from ordinary people settle what pixels cannot. I learned to say what a result does not show: 2022 was the least green dry season of Maui's nine years I measured and the lowest of 26 at Pukalani, but the study area did not burn, so browning is not proof of fire. I also learned to rebuild my own result independently and report when the match was imperfect. [Add a personal takeaway, such as what the project taught you about yourself or your community.]

*(144 words)*
