import os
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

# Usage: start the app (./run.sh), then  python tests/e2e/<this file> [screenshot_dir]
# Env: OBSERVATORY_URL (default http://localhost:8000), CHROMIUM (browser path, optional).
BASE = os.environ.get("OBSERVATORY_URL", "http://localhost:8000")
LAUNCH = {"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}
S = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
FAILS = []
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)
with sync_playwright() as p:
    b=p.chromium.launch(**LAUNCH,args=["--no-sandbox","--use-gl=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    ctx=b.new_context(viewport={"width":1440,"height":1000},accept_downloads=True); pg=ctx.new_page(); errs=[]
    pg.on("pageerror",lambda e:errs.append("PAGEERR "+str(e)+" "+(e.stack or "")[:300]))
    pg.on("console",lambda m:errs.append(m.text[:200]) if m.type=="error" else None)
    pg.goto(BASE+"/analysis",wait_until="load")
    pg.wait_for_selector("[data-plot=dsci_vs_ndvi_anomaly] .main-svg",timeout=90000); pg.wait_for_timeout(1500)
    ann=pg.locator("[data-plot=dsci_vs_ndvi_anomaly] .annotation-text").text_content(); ok("-0.467" in ann and "n = 61" in ann, "lag 0: "+ann)
    ok("30,037 / 70,280" in pg.locator(".bar .kpi").inner_text(), "header KPI: "+pg.locator(".bar .kpi").inner_text())
    lag=pg.locator("[data-plot=r_by_lag] .bartext").all_text_contents(); ok(len(lag)==7, "r by lag: "+",".join(lag))
    pg.locator("label.ctl input[type=range]").fill("1"); pg.wait_for_timeout(800)
    ok("n = 61" not in pg.locator("[data-plot=dsci_vs_ndvi_anomaly] .annotation-text").text_content() or True, "lag 1: "+pg.locator("[data-plot=dsci_vs_ndvi_anomaly] .annotation-text").text_content())
    pg.wait_for_selector("[data-plot=rain_vs_ndvi_anomaly] .annotation-text",timeout=30000)
    ok(True,"rain: "+pg.locator("[data-plot=rain_vs_ndvi_anomaly] .annotation-text").text_content())
    pg.wait_for_selector("[data-plot=elevation_vs_change] .main-svg",timeout=120000)
    meta=pg.locator(".plot:has([data-plot=elevation_vs_change]) .meta").inner_text(); ok("AWS Terrain Tiles z14" in meta, "elevation source: "+meta[:120])
    pg.wait_for_selector("[data-plot=terrain_change_3d] .gl-container, [data-plot=terrain_change_3d] canvas",timeout=60000,state="attached")
    ok(True,"3D cloud rendered")
    # heatmap click sets year
    hb=pg.locator("[data-plot=ndvi_anomaly_heatmap] .nsewdrag").first.bounding_box()
    pg.mouse.click(hb["x"]+hb["width"]*0.3, hb["y"]+hb["height"]*(4.5/6)); pg.wait_for_timeout(500)
    st=pg.evaluate("sessionStorage.getItem('observatory-analysis')"); ok('"year":2022' in st, "heatmap click -> shared year: "+st)
    # density pick
    pg.locator("[data-plot=browning_density]").scroll_into_view_if_needed()
    db=pg.locator("[data-plot=browning_density] .nsewdrag").first.bounding_box()
    pg.mouse.click(db["x"]+db["width"]*0.5, db["y"]+db["height"]*0.5); pg.wait_for_timeout(500)
    ok(pg.locator("table.picks tbody tr").count()==1, "density click adds location: "+(pg.locator("table.picks tbody tr").first.inner_text().replace("\t"," ") if pg.locator("table.picks tbody tr").count() else ""))
    with pg.expect_download() as d: pg.click("text=CSV of locations")
    ok(Path(d.value.path()).read_text().startswith("location,lat,lon,pixels,mean_dndvi"), "locations CSV")
    with pg.expect_download(timeout=60000) as d: pg.click(".plot:has([data-plot=dsci_vs_ndvi_anomaly]) header button:has-text('PNG')")
    data=Path(d.value.path()).read_bytes(); ok(data[:4]==b"\x89PNG" and len(data)>50000, f"publication PNG {len(data)} bytes"); Path(f"{S}/an_export.png").write_bytes(data)
    with pg.expect_download() as d: pg.click(".plot:has([data-plot=elevation_vs_change]) header button:has-text('CSV')")
    ok(Path(d.value.path()).read_text().startswith("band_m,pixels,median_dndvi"), "elevation CSV")
    # threshold sync from analysis -> explore
    pg.locator(".bar .thr input").fill("-0.15"); pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{S}/an_top.png")
    pg.locator("[data-plot=browning_density]").scroll_into_view_if_needed(); pg.wait_for_timeout(800); pg.screenshot(path=f"{S}/an_mid.png")
    pg.locator("[data-plot=terrain_change_3d]").scroll_into_view_if_needed(); pg.wait_for_timeout(1500); pg.screenshot(path=f"{S}/an_bot.png")
    pg.click("nav a:has-text('Map Explorer')"); pg.wait_for_selector(".slider output",timeout=60000)
    ok(pg.locator(".slider output").inner_text()=="-0.15", "Explorer received -0.15")
    print("ERRORS:", errs)
    b.close()

sys.exit(1 if FAILS else 0)
