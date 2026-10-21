import os
import sys
import tempfile

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
JS = """() => { const out = [];
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el); if (cs.display === 'none') continue;
    const r = [cs.borderTopLeftRadius, cs.borderTopRightRadius, cs.borderBottomLeftRadius, cs.borderBottomRightRadius];
    if (r.some(v => v !== '0px')) out.push(el.tagName.toLowerCase() + '.' + (el.className?.baseVal ?? el.className) + ' ' + r.join(' '));
    const rx = el.getAttribute && (el.getAttribute("rx") || el.getAttribute("ry")); const crx = getComputedStyle(el).rx;
    if (rx && +rx > 0 && crx !== "0px" && crx !== "0") out.push('svg ' + el.tagName + ' rx=' + rx + ' ' + (el.getAttribute('class') || ''));
  }
  return out; }"""
with sync_playwright() as p:
    b=p.chromium.launch(**LAUNCH,args=["--no-sandbox","--use-gl=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    for w,h in ((1440,900),(390,844)):
        pg=b.new_page(viewport={"width":w,"height":h})
        for path in ["/","/explore","/insights","/map","/analysis","/methods","/sources","/about","/viewer"]:
            pg.goto(BASE+""+path, wait_until="load"); pg.wait_for_timeout(9000 if path in ("/analysis","/explore","/map") else 3000)
            bad=pg.evaluate(JS)
            ov=pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            ok(not bad and ov <= 0, f"{w}px {path:10} rounded={len(bad)} overflow={ov}px {bad[:4]}")
            if w==390 and path in ("/explore","/analysis","/map"): pg.screenshot(path=f"{S}/m{path.strip('/')}.png")
        pg.close()
    b.close()

sys.exit(1 if FAILS else 0)
