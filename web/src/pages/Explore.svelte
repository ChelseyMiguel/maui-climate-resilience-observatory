<script>
  // Interactive Map Explorer. Every layer is real: the project's own analysis or a
  // verified public source. Nothing is simulated — where data doesn't exist for a
  // year or place, the sidebar says so instead.
  import { onMount, onDestroy } from 'svelte';
  import * as maplibregl from 'maplibre-gl';  // v6 has no default export
  import 'maplibre-gl/dist/maplibre-gl.css';
  // MapLibre parses GeoJSON in a web worker it locates relative to its own file.
  // Once bundled, that guess points at a file that doesn't exist and every GeoJSON
  // layer silently fails to load. Ship the (self-contained) worker as an asset and
  // tell MapLibre where it is.
  import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
  maplibregl.setWorkerUrl(workerUrl);
  import Notice from '../components/Notice.svelte';
  import * as data from '../lib/adapters.ts';
  import { getTerrain } from '../lib/api.js';
  import { reliefDataUrl } from '../lib/relief.ts';
  import { loadChangeRaster, BROWNING_THRESHOLD, rampColor } from '../lib/raster.ts';
  import { drawIcon, iconSvg, KIND_LABEL } from '../lib/icons.ts';

  const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024];
  const DM_COLORS = ['#f2e394', '#f2c46a', '#e8913e', '#c8512f', '#7a1f1f'];
  const DM_LABELS = ['D0 Abnormally dry', 'D1 Moderate', 'D2 Severe', 'D3 Extreme', 'D4 Exceptional'];
  const reduceMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  let container, map;
  // On a phone the layers panel would cover the whole map, so it starts closed
  // there; on wider screens it sits beside the map and starts open.
  let loading = true, error = null, sidebarOpen = typeof window === 'undefined' || window.innerWidth >= 860;
  let year = 2023;

  // Layer switches
  let veg = true, vegIndex = 'dndvi', vegPatches = false;
  let drought = true;
  let community = true;
  let kinds = { fire_stations: true, ems_stations: true, hospitals: true, public_schools: true, private_schools: true };
  let fires = true, firesAllYears = false;
  let regions = true, globe = true, study = true;

  // Data
  let rasters = {}, catalog = [], droughtIndex = [], observations = [], terrain = null, studyArea = null;
  let fireFeatures = [];
  let droughtCats = [];          // categories present in the loaded year's map
  let obsThisYear = 0, firesThisYear = [];
  // GLOBE pins are optional: if they cannot load, every other layer still must.
  let obsError = null;
  let selected = null;           // the feature card
  let ready = false;

  const KINDS = data.INFRA_KINDS;
  const currencyOf = (id) => catalog.find((c) => c.id === id)?.currency ?? 'not stated';

  function circle(lat, lon, radiusM, n = 96) {
    const kx = 111320 * Math.cos((lat * Math.PI) / 180);
    const ring = Array.from({ length: n + 1 }, (_, i) => {
      const a = (i / n) * 2 * Math.PI;
      return [lon + (radiusM * Math.cos(a)) / kx, lat + (radiusM * Math.sin(a)) / 111320];
    });
    return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} };
  }
  const fc = (features) => ({ type: 'FeatureCollection', features });

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
      buildMap({ regionsFc, firesFc, patchesFc, infra });
    } catch (e) {
      error = e.message;
      loading = false;
    }
  });

  function buildMap({ regionsFc, firesFc, patchesFc, infra }) {
    fireFeatures = firesFc.features;
    const b = terrain.meta.bbox;
    map = new maplibregl.Map({
      container,
      style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#1a1f24' } }] },
      bounds: [[b.west, b.south], [b.east, b.north]],
      maxBounds: [[b.west - 0.1, b.south - 0.1], [b.east + 0.1, b.north + 0.1]],
      attributionControl: { compact: true, customAttribution:
        'Relief: AWS Terrain Tiles / USGS 3DEP · Vegetation: author’s Sentinel-2 analysis · Drought: U.S. Drought Monitor · Fires: NIFC · Places & facilities: Hawaiʻi Statewide GIS Program, U.S. Census · Sites: NASA GLOBE' },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');

    map.on('load', () => {
      const corners = [[b.west, b.north], [b.east, b.north], [b.east, b.south], [b.west, b.south]];
      map.addSource('relief', { type: 'image', url: reliefDataUrl(terrain), coordinates: corners });
      map.addLayer({ id: 'relief', type: 'raster', source: 'relief', paint: { 'raster-resampling': 'linear' } });

      map.addSource('drought', { type: 'geojson', data: fc([]) });
      map.addLayer({ id: 'drought-fill', type: 'fill', source: 'drought',
        paint: { 'fill-color': ['match', ['get', 'dm'], 0, DM_COLORS[0], 1, DM_COLORS[1], 2, DM_COLORS[2], 3, DM_COLORS[3], 4, DM_COLORS[4], '#ccc'],
                 'fill-opacity': 0.42 } });
      map.addLayer({ id: 'drought-line', type: 'line', source: 'drought', paint: { 'line-color': '#7a4a18', 'line-width': 0.6, 'line-opacity': 0.6 } });

      for (const id of ['dndvi', 'dnbr']) {
        map.addSource(`raster-${id}`, { type: 'image', url: rasters[id].imageUrl, coordinates: rasters[id].meta.corners });
        map.addLayer({ id: `raster-${id}`, type: 'raster', source: `raster-${id}`, paint: { 'raster-resampling': 'nearest', 'raster-opacity': 0.92 } });
      }
      map.addSource('patches', { type: 'geojson', data: patchesFc });
      map.addLayer({ id: 'patches-line', type: 'line', source: 'patches', paint: { 'line-color': '#5c2f04', 'line-width': 0.8 } });

      map.addSource('study', { type: 'geojson', data: circle(studyArea.lat, studyArea.lon, studyArea.radius_m) });
      map.addLayer({ id: 'study-line', type: 'line', source: 'study', paint: { 'line-color': '#1f2a24', 'line-width': 2, 'line-dasharray': [3, 2] } });

      map.addSource('regions', { type: 'geojson', data: regionsFc });
      map.addLayer({ id: 'regions-fill', type: 'fill', source: 'regions', paint: { 'fill-color': '#1f6f73', 'fill-opacity': 0.04 } });
      map.addLayer({ id: 'regions-line', type: 'line', source: 'regions', paint: { 'line-color': '#1f6f73', 'line-width': 2, 'line-dasharray': [1, 1.5] } });
      for (const f of regionsFc.features) {
        const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates[0][0];
        const lon = ring.reduce((s, p) => s + p[0], 0) / ring.length, lat = ring.reduce((s, p) => s + p[1], 0) / ring.length;
        const el = Object.assign(document.createElement('div'), { className: 'region-label', textContent: f.properties.name });
        new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
      }

      map.addSource('fires', { type: 'geojson', data: firesFc });
      map.addLayer({ id: 'fires-fill', type: 'fill', source: 'fires', paint: { 'fill-color': '#b3261e', 'fill-opacity': 0.18 } });
      map.addLayer({ id: 'fires-line', type: 'line', source: 'fires', paint: { 'line-color': '#b3261e', 'line-width': 2.2 } });

      map.addSource('globe', { type: 'geojson', data: fc([]) });
      map.addLayer({ id: 'globe-points', type: 'circle', source: 'globe',
        paint: { 'circle-radius': 5.5, 'circle-color': '#1f6f73', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2 } });

      for (const k of KINDS) map.addImage(`icon-${k}`, drawIcon(k), { pixelRatio: 2 });
      map.addSource('infra', { type: 'geojson', data: fc(infra.flat().map((f) => ({
        type: 'Feature', geometry: { type: 'Point', coordinates: [f.lon, f.lat] },
        properties: { kind: f.kind, name: f.name, attrs: JSON.stringify(f.attributes) },
      }))) });
      map.addLayer({ id: 'infra', type: 'symbol', source: 'infra',
        layout: { 'icon-image': ['concat', 'icon-', ['get', 'kind']], 'icon-allow-overlap': true } });

      const interactive = ['infra', 'globe-points', 'fires-fill', 'drought-fill', 'regions-fill'];
      for (const id of interactive) {
        map.on('mouseenter', id, () => (map.getCanvas().style.cursor = 'pointer'));
        map.on('mouseleave', id, () => (map.getCanvas().style.cursor = ''));
      }
      map.on('click', onClick);

      ready = true;
      loading = false;
      applyAll();
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
    map.getSource('globe').setData(fc(yearObs.map((o) => ({
      type: 'Feature', geometry: { type: 'Point', coordinates: [o.lon, o.lat] },
      properties: { id: o.landCoverId, label: o.label, site: o.siteName, date: o.date, complete: o.complete },
    }))));
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
    vis('raster-dndvi', veg && vegIndex === 'dndvi');
    vis('raster-dnbr', veg && vegIndex === 'dnbr');
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

  $: if (ready) { year; applyYear(); }
  $: if (ready) { firesAllYears; applyFireFilter(); }
  $: if (ready) { veg; vegIndex; vegPatches; drought; community; kinds; fires; regions; globe; study; applyAll(); }

  // ---------- feature card ----------
  function onClick(e) {
    const { lng, lat } = e.lngLat;
    const order = ['infra', 'globe-points', 'fires-fill', 'drought-fill', 'regions-fill'].filter((id) => map.getLayer(id)
      && map.getLayoutProperty(id, 'visibility') !== 'none');
    const hits = map.queryRenderedFeatures(e.point, { layers: order });
    const pick = (id) => hits.find((h) => h.layer.id === id);
    const rasterValue = veg ? rasters[vegIndex].valueAt(lat, lng) : null;

    const card = { lat, lon: lng, rows: [], raster: null, links: [] };
    if (rasterValue !== null) {
      card.raster = { index: vegIndex === 'dndvi' ? 'dNDVI' : 'dNBR', value: rasterValue,
                      browned: rasterValue < BROWNING_THRESHOLD };
    }
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
                   ['area', f.properties.acres ? `${Math.round(f.properties.acres).toLocaleString()} acres` : '—']];
      card.period = `${f.properties.year} incident`;
      card.uncertainty = 'Final mapped perimeter: shows where fire burned, not how it spread or what started it.';
      card.source = 'National Interagency Fire Center';
    } else if ((f = pick('drought-fill'))) {
      const entry = droughtIndex.find((d) => d.year === year);
      card.title = DM_LABELS[f.properties.dm] ?? f.properties.label; card.kind = 'U.S. Drought Monitor category';
      card.rows = [['map week', entry?.week]];
      card.period = `Week of ${entry?.week} (nearest 8 August ${year})`;
      card.uncertainty = 'A broad-scale expert assessment blending many indicators — not a field measurement for this spot.';
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
      card.title = `${card.raster.index} at this point`; card.kind = 'Author’s Sentinel-2 change raster';
      card.period = 'Dry season (May–Sep) 2022 minus 2019';
      card.uncertainty = 'One 10 m pixel; cloud-masked dry-season medians. Greenness/moisture change is not fuel load or fire risk.';
      card.source = 'Author’s analysis (Copernicus Sentinel-2)';
    }
    selected = card;
    if (window.innerWidth < 860) sidebarOpen = true;
  }

  function focusStudyArea() {
    map?.flyTo({ center: [studyArea.lon, studyArea.lat], zoom: 13.6, duration: reduceMotion ? 0 : 1200 });
  }

  onDestroy(() => map?.remove());

  const swatch = (v) => `rgb(${rampColor(v).join(',')})`;
  $: vegShare = rasters[vegIndex]?.meta.shareBelowThreshold;
</script>

<div class="explore">
  <button class="toggle" aria-expanded={sidebarOpen} aria-controls="layers" on:click={() => (sidebarOpen = !sidebarOpen)}>
    {sidebarOpen ? 'Hide layers' : 'Layers & legend'}
  </button>

  <aside id="layers" class:open={sidebarOpen} aria-label="Map layers and legend">
    <h1>Map Explorer</h1>
    <Notice compact />

    <fieldset class="year">
      <legend>Year</legend>
      <div class="years" role="radiogroup" aria-label="Year">
        {#each YEARS as y}
          <label class:on={y === year}><input type="radio" bind:group={year} value={y} />{y}</label>
        {/each}
      </div>
      <p class="hint">Sets the drought map, fire perimeters and GLOBE observations. The vegetation layer is a fixed 2019 → 2022 comparison.</p>
    </fieldset>

    <fieldset>
      <legend><label><input type="checkbox" bind:checked={veg} /> Vegetation change</label></legend>
      <div class="sub" class:dim={!veg}>
        <label><input type="radio" bind:group={vegIndex} value="dndvi" disabled={!veg} /> dNDVI — greenness</label>
        <label><input type="radio" bind:group={vegIndex} value="dnbr" disabled={!veg} /> dNBR — moisture-sensitive</label>
        <label><input type="checkbox" bind:checked={vegPatches} disabled={!veg} /> Outline browned patches</label>
        <div class="ramp" aria-hidden="true">
          {#each [-0.4, -0.2, -0.1, 0, 0.1, 0.2, 0.4] as v}<span style="background:{swatch(v)}"></span>{/each}
        </div>
        <div class="ramp-labels"><span>−0.4 loss</span><span>0</span><span>+0.4 gain</span></div>
        <p class="hint">Dry season 2022 minus 2019, 10 m, 1.5 km study area only.
          {#if vegShare !== undefined}<b>{(vegShare * 100).toFixed(1)}%</b> of pixels are below the −0.10 browning threshold.{/if}</p>
      </div>
    </fieldset>

    <fieldset>
      <legend><label><input type="checkbox" bind:checked={drought} /> Drought</label></legend>
      <div class="sub" class:dim={!drought}>
        <ul class="key">
          {#each DM_LABELS as label, i}
            <li class:absent={!droughtCats.includes(i)}><span class="sw" style="background:{DM_COLORS[i]}"></span>{label}</li>
          {/each}
        </ul>
        {#if droughtIndex.find((d) => d.year === year)}
          <p class="hint">Map for the week of {droughtIndex.find((d) => d.year === year).week}.
            {droughtCats.length ? `Present on Maui: ${droughtCats.map((c) => 'D' + c).join(', ')}.` : 'No drought mapped on Maui that week.'}</p>
        {:else}
          <p class="empty">Drought map not available for {year}.</p>
        {/if}
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
        <p class="hint">Locations only — not open/closed status, staffing, or shelter use. Shelters and roads are not shown: no authoritative, current source has been verified.</p>
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
        <label><input type="checkbox" bind:checked={globe} /> <span class="sw dot"></span> GLOBE sites observed in {year}</label>
        {#if obsError}<p class="empty indent">GLOBE observations couldn’t load (needs the GLOBE cache or a connection to api.globe.gov). The other layers are unaffected.</p>
        {:else if globe && !obsThisYear}<p class="empty indent">No GLOBE observations in this area in {year}.</p>{/if}
        <label><input type="checkbox" bind:checked={regions} /> <span class="sw line region"></span> Pukalani, Makawao, Kula</label>
        <label><input type="checkbox" bind:checked={study} /> <span class="sw line dash"></span> Study area (1.5 km)</label>
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
            <p class="rv"><b>{selected.raster.index} = {selected.raster.value.toFixed(3)}</b>
              {selected.raster.browned ? '— below the −0.10 browning threshold' : '— not below the browning threshold'}</p>
          {/if}
          {#if selected.rows.length}
            <dl>{#each selected.rows as [k, v]}<dt>{k}</dt><dd>{v}</dd>{/each}</dl>
          {/if}
          {#if selected.period}<p class="meta"><b>Period:</b> {selected.period}</p>{/if}
          {#if selected.uncertainty}<p class="meta"><b>Uncertainty:</b> {selected.uncertainty}</p>{/if}
          {#if selected.source}<p class="meta"><b>Source:</b> {selected.source}</p>{/if}
          <p class="meta muted">{selected.lat.toFixed(5)}, {selected.lon.toFixed(5)}</p>
          {#each selected.links as l}<a class="btn" href={l.href}>{l.label} →</a>{/each}
        </div>
      {:else}
        <p class="hint">Click any symbol, shaded area or the vegetation layer to see its attributes, period, uncertainty and source.</p>
      {/if}
    </section>
  </aside>

  <div class="mapwrap">
    <div class="map" bind:this={container} role="region" aria-label="Map of Upcountry Maui"></div>
    {#if loading}<div class="state">Loading terrain, vegetation rasters and layers…</div>{/if}
    {#if error}<div class="state err" role="alert">Couldn’t load the map: {error}</div>{/if}
  </div>
</div>

<style>
  .explore { display: grid; grid-template-columns: 360px 1fr; height: 100%; position: relative; }
  aside { overflow-y: auto; padding: 14px 16px 30px; background: var(--card); border-right: 1px solid var(--line); }
  aside h1 { font-size: 1.5rem; margin-bottom: 8px; }
  fieldset { border: 0; border-top: 1px solid var(--line); padding: 10px 0 4px; margin: 10px 0 0; }
  legend { font-weight: 700; color: var(--forest); padding: 0; font-size: .95rem; }
  legend label { display: flex; gap: 6px; align-items: center; }
  .sub { display: flex; flex-direction: column; gap: 3px; padding: 6px 0 0 2px; font-size: .9rem; }
  .sub label { display: flex; gap: 6px; align-items: center; }
  .dim { opacity: .5; }
  .indent { margin-left: 22px; }
  .years { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
  .years label { border: 1px solid var(--line); border-radius: 2px; padding: 2px 8px; font-size: .85rem; cursor: pointer; }
  .years label.on { background: var(--forest); color: #111; border-color: var(--forest); }
  .years input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .years label:focus-within { outline: 3px solid var(--focus); outline-offset: 1px; }
  .hint { font-size: .8rem; color: var(--muted); margin: 4px 0 0; }
  .empty { font-size: .82rem; color: var(--amber); margin: 4px 0 0; }
  .ramp { display: flex; height: 12px; border-radius: 3px; overflow: hidden; margin-top: 6px; border: 1px solid var(--line); }
  .ramp span { flex: 1; }
  .ramp-labels { display: flex; justify-content: space-between; font-size: .72rem; color: var(--muted); }
  .key { list-style: none; padding: 0; margin: 0; font-size: .85rem; }
  .key li { display: flex; gap: 6px; align-items: center; }
  .key li.absent { color: var(--muted); text-decoration: line-through; }
  .sw { width: 14px; height: 12px; border-radius: 2px; display: inline-block; border: 1px solid rgba(0,0,0,.2); flex: none; }
  .sw.line { height: 0; border: 0; border-top: 3px solid; width: 16px; border-radius: 0; }
  .sw.line.fire { border-color: #b3261e; }
  .sw.line.region { border-top: 3px dotted #1f6f73; }
  .sw.line.dash { border-top: 3px dashed #1f2a24; }
  .sw.dot { width: 12px; height: 12px; border-radius: 50%; background: #1f6f73; border: 2px solid #fff; box-shadow: 0 0 0 1px #1f6f73; }
  .kind { font-size: .86rem; }
  .linkish { background: none; border: 0; color: var(--teal); text-decoration: underline; padding: 4px 0; text-align: left; font-size: .88rem; }
  .cardout { margin-top: 14px; }
  .feature { position: relative; padding: 14px 16px; }
  .feature h2 { font-size: 1.2rem; margin: 2px 0 6px; }
  .close { position: absolute; top: 6px; right: 8px; border: 0; background: none; font-size: 1.3rem; color: var(--muted); }
  .rv { background: var(--paper-2); padding: 6px 8px; border-radius: 2px; font-size: .9rem; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; font-size: .86rem; margin: 6px 0; }
  dt { color: var(--muted); text-transform: capitalize; }
  dd { margin: 0; }
  .meta { font-size: .82rem; margin: 4px 0; }
  .feature .btn { margin-top: 8px; font-size: .88rem; }
  .mapwrap { position: relative; }
  .map { position: absolute; inset: 0; }
  .state { position: absolute; inset: 0; display: grid; place-items: center; background: var(--paper); color: var(--muted); }
  .state.err { color: var(--fire); }
  .toggle { display: none; }
  :global(.region-label) {
    font: 700 13px/1 var(--serif); color: #5fb7c2; text-shadow: 0 0 3px #000, 0 0 3px #000;
    pointer-events: none; letter-spacing: .02em;
  }
  @media (max-width: 860px) {
    .explore { grid-template-columns: 1fr; }
    aside { position: absolute; z-index: 3; inset: 44px 0 0 0; display: none; border-right: 0; }
    aside.open { display: block; }
    .toggle { display: block; position: absolute; z-index: 4; top: 8px; left: 8px; background: var(--card);
              border: 1px solid var(--line); border-radius: 2px; padding: .4em .8em; font-weight: 600; }
  }
</style>
