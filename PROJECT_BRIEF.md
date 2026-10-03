# GLOBE Site Reconstruction — Congressional App Challenge 2026

## One-line pitch
Turn NASA GLOBE Observer's 6-directional land cover photo protocol (N/S/E/W/Up/Down) into an interactive 3D/panoramic site reconstruction tool, grounded in real Maui browning/wildfire-risk research — with a future IoT servo rig to automate capture.

## Deadline
**October 26, 2026** — Congressional App Challenge submission.

## Background / why this project
- Author is part of NASA SEES Team Terra, researching whether the 2022 Maui drought preconditioned vegetation fuels ahead of the August 2023 Upcountry Maui wildfires (Pukalani Park study area). Existing results: 42.7% of the Pukalani AOI browned (dNDVI < -0.10) 2019→2022, 879 patches / 298.6 ha, one dominant 130.7 ha patch, DSCI–NDVI r = -0.47. Manuscript in progress for JEOGA, co-authored with Dr. Russanne Low, Peder Nelson, and Cassie Soeffing; archived on Zenodo (zenodo.org/records/22195466).
- GLOBE Observer's Land Cover protocol has citizen scientists take six photos at a site — one facing each cardinal direction (N/S/E/W), one straight up (canopy/sky), one straight down (ground cover) — together documenting a 100-meter-square site. This is a NASA-funded, decades-running, well-documented citizen science dataset with a public API and archived datasets.
- Author has a direct connection to Peder Nelson, co-author of foundational GLOBE land cover papers (GO on a Trail dataset, Adopt-a-Pixel 3km dataset) — a resource for data access and domain guidance, not just documentation.
- Originally scoped this Congressional App Challenge project around a coral reef SfM/photogrammetry app (CoralPulse: FastAPI + Random Forest classifier, 98% weighted accuracy, 3D species viewer, NOAA PIFSC contacts for reef imagery). Pivoting the *capture-to-3D-environment* concept over to GLOBE data because it connects directly to author's own research and has an existing dataset to prototype against immediately.

## Core concept
1. **Ingest** a GLOBE Observer 6-photo site observation (either pulled from the public GLOBE API/archived datasets, or freshly captured).
2. **Reconstruct** an explorable environment from the 6 directional images — realistically scoped as a stitched panorama / cube-map "look-around" view of the site rather than a full photogrammetric mesh (6 images from one fixed point lack the parallax/overlap true SfM needs).
3. **Contextualize** the site with land cover / vegetation health data — tie into the browning research (dNDVI, NBR) so a user can see not just what a site looks like, but how its vegetation health has changed over time.
4. **(Future phase)** Automate the 6-shot capture sequence with a pan/tilt servo rig, turning a manual protocol into a repeatable, consistent automated station.

## Scope for Oct 26 (realistic MVP)
Prioritize a working, demoable software product using **existing/archived data** first; treat the servo rig as a proof-of-concept add-on if time allows, not a blocker.

### Phase 1 — Data pipeline
- [ ] Explore GLOBE Observer public API / sample Python scripts for pulling land cover photo observations
- [ ] Identify existing GLOBE observations near Pukalani / Upcountry Maui (ask Peder Nelson if archived multi-date coverage exists near the wildfire study site)
- [ ] Build an ingestion script: given a site ID or lat/lon, pull the 6 directional images + metadata (date, time, GPS, optional land cover classification tags)
- [ ] Basic image quality filtering (resolution, EXIF sanity checks, missing-direction handling) — citizen-submitted phone photos vary a lot in quality

### Phase 2 — Reconstruction / viewer
- [ ] Build a cube-map or panorama stitcher from the 6 directional images (up/down/N/S/E/W) into a single explorable 360°-style environment
- [ ] Web-based viewer (pan/zoom/look-around) for a reconstructed site
- [ ] If time allows: experiment with lightweight SfM (COLMAP/Meshroom) on any site with denser/multi-angle imagery to see if a partial 3D mesh is feasible — treat as a stretch goal, not the baseline deliverable

