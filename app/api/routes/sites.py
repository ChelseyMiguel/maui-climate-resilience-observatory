"""Routes for GLOBE land cover sites — search, detail, and repeat-visit history.

Follows the same shape as the CoralPulse zones router: a registry of known study
areas at the top, Pydantic response models, and thin handlers that delegate the
real work to `lib/`. The GLOBE API has no geographic filter, so every lookup here
goes through the client's local filtering over a cached date window.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from lib import hazards
from lib.globe_api import client
from lib.vegetation import browning, lcms

router = APIRouter()


def _window(start: str, end: str) -> tuple[date, date]:
    """Validate a client-supplied date window (422 rather than a 500)."""
    try:
        lo, hi = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="`start` and `end` must be YYYY-MM-DD dates."
        ) from exc
    if lo > hi:
        raise HTTPException(status_code=422, detail="`start` must not be after `end`.")
    return lo, hi


def _in_window(site: client.LandCoverSite, lo: date, hi: date) -> bool:
    if site.measured_at is None:
        # No date to compare: only part of an unfiltered (full-window) query.
        return lo <= date.fromisoformat(DEFAULT_START) and hi >= date.fromisoformat(DEFAULT_END)
    return lo <= site.measured_at.date() <= hi


def _unavailable(exc: client.GlobeUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail=f"GLOBE data unavailable and not cached. {exc}")


def _sites(start: str, end: str) -> list[client.LandCoverSite]:
    """Observations for the window, or a 503 that says what actually went wrong.

    Always reads the one default window (cached, parsed once per process) and
    narrows it here. Handing the caller's dates to the client would let any
    visitor trigger an outbound GLOBE request per year of range and write a new
    cache file per distinct window.

    The cache makes this a no-op at demo time; it only matters on a cold start
    with no network, where a bare 500 would give no hint that running
    `scripts/ingest_maui.py` once while online is the fix.
    """
    lo, hi = _window(start, end)
    try:
        sites = client.fetch_sites(DEFAULT_START, DEFAULT_END, bbox=REGION)
    except client.GlobeUnavailableError as exc:
        raise _unavailable(exc) from exc
    return [s for s in sites if _in_window(s, lo, hi)]

# ---------------------------------------------------------------------------
# Study-area registry — named places the demo can jump straight to.
# Pukalani is the anchor: it is the Upcountry Maui area of the browning /
# wildfire-risk analysis this tool is built to contextualize.
# ---------------------------------------------------------------------------

STUDY_AREAS: dict[str, dict] = {
    "pukalani": {
        "name": "Pukalani / Upcountry Maui",
        "lat": 20.827,
        "lon": -156.336,
        "radius_km": 25.0,
        "note": "Anchor study area — 2022 drought / 2023 Upcountry wildfire AOI.",
    },
    "kula": {
        "name": "Kula, Maui",
        "lat": 20.7912,
        "lon": -156.3269,
        "radius_km": 15.0,
        "note": "Upcountry, immediately south of the Pukalani AOI.",
    },
    "west-maui": {
        "name": "West Maui (Lahaina vicinity)",
        "lat": 20.8783,
        "lon": -156.6825,
        "radius_km": 20.0,
        "note": "August 2023 Lahaina fire vicinity.",
    },
}

# Default window for searches. GLOBE Observer land cover volume is low enough
# (~16k observations/year worldwide) that a multi-year pull is one cached request.
DEFAULT_START = "2017-01-01"
DEFAULT_END = "2026-12-31"

# Every study area is in Hawaii, so only Hawaii is fetched and cached. Widening
# this to a new region writes its own cache file rather than reusing this one.
REGION = client.HAWAII


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class ClassificationItem(BaseModel):
    percent: int
    muc_code: str
    label: str


class PhotoItem(BaseModel):
    direction: str
    # What the viewer should load: the local mirror when one exists, else GLOBE.
    photo_url: str | None
    # The original data.globe.gov URL, always — kept for attribution and so the
    # provenance is never lost when a local copy is served.
    source_url: str | None = None
    mirrored: bool = False
    caption: str | None
    classifications: list[ClassificationItem]


class SiteSummary(BaseModel):
    """Enough to list/pick a site without shipping every photo field."""

    land_cover_id: str
    site_id: str
    site_name: str
    measured_at: str | None
    latitude: float
    longitude: float
    elevation_m: float | None
    muc_description: str | None
    field_notes: str | None
    is_complete: bool
    missing_directions: list[str]
    location_accuracy_m: float | None = None
    # Share of the 100 m site footprint that fell in browned patches; None
    # outside the analysed area, where it cannot be measured.
    site_browned_fraction: float | None = None


class VegetationContext(BaseModel):
    """Where one observation sits relative to the 2019-2022 browning analysis."""

    available: bool
    in_analysis_area: bool | None = None
    # The primary measure: browned share of the 100 m footprint, with the range
    # it spans as the footprint slides by the recorded GPS error, and the AOI-wide
    # figure to read it against.
    site_browned_fraction: float | None = None
    site_browned_range: list[float] | None = None
    aoi_browned_fraction: float | None = None
    location_accuracy_m: float | None = None
    # Secondary: a single GPS point is fragile against fragmented patches, so this
    # comes with a confidence flag and the distance to the nearest edge.
    inside_browning_patch: bool | None = None
    edge_distance_m: float | None = None
    location_confidence: str | None = None
    patch_area_ha: float | None = None
    patch_rank_by_area: int | None = None
    distance_to_browning_km: float | None = None
    nearest_patch_area_ha: float | None = None
    threshold: float | None = None
    total_patches: int | None = None
    total_browned_ha: float | None = None


class SiteDetail(SiteSummary):
    location_accuracy_m: float | None
    muc_code: str | None
    organization_name: str | None
    globe_teams: str | None
    data_source: str | None
    country_code: str | None
    photos: dict[str, PhotoItem]
    vegetation: VegetationContext | None = None
    # Nearest 8 Aug 2023 fire perimeter. A distance to where fire actually went,
    # NOT a fire-risk score.
    fire: dict | None = None


class SeriesPoint(BaseModel):
    date: str
    value: float


class VegetationSeriesResponse(BaseModel):
    """AOI-wide monthly means. Months with no usable imagery are omitted."""

    ndvi: list[SeriesPoint]
    nbr: list[SeriesPoint]


class LcmsPoint(BaseModel):
    year: str
    acres: int
    pct: float


class LcmsHighlight(BaseModel):
    section: str
    class_name: str
    why: str
    points: list[LcmsPoint]
    baseline_year: str
    latest_year: str
    # None where the baseline is zero acres — the Wildfire class starts at 0,
    # and percent change from zero is meaningless rather than infinite.
    change_pct_vs_baseline: float | None
    change_acres_vs_baseline: int


class LcmsResponse(BaseModel):
    """County-wide LCMS context. NOT a per-site measurement."""

    available: bool
    summary_area: str | None = None
    data_version: str | None = None
    county_wide: bool | None = None
    highlights: list[LcmsHighlight] = []


class StudyAreaItem(BaseModel):
    key: str
    name: str
    lat: float
    lon: float
    radius_km: float
    note: str


class SiteHistoryResponse(BaseModel):
    site_id: str
    site_name: str
    observations: list[SiteSummary]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary(site: client.LandCoverSite) -> SiteSummary:
    d = site.to_dict()
    d["site_browned_fraction"] = browning.site_browned_fraction(
        site.latitude, site.longitude
    )
    return SiteSummary(**{k: d[k] for k in SiteSummary.model_fields})


def _with_local_photos(site: client.LandCoverSite, data: dict) -> dict:
    """Point each photo at its local mirror when one exists on disk.

    Decided per photo rather than per observation, so a partial mirror still
    works: mirrored faces load locally and the rest fall back to GLOBE.
    """
    for direction, photo in data["photos"].items():
        photo["source_url"] = photo["photo_url"]
        photo["mirrored"] = False
        local = client.local_photo_path(site.land_cover_id, direction)
        if photo["photo_url"] and local.exists() and local.stat().st_size > 0:
            photo["photo_url"] = f"/photos/{site.land_cover_id}/{local.name}"
            photo["mirrored"] = True
    return data


def _detail(site: client.LandCoverSite) -> SiteDetail:
    """Full detail plus the vegetation-health context for where the observer stood."""
    detail = SiteDetail(**_with_local_photos(site, site.to_dict()))
    detail.fire = hazards.fire_context(site.latitude, site.longitude)
    detail.vegetation = VegetationContext(
        **browning.context_for_point(
            site.latitude, site.longitude, site.location_accuracy_m
        )
    )
    return detail


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/study-areas", response_model=list[StudyAreaItem])
def list_study_areas() -> list[StudyAreaItem]:
    """Named study areas the viewer offers as one-click entry points."""
    return [StudyAreaItem(key=k, **v) for k, v in STUDY_AREAS.items()]


@router.get("/vegetation-series", response_model=VegetationSeriesResponse)
def get_vegetation_series() -> VegetationSeriesResponse:
    """Monthly NDVI and NBR across the Pukalani AOI, Dec 2018 - Dec 2023.

    Spans both the 2022 drought and the August 2023 Upcountry fires, so a site's
    photos can be read against the vegetation trend for the same ground.
    """
    return VegetationSeriesResponse(
        ndvi=[SeriesPoint(date=d, value=v) for d, v in browning.ndvi_series()],
        nbr=[SeriesPoint(date=d, value=v) for d, v in browning.nbr_series()],
    )


@router.get("/lcms", response_model=LcmsResponse)
def get_lcms() -> LcmsResponse:
    """LCMS land-change trajectories for Maui County, 2018-2024.

    Independent corroboration: LCMS is a published USDA Forest Service product
    built from different imagery by other people, so where it agrees with the
    project's own browning analysis the claim is much harder to dismiss.

    These are county-wide figures, not a measurement at any one GLOBE site —
    per-site LCMS classes need `scripts/gee/lcms_site_sample.js`.
    """
    return LcmsResponse(**lcms.summary())


@router.get("/search", response_model=list[SiteSummary])
def search_sites(
    lat: float | None = Query(None, description="Latitude; omit if using `area`."),
    lon: float | None = Query(None, description="Longitude; omit if using `area`."),
    area: str | None = Query(None, description="Study-area key, e.g. 'pukalani'."),
    radius_km: float = Query(25.0, gt=0, le=500),
    start: str = Query(DEFAULT_START),
    end: str = Query(DEFAULT_END),
    complete_only: bool = Query(
        False, description="Only observations with all six protocol photos."
    ),
    limit: int = Query(100, gt=0, le=1000),
) -> list[SiteSummary]:
    """Find land cover observations near a point, nearest first."""
    if area is not None:
        study = STUDY_AREAS.get(area)
        if study is None:
            raise HTTPException(status_code=404, detail=f"Unknown study area '{area}'")
        lat, lon, radius_km = study["lat"], study["lon"], study["radius_km"]
    if lat is None or lon is None:
        raise HTTPException(
            status_code=400, detail="Provide either `area` or both `lat` and `lon`."
        )

    lo, hi = _window(start, end)
    try:
        sites = client.fetch_near(
            lat,
            lon,
            radius_km=radius_km,
            start=DEFAULT_START,
            end=DEFAULT_END,
            bbox=REGION,
            complete_only=complete_only,
        )
    except client.GlobeUnavailableError as exc:
        raise _unavailable(exc) from exc
    sites = [s for s in sites if _in_window(s, lo, hi)]
    return [_summary(s) for s in sites[:limit]]


@router.get("/observation/{land_cover_id}", response_model=SiteDetail)
def get_observation(
    land_cover_id: str,
    start: str = Query(DEFAULT_START),
    end: str = Query(DEFAULT_END),
) -> SiteDetail:
    """Full detail for one observation, including all six photo URLs.

    This is what the cube-map viewer loads. Lookup scans the cached date window
    rather than hitting a per-id endpoint, because the GLOBE search API does not
    expose one.
    """
    for site in _sites(start, end):
        if site.land_cover_id == land_cover_id:
            return _detail(site)
    raise HTTPException(
        status_code=404, detail=f"No observation with id '{land_cover_id}'"
    )


@router.get("/{site_id}/history", response_model=SiteHistoryResponse)
def get_site_history(
    site_id: str,
    start: str = Query(DEFAULT_START),
    end: str = Query(DEFAULT_END),
) -> SiteHistoryResponse:
    """Every observation recorded at one site, oldest first.

    Repeat visits are what make the before/after comparison possible — a site
    with several dates can be shown changing over time alongside the dNDVI signal.
    """
    observations = [
        s for s in _sites(start, end) if s.site_id == site_id
    ]
    if not observations:
        raise HTTPException(status_code=404, detail=f"No site with id '{site_id}'")
    observations.sort(key=lambda s: s.measured_at or datetime.min)  # noqa: DTZ901 — GLOBE timestamps are naive
    return SiteHistoryResponse(
        site_id=site_id,
        site_name=observations[0].site_name,
        observations=[_summary(s) for s in observations],
    )
