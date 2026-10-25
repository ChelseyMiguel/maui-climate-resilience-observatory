# Demo video v2 — CAC format (max 3:00)

Modelled on the structure of strong past CAC videos: who you are and who you
worked with → the problem, with numbers → why existing tools fall short → your
solution and who it is for → the code, briefly → a live demo → one headline
result → close. Every number traces to docs/evidence-claims.md. Say it in your
own words; [BRACKETS] are yours to fill.

**Pace:** ~430 words ≈ 2:50 at a normal speaking pace, leaving ~10 s of demo
pauses. Time yourself once; if over 3:00, cut the 3D-view line first.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:14 | You on camera, or title slide | "Hello, my name is [NAME] from [SCHOOL]. In this project I built the **Browning Viewer**, a web app that helps Upcountry Maui residents, students and planners see how drought, vegetation and wildfire fit together. It grew out of my NASA SEES research with Team Terra, where I worked with Dr. Russanne Low, Peder Nelson and Cassie Soeffing." |
| 0:14–0:36 | Research poster / slide "From research to a tool" | "On August 8, 2023, fires burned in Upcountry Maui and Lahaina. The year before, Maui County had **20 weeks of exceptional drought**, the most of 2018 to 2024. My SEES research asked whether that drought browned the vegetation first. Using Google Earth Engine and Sentinel-2, I found **42.7%** of my Pukalani study area browned between the 2019 and 2022 dry seasons." |
| 0:36–0:56 | Same slide, right side | "But that result lived in a poster and in code. Drought data is county-wide. Satellite land-cover maps disagree at the scale of a park. And NASA GLOBE Observer's citizen-science photos are six flat pictures that are hard to explore. There was no single place for a community to see this, or to check it." |
| 0:56–1:18 | Overview page | "So I built the Observatory, for residents, teachers, GLOBE observers and local planners. It puts satellite vegetation change, weekly drought, rainfall, the 2023 fire perimeters and community facilities side by side, and every chart states its source and its limits. It's for research and education, not a fire-risk or alert tool." |
| 1:18–1:42 | Code editor: `lib/`, then `web/src/components/`, then `notebooks/` | "I built it in three languages. **Python** with FastAPI is the backend: the `lib` folder holds the analysis, browning, rainfall and the satellite cross-check, with over 200 automated tests. **JavaScript** with Svelte builds the interface: each chart in `web/src/components` is its own component. And **Google Earth Engine** scripts and a Colab notebook export the satellite data." |
| 1:42–2:00 | Overview → drought calendar, hover a 2022 week | "Here are seven years of drought, week by week. The white dots are exceptional drought, and 2022 stands out." |
| 2:00–2:16 | Region Insights → Drought and greenness, then Rain and greenness | "Month by month, drought and greenness move together: r = −0.69 over 61 months. [Only if that is your chosen number — see the DECISION section.] And rain over the previous two to three months matches greenness best." |
| 2:16–2:36 | Site Viewer: drag the 360° view, then the "What satellites call this spot" panel | "This is a real GLOBE site rebuilt in 360°. Three satellite maps disagree about what is here: two say grassland, Google's Dynamic World says built. The photos settle it." |
| 2:36–2:52 | Slide with the result | "Across 15 GLOBE sites, two satellite maps agreed on 13, but Dynamic World matched them at as few as 4. At this scale satellites can't settle what's on the ground; citizen-science photos can. Next, I'm planning a drone survey and a capture rig to turn these sites into real 3D models." |
| 2:52–3:00 | Title card + GitHub link | "The Browning Viewer: making environmental change in Maui visible, and checkable. Mahalo." |

## Rubric check (CAC video requirements)

- [x] Name(s) — 0:00 · [x] App name — 0:00 · [x] One-sentence purpose — 0:00
- [x] Target audience — 0:56 · [x] Tools and languages — 1:18 · [x] Working demo — 1:42–2:36

## Say it honestly

- The study area did **not** burn; the nearest fire (Olinda) was ~1.5 km outside it.
- "Browning before the fires", never "browning caused the fires".
- Quote the same correlation as the written answers (DECISION section).
- If you mention AI help, say it the way docs/ai-disclosure-and-code-tour.md does.

## Upload

- [ ] Under 3:00 · YouTube or Vimeo, **Public** · made for kids: No
- [ ] Link in the CAC form before **Oct 26, 12:00 PM EDT**
