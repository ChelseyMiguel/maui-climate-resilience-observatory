# Next steps to Oct 26 — in order

Each step either needs you (Earth Engine, field work, a decision) or is code that
waits on the step before it. Do them top to bottom.

| # | Step | Who | Unlocks |
|---|---|---|---|
| 1 | Run `scripts/gee/rainfall_monthly.js` in the Earth Engine Code Editor; save the export as `data/research/pukalani_rainfall_monthly.csv`; check `python -m lib.rainfall` prints numbers | you, ~20 min | A Rainfall card next to "Drought and greenness": do the four products agree here, and how many months after rain does greenness respond? |
| 2 | Run `scripts/gee/lcms_site_sample.js` (sites from `scripts/export_sites_for_gee.py`); save `data/research/lcms_site_classes.csv`; run `scripts/crosscheck_lcms.py` | you, ~20 min | First real "do citizen labels agree with satellite land cover" figure |
| 3 | Find how the manuscript's r = -0.47 was computed | you | Every correlation on the site and in the video says one consistent thing |
| 4 | 3D from open data: check whether the 2022-2023 NOAA/USGS Maui lidar covers the Pukalani study area, and its flight dates vs. 8 Aug 2023 | you or me (needs network) | A measured vegetation-height layer (surface minus ground) on the 3D map — the real-data version of what SfM could not give (docs/sfm-experiment.md) |
| 5 | Record the video against the rubric (docs/video-script.md) | you | The artifact judges actually watch |

Not worth starting before Oct 26: photo-based ML, a full lidar point-cloud viewer,
new GLOBE endpoints that are untested live (docs/globe-api-verification.md).

## Why lidar instead of SfM

SfM needs overlapping photos of the same ground from known, different
positions under the same light; the GLOBE photos fail that (docs/sfm-experiment.md),
and the open post-fire aerial imagery found so far is straight-down orthophotos,
which SfM cannot use either. Airborne lidar measures the 3D surface directly.
Sources to check: NOAA InPort "2022 - 2023 NOAA USGS Lidar: Hawaii (Kahoolawe,
Lanai, Maui, Molokai, Oahu)" (point cloud, LAS/LAZ, plus a companion DEM), and
USGS 3DEP point clouds on AWS (public Entwine Point Tiles). Coverage of Upcountry
and the flight dates are not yet confirmed.
