<script>
  // Analysis workspace: interactive figures over the study's own data (the
  // 2019 -> 2022 change rasters, study-area monthly NDVI/NBR) and additional
  // exploratory datasets (gridded rainfall, AWS terrain elevation). Each figure
  // says which it uses. The threshold, index, period and year are shared with
  // the Map Explorer and the 3D view (lib/state.js).
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import PlotPanel from '../components/PlotPanel.svelte';
  import * as api from '../lib/adapters.ts';
  import { loadChangeRaster } from '../lib/raster.ts';
  import { fromUtm } from '../lib/utm.ts';
  import { createSampler } from '../lib/terrarium.js';
  import { getTerrain } from '../lib/api.js';
  import { sampleElevation } from '../lib/geo.js';
  import { monthlyDsci, toCsv } from '../lib/series.js';
  import { countBelow, classify, RESEARCH_THRESHOLD } from '../lib/threshold.js';
  import { binStats, blockShare, climatologyZ, lagPairs, monthlyAnomaly, pearson, rollingSum } from '../lib/analysis.js';
  import { analysis } from '../lib/state.js';
  import { loadBands, remoteManifest } from '../lib/remote.ts';

  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const RAIN = { chirps: 'CHIRPS', terraclimate: 'TerraClimate', imerg: 'IMERG V07', era5land: 'ERA5-Land' };
  const DIVERGING = [[0, '#8c510a'], [0.3, '#d8b365'], [0.5, '#3a4248'], [0.7, '#5ab4ac'], [1, '#01665e']];
  const CLASS_COLOR = { browning: '#d08a3c', stable: '#6e767c', greening: '#40a8a0' };

  let Plotly = null, loading = 'Loading data…', error = null;
  let ndviMap = new Map(), nbrMap = new Map(), dsciMap = new Map(), rainRows = [], rainError = null;
  let rasters = {}, elev = null, elevSource = '', elevError = null, pixels = null;
  // Remote-sensing products (scripts/remote_sensing/): annual Sentinel-2 composites, lidar, WorldCover.
  let annual = null, lidar = null, manifest = {}, rsError = null, cubeStride = 6, baseline = null, island = null, overlays = null, hdrought = null, gauges = [];

  // Shared state
  const s0 = get(analysis);
  let threshold = s0.threshold, index = s0.index, year = s0.year;
  let from = s0.from ?? '2018-12', to = s0.to ?? '2023-12';
  $: analysis.update((s) => ({ ...s, threshold, index, year, from, to }));

  // Local controls
  let lag = 0, rainKey = 'chirps', rainWindow = 3, exaggeration = 2, colourBy = 'value';
  let picks = [];                // compared 100 m blocks

  onMount(async () => {
    try {
      const [mod, dg, weeks, dndvi, dnbr] = await Promise.all([
        import('plotly.js-dist-min'), api.droughtGreenness(), api.droughtWeeks(),
        loadChangeRaster('dndvi'), loadChangeRaster('dnbr'),
      ]);
      Plotly = mod.default ?? mod;
      ndviMap = new Map(dg.indices.ndvi.points.map((p) => [p.month, p.value]));
      nbrMap = new Map(dg.indices.nbr.points.map((p) => [p.month, p.value]));
      dsciMap = monthlyDsci(weeks);
      rasters = { dndvi, dnbr };
      loading = null;
    } catch (e) { error = e.message; loading = null; return; }
    // Exploratory datasets load after the study data, and may fail on their own.
    api.rainfall().then((r) => (rainRows = r.monthly)).catch((e) => (rainError = e.message));
    loadElevation();
    Promise.all([loadBands('s2_aoi_annual'), loadBands('lidar_aoi'), remoteManifest()])
      .then(([a, l, m]) => { annual = a; lidar = l; manifest = m ?? {}; })
      .catch((e) => (rsError = e.message));
    fetch('/api/layers/island-info').then((r) => (r.ok ? r.json() : null)).then((d) => (island = d)).catch(() => (island = null));
    const j = (u) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    j('/api/layers/portal-overlays').then((d) => (overlays = d?.moisture_zones ? d : null));
    j('/api/layers/hawaii-drought').then((d) => (hdrought = d?.available ? d : null));
    j('/api/layers/portal/rain_gauges').then((d) => (gauges = (d?.features ?? []).map((f) => f.properties)));
    api.ndviBaseline().then((b) => (baseline = b?.available ? b : null)).catch(() => (baseline = null))
      .catch((e) => (rsError = e.message));
  });

  /** Pixel centres (lon/lat) of every valid pixel, then their elevation. */
  async function loadElevation() {
    const r = rasters.dndvi, [west, , , north] = r.meta.utmBbox, px = r.meta.pixelMetres;
    const idx = [], lonlat = [], east = [], northing = [];
    for (let row = 0; row < r.meta.height; row++) {
      for (let col = 0; col < r.meta.width; col++) {
        const i = row * r.meta.width + col;
        if (Number.isNaN(r.values[i])) continue;
        const e = west + (col + 0.5) * px, n = north - (row + 0.5) * px;
        const [lat, lon] = fromUtm(e, n, 4);
        idx.push(i); lonlat.push([lon, lat]); east.push(e / 1000); northing.push(n / 1000);
      }
    }
    pixels = { idx, east, north: northing, lonlat };
    try {
      elev = await createSampler().many(lonlat);
      elevSource = 'AWS Terrain Tiles z14 (~9 m), bilinear at each 10 m pixel centre';
    } catch (e) {
      try {
        const t = await getTerrain();
        elev = Float32Array.from(lonlat, ([lon, lat]) => sampleElevation(t.grid, t.meta, lon, lat) ?? NaN);
        elevSource = 'local 68 m DEM grid (terrain tiles unreachable), coarser than the 10 m pixels';
      } catch { elevError = `Elevation unavailable: ${e.message}`; }
    }
  }

  // ---------- derived series ----------
  const inRange = (m) => m >= from && m <= to;
  $: label = index === 'dndvi' ? 'dNDVI' : 'dNBR';
  $: zMap = climatologyZ(ndviMap, [2019, 2021]);
  $: months = [...ndviMap.keys()].sort();
  $: lagged = lagPairs(dsciMap, new Map([...zMap].filter(([m]) => inRange(m))), lag);
  $: fit = pearson(lagged.map((p) => p.x), lagged.map((p) => p.y));
  $: lagTable = [0, 1, 2, 3, 4, 5, 6].map((k) => {
    const pr = lagPairs(dsciMap, new Map([...zMap].filter(([m]) => inRange(m))), k);
    return { lag: k, ...pearson(pr.map((p) => p.x), pr.map((p) => p.y)) };
  });
  $: rainMap = new Map(rainRows.map((r) => [r.month, Number.isFinite(r[rainKey]) ? r[rainKey] : null]));
  $: rainSum = rollingSum(rainMap, rainWindow);
  $: rainAnom = monthlyAnomaly(rainSum);
  $: rainPairs = lagPairs(rainAnom, new Map([...zMap].filter(([m]) => inRange(m))), 0);
  $: rainFit = pearson(rainPairs.map((p) => p.x), rainPairs.map((p) => p.y));
  $: multi = months.filter(inRange).map((m) => ({ month: m, rain: rainSum.get(m) ?? null, dsci: dsciMap.get(m) ?? null, z: zMap.get(m) ?? null }))
    .filter((r) => r.rain !== null && r.dsci !== null && r.z !== null);

  // ---------- figures ----------
  const yearOf = (m) => +m.slice(0, 4);
  const yearMarker = (ms) => ({ color: ms.map(yearOf), colorscale: 'Cividis', cmin: 2018, cmax: 2023, size: 8, line: { width: 0.5, color: '#000' },
    colorbar: { title: { text: 'Year', side: 'right' }, thickness: 10, tickfont: { size: 9 }, outlinewidth: 0 } });

  // 1. NDVI anomaly heatmap
  $: heatYears = [...new Set(months.map(yearOf))];
  $: heat = {
    data: [{ type: 'heatmap', x: MONTHS, y: heatYears.map(String),
      z: heatYears.map((y) => MONTHS.map((_, i) => { const m = `${y}-${String(i + 1).padStart(2, '0')}`; const v = zMap.get(m); return inRange(m) && v !== undefined ? v : null; })),
      customdata: heatYears.map((y) => MONTHS.map((_, i) => ndviMap.get(`${y}-${String(i + 1).padStart(2, '0')}`) ?? null)),
      colorscale: DIVERGING, zmid: 0, zmin: -4, zmax: 4, xgap: 2, ygap: 2,
      texttemplate: '%{z:.1f}', textfont: { size: 9, color: '#e4e8ea' },
      hovertemplate: '%{x} %{y}<br>NDVI anomaly z = %{z:.2f}<br>NDVI = %{customdata:.4f}<extra>Sentinel-2 study area</extra>',
      colorbar: { title: { text: 'z (SD)', side: 'right' }, thickness: 10, outlinewidth: 0 } }],
    layout: { yaxis: { autorange: 'reversed', title: { text: 'Year' }, type: 'category' }, xaxis: { title: { text: 'Month' } } },
  };
  $: heatRows = months.map((m) => ({ month: m, ndvi: ndviMap.get(m), ndvi_anomaly_z: zMap.get(m) === null ? null : +zMap.get(m).toFixed(4) }));

  // 2. DSCI vs NDVI anomaly with lag
  $: xs = lagged.map((p) => p.x);
  $: scatter = {
    data: [
      { type: 'scatter', mode: 'markers', x: xs, y: lagged.map((p) => p.y), text: lagged.map((p) => p.month), marker: yearMarker(lagged.map((p) => p.month)),
        hovertemplate: 'NDVI month %{text}<br>DSCI ' + (lag ? `${lag} mo earlier` : 'same month') + ' = %{x:.1f}<br>NDVI z = %{y:.2f}<extra></extra>', name: 'months' },
      ...(fit.r === null ? [] : [{ type: 'scatter', mode: 'lines', x: [Math.min(...xs), Math.max(...xs)],
        y: [Math.min(...xs), Math.max(...xs)].map((v) => fit.intercept + fit.slope * v), line: { color: '#e07b2c', width: 2, dash: 'dash' }, name: 'least squares', hoverinfo: 'skip' }]),
    ],
    layout: { showlegend: false, xaxis: { title: { text: `Maui County DSCI, monthly mean${lag ? `, ${lag} month${lag > 1 ? 's' : ''} earlier` : ''} (0–500)` } },
      yaxis: { title: { text: 'NDVI anomaly z (SD vs 2019–21)' } },
      annotations: [{ xref: 'paper', yref: 'paper', x: 0.99, y: 0.98, xanchor: 'right', showarrow: false, align: 'right',
        text: fit.r === null ? 'too few months' : `r = ${fit.r.toFixed(3)} · n = ${fit.n}`, font: { family: 'ui-monospace, monospace', size: 12, color: '#e4e8ea' },
        bgcolor: '#0f1215', bordercolor: '#4a555c', borderpad: 4 }] },
  };
  $: lagFig = {
    data: [{ type: 'bar', x: lagTable.map((l) => l.lag), y: lagTable.map((l) => l.r), text: lagTable.map((l) => (l.r === null ? '' : l.r.toFixed(2))), textposition: 'outside',
      marker: { color: lagTable.map((l) => (l.lag === lag ? '#e07b2c' : '#4a555c')) },
      hovertemplate: 'lag %{x} mo<br>r = %{y:.3f}<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Lag: DSCI months before NDVI' }, dtick: 1 }, yaxis: { title: { text: 'Pearson r' }, range: [-1, 0.4] }, margin: { t: 16 } },
  };

  // 3. rainfall anomaly vs NDVI anomaly
  $: rainFig = {
    data: [
      { type: 'scatter', mode: 'markers', x: rainPairs.map((p) => p.x), y: rainPairs.map((p) => p.y), text: rainPairs.map((p) => p.month),
        marker: yearMarker(rainPairs.map((p) => p.month)),
        hovertemplate: '%{text}<br>' + `${rainWindow}-month ${RAIN[rainKey]} anomaly` + ' = %{x:.0f} mm<br>NDVI z = %{y:.2f}<extra></extra>' },
      ...(rainFit.r === null ? [] : (() => { const rx = rainPairs.map((p) => p.x); const lo = Math.min(...rx), hi = Math.max(...rx);
        return [{ type: 'scatter', mode: 'lines', x: [lo, hi], y: [lo, hi].map((v) => rainFit.intercept + rainFit.slope * v), line: { color: '#e07b2c', width: 2, dash: 'dash' }, hoverinfo: 'skip' }]; })()),
    ],
    layout: { showlegend: false, xaxis: { title: { text: `${rainWindow}-month ${RAIN[rainKey]} rainfall anomaly (mm vs the same months 2018–24)` }, zeroline: true },
      yaxis: { title: { text: 'NDVI anomaly z (SD)' } },
      annotations: [{ xref: 'paper', yref: 'paper', x: 0.01, y: 0.98, xanchor: 'left', showarrow: false,
        text: rainFit.r === null ? 'no overlapping months' : `r = ${rainFit.r.toFixed(3)} · n = ${rainFit.n}`, font: { family: 'ui-monospace, monospace', size: 12, color: '#e4e8ea' },
        bgcolor: '#0f1215', bordercolor: '#4a555c', borderpad: 4 }] },
  };

  // 4. multivariable 3D
  $: multiFig = {
    data: [{ type: 'scatter3d', mode: 'markers', x: multi.map((r) => r.rain), y: multi.map((r) => r.dsci), z: multi.map((r) => r.z), text: multi.map((r) => r.month),
      marker: { ...yearMarker(multi.map((r) => r.month)), size: 5 },
      hovertemplate: '%{text}<br>rain %{x:.0f} mm<br>DSCI %{y:.0f}<br>NDVI z %{z:.2f}<extra></extra>' }],
    layout: { margin: { l: 0, r: 0, t: 0, b: 0 }, scene: {
      xaxis: { title: { text: `${rainWindow}-mo ${RAIN[rainKey]} (mm)` } }, yaxis: { title: { text: 'DSCI (0–500)' } }, zaxis: { title: { text: 'NDVI z (SD)' } },
      camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } } } },
  };

  // 5. distributions
  $: boxFig = {
    data: heatYears.map((y) => ({ type: 'box', name: String(y), y: months.filter((m) => yearOf(m) === y && inRange(m)).map((m) => ndviMap.get(m)),
      boxpoints: 'all', jitter: 0.4, pointpos: 0, marker: { size: 4, color: y === 2022 ? '#e07b2c' : '#8a959c' }, line: { color: y === 2022 ? '#e07b2c' : '#b3bcc1', width: 1.2 },
      fillcolor: 'rgba(0,0,0,0)', hovertemplate: '%{y:.4f}<extra>' + y + '</extra>' })),
    layout: { showlegend: false, yaxis: { title: { text: 'Monthly mean NDVI, study area' } }, xaxis: { title: { text: 'Year (each point = one month)' } } },
  };
  function binned(values, lo = -0.6, hi = 0.4, w = 0.01) {
    const n = Math.round((hi - lo) / w), c = new Array(n).fill(0);
    for (const v of values) if (!Number.isNaN(v)) c[Math.max(0, Math.min(n - 1, Math.floor((v - lo) / w)))]++;
    return { x: c.map((_, i) => +(lo + (i + 0.5) * w).toFixed(3)), y: c };
  }
  $: distFig = rasters.dndvi ? {
    data: ['dndvi', 'dnbr'].map((k, i) => { const b = binned(rasters[k].values); return { type: 'scatter', mode: 'lines', line: { shape: 'hvh', color: i ? '#5ab4ac' : '#e07b2c', width: 1.6, dash: i ? 'dot' : 'solid' },
      x: b.x, y: b.y, name: k === 'dndvi' ? 'dNDVI' : 'dNBR', hovertemplate: '%{x:.2f}: %{y} px<extra>' + (k === 'dndvi' ? 'dNDVI' : 'dNBR') + '</extra>' }; }),
    layout: { xaxis: { title: { text: 'Change, 2022 − 2019 dry season (0.01 bins)' } }, yaxis: { title: { text: 'Pixels (10 m)' } },
      shapes: [{ type: 'line', x0: threshold, x1: threshold, yref: 'paper', y0: 0, y1: 1, line: { color: '#e4e8ea', dash: 'dash', width: 1 } }],
      legend: { y: 1.12, x: 0 } } } : null;

  // 6. elevation vs change
  $: vals = rasters[index] && pixels ? Float32Array.from(pixels.idx, (i) => rasters[index].values[i]) : null;
  // Loops, not Math.min(...array): 70,280 arguments can overflow the call stack.
  function extent(arr) {
    let lo = Infinity, hi = -Infinity;
    for (const v of arr) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
    return [lo, hi];
  }
  $: bands = elev && vals ? (() => {
    const [e0, e1] = extent(elev);
    const lo = Math.floor(e0 / 20) * 20, hi = Math.ceil(e1 / 20) * 20;
    const edges = []; for (let e = lo; e <= hi; e += 20) edges.push(e);
    return binStats(elev, vals, edges, threshold);
  })() : [];
  $: elevFig = elev && vals ? {
    data: [
      { type: 'histogram2d', x: elev, y: vals, nbinsx: 60, nbinsy: 60, ybins: { start: -0.6, end: 0.4, size: 0.02 },
        colorscale: [[0, '#151a1e'], [0.0001, '#1f2a33'], [0.3, '#3e6b78'], [0.7, '#8fc1c4'], [1, '#f4f7f7']], zsmooth: false,
        colorbar: { title: { text: 'Pixels', side: 'right' }, thickness: 10, outlinewidth: 0, x: 1.08 },
        hovertemplate: 'elev %{x} m<br>' + label + ' %{y}<br>%{z} px<extra></extra>' },
      { type: 'scatter', mode: 'lines+markers', x: bands.map((b) => (b.lo + b.hi) / 2), y: bands.map((b) => b.median), name: `median ${label} per 20 m band`,
        line: { color: '#e07b2c', width: 2 }, marker: { size: 5, symbol: 'square' }, hovertemplate: '%{x} m band: median %{y:.3f}<extra></extra>' },
      { type: 'bar', x: bands.map((b) => (b.lo + b.hi) / 2), y: bands.map((b) => (b.shareBelow === null ? null : b.shareBelow * 100)), yaxis: 'y2', name: `% below ${threshold.toFixed(2)}`,
        marker: { color: 'rgba(224,123,44,0.25)', line: { color: '#e07b2c', width: 1 } }, width: 18, customdata: bands.map((b) => b.n),
        hovertemplate: '%{x} m band: %{y:.1f}% browned (n=%{customdata})<extra></extra>' },
    ],
    layout: { barmode: 'overlay', xaxis: { title: { text: 'Elevation (m)' } }, yaxis: { title: { text: `${label} (10 m pixel)` }, range: [-0.6, 0.4] },
      yaxis2: { title: { text: `% of band below ${threshold.toFixed(2)}` }, overlaying: 'y', side: 'right', range: [0, 100], showgrid: false },
      margin: { r: 90 }, legend: { y: -0.25 } },
  } : null;
  $: bandRows = bands.map((b) => ({ band_m: `${b.lo}-${b.hi}`, pixels: b.n, [`median_${index}`]: b.median === null ? null : +b.median.toFixed(4), share_below_threshold: b.shareBelow === null ? null : +b.shareBelow.toFixed(4) }));

  // 7. 3D pixel terrain (every 2nd pixel each way)
  $: cloud = elev && vals ? (() => {
    const keep = []; const W = rasters.dndvi.meta.width;
    pixels.idx.forEach((i, k) => { if ((i % W) % 2 === 0 && Math.floor(i / W) % 2 === 0 && Number.isFinite(elev[k])) keep.push(k); });
    return keep;
  })() : [];
  $: zRange = cloud.length ? extent(cloud.map((k) => elev[k])) : [0, 1];
  $: cloudFig = cloud.length ? {
    data: [{ type: 'scatter3d', mode: 'markers', x: cloud.map((k) => pixels.east[k]), y: cloud.map((k) => pixels.north[k]), z: cloud.map((k) => elev[k]),
      customdata: cloud.map((k) => vals[k]),
      marker: colourBy === 'value'
        ? { size: 2, color: cloud.map((k) => vals[k]), colorscale: DIVERGING, cmin: -0.4, cmax: 0.4, colorbar: { title: { text: label, side: 'right' }, thickness: 10, outlinewidth: 0 } }
        : { size: 2, color: cloud.map((k) => CLASS_COLOR[classify(vals[k], threshold)]) },
      hovertemplate: 'E %{x:.2f} km · N %{y:.2f} km<br>%{z:.0f} m<br>' + label + ' %{customdata:.3f}<extra></extra>' }],
    layout: { margin: { l: 0, r: 0, t: 0, b: 0 }, scene: {
      xaxis: { title: { text: 'Easting (km, UTM 4N)' } }, yaxis: { title: { text: 'Northing (km)' } }, zaxis: { title: { text: 'Elevation (m)' } },
      aspectmode: 'manual', aspectratio: { x: 1, y: 1, z: Math.max(0.05, ((zRange[1] - zRange[0]) / 3000) * exaggeration) },
      camera: { eye: { x: 0.75, y: -0.95, z: 0.55 } } } },
  } : null;

  // 8. spatial browning density (100 m blocks)
  $: grid = rasters[index] ? blockShare(rasters[index].values, rasters[index].meta.width, rasters[index].meta.height, 10, threshold) : null;
  $: gx = grid ? Array.from({ length: grid.cols }, (_, c) => +((rasters[index].meta.utmBbox[0] + (c + 0.5) * 100) / 1000).toFixed(3)) : [];
  $: gy = grid ? Array.from({ length: grid.rows }, (_, r) => +((rasters[index].meta.utmBbox[3] - (r + 0.5) * 100) / 1000).toFixed(3)) : [];
  $: densFig = grid ? {
    data: [{ type: 'heatmap', x: gx, y: gy, z: grid.z.map((row) => row.map((v) => (v === null ? null : v * 100))),
      colorscale: [[0, '#1d2328'], [0.25, '#5a3d1e'], [0.5, '#9a5a1e'], [0.75, '#d08a3c'], [1, '#f6c478']], zmin: 0, zmax: 100, xgap: 1, ygap: 1,
      colorbar: { title: { text: '% browned', side: 'right' }, thickness: 10, outlinewidth: 0 },
      hovertemplate: 'E %{x:.2f} · N %{y:.2f} km<br>%{z:.0f}% of pixels below ' + threshold.toFixed(2) + '<extra>100 m block</extra>' },
      { type: 'scatter', mode: 'markers+text', x: picks.map((p) => p.e), y: picks.map((p) => p.n), text: picks.map((_, i) => String(i + 1)), textposition: 'top center',
        textfont: { color: '#fff', size: 12 }, marker: { symbol: 'square-open', size: 14, color: '#fff', line: { width: 2 } }, hoverinfo: 'skip' }],
    layout: { showlegend: false, xaxis: { title: { text: 'Easting (km, UTM 4N)' }, scaleanchor: 'y', constrain: 'domain' }, yaxis: { title: { text: 'Northing (km)' } } },
  } : null;
  $: densRows = grid ? grid.z.flatMap((row, r) => row.map((v, c) => ({ easting_km: gx[c], northing_km: gy[r], share_below: v === null ? null : +v.toFixed(4) }))) : [];

  function pickBlock(pt) {
    if (!pt || pt.data?.type !== 'heatmap' || picks.length >= 6) return;
    const c = gx.indexOf(pt.x), r = gy.indexOf(pt.y);
    if (c < 0 || r < 0) return;
    const W = rasters.dndvi.meta.width, H = rasters.dndvi.meta.height;
    const vi = [], vb = [], el = [];
    const pos = elev ? new Map(pixels.idx.map((i, k) => [i, k])) : null;
    for (let rr = r * 10; rr < Math.min(H, (r + 1) * 10); rr++) for (let cc = c * 10; cc < Math.min(W, (c + 1) * 10); cc++) {
      const i = rr * W + cc;
      if (Number.isNaN(rasters.dndvi.values[i])) continue;
      vi.push(rasters.dndvi.values[i]); vb.push(rasters.dnbr.values[i]);
      if (pos?.has(i)) el.push(elev[pos.get(i)]);
    }
    if (!vi.length) return;
    const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
    const [lat, lon] = fromUtm(pt.x * 1000, pt.y * 1000, 4);
    picks = [...picks, { e: pt.x, n: pt.y, lat, lon, pixels: vi.length, dndvi: mean(vi), dnbr: mean(vb),
      browned: countBelow(Float32Array.from(index === 'dndvi' ? vi : vb), threshold).share, elevation: el.length ? mean(el.filter(Number.isFinite)) : null }];
  }
  $: pickRows = picks.map((p, i) => ({ location: i + 1, lat: +p.lat.toFixed(5), lon: +p.lon.toFixed(5), pixels: p.pixels,
    mean_dndvi: +p.dndvi.toFixed(4), mean_dnbr: +p.dnbr.toFixed(4), [`share_${index}_below_${threshold.toFixed(2)}`]: +p.browned.toFixed(4),
    mean_elevation_m: p.elevation === null ? null : +p.elevation.toFixed(1) }));
  function savePicks() {
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([toCsv(pickRows, Object.keys(pickRows[0]))], { type: 'text/csv' })), download: 'compared_locations.csv' });
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ---------- remote sensing ----------
  $: aYears = annual ? Object.keys(manifest?.sentinel2?.products ?? {}).filter((k) => k.startsWith('aoi_')).map((k) => +k.slice(4)).sort() : [];
  $: nY = aYears.length;
  // Independent check: this pipeline's 2022 - 2019 dNDVI vs the study raster, pixel by pixel.
  $: check = annual && rasters.dndvi && nY ? (() => {
    const a19 = annual.bands[aYears.indexOf(2019)], a22 = annual.bands[aYears.indexOf(2022)], st = rasters.dndvi.values;
    const x = [], y = [];
    for (let i = 0; i < st.length; i++) { const m = a22[i] - a19[i]; if (Number.isFinite(m) && !Number.isNaN(st[i])) { x.push(st[i]); y.push(m); } }
    return { x, y, fit: pearson(x, y) };
  })() : null;
  $: checkFig = check ? {
    data: [{ type: 'histogram2d', x: check.x, y: check.y, xbins: { start: -0.6, end: 0.4, size: 0.01 }, ybins: { start: -0.6, end: 0.4, size: 0.01 },
      colorscale: [[0, '#151a1e'], [0.0001, '#1f2a33'], [0.3, '#3e6b78'], [0.7, '#8fc1c4'], [1, '#f4f7f7']],
      colorbar: { title: { text: 'Pixels', side: 'right' }, thickness: 10, outlinewidth: 0 }, hovertemplate: 'study %{x}<br>pipeline %{y}<br>%{z} px<extra></extra>' },
      { type: 'scatter', mode: 'lines', x: [-0.6, 0.4], y: [-0.6, 0.4], line: { color: '#e4e8ea', dash: 'dot', width: 1 }, hoverinfo: 'skip', name: '1:1' }],
    layout: { showlegend: false, xaxis: { title: { text: 'Study dNDVI (Earth Engine export)' }, range: [-0.6, 0.4] },
      yaxis: { title: { text: 'This pipeline dNDVI (AWS Sentinel-2)' }, range: [-0.6, 0.4], scaleanchor: 'x' },
      shapes: [{ type: 'line', x0: -0.1, x1: -0.1, y0: -0.6, y1: 0.4, line: { color: '#e07b2c', dash: 'dash', width: 1 } },
               { type: 'line', y0: -0.1, y1: -0.1, x0: -0.6, x1: 0.4, line: { color: '#e07b2c', dash: 'dash', width: 1 } }],
      annotations: [{ xref: 'paper', yref: 'paper', x: 0.02, y: 0.98, xanchor: 'left', showarrow: false, align: 'left',
        text: `r = ${check.fit.r?.toFixed(3)} · n = ${check.fit.n.toLocaleString()}`, font: { family: 'ui-monospace, monospace', size: 12, color: '#e4e8ea' },
        bgcolor: '#0f1215', bordercolor: '#4a555c', borderpad: 4 }] },
  } : null;

  // Space-time: every year's pixel distribution, and a cube of (easting, northing, year).
  $: yearDist = annual && nY ? {
    data: aYears.map((y, k) => ({ type: 'violin', name: String(y), y: Array.from(annual.bands[k]).filter(Number.isFinite), points: false,
      box: { visible: true, width: 0.15 }, meanline: { visible: false }, line: { color: y === 2022 ? '#e07b2c' : y === 2019 ? '#5ab4ac' : '#8a959c', width: 1 },
      fillcolor: 'rgba(0,0,0,0)', spanmode: 'hard', hoverinfo: 'y' })),
    layout: { showlegend: false, yaxis: { title: { text: 'Dry-season NDVI per 10 m pixel' }, range: [-0.05, 0.9] }, xaxis: { title: { text: 'Year (May–Sep median)' } } },
  } : null;
  $: cube = annual && nY ? (() => {
    const W = annual.width, H = annual.height, [w, , , n] = annual.bounds;
    const x = [], y = [], z = [], c = [];
    for (let k = 0; k < nY; k++) for (let row = 0; row < H; row += cubeStride) for (let col = 0; col < W; col += cubeStride) {
      const v = annual.bands[k][row * W + col];
      if (!Number.isFinite(v)) continue;
      x.push((w + (col + 0.5) * 10) / 1000); y.push((n - (row + 0.5) * 10) / 1000); z.push(aYears[k]); c.push(v);
    }
    return { x, y, z, c };
  })() : null;
  $: cubeFig = cube ? {
    data: [{ type: 'scatter3d', mode: 'markers', x: cube.x, y: cube.y, z: cube.z,
      marker: { size: 2.2, symbol: 'square', color: cube.c, colorscale: [[0, '#8c510a'], [0.25, '#d8b365'], [0.44, '#f6e8c3'], [0.62, '#80cdc1'], [0.81, '#35978f'], [1, '#01665e']], cmin: 0, cmax: 0.8,
        colorbar: { title: { text: 'NDVI', side: 'right' }, thickness: 10, outlinewidth: 0 } },
      hovertemplate: 'E %{x:.2f} · N %{y:.2f} km<br>%{z}: NDVI %{marker.color:.3f}<extra></extra>' }],
    layout: { margin: { l: 0, r: 0, t: 0, b: 0 }, scene: { xaxis: { title: { text: 'Easting (km, UTM 4N)' } }, yaxis: { title: { text: 'Northing (km)' } },
      zaxis: { title: { text: 'Dry season (year)' }, dtick: 1 }, aspectmode: 'manual', aspectratio: { x: 1, y: 1, z: 1.3 }, camera: { eye: { x: 1.5, y: -1.5, z: 0.7 } } } },
  } : null;

  // Land cover and canopy height vs the study's browning.
  $: lcRows = manifest?.worldcover?.study_area ?? [];
  $: lcFig = lcRows.length ? {
    data: [{ type: 'bar', orientation: 'h', y: lcRows.map((r) => r.name), x: lcRows.map((r) => r['share_browned_dndvi_lt_-0.10'] * 100),
      marker: { color: lcRows.map((r) => r.colour), line: { color: '#000', width: 1 } }, customdata: lcRows.map((r) => [r.pixels, (r.share_of_study_area * 100).toFixed(1), r.median_dndvi]),
      text: lcRows.map((r) => `${(r['share_browned_dndvi_lt_-0.10'] * 100).toFixed(0)}% · ${(r.share_of_study_area * 100).toFixed(1)}% of area`), textposition: 'outside',
      hovertemplate: '%{y}<br>%{x:.1f}% browned (dNDVI < −0.10)<br>%{customdata[0]} px = %{customdata[1]}% of the study area<br>median dNDVI %{customdata[2]}<extra></extra>' }],
    layout: { xaxis: { title: { text: '% of the class’s pixels with study dNDVI < −0.10' }, range: [0, 110] }, yaxis: { autorange: 'reversed' }, margin: { l: 150 } },
  } : null;
  const CHM_BINS = [[0, 0.5, '< 0.5 m'], [0.5, 2, '0.5–2 m'], [2, 5, '2–5 m'], [5, 10, '5–10 m'], [10, 99, '> 10 m']];
  $: chmStats = lidar && rasters[index] ? (() => {
    // Mean canopy height of the 5 x 5 lidar cells (2 m) inside each 10 m study pixel: the grids share an origin.
    const L = lidar.width, v = rasters[index].values, W = rasters[index].meta.width, H = rasters[index].meta.height;
    const bins = CHM_BINS.map(([lo, hi, name]) => ({ lo, hi, name, vals: [] }));
    for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) {
      const val = v[r * W + c];
      if (Number.isNaN(val)) continue;
      let sum = 0, cnt = 0;
      for (let dr = 0; dr < 5; dr++) for (let dc = 0; dc < 5; dc++) {
        const h = lidar.bands[1][(r * 5 + dr) * L + c * 5 + dc];
        if (Number.isFinite(h)) { sum += h / 100; cnt++; }
      }
      if (cnt < 13) continue;                   // need most of the 10 m pixel measured
      const h = sum / cnt;
      bins.find((b) => h >= b.lo && h < b.hi)?.vals.push(val);
    }
    return bins.map((b) => ({ name: b.name, n: b.vals.length, browned: b.vals.length ? countBelow(Float32Array.from(b.vals), threshold).share : null,
      vals: b.vals }));
  })() : [];
  $: chmFig = chmStats.length ? {
    data: [{ type: 'box', x: chmStats.flatMap((b) => b.vals.map(() => b.name)), y: chmStats.flatMap((b) => b.vals), boxpoints: false,
      line: { color: '#5ec962', width: 1.2 }, fillcolor: 'rgba(0,0,0,0)', name: label, hoverinfo: 'y' },
      { type: 'scatter', mode: 'markers+text', x: chmStats.map((b) => b.name), y: chmStats.map((b) => (b.browned === null ? null : b.browned * 100)), yaxis: 'y2',
        marker: { symbol: 'square', size: 10, color: '#e07b2c' }, text: chmStats.map((b) => (b.browned === null ? '' : `${(b.browned * 100).toFixed(0)}%`)),
        textposition: 'middle right', textfont: { color: '#e07b2c' }, name: `% below ${threshold.toFixed(2)}`, customdata: chmStats.map((b) => b.n),
        hovertemplate: '%{x}: %{y:.1f}% browned (n=%{customdata})<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Lidar height above ground, mean over the 10 m pixel (Feb–Mar 2023)' }, categoryorder: 'array', categoryarray: CHM_BINS.map((b) => b[2]) },
      yaxis: { title: { text: `${label} 2019 → 2022` }, range: [-0.6, 0.4] },
      yaxis2: { title: { text: `% below ${threshold.toFixed(2)}` }, overlaying: 'y', side: 'right', range: [0, 100], showgrid: false }, margin: { r: 70 }, legend: { y: -0.3 } },
  } : null;

  // 26 years of Landsat (study-area mean of per-pixel dry-season medians) with the
  // Sentinel-2 study-area means for the overlapping years: a cross-sensor check.
  $: s2Means = annual && nY ? aYears.map((y, k) => { const v = Array.from(annual.bands[k]).filter(Number.isFinite); return { year: y, ndvi: v.reduce((a, b) => a + b, 0) / v.length }; }) : [];
  $: lsFig = baseline ? {
    data: [
      { type: 'scatter', mode: 'lines', x: [baseline.normal.years[0] - 0.5, baseline.normal.years[1] + 0.5], y: [baseline.normal.mean, baseline.normal.mean],
        line: { color: '#8a959c', dash: 'dot', width: 1 }, name: `2000–2018 normal ${baseline.normal.mean.toFixed(3)}`, hoverinfo: 'skip' },
      { type: 'scatter', mode: 'lines+markers', x: baseline.rows.map((r) => r.year), y: baseline.rows.map((r) => r.ndvi), name: 'Landsat 5/7/8/9, 30 m',
        line: { color: '#5ab4ac', width: 2 }, marker: { symbol: 'square', size: baseline.rows.map((r) => (r.year === 2022 ? 11 : 7)), color: baseline.rows.map((r) => (r.year === 2022 ? '#e07b2c' : '#5ab4ac')) },
        customdata: baseline.rows.map((r) => [r.z, r.rank_lowest, r.n_scenes, r.sensors]),
        hovertemplate: '%{x}: NDVI %{y:.3f}<br>z %{customdata[0]} · rank %{customdata[1]} lowest<br>%{customdata[2]} scenes (%{customdata[3]})<extra>Landsat</extra>' },
      { type: 'scatter', mode: 'lines+markers', x: s2Means.map((r) => r.year), y: s2Means.map((r) => r.ndvi), name: 'Sentinel-2, 10 m',
        line: { color: '#e4e8ea', width: 1.5, dash: 'dash' }, marker: { symbol: 'diamond', size: 6, color: '#e4e8ea' }, hovertemplate: '%{x}: NDVI %{y:.3f}<extra>Sentinel-2</extra>' }],
    layout: { xaxis: { title: { text: 'Dry season (May–Sep)' }, dtick: 2 }, yaxis: { title: { text: 'Study-area mean NDVI' } }, legend: { y: -0.25 } },
  } : null;

  // Burn severity of the Aug 2023 fires and surface temperature (scripts/remote_sensing/).
  const SEV = [['Low', '#f3d250'], ['Moderate-low', '#ef9a3b'], ['Moderate-high', '#d4442c'], ['High', '#7b1d6a']];
  $: fires = manifest?.burn_severity?.fires ?? [];
  $: sevFig = fires.length ? {
    data: SEV.map(([name, col]) => ({ type: 'bar', orientation: 'h', name, y: fires.map((f) => f.name), x: fires.map((f) => f.class_ha[name]),
      marker: { color: col, line: { color: '#000', width: 1 } }, hovertemplate: '%{y}: %{x:.0f} ha ' + name + '<extra></extra>' })),
    layout: { barmode: 'stack', xaxis: { title: { text: 'Hectares burned, by severity (Sentinel-2 dNBR, 20 m)' } }, legend: { y: -0.3 }, margin: { l: 70 } },
  } : null;
  const PRIOR = ['< −0.20', '−0.20 to −0.10', '−0.10 to 0', '> 0'];
  $: priorFig = fires.length ? {
    data: fires.map((f, k) => ({ type: 'bar', name: f.name, x: PRIOR, y: f.by_prior_browning.map((b) => (b.share_moderate_or_high === null ? null : b.share_moderate_or_high * 100)),
      customdata: f.by_prior_browning.map((b) => [b.pixels, b.mean_dnbr]), marker: { color: ['#5ab4ac', '#e07b2c', '#b3bcc1'][k % 3], line: { color: '#000', width: 1 } },
      hovertemplate: f.name + ', dNDVI %{x}: %{y:.0f}% moderate or worse<br>%{customdata[0]} px, mean dNBR %{customdata[1]}<extra></extra>' })),
    layout: { barmode: 'group', xaxis: { title: { text: 'Regional dNDVI 2019 → 2022 inside the perimeter (browning →  ← greening)' } },
      yaxis: { title: { text: '% of pixels burned moderate or worse' }, range: [0, 100] }, legend: { y: -0.3 } },
  } : null;
  $: lst = manifest?.lst ?? [];
  function padRange(v) {
    const f = v.filter(Number.isFinite), lo = Math.min(...f), hi = Math.max(...f), pad = (hi - lo) * 0.08 || 1;
    return [lo - pad, hi + pad];
  }
  $: lstFig = lst.length ? {
    data: [
      { type: 'scatter', mode: 'lines+markers', name: 'Surface temperature (°C)', x: lst.map((r) => r.year), y: lst.map((r) => r.lst_c),
        line: { color: '#ef9a3b', width: 2 }, marker: { symbol: 'square', size: lst.map((r) => (r.year === 2022 ? 11 : 7)) },
        customdata: lst.map((r) => [r.n_scenes, r.sensors]), hovertemplate: '%{x}: %{y:.1f} °C<br>%{customdata[0]} scenes (%{customdata[1]})<extra></extra>' },
      ...(baseline ? [{ type: 'scatter', mode: 'lines+markers', name: 'NDVI (Landsat)', yaxis: 'y2', x: baseline.rows.filter((r) => r.year >= lst[0].year).map((r) => r.year),
        y: baseline.rows.filter((r) => r.year >= lst[0].year).map((r) => r.ndvi), line: { color: '#5ab4ac', width: 1.5, dash: 'dash' }, marker: { size: 6 },
        hovertemplate: '%{x}: NDVI %{y:.3f}<extra></extra>' }] : [])],
    // Explicit ranges: this chart renders before its data arrives, and Plotly.react
    // otherwise keeps the empty-plot default ranges.
    layout: { xaxis: { title: { text: 'Dry season (May–Sep)' }, dtick: 1, range: [lst[0].year - 0.5, lst[lst.length - 1].year + 0.5] },
      yaxis: { title: { text: 'Land surface temperature, °C' }, range: padRange(lst.map((r) => r.lst_c)) },
      yaxis2: { title: { text: 'NDVI' }, overlaying: 'y', side: 'right', showgrid: false, tickformat: '.2f',
        range: baseline ? padRange(baseline.rows.filter((r) => r.year >= lst[0].year).map((r) => r.ndvi)) : undefined },
      legend: { y: -0.3 }, margin: { r: 60 } },
  } : null;
  $: lstNdvi = lst.length && baseline ? (() => {
    const pairs = lst.map((r) => [r.lst_c, baseline.rows.find((b) => b.year === r.year)?.ndvi]).filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));
    return pearson(pairs.map((p) => p[0]), pairs.map((p) => p[1]));
  })() : null;

  // Whole island (scripts/remote_sensing/island_annual.py): medians and spread per year, by elevation zone.
  $: iYears = island ? Object.keys(island.years).map(Number).sort((a, b) => a - b) : [];
  $: islandFig = iYears.length ? {
    data: ['ndvi', 'nbr'].flatMap((k, j) => {
      const col = j ? '#ef9a3b' : '#5ab4ac', st = iYears.map((y) => island.years[y][k]);
      return [
        { type: 'scatter', mode: 'lines', x: [...iYears, ...[...iYears].reverse()], y: [...st.map((v) => v.p75), ...[...st].reverse().map((v) => v.p25)], fill: 'toself',
          fillcolor: j ? 'rgba(239,154,59,0.15)' : 'rgba(90,180,172,0.18)', line: { width: 0 }, hoverinfo: 'skip', name: `${k.toUpperCase()} middle 50 %` },
        { type: 'scatter', mode: 'lines+markers', x: iYears, y: st.map((v) => v.median), name: `${k.toUpperCase()} island median`, line: { color: col, width: 2 },
          marker: { symbol: 'square', size: iYears.map((y) => (y === 2022 ? 10 : 6)) },
          customdata: iYears.map((y) => [island.years[y].scenes, island.years[y].clear_obs_median]),
          hovertemplate: `%{x}: ${k.toUpperCase()} %{y:.3f}<br>%{customdata[0]} scenes · %{customdata[1]} clear looks/pixel<extra></extra>` }];
    }),
    layout: { xaxis: { title: { text: 'Dry season (May–Sep)' }, dtick: 1, range: [iYears[0] - 0.5, iYears[iYears.length - 1] + 0.5] },
      yaxis: { title: { text: 'Index value, all of Maui (60 m)' }, range: [0, 0.85] }, legend: { y: -0.3 } },
  } : null;
  $: zoneFig = iYears.length ? {
    data: [{ type: 'heatmap', x: iYears.map(String), y: island.zones.map(([a, b]) => `${a}–${b} m`),
      z: island.zones.map((_, zi) => iYears.map((y) => island.years[y].zones[zi].ndvi?.median ?? null)),
      colorscale: [[0, '#8c510a'], [0.25, '#d8b365'], [0.44, '#f6e8c3'], [0.62, '#80cdc1'], [0.81, '#35978f'], [1, '#01665e']], zmin: 0, zmax: 0.8,
      texttemplate: '%{z:.2f}', textfont: { size: 10, color: '#111' }, xgap: 2, ygap: 2,
      colorbar: { title: { text: 'NDVI', side: 'right' }, thickness: 10, outlinewidth: 0 }, hovertemplate: '%{y}, %{x}: median NDVI %{z:.3f}<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Dry season' }, type: 'category' }, yaxis: { title: { text: 'Elevation zone (Copernicus DEM)' } }, margin: { l: 90 } },
  } : null;
  $: changeZones = island?.change_2019_2022_by_zone ?? [];
  $: zoneChangeFig = changeZones.length ? {
    data: [{ type: 'bar', x: changeZones.map((z) => `${z.zone_m[0]}–${z.zone_m[1]} m`), y: changeZones.map((z) => z['share_below_-0.10'] * 100),
      marker: { color: '#d08a3c', line: { color: '#000', width: 1 } }, text: changeZones.map((z) => `${(z['share_below_-0.10'] * 100).toFixed(0)}%`), textposition: 'outside',
      customdata: changeZones.map((z) => [z.median, z.n]), hovertemplate: '%{x}: %{y:.1f}% browned (dNDVI < −0.10)<br>median change %{customdata[0]}<br>%{customdata[1]} px<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Elevation zone' } }, yaxis: { title: { text: '% of land with dNDVI 2019 → 2022 < −0.10' }, range: [0, 100] } },
  } : null;

  // Hawaii state layers x our satellite results (scripts/remote_sensing/portal_overlays.py).
  const ZONE_COL = { Arid: '#8c510a', 'Very Dry': '#bf812d', 'Moderately Dry': '#dfc27d', 'Seasonal Mesic': '#c7eae5', 'Moist Mesic': '#80cdc1', 'Moderately Wet': '#35978f', 'Very Wet': '#01665e' };
  $: mz = overlays?.moisture_zones ?? [];
  $: studyZones = overlays?.study_area?.moisture_zone_share ?? {};
  $: moistFig = mz.length ? {
    data: [{ type: 'bar', x: mz.map((z) => z.zone), y: mz.map((z) => z.share_browned * 100), text: mz.map((z) => `${(z.share_browned * 100).toFixed(0)}%`), textposition: 'outside',
      marker: { color: mz.map((z) => ZONE_COL[z.zone]), line: { color: mz.map((z) => (studyZones[z.zone] > 0 ? '#e07b2c' : '#000')), width: mz.map((z) => (studyZones[z.zone] > 0 ? 3 : 1)) } },
      customdata: mz.map((z) => [z.area_km2, z.median_change, z.ndvi_2019, z.ndvi_2022]),
      hovertemplate: '%{x}: %{y:.1f}% browned<br>%{customdata[0]} km² · NDVI %{customdata[2]} → %{customdata[3]}<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Moisture zone (driest → wettest)' }, tickangle: -20 }, yaxis: { title: { text: '% of land with dNDVI 2019 → 2022 < −0.10' }, range: [0, 70] }, margin: { b: 80 } },
  } : null;
  $: plantFig = overlays?.plantation_within_moisture_zone ? {
    data: [['plantation', 'Former sugarcane / pineapple', '#c28f2c'], ['other', 'Never in plantation', '#6e767c']].map(([k, name, col]) => ({
      type: 'bar', name, x: overlays.plantation_within_moisture_zone.map((z) => z.zone), y: overlays.plantation_within_moisture_zone.map((z) => (z[k].share_browned ?? null) === null ? null : z[k].share_browned * 100),
      customdata: overlays.plantation_within_moisture_zone.map((z) => z[k].pixels), marker: { color: col, line: { color: '#000', width: 1 } },
      hovertemplate: `%{x}, ${name}: %{y:.1f}% browned (%{customdata} px)<extra></extra>` })),
    layout: { barmode: 'group', xaxis: { title: { text: 'Moisture zone' }, tickangle: -20 }, yaxis: { title: { text: '% browned 2019 → 2022' }, range: [0, 70] }, legend: { y: -0.4 }, margin: { b: 90 } },
  } : null;
  const RATINGS = ['High', 'Medium', 'Low', 'Not rated'], RCOL = { High: '#d4442c', Medium: '#ef9a3b', Low: '#f3d250', 'Not rated': '#6e767c' };
  $: ratingFig = overlays?.fire_risk_rating ? {
    data: [{ type: 'bar', x: RATINGS, y: RATINGS.map((n) => overlays.fire_risk_rating[n].share_browned * 100), text: RATINGS.map((n) => `${(overlays.fire_risk_rating[n].share_browned * 100).toFixed(0)}%`), textposition: 'outside',
      marker: { color: RATINGS.map((n) => RCOL[n]), line: { color: '#000', width: 1 } }, customdata: RATINGS.map((n) => [overlays.fire_risk_rating[n].area_km2, overlays.fire_risk_rating[n].ndvi_2019]),
      hovertemplate: '%{x}: %{y:.1f}% browned<br>%{customdata[0]} km² · 2019 NDVI %{customdata[1]}<extra></extra>' }],
    layout: { xaxis: { title: { text: 'DLNR fire-risk rating (populated areas only)' } }, yaxis: { title: { text: '% browned 2019 → 2022' }, range: [0, 80] } },
  } : null;
  $: fireRatingFig = overlays?.fires_2023_by_rating?.length ? {
    data: RATINGS.map((n) => ({ type: 'bar', orientation: 'h', name: n, y: overlays.fires_2023_by_rating.map((f) => f.fire), x: overlays.fires_2023_by_rating.map((f) => f.share_by_rating[n] * 100),
      marker: { color: RCOL[n], line: { color: '#000', width: 1 } }, hovertemplate: `%{y}: %{x:.0f}% of the burned area was ${n}<extra></extra>` })),
    layout: { barmode: 'stack', xaxis: { title: { text: '% of each 2023 fire’s area, by DLNR rating of the land' }, range: [0, 100] }, legend: { y: -0.35 }, margin: { l: 70 } },
  } : null;
  $: hd = hdrought?.annual ?? [];
  const CCOL = { maui: '#e07b2c', hawaii: '#5ab4ac', kauai: '#b3bcc1', honolulu: '#6cb6ff' };
  $: hdFig = hd.length ? {
    data: ['hawaii', 'honolulu', 'kauai', 'maui'].map((c) => ({ type: 'scatter', mode: 'lines+markers', name: c === 'hawaii' ? 'Hawaiʻi Island' : c === 'honolulu' ? 'Oʻahu (Honolulu)' : c === 'kauai' ? 'Kauaʻi' : 'Maui County',
      x: hd.map((a) => a.year), y: hd.map((a) => a[c]), line: { color: CCOL[c], width: c === 'maui' ? 3 : 1.5 }, marker: { symbol: 'square', size: c === 'maui' ? 7 : 4 },
      hovertemplate: '%{x}: DSCI %{y}<extra>' + c + '</extra>' })),
    layout: { xaxis: { title: { text: 'Year (mean of weekly values; 2026 to Oct)' }, dtick: 2 }, yaxis: { title: { text: 'Drought index DSCI (0–500)' } }, legend: { y: -0.3 },
      shapes: [{ type: 'rect', xref: 'x', x0: 2021.5, x1: 2022.5, yref: 'paper', y0: 0, y1: 1, fillcolor: 'rgba(224,123,44,0.12)', line: { width: 0 } }] },
  } : null;
  $: d4Fig = hdrought ? {
    data: [{ type: 'bar', x: Object.keys(hdrought.maui_d4_weeks).map(Number), y: Object.values(hdrought.maui_d4_weeks),
      marker: { color: Object.keys(hdrought.maui_d4_weeks).map((y) => (+y === 2022 ? '#e07b2c' : '#8a959c')), line: { color: '#000', width: 1 } },
      hovertemplate: '%{x}: %{y} weeks with exceptional drought (D4) somewhere in Maui County<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Year' }, dtick: 2 }, yaxis: { title: { text: 'Weeks with D4 drought' } } },
  } : null;
  $: gaugeFig = gauges.length ? {
    data: [{ type: 'scatter', mode: 'markers', x: gauges.map((g) => g.elevm), y: gauges.map((g) => g.annavgmm), text: gauges.map((g) => g.name),
      marker: { symbol: 'square', size: 6, color: gauges.map((g) => g.annavgmm), colorscale: [[0, '#bf812d'], [0.3, '#dfc27d'], [0.6, '#80cdc1'], [1, '#01665e']], colorbar: { title: { text: 'mm/yr', side: 'right' }, thickness: 10, outlinewidth: 0 }, line: { width: 0.5, color: '#000' } },
      hovertemplate: '%{text}<br>%{x} m · %{y:.0f} mm/yr<extra></extra>' }],
    layout: { xaxis: { title: { text: 'Gauge elevation (m)' } }, yaxis: { title: { text: 'Mean annual rainfall (mm), 1978–2007' }, type: 'log' } },
  } : null;

  $: studyShare = rasters[index] ? countBelow(rasters[index].values, threshold) : null;
