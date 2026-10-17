# CAC written answers — DRAFT SCAFFOLD, write the final text yourself

The six questions are copied from PROJECT_BRIEF.md. For each: what a judge is
looking for, facts you can use (every number traces to docs/evidence-claims.md),
and a skeleton. **The words must be yours.** CAC requires the work to be your own
and AI use to be disclosed; these notes are a checklist, not an answer to paste.
Answer the question asked, directly, in the first sentence.

---

## 1. What is the title of your app?

Rural Hawaiʻi Climate Resilience Observatory. (Keep it identical in the video,
the form and the GitHub README.)

## 2. Explain the app's purpose.

**Judges want:** one clear sentence, then who it is for and what it lets them do.

**Facts:** Upcountry Maui; 2022 drought (20 weeks of D4 exceptional drought in
Maui County, the most of 2018–2024); August 2023 fires nearby (Olinda, Kula);
one place for satellite vegetation change, drought, fire perimeters, rainfall,
community facilities and NASA GLOBE citizen-science photos; every chart says its
source and its limits; research and education, not emergency alerts.

**Skeleton:**
- Sentence 1: what it does, for whom. [YOUR WORDS]
- Sentence 2–3: what someone can actually do in it (see the change around
  Pukalani, compare years, stand inside a GLOBE site in 360°, download the data
  with its sources). [YOUR WORDS]
- Sentence 4: what it is not (not a fire-risk or alert tool). [YOUR WORDS]

## 3. What inspired you to create this app?

**Judges want:** a real, specific reason (Concept score).

**Facts you can draw on:** your NASA SEES Team Terra research on whether the 2022
drought preconditioned vegetation before the 2023 Upcountry fires; living in the
area (only if true — the video script says "where I live"); GLOBE Observer
photos being flat and hard to explore; the pivot from the coral-reef idea
(CoralPulse) because this connected to your own research.

**Skeleton:** the moment or question that started it → why existing tools did
not answer it → what you decided to build. [YOUR WORDS, a personal detail beats
a general statement]

## 4. What technical/coding difficulty did you face, and how did you address it?

**Judges want:** one real problem, what you tried, what worked, what you learned.
Pick ONE as the main story; mention a second in a sentence at most.

**Option A — 3D from six photos failed.** You tried structure-from-motion
(COLMAP) on the one GLOBE site with 8 visits: only 12 of 496 photo pairs matched
(repetitive grass, changing light), so no 3D model. You turned it into a
cube-map 360° viewer instead, and the failure became the requirement for the
capture rig / drone survey. (docs/sfm-experiment.md)

**Option B — one correlation, many answers.** The drought–greenness correlation
came out anywhere from −0.42 to −0.99 depending on method on the same data; the
−0.99 is from only 5 points. You chose one method (monthly, same month, n = 61,
r = −0.69), tested it, and report the strict version too. (DECISION section in
evidence-claims.md — settle −0.47 first.)

**Option C — decoding a dataset with no labels.** The newer USDA LCMS dataset
gave class numbers but no names. Instead of guessing, you tested the assumption
that code n = the n-th probability band: it held for land cover in 105 of 105
site-years (so you used it) but only 83% for land use (so you didn't).

**Honesty:** if Claude helped design the fix (it did for B's analysis code and
C's test), say what you did and what the AI did, consistent with
docs/ai-disclosure-and-code-tour.md.

**Skeleton:** the problem in one line → what you expected → what actually
happened (with the number) → what you did → the result. [YOUR WORDS]

## 5. What did you learn? What was your biggest takeaway?

**Facts that make a strong takeaway:**
- Scale matters: county drought vs. a 1.5 km study area vs. a 100 m GLOBE site
  vs. a 10–30 m satellite pixel are different questions.
- Satellites disagree about the ground here: LCMS and WorldCover call 13 of 15
  GLOBE sites grassland; Dynamic World often calls the same parks built-up. Ground
  photos are not a nice extra; they settle what the pixels can't.
- Rain over the last 2–3 months tracks greenness better than one month; with
  seasons removed, a whole year of rain matters most.
- A number without its method can mislead (the correlation table).

**Skeleton:** the takeaway in one sentence → the moment you realised it → how it
changed what you built or how you'll do research. [YOUR WORDS]

## 6. What would you change in a 2.0 version?

**Facts:** drone survey + OpenDroneMap for a real 3D model and vegetation height
at a GLOBE site (docs/uas-sfm-plan.md; FAA/airspace rules first); the servo
pan/tilt capture rig (Phase 4); NOAA/USGS 2022–23 lidar if it covers the area;
per-region vegetation series for Makawao and Kula (scripts/gee/region_timeseries.js);
repeat GLOBE observations at the same sites to show change over time
(docs/reshoot-plan.md).

**Skeleton:** the biggest limitation now → the specific 2.0 fix → why it
matters to the people using it. Pick two items, not five. [YOUR WORDS]

---

### Before submitting
- [ ] Every number matches docs/evidence-claims.md (and the video).
- [ ] The same correlation everywhere (see DECISION section).
- [ ] No "fire risk", "predicts", "caused".
- [ ] AI use described the same way here, in the video if asked, and in the disclosure.
