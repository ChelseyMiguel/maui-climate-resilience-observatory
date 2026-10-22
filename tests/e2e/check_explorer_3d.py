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
import json

with sync_playwright() as p:
    b=p.chromium.launch(**LAUNCH,args=["--no-sandbox","--use-gl=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    ctx=b.new_context(viewport={"width":1440,"height":900}, accept_downloads=True)
    pg=ctx.new_page(); errs=[]
    pg.on("pageerror",lambda e:errs.append("PAGEERR "+str(e)+" "+(e.stack or "")[:500]))
    pg.on("console",lambda m:errs.append(m.text[:160]) if m.type=="error" else None)
    pg.goto(BASE+"/explore",wait_until="load")
    pg.wait_for_selector("table.classes",timeout=60000)
    row=pg.locator("table.classes tbody tr").first.inner_text()
    ok("30,037" in row and "42.7" in row, "baseline at -0.10: "+row.replace("\t"," | "))
    tot=pg.locator("table.classes tfoot").inner_text(); ok("70,280" in tot, "valid pixels: "+tot.replace("\t"," | "))
    # histogram drag
    pg.locator("svg.hist").scroll_into_view_if_needed(); h=pg.locator("svg.hist").bounding_box()
    x=h["x"]+h["width"]*((-0.25+0.6)/1.0); y=h["y"]+h["height"]*0.5
    pg.mouse.move(h["x"]+h["width"]*0.5, y); pg.mouse.down(); pg.mouse.move(x,y,steps=8); pg.mouse.up(); pg.wait_for_timeout(500)
    out=pg.locator(".slider output").inner_text(); ok(out in ("-0.25","-0.24","-0.26"), "histogram drag sets threshold: "+out)
    pg.locator("svg.hist").focus(); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(200)
    ok(pg.locator(".slider output").inner_text()!=out, "arrow key moves threshold: "+pg.locator(".slider output").inner_text())
    pg.click("text=reset to the study’s −0.10"); pg.wait_for_timeout(300)
    ok("30,037" in pg.locator("table.classes tbody tr").first.inner_text(), "reset restores 30,037")
    pg.click("text=Zoom to the study area"); pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{S}/x_2d.png")
    # basemap fallback (tiles blocked in this sandbox)
    pg.route("**/USGSImageryOnly/**", lambda route: route.abort())   # simulate an outage, whatever the network allows
    pg.select_option("select[aria-label='Basemap']", "imagery"); pg.wait_for_timeout(6000)
    msg=pg.locator("aside .empty").all_inner_texts()
    ok(any("couldn’t load" in m for m in msg) and pg.locator("select[aria-label='Basemap']").input_value()=="relief", "blocked basemap falls back: "+" / ".join(msg)[:160])
    # pixel inspection
    mb=pg.locator(".map").bounding_box(); cx=mb["x"]+mb["width"]/2; cy=mb["y"]+mb["height"]/2
    pg.mouse.click(cx+30, cy+20); pg.wait_for_timeout(2500)
    card=pg.locator(".feature").inner_text()
    ok("DNDVI" in card.upper() and " m" in card.split("Elevation")[1][:20], "pixel card: "+card.replace("\n"," | ")[:260])
    # profile
    pg.click("text=Profile"); pg.mouse.click(cx-200, cy-60); pg.mouse.click(cx+220, cy+80)
    pg.wait_for_selector(".panel[aria-label='Transect profile'] .kpi", timeout=30000)
    ok(True, "profile: "+pg.locator(".panel[aria-label='Transect profile'] .kpi").inner_text().replace("\n"," "))
    ok("Terrain Tiles" in pg.locator(".panel[aria-label='Transect profile'] svg").inner_html(), "profile uses AWS tiles")
    with pg.expect_download() as d: pg.click(".panel[aria-label='Transect profile'] button:has-text('CSV')")
    txt=Path(d.value.path()).read_text().splitlines(); ok(txt[0].startswith("distance_m,lon,lat,elevation_m") and len(txt)==242, f"profile CSV {len(txt)} lines: {txt[0]}")
    pg.screenshot(path=f"{S}/x_profile.png")
    pg.click(".panel[aria-label='Transect profile'] .x")
    # 3D
    pg.click(".toolbar button:has-text('3D')"); pg.wait_for_timeout(5000)
    ok(pg.locator(".subbar").count()==1, "3D controls shown")
    pg.screenshot(path=f"{S}/x_3d.png")
    pg.click(".toolbar button:has-text('2D')"); pg.wait_for_timeout(1500)
    # compare
    pg.click(".toolbar button:has-text('Compare')"); pg.wait_for_timeout(500)
    pg.click("text=dNDVI | dNBR"); pg.wait_for_timeout(3000)
    ok(pg.locator(".side.right").inner_text().endswith("dNBR"), "compare labels: "+pg.locator(".side.left").inner_text()+" | "+pg.locator(".side.right").inner_text())
    pg.screenshot(path=f"{S}/x_compare.png")
    pg.click(".toolbar button:has-text('Compare')"); pg.wait_for_timeout(500)
    # data panel: brush + click + downloads
    pg.click("text=Data over time"); pg.wait_for_selector(".panel[aria-label='Study-area data over time'] svg[role=img]", timeout=20000)
    sv=pg.locator(".panel[aria-label='Study-area data over time'] svg[role=img]").bounding_box()
    y=sv["y"]+sv["height"]*0.5
    pg.mouse.move(sv["x"]+sv["width"]*0.45,y); pg.mouse.down(); pg.mouse.move(sv["x"]+sv["width"]*0.75,y,steps=6); pg.mouse.up(); pg.wait_for_timeout(300)
    sel=pg.locator(".panel select").all(); fr=sel[0].input_value(); to=sel[1].input_value()
    ok(fr>"2019" and to<"2024-06", f"brush zoom -> {fr} .. {to}")
    pg.click(".panel button.b:text-is('All')"); pg.wait_for_timeout(200)
    pg.mouse.click(sv["x"]+sv["width"]*0.62, y); pg.wait_for_timeout(500)
    yr=pg.locator(".years label.on").inner_text(); ok(yr in ("2021","2022"), "click picks map year: "+yr)
    for kind in ("CSV","JSON","PNG"):
        with pg.expect_download() as d: pg.click(f".panel[aria-label='Study-area data over time'] button:has-text('{kind}')")
        path=d.value.path(); data=Path(path).read_bytes()
        if kind=="CSV": ok(data.decode().startswith("month,ndvi,nbr,dsci"), f"CSV {len(data)} bytes")
        if kind=="JSON": j=json.loads(data); ok(len(j["rows"])>60 and "sources" in j, f"JSON rows={len(j['rows'])}")
        if kind=="PNG": ok(data[:8]==b"\x89PNG\r\n\x1a\n" and len(data)>20000, f"PNG {len(data)} bytes"); Path(f"{S}/x_export.png").write_bytes(data)
    pg.screenshot(path=f"{S}/x_data.png")
    # threshold sync to 3D page
    pg.fill(".slider input", "-0.2"); pg.wait_for_timeout(400)
    pg.click("nav a:has-text('3D View')"); pg.wait_for_selector(".controls .note.num", timeout=60000); pg.wait_for_timeout(1500)
    lab=pg.locator(".controls").inner_text(); ok("-0.20" in lab, "3D view received threshold: "+next(ln for ln in lab.splitlines() if "px" in ln))
    cv=pg.locator(".stage canvas").bounding_box(); pg.mouse.click(cv["x"]+cv["width"]*0.5, cv["y"]+cv["height"]*0.55); pg.wait_for_timeout(2500)
    ins=pg.locator("aside .card.site").first.inner_text() if pg.locator("aside .card.site").count() else ""
    ok("Elevation" in ins, "3D ground inspect: "+ins.replace("\n"," | ")[:200])
    pg.screenshot(path=f"{S}/x_m3d.png")
    print("ERRORS:", [e for e in errs if "TUNNEL" not in e])
    b.close()

sys.exit(1 if FAILS else 0)
