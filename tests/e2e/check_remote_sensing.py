import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

# Usage: start the app (./run.sh), then  python tests/e2e/check_remote_sensing.py [screenshot_dir]
# Env: OBSERVATORY_URL (default http://localhost:8000), CHROMIUM (browser path, optional).
BASE = os.environ.get("OBSERVATORY_URL", "http://localhost:8000")
LAUNCH = {"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}
S = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
FAILS = []


def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/explore")
    pg.wait_for_selector("select[aria-label='Sentinel-2 image'] option[value='s2_dry_2022']", state="attached", timeout=60000)
    ok(pg.locator(".notice, [role=note]:has-text('Research and education only')").count() == 0, "no research-only banner")
    opts = pg.locator("select[aria-label='Sentinel-2 image'] option").all_text_contents()
    ok(len(opts) >= 7, "imagery options: " + ", ".join(opts))
    pg.select_option("select[aria-label='Sentinel-2 image']", "after_2023")
    pg.wait_for_timeout(1500)
    ok("satellite scenes" in pg.locator("aside").inner_text(), "imagery provenance shown")
    pg.click("text=Zoom to the study area")
    pg.wait_for_timeout(1500)
    pg.check("label.lyr:has-text('Annual') input")
    pg.click("text=Show all years side by side")
    pg.wait_for_timeout(1000)
    ok(pg.locator(".fcell").count() == 9, f"small multiples: {pg.locator('.fcell').count()} years")
    pg.locator(".fcell:has-text('2019')").click()
    ok(pg.locator(".sub2:has(select[aria-label='Index']) .row b.num").inner_text() == "2019", "facet click sets the year")
    ok("Check vs the study raster" not in pg.locator("aside").inner_text(), "technical caption removed")
    mb = pg.locator(".map").bounding_box()
    pg.mouse.click(mb["x"] + mb["width"] / 2 + 40, mb["y"] + mb["height"] / 2 - 60)
    pg.wait_for_timeout(1500)
    card = pg.locator(".feature").inner_text()
    ok("Dry-season NDVI here" in card and "Land cover 2021" in card.replace("Land Cover", "Land cover") or "LAND COVER" in card.upper(), "pixel card has annual series and land cover")
    ok("HEIGHT ABOVE GROUND" in card.upper() and "GROUND (LIDAR)" in card.upper(), "pixel card has lidar height and ground")
    pg.screenshot(path=f"{S}/rs_explore.png")
    # Hawaii state layers: each loads on first use, shows its legend, and the click card names the state data.
    pg.check("label:has-text('Moisture zones') input")
    pg.check("label:has-text('DLNR fire-risk areas') input")
    pg.wait_for_timeout(2500)
    ok("populated areas only" in pg.locator("aside").inner_text(), "fire-risk legend states it covers populated areas only")
    pg.mouse.click(mb["x"] + mb["width"] / 2 + 70, mb["y"] + mb["height"] / 2 - 30)
    pg.wait_for_timeout(1800)
    card2 = pg.locator(".feature").inner_text()
    ok("Hawaiʻi state data here" in card2 and "Moisture Zone" in card2 and "Moderately Dry" in card2, "click card reports the state moisture zone")
    ok("DLNR Fire Risk" in card2 and "Low" in card2, "click card reports the DLNR fire rating")
    pg.goto(BASE + "/map")
    pg.wait_for_selector(".controls", timeout=60000)
    pg.check("text=Lidar points, 2023")
    pg.wait_for_selector(".controls .note.num:has-text('points')", timeout=60000)
    ok("300,515 points" in pg.locator(".controls").inner_text(), "3D lidar points loaded")
    pg.click("label:has-text('Land cover 2021')")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=f"{S}/rs_3d.png")
    pg.goto(BASE + "/analysis")
    pg.wait_for_selector("[data-plot=independent_check] .main-svg", state="attached", timeout=120000)
    ok("r = 0.854" in pg.locator("[data-plot=independent_check] .annotation-text").text_content(), "analysis independent check")
    pg.wait_for_selector("[data-plot=space_time_cube] .gl-container", state="attached", timeout=60000)
    ok(pg.locator("[data-plot=landcover_browning] .bartext").count() >= 5, "land-cover bars")
    ok(pg.locator("[data-plot=canopy_vs_browning]").count() == 1, "lidar height figure")
    for k in ("hawaii_drought_by_county", "maui_d4_weeks", "browning_by_moisture_zone", "plantation_vs_browning", "browning_by_fire_risk", "fires_by_rating", "rain_gauges_by_elevation"):
        pg.wait_for_selector(f"[data-plot={k}] .main-svg", state="attached", timeout=60000)
        ok(pg.locator(f"[data-plot={k}]").count() == 1, f"state-data figure {k}")
    ok("#3 by annual index" in pg.locator(".plot:has([data-plot=hawaii_drought_by_county]) .note").inner_text(), "drought note says 2022 ranks #3 by annual index")
    ok(not errs, f"no page errors {errs[:2]}")
    b.close()
sys.exit(1 if FAILS else 0)
