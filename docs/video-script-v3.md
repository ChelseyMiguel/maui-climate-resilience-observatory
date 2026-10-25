# Demo video v3 — matches the slides, 3:00 max

Follows the structure of strong past CAC videos and your five slides:
Motivation → My NASA SEES work → Research & application landscape →
How it expanded → Demo. Numbers come from the manuscript (Miguel et al. 2026,
JEOGA, revised) and docs/evidence-claims.md.

**✂ = cut this sentence first if you run long.** Core script ≈ 2:25; with every
✂ sentence ≈ 2:50. Time one full read before recording.

---

### Slide 1 — Motivation: the problem of browning (0:00–0:30)
> Hello, my name is Chelsey Miguel from King Kekaulike High School on Maui. In
> this project I built the Browning Viewer, a web app
> showing Upcountry communities how drought, vegetation and wildfire connect. It grew
> out of my NASA SEES research with Peder Nelson, Dr. Russanne Low and Cassie Soeffing.
>
> On August 8, 2023, wildfires burned in Upcountry Maui and Lahaina. The year
> before, Maui County spent 20 weeks in exceptional drought, the most of 2018 to
> 2024. ✂ *Much of Upcountry's old plantation land is now unmanaged grass.* Drought
> is an often overlooked driver of these fires.

### Slide 2 — My NASA SEES work (0:30–1:05)
> My research asked: did the 2022 drought brown the vegetation before the fires?
> With Sentinel-2 imagery in Google Earth Engine, I compared the 2019 and 2022 dry
> seasons around Pukalani Park. Of 70,280 pixels, 42.7% browned; the largest patch
> covered 130.7 hectares. Drought and greenness anomalies were correlated, r = −0.47.
> ✂ *A USDA Forest Service product partly agreed: 48% of its vegetation-loss area had
> also browned.* That doesn't show the browned areas burned; it shows the land was
> drying before the fires.

### Slide 3 — Research & application landscape (1:05–1:30)
> The data already exists, but it's scattered. The Drought Monitor is county-wide.
> Satellite land-cover maps are built for experts, and at the scale of a park they
> disagree. ✂ *NASA GLOBE Observer's citizen photos are six flat pictures.* My results
> lived in a poster and in code, so no one place let a community see it, or check it.

### Slide 4 — How it expanded (1:30–2:00)
> So I turned it into the Observatory, for residents, teachers, GLOBE observers and
> planners. It combines browning, drought, rainfall, fire perimeters and community
> facilities, with each chart's source and limits shown. I built it with Python and
> FastAPI, JavaScript and Svelte, and Google Earth Engine. ✂ *It has over 200
> automated tests.* It's for learning, not fire alerts.

### Slide 5 — Demo (2:00–2:52)
> *(Overview, drought calendar; hover a 2022 week)* Here are seven years of
> drought, week by week. The white dots are exceptional drought, and 2022 stands out.
>
> *(Region Insights → Drought and greenness, then Rain and greenness)* Drought and
> greenness move together month by month. ✂ *Rain over the last two to three months
> matters most.*
>
> ✂ *(3D View)* *Here's the browning and the fire perimeters on 3D terrain.*
>
> *(Site Viewer: drag the 360° view, then the satellite panel)* This is a real GLOBE
> site rebuilt in 360 degrees. Three satellite maps disagree about what's here: two
> say grassland, one says built. Across 15 sites, two maps agreed on 13, but Google's
> Dynamic World matched as few as 4. Satellites can't settle it; citizen photos can.

### Close (2:52–3:00)
> Next, I'm planning a drone survey to turn these sites into real 3D models. The
> Browning Viewer: making environmental change in
> Maui visible, and checkable. Mahalo.

---

### On screen during the demo
The Drought and greenness card shows **r = −0.69**: drought against *raw*
greenness. The −0.47 above is drought against greenness *anomalies* (your
published method). Both are correct answers to different questions, so the demo
line deliberately quotes no number. If a judge asks, that is the answer.

### Required elements
Name 0:00 · App name 0:00 · Purpose 0:00 · Audience 1:30 · Tools/languages 1:30 · Working demo 2:00
