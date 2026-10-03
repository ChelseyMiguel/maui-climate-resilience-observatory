"""FastAPI entry point for the GLOBE site reconstruction viewer.

Structure ported from CoralPulse: static mount, Jinja2 index, thin routers.
No database and no background tasks — GLOBE responses are cached as JSON files
under `data/cache/` by `lib.globe_api.client`, which is all this needs for now.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import sites
from lib.globe_api import client

# Browsers refuse to execute ES modules served with a non-JS Content-Type, and
# the host Python's mime DB does not always know .mjs.
mimetypes.add_type("text/javascript", ".mjs")

app = FastAPI(title="GLOBE Site Reconstruction", version="0.1.0")

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


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(_INDEX, media_type="text/html")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
