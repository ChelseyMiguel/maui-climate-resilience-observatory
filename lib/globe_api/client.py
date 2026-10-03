"""Client for the public GLOBE Observer measurement search API (land cover protocol).

The GLOBE land cover protocol has a citizen scientist stand at one point and take
six photos — one facing each cardinal direction (North/South/East/West), one
straight up at the canopy/sky, one straight down at the ground. Together those
document a 100 m square site. This module pulls those observations and normalizes
each one into a `LandCoverSite` the reconstruction and viewer layers can consume.

API facts confirmed against the live service (2026-09):

* Endpoint  GET https://api.globe.gov/search/v1/measurement/protocol/measureddate/
            The trailing slash is REQUIRED (404 without it) and the boolean params
            must be uppercase TRUE/FALSE (406 otherwise).
* Auth      None. This is a public read API — no developer key, no access code.
            (The key/access-code scheme documented at api.globe.gov/docs applies
            only to the separate *submission* API for POSTing new device data,
            which does not even support the land_covers protocol.)
* Limits    No documented or observed rate limit. GLOBE caps any single query at
            1 million records; land_covers runs ~16k observations/year worldwide,
            so a multi-year pull is comfortably one request.
* Geography NOT filterable server-side. `countrycode` / lat-lon bbox params are
            silently ignored — every geographic filter here happens client-side
            after the fetch. That is cheap at this data volume.
* Photos    Served from data.globe.gov, publicly fetchable, no auth, ~300 KB JPEGs.

Responses are cached as GeoJSON under `data/cache/` so a demo never depends on the
API being reachable at run time. Because the API cannot filter geographically,
callers pass a `BoundingBox` (e.g. `HAWAII`) and only that region is persisted —
a decade worldwide is ~200 MB, the same window clipped to Hawaii is well under a
megabyte.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.globe.gov/search/v1/measurement/protocol/measureddate/"
PROTOCOL = "land_covers"

# Canonical order of the six protocol shots. The API spells the two vertical
# shots "Upward"/"Downward"; we keep GLOBE's own vocabulary so field names map
# straight onto `landcovers{Direction}PhotoUrl` without a translation table.
DIRECTIONS: tuple[str, ...] = ("North", "South", "East", "West", "Upward", "Downward")

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
PHOTO_DIR = Path(__file__).resolve().parents[2] / "data" / "photos"

# "80% MUC 43 [Herbaceous/Grassland, Short Grass]; 20% MUC 93 [Urban, Roads and Parking]"
_CLASSIFICATION_RE = re.compile(
    r"(?P<pct>\d+)%\s*MUC\s*(?P<code>\d+)\s*(?:\((?P<variant>[^)]*)\)\s*)?\[(?P<label>[^\]]*)\]"
)


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundingBox:
    """A named lat/lon box used to clip what gets cached.

    The GLOBE search API ignores geographic query parameters, so clipping is the
    only way to avoid persisting the entire worldwide dataset. `name` becomes
    part of the cache filename, so widening the area writes a separate file
    rather than silently reusing a narrower one.
    """

    name: str
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        return (
            self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon
        )

    def contains_feature(self, feature: dict) -> bool:
        """Test a raw GeoJSON feature, preferring the observer's own coordinates.

        Falls back to the Feature geometry, and keeps nothing when neither
        parses — an observation with no usable position cannot be placed anyway.
        """
        props = feature.get("properties", {})
        lat = _as_float(props.get("landcoversMeasurementLatitude"))
        lon = _as_float(props.get("landcoversMeasurementLongitude"))
        if lat is None or lon is None:
            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            lat = lat if lat is not None else _as_float(coords[1])
            lon = lon if lon is not None else _as_float(coords[0])
        if lat is None or lon is None:
            return False
        return self.contains(lat, lon)


# Wide enough to cover the whole Hawaiian chain, not just Maui, so neighbouring
# islands stay available without a re-fetch.
HAWAII = BoundingBox(
    name="hawaii", min_lat=18.5, min_lon=-160.5, max_lat=22.5, max_lon=-154.5
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Classification:
    """One land-cover class a citizen scientist assigned to a single photo.

    A direction usually carries several of these and the percentages are eyeball
    estimates, so they do NOT reliably sum to 100 — treat them as ranked
    impressions of what is in frame, not as a partition.
    """

    percent: int
    muc_code: str  # MUC (Modified UNESCO Classification) number, e.g. "43"
    label: str  # e.g. "Herbaceous/Grassland, Short Grass"


@dataclass(frozen=True)
class DirectionalPhoto:
    """One of the six shots that make up a land cover observation."""

    direction: str  # one of DIRECTIONS
    photo_url: str | None  # None when the observer skipped this direction
    classifications: list[Classification] = field(default_factory=list)
    caption: str | None = None

    @property
    def present(self) -> bool:
        return self.photo_url is not None


@dataclass(frozen=True)
class LandCoverSite:
    """A single GLOBE land cover observation, normalized.

    One of these is one visit to one site at one moment: six photos plus the
    metadata needed to place it in space and time. Multiple observations can
    share a `site_id` across dates — that repeat coverage is what makes a
    before/after comparison at a location possible.
    """

    land_cover_id: str
    site_id: str
    site_name: str  # MGRS grid tile, e.g. "04QGH777957"
    measured_at: datetime | None
    latitude: float
    longitude: float
    elevation_m: float | None
    location_accuracy_m: float | None
    muc_code: str | None  # dominant class for the site overall
    muc_description: str | None
    field_notes: str | None
    organization_name: str | None
    globe_teams: str | None  # e.g. "[Oregon State University GEOGRAPHY]"
    data_source: str | None  # "GLOBE Observer App" vs manual site definition
    country_code: str | None
    photos: dict[str, DirectionalPhoto]
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def present_directions(self) -> list[str]:
        return [d for d in DIRECTIONS if self.photos[d].present]

    @property
    def missing_directions(self) -> list[str]:
        return [d for d in DIRECTIONS if not self.photos[d].present]

    @property
    def is_complete(self) -> bool:
        """True when all six protocol photos are present.

        Only complete observations can fill all six cube faces; partial ones are
        still useful but the viewer has to fill the gaps.
        """
        return not self.missing_directions

    def photo_urls(self) -> dict[str, str]:
        """Direction -> URL for the directions that actually have a photo."""
        return {d: self.photos[d].photo_url for d in self.present_directions}  # type: ignore[misc]

    def to_dict(self) -> dict:
        """Plain-JSON form, for the API layer and the on-disk site cache."""
        return {
            "land_cover_id": self.land_cover_id,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "measured_at": self.measured_at.isoformat() if self.measured_at else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation_m": self.elevation_m,
            "location_accuracy_m": self.location_accuracy_m,
            "muc_code": self.muc_code,
            "muc_description": self.muc_description,
            "field_notes": self.field_notes,
            "organization_name": self.organization_name,
            "globe_teams": self.globe_teams,
            "data_source": self.data_source,
            "country_code": self.country_code,
            "is_complete": self.is_complete,
            "missing_directions": self.missing_directions,
            "photos": {
                d: {
                    "direction": d,
                    "photo_url": p.photo_url,
                    "caption": p.caption,
                    "classifications": [
                        {"percent": c.percent, "muc_code": c.muc_code, "label": c.label}
                        for c in p.classifications
                    ],
                }
                for d, p in self.photos.items()
            },
        }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _clean(value) -> str | None:
    """Normalize GLOBE's several spellings of "no value" to None.

    The API returns the *string* "null" (not JSON null) for empty fields, and
    occasionally an empty string or the literal "(none)" in free-text fields.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "null", "None", "(none)"):
        return None
    return text


