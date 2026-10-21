# Browser checks

End-to-end checks of the Map Explorer, 3D view and Analysis workspace, run
against a running app with Playwright (`pip install playwright`; Chromium).

    ./run.sh &                               # http://localhost:8000
    python tests/e2e/check_explorer_3d.py    # threshold baseline, histogram drag, basemap
                                             # fallback, pixel inspection, profile, 3D, compare,
                                             # brushing, CSV/JSON/PNG exports, 2D -> 3D sync
    python tests/e2e/check_analysis.py       # r = -0.467 (n = 61), lag/rain plots, elevation,
                                             # heatmap -> map year, location compare, exports
    python tests/e2e/check_square_and_mobile.py   # no rounded corners and no horizontal
                                                  # overflow on every page at 1440 and 390 px

Each prints PASS/FAIL lines and exits non-zero on a failure. Screenshots go to
the directory given as the first argument (a temp dir by default). Remote
basemaps (USGS, CARTO, EOX) are expected to fail in an offline sandbox; the
explorer check then verifies the fallback to the offline terrain.
