# Capture protocol: photos that structure-from-motion can actually use

**Why this exists.** Structure-from-motion failed on the public GLOBE photos
(`docs/sfm-experiment.md`): only 12 of 496 photo pairs matched. The photos close
enough together to match had no parallax; the ones far enough apart didn't match,
because grass is repetitive texture and the light changed between visits. This
protocol fixes all three causes in one session.

It is also the specification for the Phase 4 servo rig: everything below is what
the rig would do automatically.

## Before you go

- **Pick the spot:** `04QGJ763065`, Pukalani — `20.83841, -156.34459` (the re-shoot
  target in `docs/reshoot-plan.md`). Doing the GLOBE re-shoot and this capture in
  one visit gets you both the second date and an SfM set.
- **Permission and safety:** public ground or the owner's permission; never stand in
  a road. Go with someone.
- **Light:** overcast is best (soft, even, no moving shadows). Otherwise early or
  late in the day — avoid midday hard shadows. Finish the whole set within
  **30 minutes** so the light can't change much.
- **Phone settings:** main (1x) lens only — no zoom, no ultra-wide. Landscape
  orientation for every photo. **Lock focus and exposure** (press and hold on the
  screen until "AE/AF LOCK" appears). HDR and portrait/night modes off. Save as
  **JPEG**, not HEIC (on iPhone: Settings → Camera → Formats → Most Compatible).

## What to photograph

SfM needs **static, textured** things it can recognise from different positions.

- Frame each photo so it includes **fixed features**: fence posts, rocks, kerbs,
  signs, tree trunks, building corners. Grass alone will fail again.
- Keep the main subject **10–40 m away**. Much closer and neighbouring photos look
  too different; much further and your steps make too little parallax.
- Put an object of **known length** in view — a 1 m stick, or a tape measure laid
  flat — so the model can be scaled to metres.
- Avoid moving things in frame: cars, people, animals, branches in wind.

## How to move

1. Stand at the GLOBE site point. Take the normal six GLOBE photos first.
2. Choose the scene you want in 3D (e.g. the fence line and grass to the east).
3. Walk a **slow arc around it**, or a straight line past it, taking a photo
   **every 1–2 steps** (~1 m). Neighbouring photos should **overlap by about 70%**
   — most of the frame repeated, shifted a little.
4. Keep the subject roughly **centred** the whole way.
5. Aim for **40–60 photos**. If there's time, do a second pass at a different
   height (crouching), same spacing.
6. Never turn on the spot to "get the next view" — rotating without moving adds no
   parallax. **Move, then shoot.**

## Afterwards

Copy the photos (as JPEG) into a folder, then run the experiment script on them:

```bash
python -m venv .sfmenv && .sfmenv/bin/pip install pycolmap httpx
```

```bash
.sfmenv/bin/python scripts/sfm/run_sfm.py --site 04QGJ763065 --images ~/Pictures/pukalani-sfm
```

The report (`data/sfm/04QGJ763065/report.json`) says how many photos registered,
how many 3D points were recovered, and the mean reprojection error. A sparse point
cloud is written to `points.ply` (opens in MeshLab or CloudCompare).

## Reading the result honestly

- A **sparse** cloud of a few thousand points is a success for a phone and 50
  photos. It is not a photoreal model.
- If few photos register, the usual causes are: too little overlap, the subject too
  far away, or too much grass and sky in frame.
- Only describe the tool as doing SfM for a site where this capture actually
  produced a reconstruction — and say it came from a dedicated capture, not from
  standard GLOBE photos.
