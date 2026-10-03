<script>
  // Drought vs vegetation, 2018-2024, with the August 2023 fires marked.
  //
  // Two series on one time axis, each with its own scale:
  //   * Maui County drought (U.S. Drought Monitor DSCI, weekly, 0-500) — area
  //   * Study-area mean NDVI (this project's Sentinel-2 series, monthly) — line
  // They are different places (whole county vs a 1.5 km circle) and different
  // units, so the chart shows TIMING, not a correlation. The manuscript's
  // r = -0.47 comes from a proper analysis; this picture only illustrates it.
  import { dsciLabel } from './geo.js';

  export let drought = [];   // [{date, dsci}]
  export let ndvi = [];      // [{date, value}]
  export let worstYear = null;

  // Drawn at roughly the width it is shown at (the 380 px side panel), so 10-unit
  // text renders near 10 px. A wider viewBox scaled down made the labels ~5 px.
  const W = 340, H = 210, L = 30, R = 30, T = 18, B = 24;
  const t0 = Date.parse('2018-01-01'), t1 = Date.parse('2025-01-01');
  const FIRE = Date.parse('2023-08-08');
  const DSCI_MAX = 350, NDVI_LO = 0.25, NDVI_HI = 0.65;

  const x = (d) => L + ((Date.parse(d) - t0) / (t1 - t0)) * (W - L - R);
  const xt = (t) => L + ((t - t0) / (t1 - t0)) * (W - L - R);
  const yD = (v) => H - B - (Math.min(v, DSCI_MAX) / DSCI_MAX) * (H - B - T);
  const yN = (v) => H - B - ((v - NDVI_LO) / (NDVI_HI - NDVI_LO)) * (H - B - T);

  $: dArea = drought.length
    ? `M${x(drought[0].date)},${H - B} ` +
      drought.map((p) => `L${x(p.date).toFixed(1)},${yD(p.dsci).toFixed(1)}`).join(' ') +
      ` L${x(drought[drought.length - 1].date)},${H - B} Z`
    : '';
  $: nLine = ndvi.map((p, i) => `${i ? 'L' : 'M'}${x(p.date).toFixed(1)},${yN(p.value).toFixed(1)}`).join(' ');
  $: fireWeek = drought.find((p) => p.date >= '2023-08-08');
  $: peak = drought.reduce((a, p) => (p.dsci > (a?.dsci ?? -1) ? p : a), null);
  $: band = worstYear ? [xt(Date.parse(`${worstYear}-01-01`)), xt(Date.parse(`${+worstYear + 1}-01-01`))] : null;

  const years = [2018, 2020, 2022, 2024];  // every other year: all eight crowd at this width
</script>

<figure class="timeline">
  <svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="tl-title tl-desc">
    <title id="tl-title">Drought and vegetation greenness, 2018 to 2024</title>
    <desc id="tl-desc">
      Maui County drought index rises from 2019, peaks in {peak?.date?.slice(0, 7)} and stays high through
      {worstYear}, the worst year. Study-area NDVI reaches its lowest point in August 2022. The fires
      were on 8 August 2023, when the drought index was {fireWeek?.dsci}.
    </desc>

    {#if band}
      <rect x={band[0]} y={T} width={band[1] - band[0]} height={H - B - T} class="band" />
      <text x={(band[0] + band[1]) / 2} y={T - 5} class="band-label">{worstYear}: worst drought</text>
    {/if}

    <line x1={L} x2={W - R} y1={yD(0)} y2={yD(0)} class="grid" />
    <!-- No "0" label: it collides with the first year label in the corner. -->
    {#each [100, 200, 300] as v}
      <line x1={L} x2={W - R} y1={yD(v)} y2={yD(v)} class="grid" />
      <text x={L - 6} y={yD(v) + 3} class="axis left">{v}</text>
    {/each}
    {#each [0.3, 0.4, 0.5, 0.6] as v}
      <text x={W - R + 6} y={yN(v) + 3} class="axis right">{v.toFixed(1)}</text>
    {/each}
    {#each years as yr}
      <text x={xt(Date.parse(`${yr}-01-01`))} y={H - 10} class="axis year">{yr}</text>
    {/each}

    <path d={dArea} class="dsci" />
    <path d={nLine} class="ndvi" />

    <line x1={xt(FIRE)} x2={xt(FIRE)} y1={T} y2={H - B} class="fire" />
    <!-- Low on the chart and left of the line: Aug 2023 is near the right edge,
         so a label to its right would run off the chart. -->
    <text x={xt(FIRE) - 4} y={H - B - 6} class="fire-label">Aug 8 2023 fires</text>
  </svg>
  <figcaption>
    <span class="key k-dsci">Maui County drought (USDM DSCI, left)</span>
    <span class="key k-ndvi">Study-area NDVI (right)</span>
    {#if fireWeek}
      <span class="note">Fire week: DSCI {fireWeek.dsci} ({dsciLabel(fireWeek.dsci)}) and rising.</span>
    {/if}
    <span class="note">Shows timing only — county-wide drought vs a 1.5 km study area, different units.</span>
  </figcaption>
</figure>

<style>
  .timeline { margin: 0; }
  svg { width: 100%; height: auto; display: block; }
  .grid { stroke: #24323a; stroke-width: 1; }
  .axis { fill: #8fa3aa; font-size: 10px; }
  .axis.left { text-anchor: end; }
  .axis.year { text-anchor: middle; }
  .band { fill: rgba(217, 164, 65, 0.10); }
  .band-label { fill: #d9a441; font-size: 10px; text-anchor: middle; }
  .dsci { fill: rgba(217, 164, 65, 0.35); stroke: #d9a441; stroke-width: 1; }
  .ndvi { fill: none; stroke: #4fb286; stroke-width: 1.8; }
  .fire { stroke: #ff3b30; stroke-width: 1.5; stroke-dasharray: 4 3; }
  .fire-label { fill: #ff6b5e; font-size: 10px; text-anchor: end; font-weight: 600; paint-order: stroke; stroke: #172025; stroke-width: 3px; }
  figcaption { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 11px; color: #8fa3aa; margin-top: 4px; }
  .key::before { content: '▬ '; }
  .k-dsci::before { color: #d9a441; }
  .k-ndvi::before { color: #4fb286; }
  .note { width: 100%; }
</style>
