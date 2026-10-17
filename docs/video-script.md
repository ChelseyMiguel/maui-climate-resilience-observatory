# Demo video: script and shot list

CAC rules: **3 minutes max**, uploaded to YouTube or Vimeo (unlisted is fine),
showing the app working and explaining what it does. Aim for **2:45**.
Show **you**: either your face for the intro, or at least your voice the whole way.
Every number below is in `docs/evidence-claims.md`. Don't add numbers that aren't there.

## Before recording
- Start the app with `./run.sh`, then open http://localhost:8000 in Chrome, full screen (⌃⌘F).
- Set browser zoom to 110–125% so text reads on a phone.
- Close other tabs and turn on Do Not Disturb.
- Record: **⌘⇧5 → Record Entire Screen**, with Options → Microphone set to the built-in mic.
  Or use QuickTime → New Screen Recording.
- Record one scene at a time. It's easier to redo a single scene than the whole video.
- Edit in iMovie or CapCut: trim pauses, add the title card, export at 1080p.

## Script (≈ 400 words at a normal pace)

| Time | Screen | Say (in your own words, this is a guide) |
|---|---|---|
| 0:00–0:20 | You on camera, or a photo of Upcountry | "In August 2023, fires burned through Upcountry Maui, where I live. A year before, in 2022, Maui had 20 weeks of exceptional drought. My question was whether that drought left vegetation browned before the fires, and how communities could see that." |
| 0:20–0:40 | **Overview** page (`/`), scroll slowly | "So I built the Rural Hawaiʻi Climate Resilience Observatory. It puts vegetation change, drought, the 2023 fire perimeters and community facilities in one place, using real public data from NASA, USGS, the Drought Monitor and the State of Hawaiʻi." |
| 0:40–1:15 | **Map Explorer** (`/explore`): turn on vegetation change, then drought, then fires; click one fire and one GLOBE site | "Here's the satellite vegetation change from 2019 to 2022. In my Pukalani study area, 42.7% of the land browned. I can add the drought map for each year, and the 2023 fire perimeters. Clicking anything shows where the data came from, and how uncertain it is." |
| 1:15–1:40 | **Region Insights** (`/insights`): Pukalani chart, the 2019 vs 2022 comparison, click CSV | "For each community you can see the trend. Pukalani's dry-season greenness dropped 19% from 2019 to 2022. And anyone can download the data, with its sources attached." |
| 1:40–2:10 | **3D View** (`/map`): press ▶ Play the guided tour | "This is a 3D tour of the terrain, with the same layers draped over it, so people can see where the fires were relative to where they live." |
| 2:10–2:30 | **Site Viewer** (`/viewer`): drag around 360°, show the mini-map | "And this is the part I'm proudest of. NASA's GLOBE Observer app has citizen scientists take six photos at a site. My app rebuilds them into a 360° view, so you can stand where they stood." |
| 2:30–2:45 | **Methods / Sources** pages, quick scroll; end on a title card | "Everything is cited, and the app says clearly that it's for research and education, not emergency alerts. I built it with Python, FastAPI, Svelte and Google Earth Engine. Thank you." |

## Things to say honestly
- The tool is for **research and education**, not for evacuation or alerts.
- Your study area **did not burn**. The fires were nearby, in Makawao and Kula. Don't imply the browned patches caught fire.
- Say "the worst drought from 2018 to 2024", not "on record".
- If asked about AI help, follow your disclosure in `docs/ai-disclosure-and-code-tour.md`.

## Upload checklist
- [ ] Under 3:00
- [ ] YouTube → Visibility **Public** (CAC requires a public YouTube or Vimeo video, 1–3 min; PROJECT_BRIEF.md and district pages such as larsen.house.gov and case.house.gov; confirm with your representative's office), made for kids: **No**
- [ ] Title: "Rural Hawaiʻi Climate Resilience Observatory — Congressional App Challenge 2026"
- [ ] Paste the YouTube link and the GitHub link into the CAC submission form before **Oct 26, 12:00 PM EDT**
