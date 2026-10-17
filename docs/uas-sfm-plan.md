# Drone (UAS) structure-from-motion — the route that can work

`docs/sfm-experiment.md` showed why the GLOBE photos cannot be reconstructed:
the views that overlap enough to match are too close together to triangulate,
and the ones far enough apart no longer match (repetitive grass, changing
light). A drone survey is the opposite by design: hundreds of photos of the
same ground, from known positions, with deliberate overlap, in one session
under one light. That is exactly what SfM needs.

## What it would add to the Observatory

| Output (OpenDroneMap) | Use in the app |
|---|---|
| Orthophoto (GeoTIFF) | A centimetre-scale "what the site looks like from above" layer under the GLOBE pin |
| DSM and DTM (GeoTIFF) | Vegetation height = DSM - DTM: dry grass vs. shrubs vs. trees, i.e. fuel structure, at the site |
| Point cloud (LAZ) / textured mesh (OBJ, GLB) | A real 3D model of the site in the 3D view (three.js already loads GLB) |

These are measurements of one place on one day. They make the GLOBE site
tangible; they are not a fire-risk map.

## Software (all open source)

- **OpenDroneMap / WebODM** — the standard open-source SfM pipeline for drone
  photos; WebODM is its browser interface. Produces every output above.
- COLMAP (already used in `scripts/sfm/run_sfm.py`) works too, but ODM adds the
  georeferencing and the orthophoto/DSM/DTM outputs the app can use directly.

## Capture, in outline

- A lawn-mower grid over the 100 m GLOBE site plus a margin, at constant height.
- High overlap between neighbouring photos, front and side. Typical guidance for
  vegetation is higher than for buildings; check the OpenDroneMap documentation
  for current numbers before flying.
- Add an oblique (tilted camera) pass for a better 3D model; nadir only is
  enough for the orthophoto and DSM.
- One session, steady light (overcast is good), little wind (moving grass
  defeats matching, the same failure as the GLOBE photos).
- Optional: a few ground control points measured with a good GPS for absolute
  accuracy; without them the model is right in shape but can be offset by metres.

## Rules (must be checked before any flight — not legal advice)

- US drone flights fall under FAA rules: recreational flying (needs the free
  TRUST certificate) or Part 107 for anything else (minimum age 16). A school or
  competition project may not count as recreational; confirm which applies.
- **Check the airspace** with the FAA B4UFLY app or a LAANC provider: Kahului
  Airport's controlled airspace may reach toward Upcountry, and controlled
  airspace needs authorization.
- Landowner permission for take-off and the area overflown; no flights over
  people or near the 2023 burn-recovery work.

## Where it fits the timeline

Not required for Oct 26. The submission already shows *why* SfM fails on the
existing data; a flight is the strongest form of the "2.0 / Phase 4" story
(answer 6 of the written questions). If a legal, permitted flight happens before
the deadline, the outputs above slot into the 3D view; otherwise present this as
the next step, next to the servo capture rig.

## Open drone/aerial data checked so far

- NOAA post-fire aerial imagery of Maui (Aug 2023) is straight-down orthophotos —
  usable as imagery, not for SfM.
- OpenAerialMap was not confirmed to have Upcountry Maui drone imagery.
- For measured 3D without flying: the 2022-2023 NOAA/USGS Maui lidar
  (see docs/next-steps.md) — coverage of the study area not yet confirmed.