### Phase 3 — Research tie-in
- [ ] Overlay or link vegetation health indicators (dNDVI/NBR) for the site, using existing Pukalani analysis pipeline outputs as the reference implementation
- [ ] If multi-date GLOBE imagery exists for the same site, show a before/after comparison view (visual browning alongside the quantitative dNDVI signal)

### Phase 4 — Future work (present as roadmap, not required for submission)
- [ ] Servo tripod / IoT capture rig: 2-servo pan/tilt mount (compass heading servo + pitch servo) driven by ESP32/Arduino, automating the N/S/E/W/Up/Down sequence at a fixed site
- [ ] Even a minimal working prototype (2 servos + phone mount, manually triggered) would strengthen the submission as a "here's software working today, here's the hardware path to scale it" story

## Technical notes / open questions for Claude Code to help resolve
- Confirm current GLOBE Observer API access requirements (auth, rate limits, data format) — check https://observer.globe.gov/get-data and the linked sample Python scripts
- Decide stitching approach: simple cube-map (six images mapped to cube faces, viewable with a WebGL/Three.js viewer) is the most achievable "3D-feeling" result without true photogrammetry
- Decide viewer stack: likely a web app (React + Three.js, or a simpler panorama library) so it's easily demoable and shareable for judging
- Data storage: decide whether to cache pulled GLOBE observations locally/in a small DB, or query live each time
- Keep the reef-based CoralPulse backend (FastAPI + Random Forest, 3D viewer code, CDN work) available for reference — some infrastructure (3D viewer patterns, FastAPI backend structure) may be reusable even though the domain is changing

## Key people / resources
- **Peder Nelson** — NASA SEES mentor; co-author of foundational GLOBE land cover papers; built the GLOBE land-cover labeling/confusion-matrix HTML tools used elsewhere in author's Team Terra work. Primary contact for data access questions.
- **Dr. Russanne Low** — NASA SEES contact, co-author on the browning/wildfire manuscript.
- **GLOBE Observer data resources**: https://observer.globe.gov/get-data (Land Cover data, sample Python API scripts), https://observer.globe.gov/download-data
- **Existing research to draw from**: Pukalani drought/wildfire manuscript and figures (Zenodo: zenodo.org/records/22195466)

## Success criteria for the Oct 26 submission
- A working demo: pull at least one real GLOBE site's 6 directional photos and render it as an explorable panoramic/cube-map environment
- A clear, honest narrative connecting the tool to real Maui wildfire/browning research (not just a tech demo — a civic science story)
- A documented roadmap section covering the servo rig as future work, showing technical vision beyond the MVP

---

## Congressional App Challenge — official rules & judging rubric (2026)

### Key dates
- **Submissions open:** May 2026
- **Submission deadline:** Monday, **October 26, 2026, 12:00 PM EDT** (hard deadline; submissions cannot be modified after this)
- Judging period runs after the deadline; winners are typically announced in December (Computer Science Education Week, Dec 8–14, is a common announcement window), though the official embargo on any results is January 15, 2027.

### Eligibility
- Must be enrolled in middle or high school as of Oct 26, 2026.
- Compete as an individual or in a team of up to 4 (at least half the team must live/attend school in the same congressional district).
- Compete in only ONE district — either where you live or where you go to school, not both.
- App must be created after October 30, 2025. A "2.0" of an older app is allowed, but only the new work counts.
- One submission per person per year.

### App parameters
- **Topic:** completely open — any subject.
- **Platform:** any — web, desktop, mobile, browser extension, robot, AR/VR, wearable, smart device, embedded system. (Good news: this means the servo/IoT rig angle is explicitly a valid "platform," not a distraction from a "real" app.)
- **Programming language:** any (text-based strongly preferred over block-based for scoring — see rubric below).
- **Functionality:** must demonstrate real, working functionality — not just a concept or mockup.
- **AI usage:** allowed, but must be fully and clearly disclosed in the submission materials; AI cannot do the entire technical development — must show significant personal contribution and understanding.
- **Originality:** must be the student's/team's own work; open-source libraries and frameworks are fine but must be documented.

