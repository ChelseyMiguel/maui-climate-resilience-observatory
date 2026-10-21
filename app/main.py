"""FastAPI entry point for the GLOBE site reconstruction viewer.

Structure ported from CoralPulse: static mount, Jinja2 index, thin routers.
No database and no background tasks — GLOBE responses are cached as JSON files
under `data/cache/` by `lib.globe_api.client`, which is all this needs for now.
"""

from __future__ import annotations

import mimetypes
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import layers, sites
from app.middleware import PolicyHeaders, SelectiveGZip
from lib.globe_api import client

# Browsers refuse to execute ES modules served with a non-JS Content-Type, and
# the host Python's mime DB does not always know .mjs.
mimetypes.add_type("text/javascript", ".mjs")

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Region insights take a few seconds of geometry each the first time. Compute
    # them in the background so the first person to open the page doesn't wait.
    from lib import regions

    threading.Thread(target=regions.warm, name="warm-regions", daemon=True).start()
    yield


app = FastAPI(title="GLOBE Site Reconstruction", version="0.1.0", lifespan=lifespan)
# Last added is outermost: gzip wraps the policy headers, which wrap the routes.
app.add_middleware(PolicyHeaders)
app.add_middleware(SelectiveGZip)

# The page is served as a plain static file rather than through a template
# engine. It carries no server-side variables, and htm's inline-style syntax
# (`style=${{ ... }}`) collides with Jinja2's own `{{ }}` delimiters — so
# templating would buy nothing and cost an escaping workaround.
_INDEX = Path(__file__).parent / "templates" / "index.html"

# Vendored ES modules (react, three, r3f, drei, htm) are served locally so the
# cube-map viewer runs with no CDN at runtime — same approach as CoralPulse.
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Locally mirrored GLOBE photos (scripts/ingest_maui.py --download-photos), so the
# viewer works with no network. StaticFiles refuses a missing directory, and the
# mirror may not exist yet, so make sure it does — an empty one is harmless
# because the API only rewrites a photo URL when its file is actually present.
client.PHOTO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=str(client.PHOTO_DIR)), name="photos")

app.include_router(sites.router, prefix="/api/sites", tags=["sites"])
app.include_router(layers.router, prefix="/api/layers", tags=["layers"])

# The Observatory (Svelte, built by Vite into static/site) owns these paths; the
# browser router inside it decides which page to show. Node is only needed to
# rebuild it, never to run it.
_SITE_INDEX = _static_dir / "site" / "index.html"
SITE_PATHS = ("/", "/explore", "/insights", "/map", "/analysis", "/methods", "/sources", "/about")


def _site() -> FileResponse:
    if not _SITE_INDEX.exists():
        raise HTTPException(
            status_code=503,
            detail="Observatory not built — run: cd web && npm install && npm run build",
        )
    return FileResponse(_SITE_INDEX, media_type="text/html")


@app.get("/", response_class=FileResponse, response_model=None)
def index(request: Request) -> FileResponse | RedirectResponse:
    # Links made before the Observatory existed pointed at /?obs=<id> for the
    # 360-degree viewer; keep them working.
    obs = request.query_params.get("obs")
    if obs:
        return RedirectResponse(url=f"/viewer?obs={quote(obs)}", status_code=307)
    return _site()


@app.get("/viewer", response_class=FileResponse)
def viewer() -> FileResponse:
    """The 360-degree GLOBE site viewer (no build step)."""
    return FileResponse(_INDEX, media_type="text/html")


for _path in SITE_PATHS[1:]:
    app.add_api_route(_path, _site, methods=["GET"], response_class=FileResponse, include_in_schema=False)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