</script>

<div class="ws">
  <header class="bar">
    <div class="ttl"><h1>Analysis workspace</h1>
      <p>Pukalani study area · shared with the <a href="/explore">Map Explorer</a> and <a href="/map">3D view</a></p></div>
    <label>Index <select bind:value={index}><option value="dndvi">dNDVI</option><option value="dnbr">dNBR</option></select></label>
    <label class="thr">Threshold <b class="num">{label} &lt; {threshold.toFixed(2)}</b>
      <input type="range" min="-0.4" max="0" step="0.01" bind:value={threshold} /></label>
    {#if studyShare}<span class="kpi num">{studyShare.below.toLocaleString()} / {studyShare.valid.toLocaleString()} px · {(studyShare.share * 100).toFixed(1)}%</span>{/if}
    {#if threshold !== RESEARCH_THRESHOLD}<button on:click={() => (threshold = RESEARCH_THRESHOLD)}>Reset −0.10</button>{/if}
    <label>Period <select bind:value={from}>{#each months as m}<option value={m} disabled={m > to}>{m}</option>{/each}</select>
      – <select bind:value={to}>{#each months as m}<option value={m} disabled={m < from}>{m}</option>{/each}</select></label>
    <button on:click={() => { from = months[0]; to = months[months.length - 1]; }}>All months</button>
  </header>

  {#if error}
    <p class="err" role="alert">Couldn’t load the study data: {error}</p>
  {:else if loading}
    <p class="muted pad">{loading}</p>
  {:else}
    <p class="lede">Figures tagged <span class="t study">Study data</span> use the project’s own Sentinel-2 results, unchanged.
      <span class="t exploratory">Exploratory dataset</span> figures add public data at a different scale. Read their provenance line.
      Correlations here describe co-variation over 2018–2023; they do not show that drought or browning caused any fire.</p>

    <div class="grid">
      <PlotPanel {Plotly} id="ndvi_anomaly_heatmap" title="Monthly NDVI anomaly" tag="study" height={300}
        meta="Study-area mean NDVI, Sentinel-2 10 m, cloud-masked monthly; z = (NDVI − 2019–21 mean for that month) / SD. Dec 2018 – Dec 2023. Colours clip at ±4; hover for the exact value."
        data={heat.data} layout={heat.layout} rows={heatRows}
        on:pick={(e) => { const y = +e.detail?.y; if (y >= 2018 && y <= 2024) year = y; }}
        note="Click a cell to set the Map Explorer’s year. Empty cells: no cloud-free composite that month, or outside the selected period." />

      <PlotPanel {Plotly} id="dsci_vs_ndvi_anomaly" title="Drought index vs NDVI anomaly" tag="study" height={300}
        meta="Monthly mean of weekly Maui County DSCI (U.S. Drought Monitor) vs the study-area NDVI anomaly. The manuscript’s method; at lag 0 over all months r = −0.47, n = 61."
        data={scatter.data} layout={scatter.layout} rows={lagged.map((p) => ({ ndvi_month: p.month, dsci: +p.x.toFixed(2), ndvi_anomaly_z: +p.y.toFixed(4) }))}>
        <label class="ctl">Lag <input type="range" min="0" max="6" step="1" bind:value={lag} /> <b class="num">{lag} mo</b></label>
      </PlotPanel>

      <PlotPanel {Plotly} id="r_by_lag" title="Correlation by lag" tag="study" height={220}
        meta="Pearson r of DSCI k months earlier vs NDVI anomaly, within the selected period. County-scale index vs a 1.5 km area: co-variation, not cause."
        data={lagFig.data} layout={lagFig.layout} rows={lagTable.map((l) => ({ lag_months: l.lag, r: l.r === null ? null : +l.r.toFixed(4), n: l.n }))}
        on:pick={(e) => { if (Number.isInteger(e.detail?.x)) lag = e.detail.x; }} />

      <PlotPanel {Plotly} id="rain_vs_ndvi_anomaly" title="Rainfall anomaly vs NDVI anomaly" tag="mixed" height={300}
        meta="{RAIN[rainKey]} via Google Earth Engine: one coarse pixel (5–11 km) at the study-area centre, summed over {rainWindow} months, minus the 2018–24 mean of the same months. NDVI anomaly as above."
        data={rainFig.data} layout={rainFig.layout} rows={rainPairs.map((p) => ({ month: p.month, rain_anomaly_mm: +p.x.toFixed(1), ndvi_anomaly_z: +p.y.toFixed(4) }))}>
        {#if rainError}<p class="err small">Rainfall couldn’t load: {rainError}</p>{/if}
        <div class="ctl">
          <select bind:value={rainKey}>{#each Object.entries(RAIN) as [k, v]}<option value={k}>{v}</option>{/each}</select>
          <select bind:value={rainWindow}>{#each [1, 2, 3, 6, 12] as w}<option value={w}>{w}-month sum</option>{/each}</select>
        </div>
      </PlotPanel>

      <PlotPanel {Plotly} id="rain_dsci_ndvi_3d" title="Rain, drought and greenness together" tag="mixed" height={360}
        meta="Each point is one month: {rainWindow}-month {RAIN[rainKey]} rain (mm), county DSCI, study-area NDVI anomaly. Drag to rotate, scroll to zoom. Use the 2D plots for exact relationships."
        data={multiFig.data} layout={multiFig.layout} rows={multi.map((r) => ({ month: r.month, rain_mm: +r.rain.toFixed(1), dsci: +r.dsci.toFixed(1), ndvi_anomaly_z: +r.z.toFixed(4) }))} />

      <PlotPanel {Plotly} id="ndvi_by_year" title="Monthly NDVI by year" tag="study" height={300}
        meta="Distribution of the study area’s monthly mean NDVI within each year (box: quartiles; whiskers 1.5 IQR). 2022 highlighted. Within the selected period."
        data={boxFig.data} layout={boxFig.layout} rows={months.filter(inRange).map((m) => ({ month: m, ndvi: ndviMap.get(m) }))} />

      {#if distFig}
        <PlotPanel {Plotly} id="change_distributions" title="Pixel change distributions" tag="study" height={300}
          meta="All 70,280 valid 10 m pixels of the 1.5 km study area; dry season (May–Sep) 2022 minus 2019. Dashed line: current threshold. Values beyond −0.6 or +0.4 are counted in the end bins (the spikes at the edges)."
          data={distFig.data} layout={distFig.layout}
          rows={binned(rasters.dndvi.values).x.map((x, i) => ({ bin_centre: x, dndvi_pixels: binned(rasters.dndvi.values).y[i], dnbr_pixels: binned(rasters.dnbr.values).y[i] }))} />
      {/if}

      {#if elevFig}
        <PlotPanel {Plotly} id="elevation_vs_change" title="Elevation vs vegetation change" tag="mixed" height={340}
          meta="Each 10 m pixel’s {label} against its elevation, {elevSource}. Line: median per 20 m band; bars: share below {threshold.toFixed(2)}."
          data={elevFig.data} layout={elevFig.layout} rows={bandRows} />
      {:else}
        <section class="plot-wait"><h3>Elevation vs vegetation change</h3><p class="muted small">{elevError ?? 'Sampling elevation at 70,280 pixel centres…'}</p></section>
      {/if}

      {#if densFig}
        <PlotPanel {Plotly} id="browning_density" title="Spatial browning density" tag="study" height={460}
          meta="Share of valid pixels with {label} below {threshold.toFixed(2)} in each 100 m × 100 m block (10 × 10 pixels); blocks under half valid are blank. Click blocks to compare locations."
          data={densFig.data} layout={densFig.layout} rows={densRows} on:pick={(e) => pickBlock(e.detail)}>
          {#if picks.length}
            <table class="picks">
              <thead><tr><th>#</th><th>lat, lon</th><th>px</th><th>dNDVI</th><th>dNBR</th><th>% &lt; {threshold.toFixed(2)}</th><th>elev m</th><th></th></tr></thead>
              <tbody>{#each picks as p, i}<tr><td>{i + 1}</td><td>{p.lat.toFixed(4)}, {p.lon.toFixed(4)}</td><td>{p.pixels}</td><td>{p.dndvi.toFixed(3)}</td>
                <td>{p.dnbr.toFixed(3)}</td><td>{(p.browned * 100).toFixed(0)}</td><td>{p.elevation === null ? 'n/a' : p.elevation.toFixed(0)}</td>
                <td><button on:click={() => (picks = picks.filter((_, j) => j !== i))} aria-label="Remove location {i + 1}">×</button></td></tr>{/each}</tbody>
            </table>
            <div class="ctl"><button on:click={savePicks}>CSV of locations</button><button on:click={() => (picks = [])}>Clear</button></div>
          {:else}<p class="note">Click up to six blocks to compare their mean dNDVI, dNBR, browned share and elevation.</p>{/if}
        </PlotPanel>
      {/if}

      {#if cloudFig}
        <PlotPanel {Plotly} id="terrain_change_3d" title="3D terrain with vegetation change" tag="mixed" height={460}
          meta="Every 2nd pixel each way (~17,600 of 70,280) at its true UTM position and terrain elevation ({elevSource}). Height is terrain only; {label} is shown by colour, never as height."
          data={cloudFig.data} layout={cloudFig.layout}
          rows={cloud.map((k) => ({ easting_km: +pixels.east[k].toFixed(3), northing_km: +pixels.north[k].toFixed(3), elevation_m: +elev[k].toFixed(1), [index]: +vals[k].toFixed(4) }))}>
          <div class="ctl">
            <label>Vertical exaggeration <select bind:value={exaggeration}>{#each [1, 2, 3, 5] as x}<option value={x}>×{x}</option>{/each}</select></label>
            <label>Colour <select bind:value={colourBy}><option value="value">{label} value</option><option value="class">class at {threshold.toFixed(2)}</option></select></label>
            {#if colourBy === 'class'}<span class="key"><i style="background:{CLASS_COLOR.browning}"></i>browning <i style="background:{CLASS_COLOR.stable}"></i>stable <i style="background:{CLASS_COLOR.greening}"></i>greening</span>{/if}
          </div>
        </PlotPanel>
      {/if}

      {#if rsError}<p class="err small wide">Remote-sensing products couldn’t load: {rsError}</p>{/if}
      {#if hdFig}
        <PlotPanel {Plotly} id="hawaii_drought_by_county" title="Drought across Hawaiʻi since 2000" tag="exploratory" height={320}
          meta="U.S. Drought Monitor drought index (DSCI), annual mean of weekly values, each county as a whole. 2022 shaded. County-wide: it does not describe any single place."
          data={hdFig.data} layout={hdFig.layout} rows={hd}
          note={hdrought ? `Maui County’s annual drought index ranks #${hdrought.maui_rank_by_annual_dsci[2022]} for 2022 since 2000 (2010 and 2025 were higher), but 2022 had more weeks of exceptional (D4) drought than any other year.` : ''} />
      {/if}
      {#if d4Fig}
        <PlotPanel {Plotly} id="maui_d4_weeks" title="Exceptional drought on Maui, week counts" tag="exploratory" height={300}
          meta="Weeks each year in which any part of Maui County was in D4 (exceptional) drought, U.S. Drought Monitor, 2000–2026."
          data={d4Fig.data} layout={d4Fig.layout} rows={Object.entries(hdrought.maui_d4_weeks).map(([year, weeks]) => ({ year: +year, weeks_with_d4: weeks }))}
          note="2022: 20 weeks, more than any other year since 2000 (2010 had 9, 2021 had 8). D4 means some of the county, not all of it." />
      {/if}
      {#if moistFig}
        <PlotPanel {Plotly} id="browning_by_moisture_zone" title="Where Maui browned, by moisture zone" tag="exploratory" height={320}
          meta="Share of land in each state moisture zone (Hawaiʻi Statewide GIS) whose dry-season NDVI fell more than 0.10 from 2019 to 2022 (Sentinel-2, 60 m). Orange outline: zones inside the 1.5 km study circle."
          data={moistFig.data} layout={moistFig.layout} rows={mz}
          note="The study area sits in the Moderately Dry (73 %) and Very Dry (27 %) zones, where Maui browned most." />
      {/if}
      {#if plantFig}
        <PlotPanel {Plotly} id="plantation_vs_browning" title="Former plantation land browned more, where it was dry" tag="exploratory" height={340}
          meta="Browning 2019 → 2022 (60 m) on land in sugarcane or pineapple production at some time in 1900–1937 (state digitised maps) vs land never in plantation, compared within each moisture zone so dry and wet land are not mixed."
          data={plantFig.data} layout={plantFig.layout} rows={overlays.plantation_within_moisture_zone.map((z) => ({ zone: z.zone, plantation_share_browned: z.plantation.share_browned ?? null, plantation_px: z.plantation.pixels, other_share_browned: z.other.share_browned ?? null, other_px: z.other.pixels }))}
          note="In the three driest zones former plantation land browned more (Arid 25 % vs 13 %, Very Dry 56 % vs 30 %, Moderately Dry 56 % vs 51 %); in wetter zones it browned less. Association only, from historical land use, not a cause." />
      {/if}
      {#if ratingFig}
        <PlotPanel {Plotly} id="browning_by_fire_risk" title="Browning inside DLNR’s fire-risk areas" tag="exploratory" height={300}
          meta="Share browned 2019 → 2022 (60 m) in land DLNR-DOFAW rated High, Medium or Low (2007; reconfirmed 2017 and 2022), and in all unrated land. The ratings cover populated areas only."
          data={ratingFig.data} layout={ratingFig.layout} rows={RATINGS.map((n) => ({ rating: n, ...overlays.fire_risk_rating[n] }))}
          note="Browning does not follow the state’s ratings: High-rated land is mostly dry coastal land with little greenness to lose (8 % browned), Medium-rated land browned most (62 %). These are different questions: the rating is not a forecast of browning." />
      {/if}
      {#if fireRatingFig}
        <PlotPanel {Plotly} id="fires_by_rating" title="Where the 2023 fires burned, by DLNR rating" tag="exploratory" height={300}
          meta="Each 2023 perimeter (NIFC) overlaid on DLNR’s fire-risk areas. The Lahaina fire is outside the terrain box but inside the island grid."
          data={fireRatingFig.data} layout={fireRatingFig.layout} rows={overlays.fires_2023_by_rating.map((f) => ({ fire: f.fire, pixels: f.pixels, ...f.share_by_rating }))}
          note="Lahaina burned mostly in land rated High. The Upcountry Pulehu fire, the largest, burned 99 % outside any rated area, because the ratings only cover populated communities." />
      {/if}
      {#if gaugeFig}
        <PlotPanel {Plotly} id="rain_gauges_by_elevation" title="Rainfall across Maui’s gauges" tag="exploratory" height={320}
          meta="Mean annual rainfall at each Rainfall Atlas gauge (Giambelluca et al. 2011; station means, 1978–2007 base period) against elevation; log scale. Station measurements, unlike the gridded products elsewhere."
          data={gaugeFig.data} layout={gaugeFig.layout} rows={gauges.map(({ skn, name, elevm, annavgmm, annsd_mm, nummoswith }) => ({ skn, name, elevm, annavgmm, annsd_mm, nummoswith }))} />
      {/if}
      {#if islandFig}
        <PlotPanel {Plotly} id="island_by_year" title="All of Maui, nine dry seasons" tag="exploratory" height={320}
          meta="Sentinel-2 L2A May–Sep medians over the whole island (tiles 4QGJ, 4QGH, 4QHJ; 60 m; ocean masked). Lines: island median; bands: middle 50 % of land pixels. Windward rain forest and the dry leeward slopes are both in here."
          data={islandFig.data} layout={islandFig.layout}
          rows={iYears.map((y) => ({ year: y, ndvi_median: island.years[y].ndvi.median, ndvi_p25: island.years[y].ndvi.p25, ndvi_p75: island.years[y].ndvi.p75, nbr_median: island.years[y].nbr.median, scenes: island.years[y].scenes }))} />
      {/if}
      {#if zoneFig}
        <PlotPanel {Plotly} id="island_by_elevation" title="Greenness by elevation, year by year" tag="exploratory" height={320}
          meta="Median dry-season NDVI of all land in each elevation zone (Copernicus DEM GLO-90). Low leeward zones are driest; the forest belt is greenest; the summit is bare rock."
          data={zoneFig.data} layout={zoneFig.layout}
          rows={island.zones.flatMap(([a, b], zi) => iYears.map((y) => ({ zone: `${a}-${b} m`, year: y, ndvi_median: island.years[y].zones[zi].ndvi?.median ?? null })))} />
      {/if}
      {#if zoneChangeFig}
        <PlotPanel {Plotly} id="island_change_by_elevation" title="Where Maui browned 2019 → 2022" tag="exploratory" height={300}
          meta="Share of land pixels in each elevation zone whose dry-season NDVI fell by more than 0.10 from 2019 to 2022, the study’s threshold applied island-wide (60 m, exploratory)."
          data={zoneChangeFig.data} layout={zoneChangeFig.layout} rows={changeZones} />
      {/if}
      {#if lsFig}
        <PlotPanel {Plotly} id="landsat_26_years" title="26 dry seasons: was 2022 unusual?" tag="mixed" height={340}
          meta="USGS Landsat Collection 2 surface reflectance via Microsoft Planetary Computer (scripts/remote_sensing/landsat_baseline.py, same method as the Earth Engine notebook): May–Sep per-pixel median NDVI, mean over the 1.5 km study area. Dashed white: Sentinel-2 for the overlapping years. Landsat 8/9 (2013 on) read NDVI higher than Landsat 7, that is why 2014 stands out, so recent years are, if anything, flattered."
          data={lsFig.data} layout={lsFig.layout} rows={baseline.rows.map(({ year, ndvi, z, rank_lowest, n_scenes, sensors }) => ({ year, ndvi, z, rank_lowest, n_scenes, sensors }))}
          note={(() => { const r = baseline.rows.find((x) => x.year === 2022); return r ? `2022: NDVI ${r.ndvi}, z = ${r.z} against the 2000–2018 normal, rank ${r.rank_lowest} lowest of ${baseline.years_with_data} years.` : ''; })()} />
      {/if}
      {#if sevFig}
        <PlotPanel {Plotly} id="burn_severity_by_fire" title="How severely the Aug 2023 fires burned" tag="exploratory" height={300}
          meta="Sentinel-2 dNBR (NBR 1 May–7 Aug minus 15 Aug–31 Oct 2023, minus the dNBR of unburned ground to remove seasonal drying), 20 m, inside each NIFC perimeter within the map area (Lahaina is outside it). USGS FIREMON classes, calibrated for forest, on grass a guide, not field-verified."
          data={sevFig.data} layout={sevFig.layout} rows={fires.map((f) => ({ fire: f.name, area_ha: f.area_ha, mean_dnbr: f.mean_dnbr, ...f.class_ha }))}
          note="Burned area from the satellite matches the official perimeters (Pulehu 1,312 ha vs 3,238 acres = 1,310 ha; Olinda 440 vs 438; Kula 84 vs 84)." />
      {/if}
      {#if priorFig}
        <PlotPanel {Plotly} id="browning_vs_burn_severity" title="Did browned ground burn more severely?" tag="exploratory" height={300}
          meta="Inside each 2023 perimeter: share of 20 m pixels burned moderate-low or worse (dNBR ≥ 0.27), by how much they browned 2019 → 2022 (regional Sentinel-2, not the study raster). Small bins are noisy. Hover for pixel counts."
          data={priorFig.data} layout={priorFig.layout}
          rows={fires.flatMap((f) => f.by_prior_browning.map((b) => ({ fire: f.name, dndvi_from: b.dndvi_2019_2022[0], dndvi_to: b.dndvi_2019_2022[1], pixels: b.pixels, mean_dnbr: b.mean_dnbr, share_moderate_or_high: b.share_moderate_or_high })))}
          note="No consistent pattern: in Kula the most-browned ground burned less severely than moderately browned ground, in Olinda the least-browned burned worst, and in Pulehu moderately browned ground burned more than unchanged ground. Browning alone does not predict burn severity here." />
      {/if}
      {#if lstFig}
        <PlotPanel {Plotly} id="surface_temperature" title="Hotter and less green: surface temperature 2013–2025" tag="exploratory" height={340}
          meta="Landsat 8/9 Collection 2 surface temperature (ST_B10, Planetary Computer), May–Sep median, mean over the study area; Landsat NDVI dashed. Skin temperature at ~10:30 a.m., not air temperature. Landsat 9 doubles the scene count from 2022."
          data={lstFig.data} layout={lstFig.layout} rows={lst}
          note={lstNdvi?.r != null ? `Across ${lstNdvi.n} dry seasons, hotter years were less green: r = ${lstNdvi.r.toFixed(2)} between surface temperature and NDVI. 2022 was the hottest (${lst.find((r) => r.year === 2022)?.lst_c?.toFixed(1)} °C).` : ''} />
      {/if}
      {#if checkFig}
        <PlotPanel {Plotly} id="independent_check" title="Independent check of the study raster" tag="mixed" height={380}
          meta="Each 10 m pixel: the study’s dNDVI (Earth Engine) vs the same quantity rebuilt from the public AWS Sentinel-2 L2A archive with the same masking and May–Sep medians (scripts/remote_sensing/). Dashed: −0.10."
          data={checkFig.data} layout={checkFig.layout}
          rows={manifest?.sentinel2?.validation_vs_study_dndvi ? [manifest.sentinel2.validation_vs_study_dndvi] : []}
          note={manifest?.sentinel2?.validation_vs_study_dndvi ? `Mean difference ${manifest.sentinel2.validation_vs_study_dndvi.mean_difference}, RMSE ${manifest.sentinel2.validation_vs_study_dndvi.rmse}; ${(manifest.sentinel2.validation_vs_study_dndvi['class_agreement_at_-0.10'] * 100).toFixed(0)}% of pixels in the same class at −0.10 (${(manifest.sentinel2.validation_vs_study_dndvi['share_below_-0.10_this_pipeline'] * 100).toFixed(1)}% vs ${(manifest.sentinel2.validation_vs_study_dndvi['share_below_-0.10_study'] * 100).toFixed(1)}% below). Differences come from scene selection and compositing, not from changing the study.` : ''} />
      {/if}
      {#if lcFig}
        <PlotPanel {Plotly} id="landcover_browning" title="Browning by land cover" tag="mixed" height={380}
          meta="ESA WorldCover 2021 (10 m, Sentinel-1/2, CC BY 4.0) resampled to the study grid (nearest); bars: share of each class’s pixels with study dNDVI < −0.10."
          data={lcFig.data} layout={lcFig.layout} rows={lcRows.map(({ colour, ...r }) => r)} />
      {/if}
      {#if yearDist}
        <PlotPanel {Plotly} id="ndvi_by_year_pixels" title="Nine dry seasons, pixel by pixel" tag="mixed" height={340}
          meta="Distribution of every valid 10 m pixel’s May–Sep median NDVI in the study area, {aYears[0]}–{aYears[nY - 1]} (Sentinel-2 L2A, AWS). 2019 teal, 2022 orange. {aYears[0]} has fewer scenes (Sentinel-2B only from mid-2017)."
          data={yearDist.data} layout={yearDist.layout}
          rows={aYears.map((y, k) => ({ year: y, scenes: manifest?.sentinel2?.products?.[`aoi_${y}`]?.scenes?.length, median_clear_obs: manifest?.sentinel2?.products?.[`aoi_${y}`]?.median_clear_obs }))} />
      {/if}
      {#if chmFig}
        <PlotPanel {Plotly} id="canopy_vs_browning" title="Browning by lidar height above ground" tag="mixed" height={340}
          meta="USGS 3DEP lidar (Feb–Mar 2023, ~5 pts/m² used): mean height of the highest returns above ground in each 10 m pixel (vegetation and buildings; the survey doesn’t separate them); boxes: {label}; squares: share below {threshold.toFixed(2)}. Canopy is measured after the change it is compared with."
          data={chmFig.data} layout={chmFig.layout} rows={chmStats.map(({ vals, ...b }) => ({ ...b, browned: b.browned === null ? null : +b.browned.toFixed(4) }))} />
      {/if}
      {#if cubeFig}
        <PlotPanel {Plotly} id="space_time_cube" title="Space-time cube: dry-season NDVI {aYears[0]}–{aYears[nY - 1]}" tag="mixed" height={520}
          meta="Each square is one 10 m pixel (every {cubeStride}th row and column) at its true UTM position, stacked by year. Drag to rotate; hover for values. Built from real annual composites; nothing interpolated between years."
          data={cubeFig.data} layout={cubeFig.layout}>
          <div class="ctl"><label>Sampling <select bind:value={cubeStride}>{#each [4, 6, 8, 12] as k}<option value={k}>every {k}th pixel</option>{/each}</select></label></div>
        </PlotPanel>
      {/if}
    </div>
  {/if}
</div>

<style>
  .ws { padding: 0 0 40px; }
  .bar { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; padding: 8px 22px;
         background: var(--card); border-bottom: 1px solid var(--line); font-size: .82rem; }
  .ttl { margin-right: auto; }
  .ttl h1 { font-size: 1.1rem; margin: 0; }
  .ttl p { margin: 0; font-size: .74rem; color: var(--muted); }
  .bar label { display: flex; align-items: center; gap: 6px; }
  .bar select, .ctl select { background: var(--paper-2); border: 1px solid var(--line); padding: 2px 4px; font: .8rem var(--mono); }
  .thr input { width: 130px; }
  .kpi { color: var(--forest); font-size: .8rem; }
  button { background: var(--paper-2); border: 1px solid var(--line); color: var(--ink-2); padding: 2px 9px; font-size: .78rem; }
  .lede { max-width: 1400px; margin: 14px auto 10px; padding: 0 22px; font-size: .84rem; color: var(--ink-2); }
  .t { font: 600 .64rem var(--sans); letter-spacing: .06em; text-transform: uppercase; padding: 1px 6px; border: 1px solid; }
  .t.study { color: var(--forest); } .t.exploratory { color: var(--teal); }
  .grid { max-width: 1400px; margin: 0 auto; padding: 0 22px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .grid :global(.plot:has([data-plot='terrain_change_3d'])), .grid :global(.plot:has([data-plot='browning_density'])), .grid :global(.plot:has([data-plot='space_time_cube'])), .wide { grid-column: 1 / -1; }
  .plot-wait { background: var(--card); border: 1px solid var(--line); padding: 10px 12px; }
  .plot-wait h3 { margin: 0 0 4px; font: 600 .82rem var(--sans); text-transform: uppercase; letter-spacing: .06em; color: var(--ink); }
  .ctl { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; margin-top: 6px; font-size: .78rem; }
  .ctl label { display: flex; gap: 6px; align-items: center; }
  .key { display: inline-flex; gap: 6px; align-items: center; color: var(--muted); }
  .key i { width: 10px; height: 10px; display: inline-block; }
  .picks { font-size: .76rem; margin-top: 8px; }
  .picks td, .picks th { padding: 2px 6px; font-family: var(--mono); }
  .note { font-size: .74rem; color: var(--muted); margin: 6px 0 0; }
  .err { color: var(--fire); }
  .pad { padding: 22px; }
  @media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
</style>
