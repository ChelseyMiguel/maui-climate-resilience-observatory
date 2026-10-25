"""Response policy for the whole app: compression, caching and safe default headers.

Written as plain ASGI wrappers (not `BaseHTTPMiddleware`) so file responses keep
streaming straight from disk.

Why it matters here: the Observatory ships a ~1 MB browning GeoJSON and ~1.6 MB
of map/3D JavaScript. Over a judge's Wi-Fi, gzip plus a long cache lifetime on
the content-hashed build files is the difference between an instant second
visit and re-downloading everything.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Vite and the vendored ESM bundle name their files by content hash, so a given
# URL can never change: cache it for a year and never revalidate.
IMMUTABLE = "public, max-age=31536000, immutable"
_IMMUTABLE_PREFIXES = ("/static/site/assets/", "/static/vendor/esm/")

# Pages must always be re-checked: after a rebuild they point at new hashed files.
REVALIDATE = "no-cache"
_PAGES = frozenset({"/", "/viewer", "/explore", "/insights", "/map", "/analysis", "/methods", "/sources"})

# Datasets served from files that only change when someone re-runs a fetch script.
DATASET = "public, max-age=300"
_DATASET_PREFIX = "/api/layers/"

# A mirrored photo is written once and never replaced (existing files are skipped).
PHOTO = "public, max-age=86400"

# Already compressed (JPEG photos, GeoTIFFs); gzip would burn CPU for no saving.
# The rasters are routed without a file extension, so match by prefix.
_NO_GZIP_PREFIXES = ("/photos/", "/api/layers/raster/", "/api/layers/imagery/")
_NO_GZIP_SUFFIXES = (".tif", ".tiff", ".jpg", ".jpeg", ".png", ".webp")


def cache_control_for(path: str) -> str | None:
    """Cache-Control for a successful GET of `path`, or None to leave it alone."""
    if path.startswith(_IMMUTABLE_PREFIXES):
        return IMMUTABLE
    if path in _PAGES:
        return REVALIDATE
    if path.startswith("/photos/"):
        return PHOTO
    if path.startswith(_DATASET_PREFIX):
        return DATASET
    return None


class PolicyHeaders:
    """Adds nosniff/referrer headers everywhere and Cache-Control on successes.

    Only 200/304 responses get a cache lifetime, so a 503 for a missing data
    file is never remembered by the browser after the file appears.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_policy(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                if scope["method"] == "GET" and message["status"] in (200, 304):
                    policy = cache_control_for(scope["path"])
                    if policy:
                        headers.setdefault("Cache-Control", policy)
            await send(message)

        await self.app(scope, receive, send_with_policy)


class SelectiveGZip:
    """GZip everything except content that is already compressed."""

    def __init__(self, app: ASGIApp, *, minimum_size: int = 1024, compresslevel: int = 6) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope["path"].lower()
            if not (path.startswith(_NO_GZIP_PREFIXES) or path.endswith(_NO_GZIP_SUFFIXES)):
                await self.gzip(scope, receive, send)
                return
        await self.app(scope, receive, send)
