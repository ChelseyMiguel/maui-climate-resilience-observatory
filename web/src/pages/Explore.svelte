<script>
  // Interactive Map Explorer. Every layer is real: the project's own analysis or a
  // verified public source. Nothing is simulated, where data doesn't exist for a
  // year or place, the sidebar says so instead.
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import * as maplibregl from 'maplibre-gl';  // v6 has no default export
  import 'maplibre-gl/dist/maplibre-gl.css';
  // MapLibre parses GeoJSON in a web worker it locates relative to its own file.
  // Once bundled, that guess points at a file that doesn't exist and every GeoJSON
  // layer silently fails to load. Ship the (self-contained) worker as an asset and
  // tell MapLibre where it is.
  import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
  maplibregl.setWorkerUrl(workerUrl);
  import SeriesPanel from '../components/SeriesPanel.svelte';
  import ProfilePanel from '../components/ProfilePanel.svelte';
  import ThresholdHistogram from '../components/ThresholdHistogram.svelte';
  import * as data from '../lib/adapters.ts';
  import { getTerrain } from '../lib/api.js';
  import { reliefDataUrl } from '../lib/relief.ts';
  import { loadChangeRaster, rampColor, renderThreshold, CLASS_COLORS } from '../lib/raster.ts';
  import { imageryIndex, imageryCanvas, loadBands, paint, ndviColour, chmColour, worldcoverColour, WORLDCOVER,
    BBOX_CORNERS, remoteManifest, cellOf, median, NDVI_STOPS, CHM_STOPS, BURN_CLASSES, burnColour, lstColour, LST_STOPS } from '../lib/remote.ts';
  import { histogram, joinMonthly } from '../lib/series.js';
  import { classify, RESEARCH_THRESHOLD } from '../lib/threshold.js';
  import { BASEMAPS, DEM_TILES, basemapById } from '../lib/basemaps.js';
  import { createSampler } from '../lib/terrarium.js';
  import { samplePoints, slopeStats } from '../lib/profile.js';
  import { sampleElevation } from '../lib/geo.js';
  import { analysis } from '../lib/state.js';
  import { toUtm } from '../lib/utm.ts';
  import { drawIcon, iconSvg, KIND_LABEL } from '../lib/icons.ts';

  const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024];
  const DM_COLORS = ['#f2e394', '#f2c46a', '#e8913e', '#c8512f', '#7a1f1f'];
  const DM_LABELS = ['D0 Abnormally dry', 'D1 Moderate', 'D2 Severe', 'D3 Extreme', 'D4 Exceptional'];
  const PERIOD = 'Dry season (May–Sep) 2022 minus dry season 2019';
  const reduceMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const dur = (ms) => (reduceMotion ? 0 : ms);

  let container, containerB, map, mapB;
  // On a phone the layers panel would cover the whole map, so it starts closed
  // there; on wider screens it sits beside the map and starts open.
  let loading = true, error = null, sidebarOpen = typeof window === 'undefined' || window.innerWidth >= 860;

  // Shared with the 3D view and the Analysis workspace.
  const shared = get(analysis);
  let year = shared.year, threshold = shared.threshold, vegIndex = shared.index;
  let seriesFrom = shared.from ?? '', seriesTo = shared.to ?? '';
  $: analysis.update((s) => ({ ...s, year, threshold, index: vegIndex, from: seriesFrom || null, to: seriesTo || null }));

  // Layer switches
  let veg = true, vegPatches = false;
  // 'classes': browning / stable / greening at the threshold; 'below': browned
  // pixels only; 'ramp': the full diverging change as in the study's figures.
  let vegMode = 'classes', thrView = null, thrCanvas = null;
  // County-scale drought polygons wash out the imagery underneath; opt-in.
  let drought = false, community = true;
  let kinds = { fire_stations: true, ems_stations: true, hospitals: true, public_schools: true, private_schools: true };
  let fires = true, firesAllYears = false;
  let regions = true, globe = true, study = false;

  // ---------- Hawaii Statewide GIS layers (scripts/fetch_hawaii_portal.py) ----------
  const MOIST = { Arid: '#8c510a', 'Very Dry': '#bf812d', 'Moderately Dry': '#dfc27d', 'Seasonal Mesic': '#c7eae5',
                  'Moist Mesic': '#80cdc1', 'Moderately Wet': '#35978f', 'Very Wet': '#01665e' };
  const RISK = { High: '#d4442c', Medium: '#ef9a3b', Low: '#f3d250', 'N/A': '#6e767c' };
  const SUGAR = '#c28f2c', PINE = '#7fb069';
  let portal = { fire_risk: false, fire_response: false, moisture_zones: false, rainfall_mm: false, rain_gauges: false, plantation: false };
  let plantYear = '1937', portalInfo = [], portalError = null;
  const portalLoaded = new Set();
  const pinfo = (k) => portalInfo.find((c) => c.id === k);
  async function ensurePortal(key) {
    if (portalLoaded.has(key) || !map) return;
    portalLoaded.add(key);
    try {
      if (!portalInfo.length) portalInfo = await fetch('/api/layers/portal').then((r) => r.json());
      const keys = key === 'plantation' ? ['sugarcane_1900', 'sugarcane_1920', 'sugarcane_1937', 'pineapple_1920', 'pineapple_1937'] : [key];
      for (const k of keys) {
        const res = await fetch(`/api/layers/portal/${k}`);
        if (!res.ok) throw new Error(`${k}: ${res.status}`);
        map.addSource(`portal-${k}`, { type: 'geojson', data: await res.json() });
      }
      const before = 'drought-fill';
      if (key === 'moisture_zones') {
        map.addLayer({ id: 'portal-moisture_zones', type: 'fill', source: 'portal-moisture_zones',
          paint: { 'fill-color': ['match', ['get', 'moisturezone'], ...Object.entries(MOIST).flat(), '#444'], 'fill-opacity': 0.55 } }, before);
      } else if (key === 'fire_risk') {
        map.addLayer({ id: 'portal-fire_risk', type: 'fill', source: 'portal-fire_risk',
          paint: { 'fill-color': ['match', ['get', 'risk_rating'], ...Object.entries(RISK).flat(), '#6e767c'], 'fill-opacity': 0.5 } }, before);
        map.addLayer({ id: 'portal-fire_risk-line', type: 'line', source: 'portal-fire_risk', paint: { 'line-color': '#111', 'line-width': 0.8 } }, before);
      } else if (key === 'fire_response') {
        map.addLayer({ id: 'portal-fire_response', type: 'fill', source: 'portal-fire_response', paint: { 'fill-color': '#f58ab6', 'fill-opacity': 0.12 } }, before);
        map.addLayer({ id: 'portal-fire_response-line', type: 'line', source: 'portal-fire_response',
          paint: { 'line-color': '#f58ab6', 'line-width': 1.4, 'line-dasharray': [4, 2] } }, before);
      } else if (key === 'rainfall_mm') {
        map.addLayer({ id: 'portal-rainfall_mm', type: 'line', source: 'portal-rainfall_mm', paint: { 'line-color': '#6cb6ff', 'line-width': 1.2 } });
        map.addLayer({ id: 'portal-rainfall_mm-label', type: 'symbol', source: 'portal-rainfall_mm',
          layout: { 'symbol-placement': 'line', 'text-field': ['concat', ['to-string', ['get', 'contour']], ' mm'], 'text-size': 11 },
          paint: { 'text-color': '#cfe6ff', 'text-halo-color': '#0b1013', 'text-halo-width': 1.5 } });
      } else if (key === 'rain_gauges') {
        map.addImage('sq-gauge', squareIcon('#6cb6ff', 8), { pixelRatio: 2 });
        map.addLayer({ id: 'portal-rain_gauges', type: 'symbol', source: 'portal-rain_gauges', layout: { 'icon-image': 'sq-gauge', 'icon-allow-overlap': true } });
      } else if (key === 'plantation') {
        for (const [k, col] of [['sugarcane', SUGAR], ['pineapple', PINE]]) {
          for (const y of ['1900', '1920', '1937']) {
            if (!map.getSource(`portal-${k}_${y}`)) continue;
            map.addLayer({ id: `portal-plant-${k}_${y}`, type: 'fill', source: `portal-${k}_${y}`, layout: { visibility: 'none' },
              paint: { 'fill-color': col, 'fill-opacity': 0.55, 'fill-outline-color': '#000' } }, before);
          }
        }
      }
      applyPortal();
    } catch (e) { portalError = e.message; portalLoaded.delete(key); }
  }
  function applyPortal() {
    if (!map) return;
    const vis2 = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
    for (const k of ['moisture_zones', 'fire_risk', 'fire_response', 'rainfall_mm', 'rain_gauges']) {
      vis2(`portal-${k}`, portal[k]); vis2(`portal-${k}-line`, portal[k]); vis2(`portal-${k}-label`, portal[k]);
    }
    for (const k of ['sugarcane', 'pineapple']) for (const y of ['1900', '1920', '1937']) vis2(`portal-plant-${k}_${y}`, portal.plantation && y === plantYear);
  }
  $: if (ready) { for (const k of Object.keys(portal)) if (portal[k]) ensurePortal(k); portal; plantYear; applyPortal(); }

  // Basemap, terrain, 3D
  let basemap = 'relief', basemapError = null, hillshade = true, demError = null;
  let view3d = false, exaggeration = 1.5, pitch = 60;

  // Tools
  let tool = null;               // 'profile' while picking transect ends
  let transect = [], profile = null;
  let compare = false, compareRight = 's2-2022', compareOverlay = 'none', split = 50, compareError = null;
  let dataOpen = false, seriesRows = [], seriesError = null, seriesLoaded = false;
  let cursor = null;             // pointer readout

  // ---------- remote-sensing layers (scripts/remote_sensing/, public AWS archives) ----------
  let rs = { imagery: [], annual: null, regional: null, lidar: null, landcover: null, landsat: null, burn: null, lst: null, island: null, islandInfo: null, manifest: {} };
  let rsLoading = true;
  let imgId = 'none', imgOpacity = 1;
  let annualOn = false, annualYear = 2022, annualIdx = 'ndvi', playing = false, facets = false;
  let regionalOn = false, landcoverOn = false, lidarOn = false, lidarProduct = 'chm', droughtPlaying = false;
  // Whole-island dry-season NDVI/NBR (scripts/remote_sensing/island_annual.py), uint8 codes.
  let islandOn = false, islandYear = 2022, islandIdx = 'ndvi', islandMode = 'value', islandPlaying = false, islandTimer = 0;
  $: islandYears = Object.keys(rs.islandInfo?.years ?? {}).map(Number).sort((a, b) => a - b);
  const dec = (c) => (Number.isFinite(c) ? c / 125 - 1 : NaN);
  function islandBand(idx, y) { const k = islandYears.indexOf(y); return k < 0 ? null : rs.island.bands[(idx === 'ndvi' ? 0 : islandYears.length) + k]; }
  function toggleIslandPlay() {
    islandPlaying = !islandPlaying; clearInterval(islandTimer);
    if (islandPlaying) { islandOn = true; islandTimer = setInterval(() => { islandYear = islandYears[(islandYears.indexOf(islandYear) + 1) % islandYears.length]; }, reduceMotion ? 2500 : 1200); }
  }
  function zoomIsland() { map?.fitBounds([[-156.72, 20.55], [-155.96, 21.04]], { padding: 20, duration: dur(1200) }); }
  let landsatOn = false, landsatYear = 2022, landsatMode = 'z', burnOn = false, lstOn = false, lstYear = 2022;
  $: lstYears = (rs.manifest?.lst ?? []).map((r) => r.year);
  $: burnFires = rs.manifest?.burn_severity?.fires ?? [];
  // Landsat 30 m dry-season NDVI per year (Planetary Computer): years from the
  // manifest, and each pixel's 2000-2018 normal (mean, sample SD).
  $: lsYears = Object.keys(rs.manifest?.landsat?.years ?? {}).map(Number).sort((a, b) => a - b);
  $: lsNormal = rs.landsat && lsYears.length ? (() => {
    const idx = lsYears.map((y, k) => (y >= 2000 && y <= 2018 ? k : -1)).filter((k) => k >= 0);
    const n = rs.landsat.width * rs.landsat.height, mean = new Float32Array(n).fill(NaN), sd = new Float32Array(n).fill(NaN);
    for (let i = 0; i < n; i++) {
      const v = idx.map((k) => rs.landsat.bands[k][i]).filter(Number.isFinite);
      if (v.length < 5) continue;
      const m = v.reduce((a, b) => a + b, 0) / v.length;
      mean[i] = m; sd[i] = Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / (v.length - 1));
    }
    return { mean, sd };
  })() : null;
  const lsZ = (i, k) => (lsNormal && lsNormal.sd[i] > 0 ? (rs.landsat.bands[k][i] - lsNormal.mean[i]) / lsNormal.sd[i] : NaN);
  const rsCanvas = {};
  let playTimer = 0, droughtTimer = 0;
  $: annualYears = rs.annual ? Array.from({ length: rs.annual.bands.length / 3 }, (_, i) => annualFirst + i) : [];
  $: annualFirst = Math.min(...Object.keys(rs.manifest?.sentinel2?.products ?? { aoi_2017: 1 })
    .filter((k) => k.startsWith('aoi_')).map((k) => +k.slice(4)));
  $: yearIdx = annualYears.indexOf(annualYear);
  $: lcRows = rs.manifest?.worldcover?.study_area ?? [];
  $: lidarMeta = rs.manifest?.lidar;

  // Data
  let rasters = {}, catalog = [], droughtIndex = [], observations = [], terrain = null, studyArea = null;
  let fireFeatures = [], droughtCats = [], obsThisYear = 0, firesThisYear = [];
  // GLOBE pins are optional: if they cannot load, every other layer still must.
  let obsError = null;
  let selected = null;           // the feature card
  let ready = false;
  let reliefUrl = null;

  const KINDS = data.INFRA_KINDS;
  const currencyOf = (id) => catalog.find((c) => c.id === id)?.currency ?? 'not stated';
  const sampler = createSampler();
  let samplerDown = false;       // terrain tiles unreachable: use the local grid

  function circle(lat, lon, radiusM, n = 96) {
    const kx = 111320 * Math.cos((lat * Math.PI) / 180);
    const ring = Array.from({ length: n + 1 }, (_, i) => {
      const a = (i / n) * 2 * Math.PI;
      return [lon + (radiusM * Math.cos(a)) / kx, lat + (radiusM * Math.sin(a)) / 111320];
    });
    return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} };
  }
  const fc = (features) => ({ type: 'FeatureCollection', features });
  const point = (lon, lat, props = {}) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: props });

  /** Square point symbol (no round markers anywhere). */
  function squareIcon(fill, size = 12, stroke = '#111') {
    const c = Object.assign(document.createElement('canvas'), { width: size * 2, height: size * 2 });
    const ctx = c.getContext('2d');
    ctx.fillStyle = stroke; ctx.fillRect(0, 0, size * 2, size * 2);
    ctx.fillStyle = fill; ctx.fillRect(3, 3, size * 2 - 6, size * 2 - 6);
    return ctx.getImageData(0, 0, size * 2, size * 2);
  }

  /** Elevation at a point: AWS Terrain Tiles (z14) or, if unreachable, the local grid. */
  async function elevationAt(lon, lat) {
    if (!samplerDown) {
      try { return { z: await sampler.at(lon, lat), source: 'AWS Terrain Tiles z14 (~9 m), bilinear' }; }
      catch { samplerDown = true; }
    }
    const z = sampleElevation(terrain.grid, terrain.meta, lon, lat);
    return { z: z ?? NaN, source: 'local 68 m DEM grid (terrain tiles unreachable)' };
  }

  onMount(async () => {
    try {
      const [t, sa, cat, di, obs, regionsFc, firesFc, patchesFc, dndvi, dnbr, ...infra] = await Promise.all([
        getTerrain(), data.studyArea(), data.infrastructureCatalog(), data.droughtMaps(),
        data.observations().catch((e) => { obsError = e.message; return []; }),
        data.regionsGeoJson(), data.firesGeoJson(), data.browningGeoJson(),
        loadChangeRaster('dndvi'), loadChangeRaster('dnbr'),
        ...KINDS.map((k) => data.infrastructure(k)),
      ]);
      terrain = t; studyArea = sa; catalog = cat; droughtIndex = di; observations = obs;
      rasters = { dndvi, dnbr };
      reliefUrl = reliefDataUrl(terrain);
      buildMap({ regionsFc, firesFc, patchesFc, infra });
    } catch (e) {
      error = e.message;
      loading = false;
    }
  });

  const baseStyle = () => ({ version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#1a1f24' } }] });

  /** Add a basemap's layer to a map (lazily), below `beforeId`. */
  function ensureBasemap(m, id, beforeId) {
    const bm = basemapById(id);
    if (!bm.tiles || m.getLayer(`bm-${id}`)) return;
    m.addSource(`bm-${id}`, { type: 'raster', tiles: bm.tiles, tileSize: 256, maxzoom: bm.maxzoom, attribution: bm.attribution });
    m.addLayer({ id: `bm-${id}`, type: 'raster', source: `bm-${id}`, paint: { 'raster-fade-duration': 0 } }, beforeId);
  }

  function buildMap({ regionsFc, firesFc, patchesFc, infra }) {
    fireFeatures = firesFc.features;
    const b = terrain.meta.bbox;
    map = new maplibregl.Map({
      container, style: baseStyle(), maxPitch: 80,
      bounds: [[b.west, b.south], [b.east, b.north]],
      // All of Maui (the whole-island layer), not just the terrain box.
      maxBounds: [[-156.85, 20.45], [-155.85, 21.15]],
      attributionControl: { compact: true, customAttribution:
        'Relief: AWS Terrain Tiles · Vegetation: author’s Sentinel-2 analysis · Drought: U.S. Drought Monitor · Fires: NIFC · Places & facilities: Hawaiʻi Statewide GIS Program, U.S. Census · Sites: NASA GLOBE' },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 140 }), 'bottom-right');

    map.on('error', (e) => {
      const id = e.sourceId ?? '';
      if (id.startsWith('bm-') && basemap !== 'relief') {
        basemapError = `${basemapById(basemap).label} tiles couldn’t load (${e.error?.status || 'network'}). Showing the offline terrain instead.`;
        basemap = 'relief';
      } else if (id.startsWith('dem') && !demError) {
        demError = 'Terrain tiles (AWS) couldn’t load, so hillshade and 3D are off. Elevation readouts use the local 68 m grid.';
        if (view3d) set3d(false);
      }
    });

    map.on('load', () => {
      const corners = [[b.west, b.north], [b.east, b.north], [b.east, b.south], [b.west, b.south]];
      map.addSource('relief', { type: 'image', url: reliefUrl, coordinates: corners });
      map.addLayer({ id: 'relief', type: 'raster', source: 'relief', paint: { 'raster-resampling': 'linear' } });

      // Hillshade and 3D terrain read separate DEM sources (MapLibre's advice).
      map.addSource('dem-hs', DEM_TILES);
      map.addSource('dem-3d', DEM_TILES);
      map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem-hs',
        paint: { 'hillshade-exaggeration': 0.35, 'hillshade-shadow-color': '#000000', 'hillshade-highlight-color': '#ffffff', 'hillshade-accent-color': '#000000' } });

      map.addSource('drought', { type: 'geojson', data: fc([]) });
      map.addLayer({ id: 'drought-fill', type: 'fill', source: 'drought',
        paint: { 'fill-color': ['match', ['get', 'dm'], 0, DM_COLORS[0], 1, DM_COLORS[1], 2, DM_COLORS[2], 3, DM_COLORS[3], 4, DM_COLORS[4], '#ccc'],
                 'fill-opacity': 0.42 } });
      map.addLayer({ id: 'drought-line', type: 'line', source: 'drought', paint: { 'line-color': '#7a4a18', 'line-width': 0.6, 'line-opacity': 0.6 } });

      for (const id of ['dndvi', 'dnbr']) {
        map.addSource(`raster-${id}`, { type: 'image', url: rasters[id].imageUrl, coordinates: rasters[id].meta.corners });
        map.addLayer({ id: `raster-${id}`, type: 'raster', source: `raster-${id}`, paint: { 'raster-resampling': 'nearest', 'raster-opacity': 0.92 } });
      }
      // The threshold view draws into one canvas that is re-uploaded on change,
      // so dragging the slider never encodes an image.
      thrCanvas = document.createElement('canvas');
      thrView = renderThreshold(rasters[vegIndex], threshold, vegMode === 'below' ? 'below' : 'classes', thrCanvas);
      map.addSource('raster-thr', { type: 'canvas', canvas: thrCanvas, coordinates: rasters[vegIndex].meta.corners, animate: false });
      map.addLayer({ id: 'raster-thr', type: 'raster', source: 'raster-thr', paint: { 'raster-resampling': 'nearest', 'raster-opacity': 0.95 } });
      map.addSource('patches', { type: 'geojson', data: patchesFc });
      map.addLayer({ id: 'patches-line', type: 'line', source: 'patches', paint: { 'line-color': '#ffd08a', 'line-width': 0.8 } });

      map.addSource('study', { type: 'geojson', data: circle(studyArea.lat, studyArea.lon, studyArea.radius_m) });
      map.addLayer({ id: 'study-line', type: 'line', source: 'study', paint: { 'line-color': '#e4e8ea', 'line-width': 1, 'line-dasharray': [4, 3] } });

      map.addSource('regions', { type: 'geojson', data: regionsFc });
      map.addLayer({ id: 'regions-fill', type: 'fill', source: 'regions', paint: { 'fill-color': '#1f6f73', 'fill-opacity': 0.04 } });
      map.addLayer({ id: 'regions-line', type: 'line', source: 'regions', paint: { 'line-color': '#5fb7c2', 'line-width': 2, 'line-dasharray': [1, 1.5] } });
      for (const f of regionsFc.features) {
        const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates[0][0];
        const lon = ring.reduce((s, p) => s + p[0], 0) / ring.length, lat = ring.reduce((s, p) => s + p[1], 0) / ring.length;
        const el = Object.assign(document.createElement('div'), { className: 'region-label', textContent: f.properties.name });
        new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
      }

      map.addSource('fires', { type: 'geojson', data: firesFc });
      map.addLayer({ id: 'fires-fill', type: 'fill', source: 'fires', paint: { 'fill-color': '#b3261e', 'fill-opacity': 0.18 } });
      map.addLayer({ id: 'fires-line', type: 'line', source: 'fires', paint: { 'line-color': '#ff5a4f', 'line-width': 2.2 } });

      map.addImage('sq-globe', squareIcon('#5fb7c2', 11), { pixelRatio: 2 });
      map.addImage('sq-transect', squareIcon('#e07b2c', 9), { pixelRatio: 2 });
      map.addImage('sq-hover', squareIcon('#ffffff', 8, '#e07b2c'), { pixelRatio: 2 });
      map.addSource('globe', { type: 'geojson', data: fc([]) });
      map.addLayer({ id: 'globe-points', type: 'symbol', source: 'globe', layout: { 'icon-image': 'sq-globe', 'icon-allow-overlap': true } });

      for (const k of KINDS) map.addImage(`icon-${k}`, drawIcon(k), { pixelRatio: 2 });
      map.addSource('infra', { type: 'geojson', data: fc(infra.flat().map((f) => point(f.lon, f.lat,
        { kind: f.kind, name: f.name, attrs: JSON.stringify(f.attributes) }))) });
      map.addLayer({ id: 'infra', type: 'symbol', source: 'infra',
        layout: { 'icon-image': ['concat', 'icon-', ['get', 'kind']], 'icon-allow-overlap': true } });

      map.addSource('transect', { type: 'geojson', data: fc([]) });
      map.addLayer({ id: 'transect-line', type: 'line', source: 'transect', filter: ['==', ['geometry-type'], 'LineString'],
        paint: { 'line-color': '#e07b2c', 'line-width': 2.5 } });
      map.addLayer({ id: 'transect-ends', type: 'symbol', source: 'transect', filter: ['==', ['geometry-type'], 'Point'],
        layout: { 'icon-image': ['coalesce', ['get', 'icon'], 'sq-transect'], 'icon-allow-overlap': true, 'text-field': ['get', 'label'],
                  'text-offset': [0, -1.2], 'text-size': 12, 'text-allow-overlap': true },
        paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.5 } });

      const interactive = ['infra', 'globe-points', 'fires-fill', 'drought-fill', 'regions-fill'];
      for (const id of interactive) {
        map.on('mouseenter', id, () => { if (!tool) map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', id, () => { if (!tool) map.getCanvas().style.cursor = ''; });
      }
      map.on('click', onClick);
      map.on('mousemove', onMove);
      map.on('mouseout', () => (cursor = null));
      map.on('pitchend', () => { if (view3d) pitch = Math.round(map.getPitch()); });

      // Start with the credits collapsed (the ⓘ button opens them); MapLibre opens
      // them on wide screens, where they cover a strip of the map.
      const attrib = container.querySelector('.maplibregl-ctrl-attrib');
      attrib?.classList.remove('maplibregl-compact-show');
      attrib?.removeAttribute('open');
      ready = true;
      loading = false;
      applyAll();
      applyBasemap();
      loadRemote();
    });
  }

  // ---------- layer state -> map ----------
  function vis(id, on) {
    if (map?.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
  }

  async function applyYear() {
    if (!ready) return;
    const entry = droughtIndex.find((d) => d.year === year);
    const fcData = entry ? await data.droughtMap(year) : fc([]);
    map.getSource('drought').setData(fcData);
    droughtCats = entry ? entry.categories : [];

    const yearObs = observations.filter((o) => o.date?.startsWith(String(year)));
    obsThisYear = yearObs.length;
    map.getSource('globe').setData(fc(yearObs.map((o) => point(o.lon, o.lat,
      { id: o.landCoverId, label: o.label, site: o.siteName, date: o.date, complete: o.complete }))));
    applyFireFilter();
  }

  function applyFireFilter() {
    if (!ready) return;
    const filter = firesAllYears ? null : ['==', ['get', 'year'], year];
    map.setFilter('fires-fill', filter);
    map.setFilter('fires-line', filter);
    // From the loaded data, not querySourceFeatures: that only sees tiles that
    // have already rendered, so it can wrongly report "no fires" early on.
    firesThisYear = fireFeatures.filter((f) => f.properties.year === year).map((f) => f.properties.name);
  }

  function applyAll() {
    if (!ready) return;
    vis('raster-dndvi', veg && vegMode === 'ramp' && vegIndex === 'dndvi');
    vis('raster-dnbr', veg && vegMode === 'ramp' && vegIndex === 'dnbr');
    vis('raster-thr', veg && vegMode !== 'ramp');
    vis('patches-line', veg && vegPatches);
    vis('drought-fill', drought); vis('drought-line', drought);
    vis('fires-fill', fires); vis('fires-line', fires);
    vis('regions-fill', regions); vis('regions-line', regions);
    for (const el of document.querySelectorAll('.region-label')) el.style.display = regions ? '' : 'none';
    vis('globe-points', globe);
    vis('study-line', study);
    vis('infra', community);
    map.setFilter('infra', ['in', ['get', 'kind'], ['literal', KINDS.filter((k) => kinds[k])]]);
  }

  function applyBasemap() {
    if (!ready) return;
    ensureBasemap(map, basemap, 'relief');
    for (const bm of BASEMAPS) if (bm.tiles) vis(`bm-${bm.id}`, bm.id === basemap);
    vis('relief', basemap === 'relief');
    vis('hillshade', hillshade && !demError);
  }

  $: if (ready) { year; applyYear(); }
  $: if (ready) { firesAllYears; applyFireFilter(); }
  $: if (ready) { basemap; hillshade; demError; applyBasemap(); }
  $: if (ready) { basemap; if (basemap !== 'relief') basemapError = null; }

  // Re-render the threshold canvas at most once per frame while the slider moves.
  let frame = 0;
  function applyThreshold() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      thrView = renderThreshold(rasters[vegIndex], threshold, vegMode === 'below' ? 'below' : 'classes', thrCanvas);
      const src = map.getSource('raster-thr');
      if (!src) return;
      src.setCoordinates(rasters[vegIndex].meta.corners);
      src.play();                       // re-upload the canvas once, then stop
      map.once('render', () => src.pause());
      map.triggerRepaint();
    });
  }
  $: if (ready) { threshold; vegIndex; vegMode; applyThreshold(); }
  $: bins = rasters[vegIndex] ? histogram(rasters[vegIndex].values) : [];
  $: label = vegIndex === 'dndvi' ? 'dNDVI' : 'dNBR';

  $: if (ready) { veg; vegIndex; vegPatches; vegMode; drought; community; kinds; fires; regions; globe; study; applyAll(); }

  // ---------- remote sensing ----------
  async function loadRemote() {
    const safe = (p) => p.catch(() => null);
    const [img, annual, regional, lidar, landcover, manifest, landsat, burn, lst, island, islandInfo] = await Promise.all([
      safe(imageryIndex()), safe(loadBands('s2_aoi_annual')), safe(loadBands('s2_regional_change', ['dndvi', 'dnbr'])),
      safe(loadBands('lidar_aoi', ['dtm_dm', 'chm_cm', 'hillshade'])), safe(loadBands('worldcover_2021', ['class'])), safe(remoteManifest()),
      safe(loadBands('landsat_aoi_annual')), safe(loadBands('s2_burn_severity_2023')), safe(loadBands('landsat_lst_annual')),
      safe(loadBands('island_annual')), safe(fetch('/api/layers/island-info').then((r) => (r.ok ? r.json() : null)))]);
    rs = { imagery: img ?? [], annual, regional, lidar, landcover, landsat, burn, lst, island, islandInfo, manifest: manifest ?? {} };
    if (!map) return;
    // Land cover and regional change sit under the drought polygons; annual NDVI
    // and lidar sit over the study rasters so they can be compared in place.
    const below = { landcover: 'drought-fill', regional: 'drought-fill', annual: 'patches-line', lidar: 'patches-line', landsat: 'patches-line', burn: 'fires-fill', lst: 'patches-line', island: 'drought-fill' };
    for (const key of Object.keys(below)) {
      const b = rs[key];
      if (!b) continue;
      rsCanvas[key] = document.createElement('canvas');
      map.addSource(`rs-${key}`, { type: 'canvas', canvas: rsCanvas[key], coordinates: b.corners, animate: false });
      map.addLayer({ id: `rs-${key}`, type: 'raster', source: `rs-${key}`, layout: { visibility: 'none' },
        paint: { 'raster-resampling': 'nearest', 'raster-opacity': key === 'landcover' ? 0.75 : key === 'island' ? 1 : 0.92 } }, below[key]);
    }
    rsLoading = false;
    paintRemote();
    applyRemote();
  }

  function repaint(key) {
    const src = map.getSource(`rs-${key}`);
    if (!src) return;
    src.play();
    map.once('render', () => src.pause());
    map.triggerRepaint();
  }
  const rgba = (c, a = 235) => [...c, a];
  function paintRemote() {
    if (!map || rsLoading) return;
    const n = annualYears.length;
    if (rs.annual && yearIdx >= 0) {
      paint(rs.annual.bands[(annualIdx === 'ndvi' ? 0 : n) + yearIdx], rs.annual.width, rs.annual.height,
        (v) => rgba(ndviColour(v)), rsCanvas.annual);
      repaint('annual');
    }
    if (rs.regional) {
      paint(rs.regional.bands[vegIndex === 'dndvi' ? 0 : 1], rs.regional.width, rs.regional.height, (v) => rgba(rampColor(v), 225), rsCanvas.regional);
      repaint('regional');
    }
    if (rs.landsat && lsYears.includes(landsatYear)) {
      const k = lsYears.indexOf(landsatYear), b = rs.landsat.bands[k];
      if (landsatMode === 'z') {
        const z = Float32Array.from(b, (_, i) => lsZ(i, k));
        // z of -3..+3 on the vegetation-change ramp (brown = below normal).
        paint(z, rs.landsat.width, rs.landsat.height, (v) => rgba(rampColor((Math.max(-3, Math.min(3, v)) / 3) * 0.4), 235), rsCanvas.landsat);
      } else paint(b, rs.landsat.width, rs.landsat.height, (v) => rgba(ndviColour(v)), rsCanvas.landsat);
      repaint('landsat');
    }
    if (rs.island && islandYears.length) {
      const now = islandBand(islandIdx, islandYear), base = islandBand(islandIdx, 2019);
      if (islandMode === 'change' && base) {
        const d = Float32Array.from(now, (c, i) => dec(c) - dec(base[i]));
        paint(d, rs.island.width, rs.island.height, (v) => rgba(rampColor(v), 255), rsCanvas.island);
      } else paint(now, rs.island.width, rs.island.height, (c) => rgba(ndviColour(dec(c)), 255), rsCanvas.island);
      repaint('island');
    }
    if (rs.burn) {
      paint(rs.burn.bands[0], rs.burn.width, rs.burn.height, burnColour, rsCanvas.burn);
      clipToFires(rsCanvas.burn, rs.burn);
      repaint('burn');
    }
    if (rs.lst && lstYears.includes(lstYear)) {
      paint(rs.lst.bands[lstYears.indexOf(lstYear)], rs.lst.width, rs.lst.height, (v) => rgba(lstColour(v)), rsCanvas.lst);
      repaint('lst');
    }
    if (rs.landcover) { paint(rs.landcover.bands[0], rs.landcover.width, rs.landcover.height, worldcoverColour, rsCanvas.landcover); repaint('landcover'); }
    if (rs.lidar) {
      const l = rs.lidar;
      if (lidarProduct === 'chm') paint(l.bands[1], l.width, l.height, (v) => rgba(chmColour(v / 100), 230), rsCanvas.lidar);
      else paint(l.bands[2], l.width, l.height, (v) => [v, v, v, 255], rsCanvas.lidar);
      repaint('lidar');
    }
  }
  /** Keep burn severity only inside the 2023 fire perimeters: outside them dNBR
   * mostly reflects seasonal drying, not fire. */
  function clipToFires(canvas, b) {
    const ctx = canvas.getContext('2d');
    const [w, s0, e, n] = b.bounds;
    const px = (lon, lat) => { const [x, y] = toUtm(lat, lon, 4); return [((x - w) / (e - w)) * b.width, ((n - y) / (n - s0)) * b.height]; };
    ctx.globalCompositeOperation = 'destination-in';
    ctx.beginPath();
    for (const f of fireFeatures.filter((f) => f.properties.year === 2023)) {
      const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const rings of polys) for (const ring of rings) ring.forEach(([lon, lat], i) => { const [x, y] = px(lon, lat); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    }
    ctx.fillStyle = '#000';
    ctx.fill('evenodd');
    ctx.globalCompositeOperation = 'source-over';
  }

  function applyRemote() {
    if (!ready || rsLoading) return;
    vis('rs-annual', annualOn); vis('rs-landsat', landsatOn); vis('rs-burn', burnOn); vis('rs-island', islandOn); vis('rs-lst', lstOn); vis('rs-regional', regionalOn); vis('rs-landcover', landcoverOn); vis('rs-lidar', lidarOn);
    // Satellite image (period-matched Sentinel-2 composites), under the hillshade.
    const item = rs.imagery.find((i) => i.id === imgId);
    if (!item) { vis('rs-img', false); return; }
    setImage(map, item, 'hillshade', imgOpacity);
  }
  async function setImage(m, item, beforeId, opacity = 1) {
    const url = item.format === 'jpg' ? `/api/layers/imagery/${item.id}` : (await imageryCanvas(item)).toDataURL('image/jpeg', 0.9);
    const src = m.getSource('rs-img');
    if (src) src.updateImage({ url, coordinates: BBOX_CORNERS });
    else {
      m.addSource('rs-img', { type: 'image', url, coordinates: BBOX_CORNERS });
      m.addLayer({ id: 'rs-img', type: 'raster', source: 'rs-img', paint: { 'raster-fade-duration': 0 } }, m.getLayer(beforeId) ? beforeId : undefined);
    }
    m.setLayoutProperty('rs-img', 'visibility', 'visible');
    m.setPaintProperty('rs-img', 'raster-opacity', opacity);
  }
  $: if (ready) { annualYear; annualIdx; vegIndex; lidarProduct; landsatYear; landsatMode; lsNormal; lstYear; islandYear; islandIdx; islandMode; rs; paintRemote(); }
  $: if (ready) { annualOn; regionalOn; landcoverOn; lidarOn; landsatOn; burnOn; lstOn; islandOn; imgId; imgOpacity; rs; applyRemote(); }

  function togglePlay() {
    playing = !playing;
    clearInterval(playTimer);
    if (playing) {
      annualOn = true;
      playTimer = setInterval(() => { annualYear = annualYears[(annualYears.indexOf(annualYear) + 1) % annualYears.length]; }, reduceMotion ? 2500 : 1200);
    }
  }
  function toggleDroughtPlay() {
    droughtPlaying = !droughtPlaying;
    clearInterval(droughtTimer);
    if (droughtPlaying) droughtTimer = setInterval(() => { year = YEARS[(YEARS.indexOf(year) + 1) % YEARS.length]; }, reduceMotion ? 2500 : 1500);
  }
  /** Small-multiples facet: paint one year's annual NDVI into a canvas. */
  function facet(node, y) {
    const draw = (yy) => {
      const k = annualYears.indexOf(yy);
      if (k >= 0) paint(rs.annual.bands[(annualIdx === 'ndvi' ? 0 : annualYears.length) + k], rs.annual.width, rs.annual.height, (v) => rgba(ndviColour(v), 255), node);
    };
    draw(y);
    return { update: draw };
  }

  /** Values of every remote-sensing product at a point, for the feature card. */
  function remoteAt(lat, lon) {
    const out = {};
    if (rs.annual) {
      const c = cellOf(rs.annual, lat, lon), n = annualYears.length;
      if (c) out.series = annualYears.map((y, k) => ({ year: y, ndvi: rs.annual.bands[k][c.i], nbr: rs.annual.bands[n + k][c.i], obs: rs.annual.bands[2 * n + k][c.i] }))
        .filter((p) => Number.isFinite(p.ndvi));
    }
    if (rs.landsat && lsNormal) {
      const c = cellOf(rs.landsat, lat, lon), k = lsYears.indexOf(2022);
      if (c && k >= 0 && Number.isFinite(lsZ(c.i, k))) out.landsat = { z2022: lsZ(c.i, k), ndvi2022: rs.landsat.bands[k][c.i], normal: lsNormal.mean[c.i] };
    }
    if (rs.island && islandYears.length) {
      const c = cellOf(rs.island, lat, lon);
      if (c) {
        const series = islandYears.map((y) => ({ year: y, ndvi: dec(islandBand('ndvi', y)[c.i]) }));
        if (series.some((p) => Number.isFinite(p.ndvi))) out.island = { series: series.filter((p) => Number.isFinite(p.ndvi)) };
      }
    }
    if (rs.burn) {
      const c = cellOf(rs.burn, lat, lon), v = c ? rs.burn.bands[0][c.i] : NaN;
      if (Number.isFinite(v)) out.burn = { dnbr: v, cls: BURN_CLASSES.find(([lo, hi]) => v >= lo && v < hi)?.[2] ?? 'Unburned / regrowth' };
    }
    if (rs.lst) {
      const c = cellOf(rs.lst, lat, lon), k = lstYears.indexOf(2022);
      if (c && k >= 0 && Number.isFinite(rs.lst.bands[k][c.i])) out.lst2022 = rs.lst.bands[k][c.i];
    }
    if (rs.landcover) {
      const c = cellOf(rs.landcover, lat, lon);
      const code = c ? rs.landcover.bands[0][c.i] : NaN;
      if (WORLDCOVER[code]) out.landcover = WORLDCOVER[code][0];
    }
    if (rs.lidar) {
      const c = cellOf(rs.lidar, lat, lon);
      if (c && Number.isFinite(rs.lidar.bands[0][c.i])) out.lidar = { ground: rs.lidar.bands[0][c.i] / 10, chm: rs.lidar.bands[1][c.i] / 100 };
    }
    if (rs.regional) {
      const c = cellOf(rs.regional, lat, lon);
      if (c && Number.isFinite(rs.regional.bands[0][c.i])) out.regional = { dndvi: rs.regional.bands[0][c.i], dnbr: rs.regional.bands[1][c.i] };
    }
    return out;
  }
  const spark = (series) => {
    const W = 220, H = 46, x = (i) => 6 + (i / Math.max(1, series.length - 1)) * (W - 12), y = (v) => H - 6 - (Math.max(0, Math.min(0.8, v)) / 0.8) * (H - 12);
    return { W, H, x, y, d: series.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.ndvi).toFixed(1)}`).join('') };
  };

  // ---------- inset locator ----------
  const INSET = { west: -156.72, south: 20.55, east: -155.95, north: 21.05, w: 154, h: 100 };
  const ix = (lon) => ((lon - INSET.west) / (INSET.east - INSET.west)) * INSET.w;
  const iy = (lat) => ((INSET.north - lat) / (INSET.north - INSET.south)) * INSET.h;
  let viewBox = null;
  $: if (ready) map.on('move', () => { const b = map.getBounds(); viewBox = { w: b.getWest(), s: b.getSouth(), e: b.getEast(), n: b.getNorth() }; });

  // ---------- 2D / 3D ----------
  function set3d(on) {
    if (on && demError) return;
    view3d = on;
    if (on) {
      map.setTerrain({ source: 'dem-3d', exaggeration });
      map.easeTo({ pitch, duration: dur(1200) });
    } else {
      map.easeTo({ pitch: 0, bearing: 0, duration: dur(900) });
      map.once('moveend', () => { if (!view3d) map.setTerrain(null); });
    }
    mapB?.setTerrain(on ? { source: 'dem-3d', exaggeration } : null);
  }
  function setExaggeration() {
    if (!view3d) return;
    map.setTerrain({ source: 'dem-3d', exaggeration });
    mapB?.setTerrain({ source: 'dem-3d', exaggeration });
  }
  const setPitch = () => map.easeTo({ pitch, duration: dur(300) });

  // ---------- pointer readout ----------
  let moveFrame = 0, lastMove = null;
  function onMove(e) {
    lastMove = e.lngLat;
    cancelAnimationFrame(moveFrame);
    moveFrame = requestAnimationFrame(async () => {
      const { lng, lat } = lastMove;
      const cell = rasters[vegIndex].cellAt(lat, lng);
      const here = { lat, lon: lng, v: veg ? cell?.value ?? null : null, z: null };
      cursor = here;
      const { z } = await elevationAt(lng, lat);
      if (cursor === here) cursor = { ...here, z };
    });
  }

  // ---------- transect profile ----------
  function startProfile() {
    tool = tool === 'profile' ? null : 'profile';
    if (tool) { transect = []; profile = null; map.getSource('transect').setData(fc([])); }
    map.getCanvas().style.cursor = tool ? 'crosshair' : '';
  }
  function drawTransect(hover = null) {
    const feats = transect.map((p, i) => point(p[0], p[1], { label: i ? 'B' : 'A' }));
    if (transect.length === 2) feats.unshift({ type: 'Feature', geometry: { type: 'LineString', coordinates: transect }, properties: {} });
    if (hover) feats.push(point(hover.lon, hover.lat, { icon: 'sq-hover', label: '' }));
    map.getSource('transect').setData(fc(feats));
  }
  async function computeProfile() {
    const pts = samplePoints(transect[0], transect[1], 240).map((p) => {
      const c = rasters[vegIndex].cellAt(p.lat, p.lon);
      return { ...p, z: NaN, v: c ? c.value : null };
    });
    profile = { points: pts, loading: true };
    let source = '', err = null;
    const zs = await Promise.all(pts.map((p) => elevationAt(p.lon, p.lat)));
    zs.forEach((r, i) => { pts[i].z = r.z; source = r.source; });
    if (samplerDown) err = 'Terrain tiles were unreachable; elevations come from the coarser local grid.';
    profile = { points: pts, stats: slopeStats(pts), source, loading: false, error: err };
  }

  // ---------- compare (swipe) ----------
  function closeCompare() {
    if (mapB) { map.off('move', syncB); mapB.remove(); mapB = null; }
  }
  const syncB = () => mapB?.jumpTo({ center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() });
  function openCompare() {
    closeCompare();
    compareError = null;
    const b = terrain.meta.bbox;
    mapB = new maplibregl.Map({ container: containerB, style: baseStyle(), interactive: false, attributionControl: false, maxPitch: 80,
      center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() });
    mapB.on('error', (e) => { if ((e.sourceId ?? '').startsWith('bm-')) compareError = `${basemapById(compareRight).label} tiles couldn’t load.`; });
    mapB.on('load', () => {
      const corners = [[b.west, b.north], [b.east, b.north], [b.east, b.south], [b.west, b.south]];
      mapB.addSource('relief', { type: 'image', url: reliefUrl, coordinates: corners });
      mapB.addLayer({ id: 'relief', type: 'raster', source: 'relief' });
      mapB.addSource('dem-3d', DEM_TILES);
      if (hillshade && !demError) {
        mapB.addSource('dem-hs', DEM_TILES);
        mapB.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem-hs',
          paint: { 'hillshade-exaggeration': 0.35, 'hillshade-shadow-color': '#000000', 'hillshade-highlight-color': '#ffffff', 'hillshade-accent-color': '#000000' } });
      }
      if (compareRight.startsWith('img:')) {
        const item = rs.imagery.find((i) => i.id === compareRight.slice(4));
        if (item) setImage(mapB, item, 'hillshade');
      } else if (compareRight !== 'relief') ensureBasemap(mapB, compareRight, mapB.getLayer('hillshade') ? 'hillshade' : undefined);
      if (compareOverlay !== 'none') {
        const r = rasters[compareOverlay];
        mapB.addSource('ov', { type: 'image', url: r.imageUrl, coordinates: r.meta.corners });
        mapB.addLayer({ id: 'ov', type: 'raster', source: 'ov', paint: { 'raster-resampling': 'nearest', 'raster-opacity': 0.92 } });
      }
      mapB.addSource('study', { type: 'geojson', data: circle(studyArea.lat, studyArea.lon, studyArea.radius_m) });
      mapB.addLayer({ id: 'study-line', type: 'line', source: 'study', paint: { 'line-color': '#e4e8ea', 'line-width': 2, 'line-dasharray': [3, 2] } });
      if (view3d) mapB.setTerrain({ source: 'dem-3d', exaggeration });
      syncB();
    });
    map.on('move', syncB);
  }
  $: if (ready && compare) { compareRight; compareOverlay; setTimeout(openCompare, 0); }
  $: if (ready && !compare) closeCompare();
  function preset(kind) {
    compare = true;
    if (kind === 's2') { basemap = 'relief'; imgId = 's2_dry_2019'; compareRight = 'img:s2_dry_2022'; compareOverlay = 'none'; veg = false; }
    else if (kind === 'fire') { basemap = 'relief'; imgId = 'before_2023'; compareRight = 'img:after_2023'; compareOverlay = 'none'; veg = false; fires = true; }
    else { basemap = 'relief'; veg = true; vegMode = 'ramp'; vegIndex = 'dndvi'; compareRight = 'relief'; compareOverlay = 'dnbr'; }
  }
  let dragging = false, wrapEl;
  function dragSplit(e) {
    if (!dragging) return;
    const r = wrapEl.getBoundingClientRect();
    split = Math.max(5, Math.min(95, ((e.clientX - r.left) / r.width) * 100));
  }
  function splitKey(e) {
    if (e.key === 'ArrowLeft') split = Math.max(5, split - 5);
    else if (e.key === 'ArrowRight') split = Math.min(95, split + 5);
  }
  $: imgLabel = (id) => rs.imagery.find((i) => i.id === id)?.label ?? id;
  $: leftLabel = `${imgId !== 'none' ? `Sentinel-2 · ${imgLabel(imgId)}` : basemapById(basemap).label}${veg ? ` + ${vegMode === 'ramp' ? label : `${label} < ${threshold.toFixed(2)}`}` : ''}`;
  $: rightLabel = `${compareRight.startsWith('img:') ? `Sentinel-2 · ${imgLabel(compareRight.slice(4))}` : basemapById(compareRight).label}${compareOverlay !== 'none' ? ` + ${compareOverlay === 'dndvi' ? 'dNDVI' : 'dNBR'}` : ''}`;

  // ---------- data panel ----------
  async function openData() {
    dataOpen = !dataOpen;
    if (!dataOpen || seriesLoaded) return;
    seriesLoaded = true;
    try {
      const [dg, rain, weeks] = await Promise.all([
        data.droughtGreenness().catch(() => null), data.rainfall().catch(() => null), data.droughtWeeks(),
      ]);
      seriesRows = joinMonthly({
        ndvi: dg?.indices?.ndvi?.points ?? [], nbr: dg?.indices?.nbr?.points ?? [],
        weeks, rain: rain?.monthly ?? [],
      });
    } catch (e) { seriesError = e.message; seriesLoaded = false; }
  }
  $: if (map && ready) { dataOpen; profile; tool; setTimeout(() => { map.resize(); mapB?.resize(); }, 0); }

  // ---------- feature card ----------
  async function onClick(e) {
    const { lng, lat } = e.lngLat;
    if (tool === 'profile') {
      transect = transect.length === 2 ? [[lng, lat]] : [...transect, [lng, lat]];
      drawTransect();
      if (transect.length === 2) { tool = null; map.getCanvas().style.cursor = ''; computeProfile(); }
      return;
    }
    const order = ['infra', 'globe-points', 'fires-fill', 'drought-fill', 'regions-fill'].filter((id) => map.getLayer(id)
      && map.getLayoutProperty(id, 'visibility') !== 'none');
    const hits = map.queryRenderedFeatures(e.point, { layers: order });
    const pick = (id) => hits.find((h) => h.layer.id === id);
    const cell = veg ? rasters[vegIndex].cellAt(lat, lng) : null;

    const card = { lat, lon: lng, rows: [], raster: null, links: [], elevation: null };
    if (cell) card.raster = { index: label, value: cell.value, row: cell.row, col: cell.col, cls: classify(cell.value, threshold) };
    let f;
    if ((f = pick('infra'))) {
      const a = JSON.parse(f.properties.attrs || '{}');
      card.title = f.properties.name; card.kind = KIND_LABEL[f.properties.kind];
      const keep = ['address', 'city', 'grades', 'grade_from', 'grade_to', 'status', 'facilitytype_name', 'aff', 'complex'];
      card.rows = keep.filter((k) => a[k] && a[k] !== 'None').map((k) => [k.replace(/_/g, ' '), a[k]]);
      card.period = `Layer currency: ${currencyOf(f.properties.kind)}`;
      card.uncertainty = 'Location only. Says nothing about whether it is open, staffed, or in use as a shelter.';
      card.source = 'Hawaiʻi Statewide GIS Program';
    } else if ((f = pick('globe-points'))) {
      card.title = f.properties.label; card.kind = 'GLOBE Observer land cover site';
      card.rows = [['site', f.properties.site], ['observed', f.properties.date], ['photos', f.properties.complete ? 'all six' : 'incomplete']];
      card.period = `Observed ${f.properties.date}`;
      card.uncertainty = 'Citizen-science GPS; recorded accuracy for Upcountry sites ranges from 3 m to over 1 km.';
      card.source = 'NASA GLOBE Observer';
      card.links = [{ href: `/viewer?obs=${encodeURIComponent(f.properties.id)}`, label: 'Open the 360° site view' }];
    } else if ((f = pick('fires-fill'))) {
      card.title = `${f.properties.name} fire`; card.kind = 'Wildfire perimeter';
      card.rows = [['year', f.properties.year], ['discovered', f.properties.discovered ? `${f.properties.discovered} (Hawaiʻi time)` : 'not given'],
                   ['area', f.properties.acres ? `${Math.round(f.properties.acres).toLocaleString()} acres` : 'n/a']];
      card.period = `${f.properties.year} incident`;
      card.uncertainty = 'Final mapped perimeter: shows where fire burned, not how it spread or what started it.';
      card.source = 'National Interagency Fire Center';
    } else if ((f = pick('drought-fill'))) {
      const entry = droughtIndex.find((d) => d.year === year);
      card.title = DM_LABELS[f.properties.dm] ?? f.properties.label; card.kind = 'U.S. Drought Monitor category';
      card.rows = [['map week', entry?.week]];
      card.period = `Week of ${entry?.week} (nearest 8 August ${year})`;
      card.uncertainty = 'A broad-scale expert assessment blending many indicators, not a field measurement for this spot.';
      card.source = 'U.S. Drought Monitor (NDMC, USDA, NOAA)';
    } else if ((f = pick('regions-fill'))) {
      card.title = f.properties.name; card.kind = '2020 Census Designated Place';
      card.rows = [['land area', `${f.properties.land_km2} km²`], ['GEOID', f.properties.geoid]];
      card.period = '2020 Census';
      card.uncertainty = 'A statistical area, not a legal town boundary.';
      card.source = 'U.S. Census Bureau via Hawaiʻi Statewide GIS Program';
      card.links = [{ href: '/insights', label: 'See region insights' }];
    } else if (!card.raster) {
      card.title = 'No mapped feature here';
      card.kind = 'Turn on more layers, or click a symbol or shaded area.';
    }
    if (card.raster && !card.title) {
      card.title = `${label} pixel`; card.kind = 'Author’s Sentinel-2 change raster (10 m, EPSG:32604)';
      card.period = PERIOD;
      card.uncertainty = 'One 10 m pixel; cloud-masked dry-season medians. Greenness/moisture change is not fuel load or fire risk.';
      card.source = 'Author’s analysis (Copernicus Sentinel-2)';
    }
    card.rs = remoteAt(lat, lng);
    card.portal = portalAt(e.point);
    selected = card;
    if (window.innerWidth < 860) sidebarOpen = true;
    const el = await elevationAt(lng, lat);
    if (selected === card) selected = { ...card, elevation: el };
  }

  /** What the Hawaii state layers say at a click: one entry per visible layer. */
  function portalAt(point) {
    const layers = ['portal-fire_risk', 'portal-fire_response', 'portal-moisture_zones', 'portal-rain_gauges',
      ...['sugarcane', 'pineapple'].flatMap((k) => ['1900', '1920', '1937'].map((y) => `portal-plant-${k}_${y}`))].filter((id) => map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none');
    if (!layers.length) return [];
    const out = [];
    const seen = new Set();
    for (const f of map.queryRenderedFeatures(point, { layers })) {
      const p = f.properties, id = f.layer.id;
      let row;
      if (id === 'portal-fire_risk') row = ['DLNR fire risk', `${p.risk_rating} · ${p.commu_name} (2007 rating; boundaries reconfirmed 2017, 2022; populated areas only)`];
      else if (id === 'portal-fire_response') row = ['Fire response', p.description];
      else if (id === 'portal-moisture_zones') row = ['Moisture zone', `${p.moisturezone} (model of climate zones)`];
      else if (id === 'portal-rain_gauges') row = ['Rain gauge', `${p.name}: ${Math.round(p.annavgmm)} mm/yr mean at ${p.elevm} m · ${p.nummoswith} months of data (Rainfall Atlas, 1978–2007 base)`];
      else row = [id.includes('sugarcane') ? 'Former sugarcane land' : 'Former pineapple land', `in production ${id.slice(-4)} (digitised historical maps)`];
      if (!seen.has(row[0] + row[1])) { seen.add(row[0] + row[1]); out.push(row); }
    }
    return out;
  }

  function focusStudyArea() {
    map?.flyTo({ center: [studyArea.lon, studyArea.lat], zoom: 13.6, duration: dur(1200) });
  }

  onDestroy(() => { clearInterval(playTimer); clearInterval(islandTimer); clearInterval(droughtTimer); closeCompare(); map?.remove(); });

  const swatch = (v) => `rgb(${rampColor(v).join(',')})`;
  const rgb = (c) => `rgb(${c.join(',')})`;
  $: pct = (n) => (thrView?.valid ? ((n / thrView.valid) * 100).toFixed(1) : '0.0');
  $: ha = (n) => ((n * 100) / 10000).toFixed(1);
  $: activeBasemap = basemapById(basemap);
</script>

<svelte:window on:pointermove={dragSplit} on:pointerup={() => (dragging = false)} />

<div class="explore">
  <button class="toggle" aria-expanded={sidebarOpen} aria-controls="layers" on:click={() => (sidebarOpen = !sidebarOpen)}>
    {sidebarOpen ? 'Hide layers' : 'Layers & legend'}
  </button>

  <aside id="layers" class:open={sidebarOpen} aria-label="Map layers and legend">
    <h1>Map Explorer</h1>

    <fieldset class="year">
      <legend>Year</legend>
      <div class="years" role="radiogroup" aria-label="Year">
        {#each YEARS as y}
          <label class:on={y === year}><input type="radio" bind:group={year} value={y} />{y}</label>
        {/each}
      </div>
      <button class="play" aria-pressed={droughtPlaying} on:click={toggleDroughtPlay}>{droughtPlaying ? '❚❚ Pause' : '▶ Animate years'}</button>
      <p class="hint">Sets the drought map, fire perimeters and GLOBE observations. The vegetation layer is a fixed 2019 → 2022 comparison.</p>
    </fieldset>

    <fieldset>
      <legend>Basemap</legend>
      <div class="sub">
        <select bind:value={basemap} aria-label="Basemap">
          {#each BASEMAPS as bm}<option value={bm.id}>{bm.label}</option>{/each}
        </select>
        <p class="hint"><b>{activeBasemap.kind}.</b> {activeBasemap.note}</p>
        {#if basemapError}<p class="empty">{basemapError}</p>{/if}
        <label><input type="checkbox" bind:checked={hillshade} disabled={!!demError} /> Hillshade (AWS Terrain Tiles)</label>
        {#if demError}<p class="empty">{demError}</p>{/if}
      </div>
    </fieldset>

    <fieldset>
      <legend>Satellite &amp; lidar</legend>
      <div class="sub">
        {#if rsLoading}<p class="hint">Loading Sentinel-2, lidar and land-cover products…</p>{/if}
        <label class="lyr"><input type="checkbox" bind:checked={islandOn} disabled={!rs.island} /> Whole island: dry-season {islandIdx.toUpperCase()} (60 m)</label>
        {#if rs.island}
          <div class="sub2" class:dim={!islandOn}>
            <div class="row">
              <button class="play" aria-pressed={islandPlaying} on:click={toggleIslandPlay}>{islandPlaying ? '❚❚' : '▶'}</button>
              <input type="range" min={islandYears[0]} max={islandYears[islandYears.length - 1]} step="1" bind:value={islandYear} aria-label="Island year" />
              <b class="num">{islandYear}</b>
            </div>
            <div class="row">
              <select bind:value={islandIdx} aria-label="Island index"><option value="ndvi">NDVI</option><option value="nbr">NBR</option></select>
              <select bind:value={islandMode} aria-label="Island display"><option value="value">value</option><option value="change">change since 2019</option></select>
              <button class="play" on:click={zoomIsland}>Zoom to all Maui</button>
            </div>
            {#if islandMode === 'change'}
              <div class="ramp" aria-hidden="true">{#each [-0.4, -0.2, -0.1, 0, 0.1, 0.2, 0.4] as v}<span style="background:{swatch(v)}"></span>{/each}</div>
              <div class="ramp-labels"><span>−0.4 browner</span><span>no change</span><span>+0.4 greener</span></div>
            {:else}
              <div class="ramp" aria-hidden="true">{#each NDVI_STOPS as [, c]}<span style="background:rgb({c.join(',')})"></span>{/each}</div>
              <div class="ramp-labels"><span>0 bare / dry</span><span>0.4</span><span>0.8 green</span></div>
            {/if}
            {#if rs.islandInfo?.years?.[islandYear]}
              {@const yi = rs.islandInfo.years[islandYear]}
              <p class="hint">Island median {islandIdx.toUpperCase()} <b class="num">{yi[islandIdx]?.median?.toFixed(3)}</b> from {yi.scenes} satellite scenes. Blank spots were cloudy all season.</p>
            {/if}
          </div>
        {/if}

        <label class="col">Sentinel-2 image
          <select bind:value={imgId} aria-label="Sentinel-2 image">
            <option value="none">none</option>
            {#each rs.imagery as im}<option value={im.id}>{im.label}</option>{/each}
          </select></label>
        {#if imgId !== 'none'}
          {@const im = rs.imagery.find((i) => i.id === imgId)}
          <label>Opacity <input type="range" min="0.2" max="1" step="0.05" bind:value={imgOpacity} /></label>
          {#if im}<p class="hint">{im.period}, from {im.scenes ?? '?'} satellite scenes.</p>{/if}
        {:else if !rsLoading && !rs.imagery.length}
          <p class="empty">No imagery yet. Run <code>scripts/remote_sensing/sentinel2_composites.py</code>.</p>
        {/if}

        <label class="lyr"><input type="checkbox" bind:checked={annualOn} disabled={!rs.annual} /> Annual dry-season {annualIdx.toUpperCase()}, study area</label>
        {#if rs.annual}
          <div class="sub2" class:dim={!annualOn}>
            <div class="row">
              <button class="play" aria-pressed={playing} on:click={togglePlay}>{playing ? '❚❚' : '▶'}</button>
              <input type="range" min={annualYears[0]} max={annualYears[annualYears.length - 1]} step="1" bind:value={annualYear} aria-label="Year" />
              <b class="num">{annualYear}</b>
              <select bind:value={annualIdx} aria-label="Index"><option value="ndvi">NDVI</option><option value="nbr">NBR</option></select>
            </div>
            <div class="ramp" aria-hidden="true">{#each NDVI_STOPS as [v, c]}<span style="background:rgb({c.join(',')})"></span>{/each}</div>
            <div class="ramp-labels"><span>0 bare / dry</span><span>0.4</span><span>0.8 green</span></div>
            <button class="linkish" on:click={() => (facets = !facets)}>{facets ? 'Hide' : 'Show'} all years side by side</button>
          </div>
        {/if}

        <label class="lyr"><input type="checkbox" bind:checked={landsatOn} disabled={!rs.landsat} /> Landsat {lsYears[0] ?? 2000}–{lsYears[lsYears.length - 1] ?? 2025}, study area (30 m)</label>
        {#if rs.landsat}
          <div class="sub2" class:dim={!landsatOn}>
            <div class="row">
              <input type="range" min={lsYears[0]} max={lsYears[lsYears.length - 1]} step="1" bind:value={landsatYear} aria-label="Landsat year" />
              <b class="num">{landsatYear}</b>
              <select bind:value={landsatMode} aria-label="Landsat display"><option value="z">vs normal</option><option value="ndvi">NDVI</option></select>
            </div>
            {#if landsatMode === 'z'}
              <div class="ramp" aria-hidden="true">{#each [-3, -2, -1, 0, 1, 2, 3] as z}<span style="background:{swatch((z / 3) * 0.4)}"></span>{/each}</div>
              <div class="ramp-labels"><span>−3 SD drier</span><span>normal</span><span>+3 SD greener</span></div>
            {/if}
            <p class="hint">USGS Landsat, 2000 to 2025. “vs normal” compares each spot with its own dry seasons from 2000 to 2018.</p>
          </div>
        {/if}

        <label class="lyr"><input type="checkbox" bind:checked={burnOn} disabled={!rs.burn} /> Burn severity, Aug 2023 fires (dNBR, 20 m)</label>
        {#if burnOn}
          <div class="sub2">
            <ul class="key">{#each BURN_CLASSES as [lo, hi, name, col]}<li><span class="sw" style="background:{col}"></span>{name} <span class="muted">({lo.toFixed(2)}{hi < 9 ? `–${hi.toFixed(2)}` : '+'})</span></li>{/each}</ul>
            {#if burnFires.length}
              <table class="classes"><thead><tr><th>Fire</th><th>ha</th><th>mod.+ ha</th></tr></thead>
                <tbody>{#each burnFires as f}<tr><td>{f.name}</td><td>{f.area_ha}</td><td>{(f.class_ha['Moderate-low'] + f.class_ha['Moderate-high'] + f.class_ha.High).toFixed(0)}</td></tr>{/each}</tbody></table>
            {/if}
            <p class="hint">How hard each spot burned in August 2023, from satellite images before and after. A rough guide on grass, not checked on the ground.</p>
          </div>
        {/if}

        <label class="lyr"><input type="checkbox" bind:checked={lstOn} disabled={!rs.lst} /> Surface temperature, study area (Landsat 8/9, 30 m)</label>
        {#if rs.lst}
          <div class="sub2" class:dim={!lstOn}>
            <div class="row"><input type="range" min={lstYears[0]} max={lstYears[lstYears.length - 1]} step="1" bind:value={lstYear} aria-label="Temperature year" />
              <b class="num">{lstYear}</b> <span class="num muted">{rs.manifest?.lst?.find((r) => r.year === lstYear)?.lst_c?.toFixed(1)} °C</span></div>
            <div class="ramp" aria-hidden="true">{#each LST_STOPS as [, c]}<span style="background:rgb({c.join(',')})"></span>{/each}</div>
            <div class="ramp-labels"><span>25 °C</span><span>38</span><span>50 °C</span></div>
            <p class="hint">Ground surface temperature in the dry season, not air temperature.</p>
          </div>
        {/if}

        <label class="lyr"><input type="checkbox" bind:checked={regionalOn} disabled={!rs.regional} /> Regional {label} 2019 → 2022 (20 m)</label>
        {#if regionalOn}<p class="hint sub2">Exploratory: the same Sentinel-2 change across the whole terrain box, not the study raster. Colours as the vegetation ramp below.</p>{/if}

        <label class="lyr"><input type="checkbox" bind:checked={landcoverOn} disabled={!rs.landcover} /> Land cover 2021 (ESA WorldCover, 10 m)</label>
        {#if landcoverOn && lcRows.length}
          <table class="classes sub2">
            <thead><tr><th>Class</th><th>% of area</th><th>% browned</th></tr></thead>
            <tbody>{#each lcRows as row}<tr><td><span class="sw" style="background:{row.colour}"></span>{row.name}</td>
              <td>{(row.share_of_study_area * 100).toFixed(1)}</td><td>{(row['share_browned_dndvi_lt_-0.10'] * 100).toFixed(0)}</td></tr>{/each}</tbody>
          </table>
          <p class="hint">Land cover inside the study area (ESA WorldCover 2021) and how much of each type browned.</p>
        {/if}

        <label class="lyr"><input type="checkbox" bind:checked={lidarOn} disabled={!rs.lidar} /> Lidar, {lidarMeta?.acquired_utc?.[0]?.slice(0, 7) ?? '2023'} (USGS 3DEP)</label>
        {#if rs.lidar}
          <div class="sub2" class:dim={!lidarOn}>
            <div class="seg" role="radiogroup" aria-label="Lidar product">
              <label class:on={lidarProduct === 'chm'}><input type="radio" bind:group={lidarProduct} value="chm" />Height above ground</label>
              <label class:on={lidarProduct === 'hillshade'}><input type="radio" bind:group={lidarProduct} value="hillshade" />Bare-earth relief</label>
            </div>
            {#if lidarProduct === 'chm'}
              <div class="ramp" aria-hidden="true">{#each CHM_STOPS as [, c]}<span style="background:rgb({c.join(',')})"></span>{/each}</div>
              <div class="ramp-labels"><span>0 m</span><span>5</span><span>10</span><span>20+ m</span></div>
            {/if}
            <p class="hint">Height of trees and buildings above the ground, from a 2023 lidar flight between the drought and the fires.</p>
          </div>
        {/if}
      </div>
    </fieldset>

    <fieldset>
      <legend><label><input type="checkbox" bind:checked={veg} /> Vegetation change</label></legend>
      <div class="sub" class:dim={!veg}>
        <label><input type="radio" bind:group={vegIndex} value="dndvi" disabled={!veg} /> dNDVI (greenness)</label>
        <label><input type="radio" bind:group={vegIndex} value="dnbr" disabled={!veg} /> dNBR (moisture-sensitive)</label>
        <p class="hint">{PERIOD}, 1.5 km study area.</p>
        <div class="seg" role="radiogroup" aria-label="Vegetation display">
          <label class:on={vegMode === 'classes'}><input type="radio" bind:group={vegMode} value="classes" disabled={!veg} />Classes</label>
          <label class:on={vegMode === 'below'}><input type="radio" bind:group={vegMode} value="below" disabled={!veg} />Browned only</label>
          <label class:on={vegMode === 'ramp'}><input type="radio" bind:group={vegMode} value="ramp" disabled={!veg} />Full change</label>
        </div>

        {#if vegMode === 'ramp'}
          <div class="ramp" aria-hidden="true">
            {#each [-0.4, -0.2, -0.1, 0, 0.1, 0.2, 0.4] as v}<span style="background:{swatch(v)}"></span>{/each}
          </div>
          <div class="ramp-labels"><span>−0.4 loss</span><span>0</span><span>+0.4 gain</span></div>
        {/if}

        <label class="slider">Browning threshold: {label} &lt;
          <output>{threshold.toFixed(2)}</output>
          <input type="range" min="-0.4" max="0" step="0.01" bind:value={threshold} disabled={!veg}
                 aria-valuetext="{label} below {threshold.toFixed(2)}" /></label>
        <div class="ramp-labels"><span>−0.40</span>
          <button class="linkish tiny" on:click={() => (threshold = RESEARCH_THRESHOLD)} disabled={threshold === RESEARCH_THRESHOLD}>reset to the study’s −0.10</button><span>0</span></div>

        <ThresholdHistogram {bins} {threshold} {label} on:change={(e) => (threshold = e.detail)} />
        <p class="hint">Drag the marker, click the histogram, or use the arrow keys (Shift = 0.05). Dashed line: the study’s −0.10.</p>

        {#if thrView}
          <table class="classes">
            <thead><tr><th>Class</th><th>Pixels</th><th>ha</th><th>%</th></tr></thead>
            <tbody>
              <tr><td><span class="sw sev"></span>Browning &lt; {threshold.toFixed(2)}</td><td>{thrView.below.toLocaleString()}</td><td>{ha(thrView.below)}</td><td>{pct(thrView.below)}</td></tr>
              <tr><td><span class="sw" style="background:{rgb(CLASS_COLORS.stable)}"></span>Stable</td><td>{thrView.stable.toLocaleString()}</td><td>{ha(thrView.stable)}</td><td>{pct(thrView.stable)}</td></tr>
              <tr><td><span class="sw" style="background:{rgb(CLASS_COLORS.greening)}"></span>Greening &gt; +{Math.abs(threshold).toFixed(2)}</td><td>{thrView.greening.toLocaleString()}</td><td>{ha(thrView.greening)}</td><td>{pct(thrView.greening)}</td></tr>
            </tbody>
            <tfoot><tr><td>Valid pixels</td><td>{thrView.valid.toLocaleString()}</td><td>{ha(thrView.valid)}</td><td>100</td></tr></tfoot>
          </table>
        {/if}
        <label><input type="checkbox" bind:checked={vegPatches} disabled={!veg} /> Outline the study’s browned patches (−0.10)</label>
      </div>
    </fieldset>

    <fieldset>
      <legend><label><input type="checkbox" bind:checked={drought} /> Drought</label></legend>
      <div class="sub" class:dim={!drought}>
        <ul class="key">
          {#each DM_LABELS as dl, i}
            <li class:absent={!droughtCats.includes(i)}><span class="sw" style="background:{DM_COLORS[i]}"></span>{dl}</li>
          {/each}
        </ul>
        {#if droughtIndex.find((d) => d.year === year)}
          <p class="hint">Map for the week of {droughtIndex.find((d) => d.year === year).week}.
            {droughtCats.length ? `Present on Maui: ${droughtCats.map((c) => 'D' + c).join(', ')}.` : 'No drought mapped on Maui that week.'}
            County-scale polygons, not a reading at any 10 m pixel.</p>
        {:else}
          <p class="empty">Drought map not available for {year}.</p>
        {/if}
      </div>
    </fieldset>

    <fieldset>
      <legend>Hawaiʻi state data</legend>
      <div class="sub">
        <label><input type="checkbox" bind:checked={portal.fire_risk} /> <span class="sw" style="background:{RISK.Medium}"></span> DLNR fire-risk areas</label>
        {#if portal.fire_risk}
          <ul class="key sub2">{#each Object.entries(RISK) as [name, col]}<li><span class="sw" style="background:{col}"></span>{name === 'N/A' ? 'Not rated' : name}</li>{/each}</ul>
          <p class="hint sub2">DLNR-DOFAW’s rating for <em>populated areas only</em> (2007; boundaries reconfirmed 2017 and 2022). Land outside these polygons is unrated, not low risk. This is the state’s rating, not this project’s.</p>
        {/if}
        <label><input type="checkbox" bind:checked={portal.fire_response} /> <span class="sw line" style="border-color:#f58ab6"></span> Fire response zones</label>
        {#if portal.fire_response}<p class="hint sub2">Which agency responds first (DLNR-DOFAW, as of April 2026). Pink dashed outlines.</p>{/if}
        <label><input type="checkbox" bind:checked={portal.moisture_zones} /> <span class="sw" style="background:{MOIST['Moderately Dry']}"></span> Moisture zones</label>
        {#if portal.moisture_zones}
          <ul class="key sub2">{#each Object.entries(MOIST) as [name, col]}<li><span class="sw" style="background:{col}"></span>{name}</li>{/each}</ul>
          <p class="hint sub2">Seven zones from a species-range model (Hawaiʻi Cooperative Studies Unit, UH Hilo / Smithsonian). A modelled classification.</p>
        {/if}
        <label><input type="checkbox" bind:checked={portal.rainfall_mm} /> <span class="sw line" style="border-color:#6cb6ff"></span> Mean annual rainfall (mm)</label>
        <label><input type="checkbox" bind:checked={portal.rain_gauges} /> <span class="sw" style="background:#6cb6ff"></span> Rain gauges ({pinfo('rain_gauges')?.count ?? 226})</label>
        {#if portal.rainfall_mm || portal.rain_gauges}<p class="hint sub2">Rainfall Atlas of Hawaiʻi (Giambelluca et al., 2011; 1978–2007 average): isohyets every 500 mm; gauges give each station’s mean. Click a gauge for its value.</p>{/if}
        <label><input type="checkbox" bind:checked={portal.plantation} /> <span class="sw" style="background:{SUGAR}"></span><span class="sw" style="background:{PINE}"></span> Former plantation land</label>
        {#if portal.plantation}
          <div class="seg sub2" role="radiogroup" aria-label="Plantation year">
            {#each ['1900', '1920', '1937'] as y}<label class:on={plantYear === y}><input type="radio" bind:group={plantYear} value={y} />{y}</label>{/each}
          </div>
          <p class="hint sub2"><span class="sw" style="background:{SUGAR}"></span> sugarcane · <span class="sw" style="background:{PINE}"></span> pineapple. Land in production in {plantYear}, digitised from historical land-use maps by the state{plantYear === '1900' ? ' (no pineapple on Maui in 1900)' : ''}.</p>
        {/if}
        {#if portalError}<p class="empty">State layer couldn’t load: {portalError}. Run <code>scripts/fetch_hawaii_portal.py</code>.</p>{/if}
        <p class="hint">Source: Hawaii Statewide GIS Program (geodata.hawaii.gov) with the data owners named above. The state gives no warranty of positional or thematic accuracy.</p>
      </div>
    </fieldset>

    <fieldset>
      <legend><label><input type="checkbox" bind:checked={community} /> Community context</label></legend>
      <div class="sub" class:dim={!community}>
        {#each KINDS as k}
          <label class="kind">
            <input type="checkbox" bind:checked={kinds[k]} disabled={!community} />
            <svg viewBox="0 0 22 22" width="18" height="18" aria-hidden="true">{@html iconSvg(k)}</svg>
            {KIND_LABEL[k]}s <span class="muted">({catalog.find((c) => c.id === k)?.count ?? '…'} · {currencyOf(k)})</span>
          </label>
        {/each}
      </div>
    </fieldset>

    <fieldset>
      <legend>Other layers</legend>
      <div class="sub">
        <label><input type="checkbox" bind:checked={fires} /> <span class="sw line fire"></span> Fire perimeters</label>
        <label class="indent"><input type="checkbox" bind:checked={firesAllYears} disabled={!fires} /> All years (2019, 2023, 2024)</label>
        {#if fires && !firesAllYears}
          <p class="hint indent">{firesThisYear.length ? `${year}: ${firesThisYear.join(', ')}` : `No mapped perimeters in ${year}.`}</p>
        {/if}
        <label><input type="checkbox" bind:checked={globe} /> <span class="sw site"></span> GLOBE sites observed in {year}</label>
        {#if obsError}<p class="empty indent">GLOBE observations couldn’t load (needs the GLOBE cache or a connection to api.globe.gov). The other layers are unaffected.</p>
        {:else if globe && !obsThisYear}<p class="empty indent">No GLOBE observations in this area in {year}.</p>{/if}
        <label><input type="checkbox" bind:checked={regions} /> <span class="sw line region"></span> Pukalani, Makawao, Kula</label>
        <label><input type="checkbox" bind:checked={study} /> <span class="sw line dash"></span> Study area (1.5 km radius)</label>
        <button class="linkish" on:click={focusStudyArea} disabled={!ready}>Zoom to the study area</button>
      </div>
    </fieldset>

    <section class="cardout" aria-live="polite">
      {#if selected}
        <div class="feature card">
          <button class="close" aria-label="Close feature details" on:click={() => (selected = null)}>×</button>
          <p class="eyebrow">{selected.kind}</p>
          <h2>{selected.title}</h2>
          {#if selected.raster}
            <dl class="px">
              <dt>{selected.raster.index}</dt><dd>{selected.raster.value >= 0 ? '+' : ''}{selected.raster.value.toFixed(4)}</dd>
              <dt>Class at {threshold.toFixed(2)}</dt><dd>{selected.raster.cls}</dd>
              <dt>Pixel</dt><dd>row {selected.raster.row}, col {selected.raster.col}</dd>
              <dt>Period</dt><dd>2019 → 2022 dry season</dd>
            </dl>
          {/if}
          {#if selected.rows.length}
            <dl>{#each selected.rows as [k, v]}<dt>{k}</dt><dd>{v}</dd>{/each}</dl>
          {/if}
          {#if selected.portal?.length}
            <p class="meta"><b>Hawaiʻi state data here</b></p>
            <dl>{#each selected.portal as [k, v]}<dt>{k}</dt><dd>{v}</dd>{/each}</dl>
          {/if}
          {#if selected.rs?.series?.length}
            {@const sp = spark(selected.rs.series)}
            <p class="meta"><b>Dry-season NDVI here, {selected.rs.series[0].year}–{selected.rs.series[selected.rs.series.length - 1].year}</b> (Sentinel-2, 10 m)</p>
            <svg class="spark" viewBox="0 0 {sp.W} {sp.H}" role="img" aria-label="NDVI by year at this pixel">
              <line x1="0" x2={sp.W} y1={sp.y(0.4)} y2={sp.y(0.4)} class="g" />
              <path d={sp.d} />
              {#each selected.rs.series as p, i}<rect x={sp.x(i) - 2.5} y={sp.y(p.ndvi) - 2.5} width="5" height="5" class:hl={p.year === 2019 || p.year === 2022}>
                <title>{p.year}: NDVI {p.ndvi.toFixed(3)}, {p.obs} clear obs</title></rect>{/each}
            </svg>
            <div class="sparkx"><span>{selected.rs.series[0].year}</span><span>2019 · 2022 marked</span><span>{selected.rs.series[selected.rs.series.length - 1].year}</span></div>
          {/if}
          {#if !selected.rs?.series?.length && selected.rs?.island?.series?.length}
            {@const sp = spark(selected.rs.island.series)}
            <p class="meta"><b>Dry-season NDVI here, {selected.rs.island.series[0].year}–{selected.rs.island.series[selected.rs.island.series.length - 1].year}</b> (whole-island Sentinel-2, 60 m)</p>
            <svg class="spark" viewBox="0 0 {sp.W} {sp.H}" role="img" aria-label="NDVI by year here">
              <line x1="0" x2={sp.W} y1={sp.y(0.4)} y2={sp.y(0.4)} class="g" /><path d={sp.d} />
              {#each selected.rs.island.series as p, i}<rect x={sp.x(i) - 2.5} y={sp.y(p.ndvi) - 2.5} width="5" height="5" class:hl={p.year === 2019 || p.year === 2022}><title>{p.year}: NDVI {p.ndvi.toFixed(2)}</title></rect>{/each}
            </svg>
            <div class="sparkx"><span>{selected.rs.island.series[0].year}</span><span>2019 · 2022 marked</span><span>{selected.rs.island.series[selected.rs.island.series.length - 1].year}</span></div>
          {/if}
          {#if selected.rs?.landcover || selected.rs?.lidar || selected.rs?.regional || selected.rs?.landsat || selected.rs?.burn || selected.rs?.lst2022 !== undefined}
            <dl class="px">
              {#if selected.rs.burn}<dt>Burn severity 2023</dt><dd>{selected.rs.burn.cls} (dNBR {selected.rs.burn.dnbr.toFixed(2)})</dd>{/if}
              {#if selected.rs.lst2022 !== undefined}<dt>Surface temp 2022</dt><dd>{selected.rs.lst2022.toFixed(1)} °C (dry-season median)</dd>{/if}
              {#if selected.rs.landsat}<dt>Landsat 2022</dt><dd>NDVI {selected.rs.landsat.ndvi2022.toFixed(3)} vs normal {selected.rs.landsat.normal.toFixed(3)} · z {selected.rs.landsat.z2022.toFixed(1)}</dd>{/if}
              {#if selected.rs.landcover}<dt>Land cover 2021</dt><dd>{selected.rs.landcover}</dd>{/if}
              {#if selected.rs.lidar}<dt>Height above ground</dt><dd>{selected.rs.lidar.chm.toFixed(1)} m (lidar 2023)</dd>
                <dt>Ground (lidar)</dt><dd>{selected.rs.lidar.ground.toFixed(1)} m</dd>{/if}
              {#if selected.rs.regional && !selected.raster}<dt>Regional dNDVI</dt><dd>{selected.rs.regional.dndvi.toFixed(3)} (20 m, exploratory)</dd>{/if}
            </dl>
          {/if}
          <dl class="px">
            <dt>Lat, lon</dt><dd>{selected.lat.toFixed(5)}, {selected.lon.toFixed(5)}</dd>
            <dt>Elevation</dt><dd>{selected.elevation ? (Number.isFinite(selected.elevation.z) ? `${selected.elevation.z.toFixed(1)} m` : 'outside DEM') : '…'}</dd>
          </dl>
          {#if selected.elevation}<p class="meta muted">Elevation: {selected.elevation.source}.</p>{/if}
          {#if selected.period}<p class="meta"><b>Period:</b> {selected.period}</p>{/if}
          {#if selected.uncertainty}<p class="meta"><b>Uncertainty:</b> {selected.uncertainty}</p>{/if}
          {#if selected.source}<p class="meta"><b>Source:</b> {selected.source}</p>{/if}
          {#each selected.links as l}<a class="btn" href={l.href}>{l.label} →</a>{/each}
        </div>
      {:else}
        <p class="hint">Click any symbol, shaded area or vegetation pixel to see its value, class, elevation, period, uncertainty and source.</p>
      {/if}
    </section>
  </aside>

  <div class="mapwrap" bind:this={wrapEl}>
    <div class="map" bind:this={container} role="region" aria-label="Map of Upcountry Maui"></div>
    {#if compare}
      <div class="mapB" bind:this={containerB} style="clip-path: inset(0 0 0 {split}%)" aria-hidden="true"></div>
      <div class="divider" style="left: {split}%" role="slider" tabindex="0" aria-label="Compare divider" aria-valuemin="5" aria-valuemax="95"
           aria-valuenow={Math.round(split)} on:pointerdown={(e) => { dragging = true; e.currentTarget.setPointerCapture(e.pointerId); }}
           on:keydown={splitKey}><span>⟷</span></div>
      <div class="side left">{leftLabel}</div>
      <div class="side right">{rightLabel}{#if compareError}: {compareError}{/if}</div>
    {/if}

    <div class="toolbar" role="toolbar" aria-label="Map tools">
      <div class="grp" role="radiogroup" aria-label="View">
        <button class:on={!view3d} aria-pressed={!view3d} on:click={() => set3d(false)} disabled={!ready}>2D</button>
        <button class:on={view3d} aria-pressed={view3d} on:click={() => set3d(true)} disabled={!ready || !!demError}
                title={demError ?? 'Tilt into 3D terrain'}>3D</button>
      </div>
      <button class:on={tool === 'profile'} aria-pressed={tool === 'profile'} on:click={startProfile} disabled={!ready}>
        {tool === 'profile' ? (transect.length ? 'Click point B' : 'Click point A') : 'Profile'}</button>
      <button class:on={compare} aria-pressed={compare} on:click={() => (compare = !compare)} disabled={!ready}>Compare</button>
      <button class:on={dataOpen} aria-pressed={dataOpen} on:click={openData} disabled={!ready}>Data over time</button>
    </div>

    {#if view3d}
      <div class="subbar">
        <label>Vertical exaggeration <b class="num">×{exaggeration.toFixed(1)}</b>
          <input type="range" min="1" max="3" step="0.1" bind:value={exaggeration} on:input={setExaggeration} /></label>
        <label>Tilt <b class="num">{pitch}°</b>
          <input type="range" min="0" max="80" step="1" bind:value={pitch} on:input={setPitch} /></label>
        <p class="hint">Right-drag or Ctrl-drag to rotate. Terrain: AWS Terrain Tiles; vegetation pixels stay at their ground coordinates.</p>
      </div>
    {/if}
    {#if compare}
      <div class="subbar compare">
        <span class="hint">Left: the map as set. Right:</span>
        <select bind:value={compareRight} aria-label="Right-hand basemap">
          {#each rs.imagery as im}<option value={'img:' + im.id}>Sentinel-2 · {im.label}</option>{/each}
          {#each BASEMAPS as bm}<option value={bm.id}>{bm.label}</option>{/each}
        </select>
        <select bind:value={compareOverlay} aria-label="Right-hand overlay">
          <option value="none">no overlay</option><option value="dndvi">dNDVI</option><option value="dnbr">dNBR</option>
        </select>
        <button on:click={() => preset('s2')} disabled={!rs.imagery.some((i) => i.id === 's2_dry_2022')}>Dry season 2019 | 2022</button>
        <button on:click={() => preset('fire')} disabled={!rs.imagery.some((i) => i.id === 'after_2023')}>Before | after Aug 2023 fires</button>
        <button on:click={() => preset('idx')}>dNDVI | dNBR</button>
      </div>
    {/if}

    <figure class="inset" aria-label="Location of the map on Maui">
      <img src="/api/layers/inset.png" alt="" width={INSET.w} height={INSET.h} />
      <svg viewBox="0 0 {INSET.w} {INSET.h}" aria-hidden="true">
        <rect class="box" x={ix(-156.45)} y={iy(20.88)} width={ix(-156.24) - ix(-156.45)} height={iy(20.70) - iy(20.88)} />
        {#if viewBox}<rect class="view" x={Math.max(0, ix(viewBox.w))} y={Math.max(0, iy(viewBox.n))}
          width={Math.max(2, Math.min(INSET.w, ix(viewBox.e)) - Math.max(0, ix(viewBox.w)))} height={Math.max(2, Math.min(INSET.h, iy(viewBox.s)) - Math.max(0, iy(viewBox.n)))} />{/if}
      </svg>
      <figcaption>Maui · view in orange</figcaption>
    </figure>

    {#if cursor}
      <div class="cursor" aria-hidden="true">
        <span>{cursor.lat.toFixed(5)}, {cursor.lon.toFixed(5)}</span>
        <span>{cursor.z === null ? 'elev …' : Number.isFinite(cursor.z) ? `${Math.round(cursor.z)} m` : 'elev n/a'}</span>
        {#if cursor.v !== null}
          <span>{label} <b class={classify(cursor.v, threshold)}>{cursor.v >= 0 ? '+' : ''}{cursor.v.toFixed(3)}</b> {classify(cursor.v, threshold)}</span>
        {/if}
      </div>
    {/if}
    {#if loading}<div class="state">Loading terrain, vegetation rasters and layers…</div>{/if}
    {#if error}<div class="state err" role="alert">Couldn’t load the map: {error}</div>{/if}
  </div>
  {#if transect.length || profile}
    <div class="dock"><ProfilePanel {profile} {threshold} {label}
      on:hover={(e) => drawTransect(e.detail)}
      on:close={() => { profile = null; transect = []; tool = null; map.getSource('transect').setData(fc([])); }} /></div>
  {/if}
  {#if facets && rs.annual}
    <div class="dock"><section class="facets" aria-label="Dry-season {annualIdx.toUpperCase()} by year">
      <header><h2>Dry-season {annualIdx.toUpperCase()} by year</h2><button class="x" on:click={() => (facets = false)} aria-label="Close">×</button></header>
      <div class="fgrid">
        {#each annualYears as y, k}
          <button class="fcell" class:on={y === annualYear} on:click={() => { annualYear = y; annualOn = true; }}>
            <canvas use:facet={y}></canvas>
            <span>{y}</span>
          </button>
        {/each}
      </div>
      <p class="hint">Same colours in every panel: brown is dry, green is healthy. Click a year to show it on the map.</p>
    </section></div>
  {/if}
  {#if dataOpen}
    <div class="dock"><SeriesPanel rows={seriesRows} error={seriesError} {year} bind:from={seriesFrom} bind:to={seriesTo} on:close={() => (dataOpen = false)}
      on:pickyear={(e) => (year = e.detail)} /></div>
  {/if}
</div>

<style>
  .explore { display: grid; grid-template-columns: 360px 1fr; grid-template-rows: 1fr auto auto auto; height: 100%; position: relative; }
  aside { grid-row: 1 / 5; min-height: 0; overflow-y: auto; padding: 14px 16px 30px; background: var(--card); border-right: 1px solid var(--line); }
  .dock { grid-column: 2; min-width: 0; max-height: 46vh; overflow-y: auto; }
  aside h1 { font-size: 1.5rem; margin-bottom: 8px; }
  fieldset { border: 0; border-top: 1px solid var(--line); padding: 10px 0 4px; margin: 10px 0 0; }
  legend { font-weight: 700; color: var(--forest); padding: 0; font-size: .95rem; }
  legend label { display: flex; gap: 6px; align-items: center; }
  .sub { display: flex; flex-direction: column; gap: 3px; padding: 6px 0 0 2px; font-size: .9rem; }
  .sub label { display: flex; gap: 6px; align-items: center; }
  .sub select, .subbar select { background: var(--paper-2); border: 1px solid var(--line); padding: 3px 6px; font-size: .85rem; }
  .dim { opacity: .5; }
  .indent { margin-left: 22px; }
  .years { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
  .years label { border: 1px solid var(--line); padding: 2px 8px; font-size: .85rem; cursor: pointer; font-family: var(--mono); }
  .years label.on { background: var(--forest); color: #111; border-color: var(--forest); }
  .years input, .seg input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .years label:focus-within, .seg label:focus-within { outline: 3px solid var(--focus); outline-offset: 1px; }
  .seg { display: flex; border: 1px solid var(--line); margin-top: 6px; }
  .seg label { flex: 1; justify-content: center; padding: 3px 4px; font-size: .8rem; cursor: pointer; }
  .seg label + label { border-left: 1px solid var(--line); }
  .seg label.on { background: var(--paper-2); box-shadow: inset 0 -2px 0 var(--forest); }
  .slider { flex-direction: column; align-items: stretch !important; margin-top: 10px; font-size: .82rem; }
  .slider output { font: 700 1rem var(--mono); color: var(--forest); }
  .slider input { width: 100%; }
  .tiny { font-size: .72rem !important; padding: 0 !important; }
  .classes { font-size: .78rem; margin-top: 8px; border: 1px solid var(--line); }
  .classes th, .classes td { padding: 3px 6px; }
  .classes td:not(:first-child), .classes th:not(:first-child) { text-align: right; font-family: var(--mono); }
  .classes td:first-child { display: flex; gap: 6px; align-items: center; }
  .classes tfoot td { color: var(--muted); border-bottom: 0; }
  .hint { font-size: .78rem; color: var(--muted); margin: 4px 0 0; }
  .empty { font-size: .8rem; color: var(--amber); margin: 4px 0 0; }
  .ramp { display: flex; height: 12px; overflow: hidden; margin-top: 8px; border: 1px solid var(--line); }
  .ramp span { flex: 1; }
  .ramp-labels { display: flex; justify-content: space-between; align-items: center; font-size: .72rem; color: var(--muted); }
  .key { list-style: none; padding: 0; margin: 0; font-size: .85rem; }
  .key li { display: flex; gap: 6px; align-items: center; }
  .key li.absent { color: var(--muted); text-decoration: line-through; }
  .sw { width: 14px; height: 12px; display: inline-block; border: 1px solid #000; flex: none; }
  .sw.sev { background: linear-gradient(90deg, rgb(246,196,120), rgb(120,52,6)); }
  .sw.line { height: 0; border: 0; border-top: 3px solid; width: 16px; }
  .sw.line.fire { border-color: #ff5a4f; }
  .sw.line.region { border-top: 3px dotted #5fb7c2; }
  .sw.line.dash { border-top: 3px dashed #e4e8ea; }
  .sw.site { width: 11px; height: 11px; background: #5fb7c2; border: 2px solid #111; }
  .kind { font-size: .86rem; }
  .linkish { background: none; border: 0; color: var(--teal); text-decoration: underline; padding: 4px 0; text-align: left; font-size: .88rem; }
  .cardout { margin-top: 14px; }
  .feature { position: relative; padding: 14px 16px; }
  .feature h2 { font-size: 1rem; margin: 2px 0 6px; text-transform: none; letter-spacing: 0; color: var(--ink); }
  .close { position: absolute; top: 6px; right: 8px; border: 0; background: none; font-size: 1.3rem; color: var(--muted); }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; font-size: .84rem; margin: 6px 0; }
  dt { color: var(--muted); text-transform: capitalize; }
  dd { margin: 0; }
  .px dd { font-family: var(--mono); }
  .meta { font-size: .8rem; margin: 4px 0; }
  .feature .btn { margin-top: 8px; font-size: .88rem; }
  .mapwrap { position: relative; min-height: 0; overflow: hidden; }
  .map, .mapB { position: absolute; inset: 0; }
  .mapB { z-index: 1; pointer-events: none; }
  .divider { position: absolute; top: 0; bottom: 0; width: 3px; margin-left: -1px; background: var(--forest); z-index: 3; cursor: ew-resize; touch-action: none; }
  .divider span { position: absolute; top: 50%; left: -13px; width: 28px; height: 28px; display: grid; place-items: center;
                  background: var(--forest); color: #111; font-weight: 700; transform: translateY(-50%); }
  .side { position: absolute; bottom: 40px; z-index: 3; background: var(--card); border: 1px solid var(--line); padding: 3px 8px; font-size: .76rem; max-width: 45%; }
  .side.left { left: 10px; } .side.right { right: 10px; }
  .toolbar { position: absolute; top: 10px; left: 10px; z-index: 4; display: flex; gap: 6px; flex-wrap: wrap; max-width: calc(100% - 64px); }
  .toolbar button, .subbar button { background: var(--card); color: var(--ink); border: 1px solid var(--line); padding: .35em .8em; font-size: .84rem; font-weight: 600; }
  .toolbar button.on { border-color: var(--forest); box-shadow: inset 0 -2px 0 var(--forest); }
  .toolbar button:disabled { color: var(--muted); }
  .grp { display: flex; } .grp button + button { border-left: 0; }
  .subbar { position: absolute; top: 48px; left: 10px; z-index: 4; background: var(--card); border: 1px solid var(--line); padding: 6px 10px;
            display: flex; gap: 14px; align-items: center; flex-wrap: wrap; max-width: calc(100% - 80px); font-size: .8rem; }
  .subbar label { display: flex; gap: 6px; align-items: center; }
  .subbar input[type=range] { width: 120px; }
  .subbar .hint { margin: 0; flex-basis: 100%; }
  .subbar.compare .hint { flex-basis: auto; }
  .cursor { position: absolute; left: 10px; bottom: 34px; z-index: 2; background: var(--card); border: 1px solid var(--line);
            padding: 4px 8px; font: .76rem var(--mono); display: flex; gap: 10px; color: var(--muted); pointer-events: none; }
  .cursor b { color: var(--ink); } .cursor b.browning { color: #e9a556; } .cursor b.greening { color: #5fc6bd; }
  .state { position: absolute; inset: 0; display: grid; place-items: center; background: var(--paper); color: var(--muted); z-index: 5; }
  .state.err { color: var(--fire); }
  .toggle { display: none; }
  .col { flex-direction: column; align-items: stretch !important; gap: 3px !important; }
  .lyr { margin-top: 8px; font-weight: 600; }
  .sub2 { margin-left: 22px; display: flex; flex-direction: column; gap: 3px; }
  .row { display: flex; gap: 6px; align-items: center; }
  .row input[type=range] { flex: 1; }
  .row select { background: var(--paper-2); border: 1px solid var(--line); font-size: .78rem; }
  .play { background: var(--paper-2); border: 1px solid var(--line); color: var(--ink); padding: 1px 8px; font-size: .78rem; margin-top: 6px; }
  .row .play { margin-top: 0; }
  .play[aria-pressed='true'] { border-color: var(--forest); color: var(--forest); }
  .spark { width: 100%; height: auto; background: var(--paper); border: 1px solid var(--line); }
  .spark path { fill: none; stroke: #5ab4ac; stroke-width: 1.5; }
  .spark rect { fill: #5ab4ac; } .spark rect.hl { fill: var(--forest); }
  .spark .g { stroke: var(--line); stroke-dasharray: 2 2; }
  .sparkx { display: flex; justify-content: space-between; font: .66rem var(--mono); color: var(--muted); }
  .inset { position: absolute; right: 10px; top: 118px; z-index: 2; margin: 0; background: #0b1013; border: 1px solid var(--line); padding: 4px; }
  .inset img, .inset svg { display: block; width: 154px; height: 100px; }
  .inset svg { position: absolute; left: 4px; top: 4px; }
  .inset .box { fill: none; stroke: #e4e8ea; stroke-width: 1; stroke-dasharray: 2 2; }
  .inset .view { fill: rgba(224, 123, 44, .15); stroke: var(--forest); stroke-width: 1.5; }
  .inset figcaption { font: .62rem var(--mono); color: var(--muted); margin-top: 2px; }
  .facets { background: var(--card); border-top: 1px solid var(--line); padding: 8px 14px 10px; }
  .facets header { display: flex; align-items: center; }
  .facets h2 { flex: 1; margin: 0; border: 0; padding: 0; font-size: .8rem; }
  .facets .x { background: var(--paper-2); border: 1px solid var(--line); color: var(--ink-2); }
  .fgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 6px; margin-top: 6px; }
  .fcell { background: var(--paper); border: 1px solid var(--line); padding: 3px; display: grid; grid-template-columns: 1fr auto; gap: 0 4px; text-align: left; color: var(--ink); }
  .fcell canvas { grid-column: 1 / -1; width: 100%; height: auto; image-rendering: pixelated; }
  .fcell span { font: 600 .78rem var(--mono); }
  .fcell.on { border-color: var(--forest); box-shadow: inset 0 -2px 0 var(--forest); }
  :global(.region-label) {
    font: 700 13px/1 var(--sans); color: #5fb7c2; text-shadow: 0 0 3px #000, 0 0 3px #000;
    pointer-events: none; letter-spacing: .02em;
  }
  @media (max-width: 860px) {
    .explore { grid-template-columns: 1fr; }
    .dock { grid-column: 1; }
    aside { position: absolute; z-index: 6; inset: 44px 0 0 0; display: none; border-right: 0; }
    aside.open { display: block; }
    .toggle { display: block; position: absolute; z-index: 7; top: 8px; right: 8px; background: var(--card);
              border: 1px solid var(--line); padding: .4em .8em; font-weight: 600; }
    .toolbar { top: 52px; }
    .inset { display: none; }
    .subbar { top: 132px; max-width: calc(100% - 20px); }
  }
</style>