### Official judging rubric
Each judge scores the app 1–5 (1 = poor, 3 = average, 5 = superior) across three criteria:

| Criteria | What judges look for |
|---|---|
| **1. Concept** | How creative/original is the idea? Does it address a specific, real problem, and how creative is the solution? |
| **2. Design** | Did the student consider user experience and interface? How intuitive is the UI? Was there real thought put into the app's design? |
| **3. Skill** | Rewards real text-based coding over block-based/no-code tools: 1 = block code only (Scratch, MIT App Inventor, Blockly), 3 = block code + some integrated text-based code, 4 = a single text-based programming language, 5 = multiple text-based languages used together. |

**Implication for this project:** using Python (data pipeline/API ingestion), JavaScript/web stack (viewer), and potentially embedded C/C++ or MicroPython (servo/IoT rig) would hit multiple text-based languages — a strong Skill score — while the GLOBE/wildfire framing and the "software today + hardware roadmap" story is a strong Concept score.

### Demonstration video requirements (max 3 minutes)
This is the single most important submission artifact — it's what judges actually watch. Must include:
1. Name(s) of participant(s)
2. The app's name
3. A clear, one-sentence explanation of the app's purpose
4. Who the app's target audience is
5. The tools/coding languages used to build it
6. A demo showing the app's actual functionality working

Must be uploaded to YouTube or Vimeo and set to **public**. Keep it tight — judges are told it's "not a video-creation competition," but a clear, compelling video reads as competence, and going over 3 minutes can be penalized at judges' discretion.

### Written submission questions (answer these directly, don't paraphrase around them)
1. What is the title of your app?
2. Explain the app's purpose.
3. What inspired you to create this app?
4. What technical/coding difficulty did you face, and how did you address it?
5. What did you learn while participating in the CAC? What was your biggest takeaway?
6. What would you change about your app in a 2.0 version?

### Structuring the demo video around this project (suggested beats, ~3 min)
Based on the rubric and a strong past winning example (a client-side flood-mapping web app that clearly explained: the real-world problem → why existing solutions fall short → the specific technical approach taken → a live walkthrough of the working app → a concrete accuracy/impact result), a good structure here would be:
1. **Intro (0:00–0:10):** name, school, app name, one-sentence purpose.
2. **The problem (0:10–0:35):** Maui's 2022 drought → 2023 Upcountry wildfires; why land cover / vegetation change monitoring matters; why GLOBE Observer's citizen-science model has value but is limited (flat photos, no spatial/3D context).
3. **The gap in existing tools (0:35–0:50):** GLOBE gives 6 flat directional photos per site — useful data, but hard to actually "see" or explore a site, and no easy way to visualize change over time at a location.
4. **Your solution + tech stack (0:50–1:15):** ingest GLOBE's public API data, reconstruct an explorable cube-map/panorama of a site, tie it to your own dNDVI/browning research. Name the languages/tools (e.g., Python for the data pipeline, JavaScript/Three.js for the viewer) — this maps directly to the Skill rubric line.
5. **Live demo (1:15–2:30):** show the actual working app — pull a real GLOBE site, show the reconstructed environment, show the vegetation-health overlay/before-after if you have it.
6. **Results + roadmap (2:30–2:55):** what you found/built works; briefly mention the servo/IoT capture rig as your 2.0/future direction.
7. **Close (2:55–3:00):** target audience (educators, land managers, GLOBE community, Maui residents) and a closing line.

### Resources
- Official rules (2026): https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf
- Official judging rubric: https://www.congressionalappchallenge.us/wp-content/uploads/2018/10/CAC_Rubric_2018.pdf
- Congressional App Challenge homepage / registration: https://www.congressionalappchallenge.us/
- Submission portal & toolkit info: https://www.congressionalappchallenge.us/congress/congressional-toolkit/
- Tips from a general how-to-win writeup (Lumiere Education): ship something finished over something ambitious-but-broken, document your code well, use the prior-work rule (you can build on existing school/program work within the eligible window)
