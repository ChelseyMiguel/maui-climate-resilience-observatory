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

  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const RAIN = { chirps: 'CHIRPS', terraclimate: 'TerraClimate', imerg: 'IMERG V07', era5land: 'ERA5-Land' };
  const DIVERGING = [[0, '#8c510a'], [0.3, '#d8b365'], [0.5, '#3a4248'], [0.7, '#5ab4ac'], [1, '#01665e']];
  const CLASS_COLOR = { browning: '#d08a3c', stable: '#6e767c', greening: '#40a8a0' };

  let Plotly = null, loading = 'Loading data…', error = null;
  let ndviMap = new Map(), nbrMap = new Map(), dsciMap = new Map(), rainRows = [], rainError = null;
  let rasters = {}, elev = null, elevSource = '', elevError = null, pixels = null;

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
        elevSource = 'local 68 m DEM grid (terrain tiles unreachable) — coarser than the 10 m pixels';
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
      <span class="t exploratory">Exploratory dataset</span> figures add public data at a different scale — read their provenance line.
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
          meta="Each 10 m pixel’s {label} against its elevation — {elevSource}. Line: median per 20 m band; bars: share below {threshold.toFixed(2)}."
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
                <td>{p.dnbr.toFixed(3)}</td><td>{(p.browned * 100).toFixed(0)}</td><td>{p.elevation === null ? '—' : p.elevation.toFixed(0)}</td>
                <td><button on:click={() => (picks = picks.filter((_, j) => j !== i))} aria-label="Remove location {i + 1}">×</button></td></tr>{/each}</tbody>
            </table>
            <div class="ctl"><button on:click={savePicks}>CSV of locations</button><button on:click={() => (picks = [])}>Clear</button></div>
          {:else}<p class="note">Click up to six blocks to compare their mean dNDVI, dNBR, browned share and elevation.</p>{/if}
        </PlotPanel>
      {/if}

      {#if cloudFig}
        <PlotPanel {Plotly} id="terrain_change_3d" title="3D terrain with vegetation change" tag="mixed" height={460}
          meta="Every 2nd pixel each way (~17,600 of 70,280) at its true UTM position and terrain elevation ({elevSource}). Height is terrain only — {label} is shown by colour, never as height."
          data={cloudFig.data} layout={cloudFig.layout}
          rows={cloud.map((k) => ({ easting_km: +pixels.east[k].toFixed(3), northing_km: +pixels.north[k].toFixed(3), elevation_m: +elev[k].toFixed(1), [index]: +vals[k].toFixed(4) }))}>
          <div class="ctl">
            <label>Vertical exaggeration <select bind:value={exaggeration}>{#each [1, 2, 3, 5] as x}<option value={x}>×{x}</option>{/each}</select></label>
            <label>Colour <select bind:value={colourBy}><option value="value">{label} value</option><option value="class">class at {threshold.toFixed(2)}</option></select></label>
            {#if colourBy === 'class'}<span class="key"><i style="background:{CLASS_COLOR.browning}"></i>browning <i style="background:{CLASS_COLOR.stable}"></i>stable <i style="background:{CLASS_COLOR.greening}"></i>greening</span>{/if}
          </div>
        </PlotPanel>
      {/if}

      <section class="plot-wait wide">
        <h3>Not shown: a pixel-by-month space-time cube</h3>
        <p class="muted small">This repository has the 2019 → 2022 change rasters and the study-area <em>mean</em> NDVI per month, not a 10 m NDVI raster for every month.
          A space-time view of how individual pixels changed would need those monthly rasters exported from Earth Engine (the same Sentinel-2 cloud masking, one image per month).
          Until then, the anomaly heatmap above is the time view and the maps are the space view — nothing here is interpolated between them.</p>
      </section>
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
  .grid :global(.plot:has([data-plot='terrain_change_3d'])), .grid :global(.plot:has([data-plot='browning_density'])), .wide { grid-column: 1 / -1; }
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
