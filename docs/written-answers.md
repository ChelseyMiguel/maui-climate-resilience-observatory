# Browning Viewer: written answers (draft)

Draft answers to the six CAC questions, built only from facts in this repo (every number traces to `docs/evidence-claims.md`). `[Brackets]` are personal details only you know. Rewrite in your own words and keep the AI disclosure consistent with `docs/ai-disclosure-and-code-tour.md`: CAC requires your own work and clear AI disclosure.

## 1. What is the title of your app?

Browning Viewer

## 2. Explain the app's purpose.

Browning Viewer lets Upcountry Maui residents, teachers, NASA GLOBE observers and planners see, and check for themselves, how drought, vegetation and wildfire connect. It shows where land turned brown between the 2019 and 2022 dry seasons (42.7% of my 1.5 km study area), alongside drought records, 2023 fire perimeters, rainfall, 26 years of Landsat and NASA GLOBE photos you can look around in 360 degrees. Every layer shows its source and its limits. It is a research and education tool, not a fire-risk or emergency alert.

## 3. What inspired you to create this app?

[One personal sentence: where you were or what you saw in August 2023.] In my NASA SEES research I asked whether the 2022 drought browned the land before the 2023 fires. My answer lived in a poster and in code, so no community could see it or check it. Existing tools are made for experts, cover a whole county, or give flat photos. I wanted one place where anyone in Upcountry could see the change at their own spot and see where the numbers come from. [Add why this place matters to you.]

## 4. What technical or coding difficulty did you face, and how did you address it?

I wanted a 3D model of a GLOBE site from its six photos, so I tried structure-from-motion on the one site with 8 visits. Only 12 of 496 photo pairs matched because the scene was repetitive grass under changing light, so no 3D model could be built. I turned the failure into the design: a cube-map 360 degree viewer that places the photos around you, and a documented plan for a better capture method. [Say what you tried or learned yourself.]

A second problem was trust. When I rebuilt my result from public Sentinel-2 data, it first matched poorly (r = 0.10). The archive had already removed an offset I was subtracting again, and some scenes were counted twice. After fixing both, the rebuild matched my study at r = 0.85. [Say which parts you wrote or debugged and which Claude did.]

## 5. What did you learn? What was your biggest takeaway?

Scale and method matter. County drought, a 1.5 km study area, a 100 m GLOBE site and a 10 m pixel answer different questions, so I label each layer with its scale. Satellite maps also disagree about the ground: WorldCover calls 13 of 15 GLOBE sites grassland, while another map often calls the same parks built-up. Ground photos settle what pixels cannot. I also learned to say what a result does not show: 2022 browned the land across Maui and was the lowest of 26 years at Pukalani, but the study area did not burn, so browning is not proof of fire. [The moment you realised this.]

## 6. What would you change in a 2.0 version?

The biggest limit is that my 3D views come from terrain and lidar, not from the GLOBE sites themselves. In 2.0 I would use a drone survey (after FAA and airspace checks) to build a real 3D model and vegetation height at a GLOBE site. I would also run my Earth Engine script for Makawao and Kula, which have no vegetation series yet, and ask GLOBE observers to repeat photos at the same sites so the app can show change over time.

---

## Check against the CAC rubric

| Criterion | What judges look for | Where Browning Viewer shows it |
|---|---|---|
| Concept | Original idea, a real specific problem | Drought to fire in Upcountry Maui; checkable layers; GLOBE photos joined to satellite results |
| Design | Thought about users and interface | Plain captions, one threshold slider, 2D, 3D and 360 views, mobile layout, source and limits on every layer |
| Skill | Text-based code; 5 = several languages together | Python (FastAPI, data pipeline), JavaScript and TypeScript (Svelte, MapLibre, three.js), Google Earth Engine JavaScript, 258 Python and 40 JavaScript tests |

## Video requirements (3 min max)

Your slide script already covers the app's name, purpose and demo. Make sure the video also says:
- your name and school
- one sentence of purpose
- who it is for: residents, teachers, GLOBE observers, planners
- the tools: Python and FastAPI, JavaScript and Svelte, Google Earth Engine

Also upload it to YouTube or Vimeo as **public**, and submit before **Oct 26, 12:00 PM EDT** (the deadline is hard).

## Before submitting

- [ ] Fill every `[bracket]` in your own words.
- [ ] Update the AI disclosure so it matches what you wrote in answer 4.
- [ ] Every number matches `docs/evidence-claims.md` and the video.
- [ ] No "predicts", "caused" or "fire risk" claims.