def _as_float(value) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_measured_at(value) -> datetime | None:
    """Parse `landcoversMeasuredAt`, which comes in two shapes.

    App submissions look like "2023-10-08T23:16:00"; older manual site
    definitions carry microseconds ("2018-02-03T17:39:03.059676").
    """
    text = _clean(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_classifications(value) -> list[Classification]:
    """Parse GLOBE's classification string into structured classes.

    Input looks like::

        "80% MUC 43 [Herbaceous/Grassland, Short Grass]; 20% MUC 93 [Urban, Roads and Parking]"

    Some entries carry a parenthesised variant — "50% MUC 81 (1) [Cultivated...]"
    or "10% MUC 33 (l) [Shrubs...]" — which we match and discard, since the
    bracketed label already spells the class out in full.
    """
    text = _clean(value)
    if text is None:
        return []
    out: list[Classification] = []
    for match in _CLASSIFICATION_RE.finditer(text):
        out.append(
            Classification(
                percent=int(match.group("pct")),
                muc_code=match.group("code"),
                label=match.group("label").strip(),
            )
        )
    return out


def parse_feature(feature: dict) -> LandCoverSite:
    """Turn one GeoJSON Feature from the API into a `LandCoverSite`."""
    props = feature.get("properties", {})

    photos = {
        d: DirectionalPhoto(
            direction=d,
            photo_url=_clean(props.get(f"landcovers{d}PhotoUrl")),
            classifications=parse_classifications(
                props.get(f"landcovers{d}Classifications")
            ),
            caption=_clean(props.get(f"landcovers{d}Caption")),
        )
        for d in DIRECTIONS
    }

    # Prefer the measurement lat/lon fields (where the observer actually stood)
    # and fall back to the Feature geometry, which is the registered site centre.
    coords = feature.get("geometry", {}).get("coordinates", [None, None])
    lat = _as_float(props.get("landcoversMeasurementLatitude"))
    lon = _as_float(props.get("landcoversMeasurementLongitude"))
    if lat is None:
        lat = _as_float(coords[1])
    if lon is None:
        lon = _as_float(coords[0])

    return LandCoverSite(
        land_cover_id=_clean(props.get("landcoversLandCoverId")) or "",
        site_id=_clean(props.get("siteId")) or "",
        site_name=_clean(props.get("siteName")) or "",
        measured_at=_parse_measured_at(props.get("landcoversMeasuredAt")),
        latitude=lat if lat is not None else float("nan"),
        longitude=lon if lon is not None else float("nan"),
        elevation_m=_as_float(props.get("landcoversMeasurementElevation"))
        or _as_float(props.get("elevation")),
        location_accuracy_m=_as_float(props.get("landcoversLocationAccuracyM")),
        muc_code=_clean(props.get("landcoversMucCode")),
        muc_description=_clean(props.get("landcoversMucDescription")),
        field_notes=_clean(props.get("landcoversFieldNotes")),
        organization_name=_clean(props.get("organizationName")),
        globe_teams=_clean(props.get("landcoversGlobeTeams")),
        data_source=_clean(props.get("landcoversDataSource")),
        country_code=_clean(props.get("countryCode")),
        photos=photos,
        raw=props,
    )


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _cache_path(start: str, end: str, area: str) -> Path:
    return CACHE_DIR / f"land_covers_{area}_{start}_{end}.geojson"


def _as_date_str(value: str | date | datetime) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _write_atomic(path: Path, text: str) -> None:
    """Write via a temp file and rename, so readers never see a partial file.

    A plain write_text that is interrupted leaves a half-written cache that
    fails to parse on every later start.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


class GlobeUnavailableError(RuntimeError):
    """The GLOBE API could not be reached and there is no cached copy to use."""


def _iter_year_chunks(start_s: str, end_s: str):
    """Split a date range into calendar-year chunks.

    The API will happily return a decade in one response, but that is a ~200 MB
    JSON document held in memory at once. Year chunks keep peak memory to roughly
    a twentieth of that and make a partial failure cheap to retry.
    """
    begin, finish = date.fromisoformat(start_s), date.fromisoformat(end_s)
    cursor = begin
    while cursor <= finish:
        chunk_end = min(date(cursor.year, 12, 31), finish)
        yield cursor.isoformat(), chunk_end.isoformat()
        cursor = date(cursor.year + 1, 1, 1)


def _fetch_chunk(start_s: str, end_s: str, timeout: float) -> list[dict]:
    """One API call for one date range; returns its GeoJSON features."""
    params = {
        "protocols": PROTOCOL,
        "startdate": start_s,
        "enddate": end_s,
        # Uppercase is required — the API 406s on lowercase booleans.
        "geojson": "TRUE",
        "sample": "FALSE",
    }
    try:
        response = httpx.get(BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GlobeUnavailableError(
            f"GLOBE API request failed for {start_s}..{end_s}: {exc}"
        ) from exc
    return response.json().get("features", [])


def fetch_raw(
    start: str | date | datetime,
    end: str | date | datetime,
    *,
    bbox: BoundingBox | None = None,
    use_cache: bool = True,
    refresh: bool = False,
    timeout: float = 60.0,
) -> dict:
    """Fetch the raw GeoJSON FeatureCollection for a date range.

    When `bbox` is given, only features inside it are kept *and cached*. This
    matters: the API cannot filter geographically, so a decade of worldwide land
    cover is ~200 MB, while the same window clipped to Hawaii is well under a
    megabyte. Caching the clipped subset keeps the repo small and cold starts
    fast, at the cost of needing a re-fetch to widen the area later.

    Results are cached on disk per (area, date range); pass `refresh=True` to
    re-fetch. Caching matters for demos — a submission deadline is a bad time to
    discover the network is down.
    """
    start_s, end_s = _as_date_str(start), _as_date_str(end)
    path = _cache_path(start_s, end_s, bbox.name if bbox else "global")

    if use_cache and not refresh and path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            # A truncated or corrupt cache file (e.g. an interrupted write) must
            # not take the app down — fall through and re-fetch it.
            path.unlink(missing_ok=True)

    features: list[dict] = []
    for chunk_start, chunk_end in _iter_year_chunks(start_s, end_s):
        for feature in _fetch_chunk(chunk_start, chunk_end, timeout):
            if bbox is None or bbox.contains_feature(feature):
                features.append(feature)

    payload = {"type": "FeatureCollection", "name": "GLOBE-data", "features": features}

    if use_cache:
        _write_atomic(path, json.dumps(payload))

    return payload


# Parsed observations, keyed by (area, start, end). Even clipped to Hawaii, the
# API layer queries the same window over and over, so one parse is reused for the
# process lifetime rather than re-reading and re-parsing the cache file per
# request.
_PARSED: dict[tuple[str, str, str], list[LandCoverSite]] = {}


def fetch_sites(
    start: str | date | datetime,
    end: str | date | datetime,
    *,
    bbox: BoundingBox | None = None,
    use_cache: bool = True,
    refresh: bool = False,
    timeout: float = 60.0,
) -> list[LandCoverSite]:
    """Fetch and parse land cover observations in a date range.

    Clipped to `bbox` when given, worldwide otherwise. Parsed results are
    memoized in process; `refresh=True` re-fetches and replaces them.
    """
    key = (bbox.name if bbox else "global", _as_date_str(start), _as_date_str(end))
    if not refresh and key in _PARSED:
        return _PARSED[key]

    payload = fetch_raw(
        start, end, bbox=bbox, use_cache=use_cache, refresh=refresh, timeout=timeout
    )
    sites = [parse_feature(f) for f in payload.get("features", [])]
    _PARSED[key] = sites
    return sites


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def fetch_near(
    latitude: float,
    longitude: float,
    *,
    radius_km: float = 25.0,
    start: str | date | datetime,
    end: str | date | datetime,
    bbox: BoundingBox | None = None,
    complete_only: bool = False,
    use_cache: bool = True,
    refresh: bool = False,
) -> list[LandCoverSite]:
    """Observations within `radius_km` of a point, nearest first.

    The API has no geographic filter, so this filters locally. Pass the `bbox`
    the point sits in (e.g. `HAWAII`) so only that region is fetched and cached
    rather than the worldwide dataset.
    """
    sites = fetch_sites(start, end, bbox=bbox, use_cache=use_cache, refresh=refresh)

    matched: list[tuple[float, LandCoverSite]] = []
    for site in sites:
        if math.isnan(site.latitude) or math.isnan(site.longitude):
            continue
        if complete_only and not site.is_complete:
            continue
        distance = haversine_km(latitude, longitude, site.latitude, site.longitude)
        if distance <= radius_km:
            matched.append((distance, site))

    matched.sort(key=lambda pair: pair[0])
    return [site for _, site in matched]


def group_by_site(sites: list[LandCoverSite]) -> dict[str, list[LandCoverSite]]:
    """Group observations by `site_id`, each list sorted oldest-first.

    Repeat visits to one site are what make a before/after view possible, so
    this is the shape the change-over-time comparison consumes.
    """
    grouped: dict[str, list[LandCoverSite]] = {}
    for site in sites:
        grouped.setdefault(site.site_id, []).append(site)
    for observations in grouped.values():
        observations.sort(key=lambda s: s.measured_at or datetime.min)  # noqa: DTZ901 — GLOBE timestamps are naive
    return grouped


# ---------------------------------------------------------------------------
# Local photo mirror
# ---------------------------------------------------------------------------


def local_photo_path(land_cover_id: str, direction: str) -> Path:
    """Where a mirrored photo lives: data/photos/<land_cover_id>/<direction>.jpg."""
    return PHOTO_DIR / land_cover_id / f"{direction.lower()}.jpg"


def mirror_photos(
    site: LandCoverSite, *, timeout: float = 60.0
) -> tuple[int, list[str]]:
    """Download one observation's photos so the viewer can run fully offline.

    Returns (files saved, error messages). Photos already on disk are skipped, so
    re-running is cheap. Each file is written via a temp file and renamed, so an
    interrupted download never leaves a truncated JPEG that would render as a
    broken cube face. One bad photo does not abort the rest: a partial mirror is
    still useful, because the API falls back to the remote URL per photo.
    """
    saved, errors = 0, []
    for direction, url in site.photo_urls().items():
        target = local_photo_path(site.land_cover_id, direction)
        if target.exists() and target.stat().st_size > 0:
            continue
        try:
            response = httpx.get(url, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/") or not response.content:
                raise ValueError(f"not an image ({content_type or 'no content-type'})")
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".jpg.tmp")
            tmp.write_bytes(response.content)
            tmp.replace(target)
            saved += 1
        except (httpx.HTTPError, ValueError, OSError) as exc:
            errors.append(f"{site.land_cover_id}/{direction}: {exc}")
    return saved, errors
