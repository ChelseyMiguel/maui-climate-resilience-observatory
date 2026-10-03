# Structure-from-motion on GLOBE data — what we tried and why it failed

**Result: no 3D reconstruction is recoverable from the public GLOBE land cover
photos at the one site where it should be most possible.** This is a real finding,
and it is the strongest argument for the Phase 4 capture rig.

## Why SfM can't work on a single observation

One GLOBE land cover observation is six photos from **one standing point**. With
no change of viewpoint there is no parallax, so no depth can be recovered. That is
why the main viewer is a cube map, not a 3D model.

## The one site where it might

`04QGJ763065` (Pukalani, SEES2026) has **8 visits over two days**, recorded up to
~85 m apart. That gives 32 horizontal photos (N/E/S/W x 8) of the same ground from
different positions — a genuine multi-view set.

Run with `scripts/sfm/run_sfm.py` (COLMAP via `pycolmap` 4.2.1; optional, not in
`requirements.txt`).

## What happened

| Attempt | Result |
|---|---|
| COLMAP defaults | No model |
| Relaxed match thresholds (`--relaxed`: 30-inlier start, 15 for adding images) | No model |
| Also lowering the minimum triangulation angle to 2 degrees | No model |

Diagnosis from the match database:

- **Features are not the problem**: 3,541-9,822 keypoints per photo.
- **Matching is**: only **12 of 496** image pairs pass geometric verification,
  with at most 104 inliers (COLMAP's default starting pair needs 100).
- The pairs that *do* match are the same direction shot on visits minutes apart
  from nearly the same spot (e.g. two east-facing shots, 68 inliers). Those have
  almost no parallax.
- The pairs with a real baseline do not match: grass is repetitive texture, and
  the light changed between visits.

The geometry itself was not the limit: an 85 m baseline gives ~24 degrees of
triangulation angle on a feature 200 m away, which would be plenty. It is the
classic SfM trade-off — the views that overlap enough to match are too close
together to triangulate, and the ones far enough apart no longer match.

## What it means for the rig (Phase 4)

A pan/tilt rig that captures **overlapping photos from several known offsets, in
one session, under the same light**, would supply exactly what this data lacks:
controlled baseline, matching lighting, and deliberate overlap. That turns
"SfM is not feasible" into a concrete hardware requirement rather than a dead end.

**Do not** describe the current tool as having SfM or a 3D reconstruction of a
site. It has a cube-map reprojection, plus a 3D *terrain* map built from
elevation data — a different thing.
