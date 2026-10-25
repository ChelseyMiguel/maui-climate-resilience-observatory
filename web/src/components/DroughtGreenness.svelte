<script>
  // Drought vs. greenness, month by month. Every number is computed server-side
  // (lib/relationships.py); this component only draws it. Emphasis chart: the
  // story is one drought year against the rest, so 2022 is filled and large,
  // 2023 (the fire year) is hollow, and every other year is muted. Shape and
  // fill carry the meaning as well as colour. A data table is always one click away.
  import { onMount } from 'svelte';
  import { droughtGreenness } from '../lib/adapters.ts';
  import { toCsv, downloadCsv } from '../lib/csv.ts';

  let data = null, error = null;
  let which = 'ndvi';
  let hover = null;
  let showTable = false;

  onMount(async () => {
    try { data = await droughtGreenness(); } catch (e) { error = e.message; }
  });

  const NAMES = { ndvi: 'NDVI (greenness)', nbr: 'NBR (moisture-sensitive)' };
  const MONTH = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const minus = (n, d = 2) => (n < 0 ? '−' : '') + Math.abs(n).toFixed(d);
  const monthName = (m) => `${MONTH[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}`;

  function niceTicks(lo, hi, want = 5) {
    const raw = (hi - lo) / want;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return { ticks: out, step };
  }

  // ---- scatter geometry ----
  const W = 600, H = 340, L = 56, R = 16, T = 14, B = 48;

  $: block = data?.indices[which];
  $: points = block?.points ?? [];
  $: fit = block?.fit;
  $: xs = niceTicks(0, Math.max(...points.map((p) => p.dsci), 1));
  $: xHi = Math.ceil(Math.max(...points.map((p) => p.dsci), 1) / xs.step) * xs.step;
  $: ysRaw = points.map((p) => p.value);
  $: yt = niceTicks(Math.min(...ysRaw, 0) - 0.0001, Math.max(...ysRaw, 0.1) + 0.0001, 5);
  $: yLo = Math.floor(Math.min(...ysRaw, 0.5) / yt.step) * yt.step;
  $: yHi = Math.ceil(Math.max(...ysRaw, 0) / yt.step) * yt.step;
  $: yTicks = niceTicks(yLo, yHi, 5).ticks;
  $: sx = (d) => L + (d / xHi) * (W - L - R);
  $: sy = (v) => H - B - ((v - yLo) / (yHi - yLo)) * (H - B - T);
  // Draw the emphasised years last so they sit on top of the muted ones.
  $: ordered = [...points].sort((a, b) => rank(a.year) - rank(b.year));
  const rank = (y) => (y === 2022 ? 2 : y === 2023 ? 1 : 0);
  $: line = fit && fit.r !== null && points.length
    ? (() => {
        const lo = Math.min(...points.map((p) => p.dsci)), hi = Math.max(...points.map((p) => p.dsci));
        return { x1: sx(lo), y1: sy(fit.intercept + fit.slope * lo), x2: sx(hi), y2: sy(fit.intercept + fit.slope * hi) };
      })()
    : null;

  function onMove(e) {
    const svg = e.currentTarget;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const { x, y } = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = null, bestD = 22 * 22;
    for (const p of ordered) {
      const d = (sx(p.dsci) - x) ** 2 + (sy(p.value) - y) ** 2;
      if (d <= bestD) { best = p; bestD = d; }
    }
    hover = best;
  }

  // ---- lag profile ----
  const LW = 600, LH = 200, LL = 56, LR = 16, LT = 14, LB = 44;
  const R_LO = -1, R_HI = 0.25;
  const ly = (r) => LT + ((R_HI - r) / (R_HI - R_LO)) * (LH - LT - LB);
  $: lags = block?.lags ?? [];
  $: slot = (LW - LL - LR) / Math.max(lags.length, 1);
  $: lagAt = (k) => lags.find((l) => l.lag === k);

  // ---- dry season ----
  $: dry = data?.drySeason ?? [];
  $: dryIndex = (row) => (which === 'ndvi' ? row.ndvi : row.nbr);
  $: dryMax = Math.max(...dry.map((r) => Math.max(dryIndex(r) ?? 0, 0)), 0.0001);
  $: dsciMax = Math.max(...dry.map((r) => r.dsci), 1);

  function exportCsv() {
    downloadCsv(`pukalani_drought_vs_${which}_monthly.csv`, toCsv(points, [
      { header: 'month', value: (p) => p.month },
      { header: 'maui_county_dsci_monthly_mean', value: (p) => p.dsci },
      { header: `${which}_study_area_mean`, value: (p) => p.value },
    ], [
      `Maui County drought (DSCI) against Pukalani study-area ${which.toUpperCase()}, one row per month. Browning Viewer (student research project).`,
      'Sources: U.S. Drought Monitor (UNL/USDA/NOAA) weekly DSCI averaged by month; author\'s Sentinel-2 SR Harmonized analysis (Google Earth Engine).',
      `Pearson r = ${fit?.r ?? 'n/a'} over ${fit?.n ?? 0} months (same month).`,
      ...(data?.notes ?? []),
    ]));
  }
</script>

<div class="dg">
  <h2>Drought and greenness, month by month</h2>
  <p class="small">Each dot is one month. Drier months sit further right; greener months sit higher. This shows
    whether the two moved together here. It does not show that one caused the other.</p>

  {#if error}
    <p class="err" role="alert">Couldn’t load the drought–greenness comparison: {error}</p>
  {:else if !data}
    <p class="muted" aria-busy="true">Loading…</p>
  {:else}
    <div class="seg" role="group" aria-label="Vegetation index">
      {#each ['ndvi', 'nbr'] as k}
        <button aria-pressed={which === k} class:on={which === k} on:click={() => { which = k; hover = null; }}>{NAMES[k]}</button>
      {/each}
    </div>

    {#if fit.r !== null}
      <p class="stat"><b>r = {minus(fit.r)}</b> across {fit.n} months, same month. Pearson correlation of county
        drought with the study area’s {which.toUpperCase()}.</p>
    {/if}

    <figure class="chart">
      <figcaption>
        <span class="title">{NAMES[which]} against drought, one dot per month</span>
        <span class="keys">
          <span class="key"><svg width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="6" class="dot y2022" /></svg>2022 (drought year)</span>
          <span class="key"><svg width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="5" class="dot y2023" /></svg>2023 (fire year)</span>
          <span class="key"><svg width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="4.5" class="dot" /></svg>other years</span>
          <span class="key"><svg width="22" height="10" aria-hidden="true"><line x1="0" y1="5" x2="22" y2="5" class="fit" /></svg>best-fit line</span>
        </span>
      </figcaption>
      <svg viewBox="0 0 {W} {H}" role="img" on:mousemove={onMove} on:mouseleave={() => (hover = null)}
           aria-label="Scatter of {NAMES[which]} against Maui County drought for {points.length} months. {fit.r !== null ? `Correlation ${minus(fit.r)}.` : ''} Use the data table for exact values.">
        {#each yTicks as v}
          <line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} class="grid" />
          <text x={L - 8} y={sy(v) + 4} class="tick end">{v.toFixed(yt.step < 0.1 ? 2 : 1)}</text>
        {/each}
        {#each xs.ticks as v}
          <line x1={sx(v)} x2={sx(v)} y1={T} y2={H - B} class="grid v" />
          <text x={sx(v)} y={H - B + 16} class="tick mid">{v}</text>
        {/each}
        <text x={(L + W - R) / 2} y={H - 6} class="axis mid">Maui County drought index (DSCI), monthly mean, drier →</text>
        <text x="14" y={(T + H - B) / 2} class="axis mid" transform="rotate(-90 14 {(T + H - B) / 2})">{which.toUpperCase()}</text>

        {#if line}<line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} class="fit" />{/if}

        {#each ordered as p (p.month)}
          <circle cx={sx(p.dsci)} cy={sy(p.value)} r={p.year === 2022 ? 6 : p.year === 2023 ? 5 : 4.5}
                  class="dot" class:y2022={p.year === 2022} class:y2023={p.year === 2023} />
        {/each}
        {#if hover}
          <circle cx={sx(hover.dsci)} cy={sy(hover.value)} r="10" class="halo" />
        {/if}
      </svg>
      <div class="readout" aria-hidden="true">
        {#if hover}<span><b>{monthName(hover.month)}</b> · DSCI {hover.dsci.toFixed(0)} · {which.toUpperCase()} {hover.value.toFixed(3)}</span>
        {:else}<span class="muted">Hover a dot for its month.</span>{/if}
      </div>
      <button class="tablebtn" aria-expanded={showTable} on:click={() => (showTable = !showTable)}>
        {showTable ? 'Hide' : 'Show'} data table
      </button>
      {#if showTable}
        <div class="tablewrap">
          <table>
            <thead><tr><th>Month</th><th>County DSCI</th><th>{which.toUpperCase()}</th></tr></thead>
            <tbody>{#each points as p}<tr><td>{monthName(p.month)}</td><td>{p.dsci.toFixed(1)}</td><td>{p.value.toFixed(3)}</td></tr>{/each}</tbody>
          </table>
        </div>
      {/if}
    </figure>

    <figure class="chart">
      <figcaption><span class="title">Does greenness follow drought later? Correlation by months apart</span></figcaption>
      <svg viewBox="0 0 {LW} {LH}" role="img"
           aria-label="Correlation between drought and {which.toUpperCase()} when the greenness reading is 0 to 6 months after the drought reading.">
        {#each [-1, -0.5, 0] as v}
          <line x1={LL} x2={LW - LR} y1={ly(v)} y2={ly(v)} class={v === 0 ? 'zero' : 'grid'} />
          <text x={LL - 8} y={ly(v) + 4} class="tick end">{minus(v, 1)}</text>
        {/each}
        {#each lags as l, i}
          {@const cx = LL + slot * (i + 0.5)}
          {#if l.r !== null}
            <rect x={cx - 17} width="34" y={l.r < 0 ? ly(0) : ly(l.r)} height={Math.max(Math.abs(ly(l.r) - ly(0)), 1)} class="bar">
              <title>{l.lag} months apart: r = {minus(l.r)} over {l.n} months</title>
            </rect>
          {/if}
          <text x={cx} y={LH - LB + 16} class="tick mid">{l.lag}</text>
        {/each}
        {#if lagAt(0)?.r != null}
          <text x={LL + slot * 0.5} y={ly(lagAt(0).r) + 14} class="barlabel mid">{minus(lagAt(0).r)}</text>
        {/if}
        <text x={(LL + LW - LR) / 2} y={LH - 6} class="axis mid">Months between drought and greenness readings</text>
        <text x="14" y={(LT + LH - LB) / 2} class="axis mid" transform="rotate(-90 14 {(LT + LH - LB) / 2})">r</text>
      </svg>
      <p class="small muted">
        {#if lagAt(0)?.r != null && lagAt(3)?.r != null}
          Same month: r = {minus(lagAt(0).r)}. Three months apart: r = {minus(lagAt(3).r)}.
        {/if}
        Each bar pairs a month’s greenness with the drought index that many months earlier.
      </p>
    </figure>

    <div class="dry">
      <h3>Dry season (May–September), year by year</h3>
      <table>
        <thead><tr><th>Year</th><th>Months</th><th>Mean county DSCI</th><th>Mean {which.toUpperCase()}</th></tr></thead>
        <tbody>
          {#each dry as row}
            <tr class:hl={row.year === 2022}>
              <th scope="row">{row.year}</th>
              <td>{which === 'ndvi' ? row.months : row.nbrMonths}</td>
              <td><span class="inbar"><i class="amber" style="width:{(row.dsci / dsciMax) * 100}%"></i></span> {row.dsci.toFixed(0)}</td>
              <td>{#if dryIndex(row) !== null}<span class="inbar"><i class="green" style="width:{(Math.max(dryIndex(row), 0) / dryMax) * 100}%"></i></span> {dryIndex(row).toFixed(3)}{:else}n/a{/if}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      <p class="small muted">“Months” is how many of the five dry-season months had usable imagery; a year with fewer is less
        reliable. County drought is averaged over the same months as the greenness beside it.</p>
    </div>

    <ul class="caveats small">
      {#each data.notes as n}<li>{n}</li>{/each}
    </ul>
    <button class="btn ghost" on:click={exportCsv}>Download monthly pairs as CSV</button>
  {/if}
</div>

<style>
  .dg { display: grid; gap: 14px; }
  h2, h3 { margin: 0; }
  .seg { display: inline-flex; border: 1px solid var(--line); border-radius: 0; overflow: hidden; width: fit-content; }
  .seg button { border: 0; background: var(--card); padding: .45em 1em; font-weight: 600; color: var(--ink-2); }
  .seg button + button { border-left: 1px solid var(--line); }
  .seg button.on { background: var(--forest); color: #111; }
  .stat { margin: 0; background: var(--paper-2); border-left: 3px solid var(--teal); padding: 8px 12px; border-radius: 0; }
  .chart { margin: 0; }
  figcaption { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 14px; margin-bottom: 4px; }
  .title { font-weight: 700; color: var(--forest); }
  .keys { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: .85rem; color: var(--ink-2); }
  .key { display: inline-flex; align-items: center; gap: 5px; }
  svg[role='img'] { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); border-radius: 0; }
  .grid { stroke: #252c31; stroke-width: 1; }
  .grid.v { stroke-dasharray: 2 3; }
  .zero { stroke: var(--ink-2); stroke-width: 1.5; }
  .tick { fill: var(--muted); font-size: 11px; }
  .axis { fill: var(--ink-2); font-size: 11.5px; }
  .end { text-anchor: end; }
  .mid { text-anchor: middle; }
  /* Marks. The 2px ring in the card colour keeps overlapping dots separable. */
  .dot { fill: #8a959c; fill-opacity: .85; stroke: var(--card); stroke-width: 2; }
  .dot.y2023 { fill: var(--card); stroke: var(--teal); stroke-width: 2.5; fill-opacity: 1; }
  .dot.y2022 { fill: var(--amber); fill-opacity: 1; }
  .halo { fill: none; stroke: var(--ink); stroke-width: 1.5; }
  .fit { stroke: var(--ink-2); stroke-width: 2; opacity: .75; fill: none; }
  .bar { fill: var(--teal); }
  .barlabel { fill: var(--ink); font-size: 11px; font-weight: 700; }
  .readout { min-height: 1.6em; font-size: .85rem; margin-top: 4px; }
  .tablebtn { margin-top: 4px; background: none; border: 1px solid var(--line); border-radius: 0; padding: .25em .7em; font-size: .82rem; }
  .tablewrap { max-height: 260px; overflow: auto; margin-top: 6px; border: 1px solid var(--line); border-radius: 0; }
  .tablewrap table { font-size: .82rem; }
  .tablewrap th { position: sticky; top: 0; background: var(--paper-2); }
  .dry h3 { font: 700 1rem var(--sans); color: var(--forest); margin-bottom: 4px; }
  .dry table { width: 100%; }
  .dry th, .dry td { text-align: left; padding: .35em .5em; }
  .dry tr.hl { background: var(--paper-2); box-shadow: inset 3px 0 0 var(--amber); font-weight: 600; }
  .inbar { display: inline-block; width: 90px; height: 8px; background: var(--paper-2); border-radius: 0; vertical-align: middle; margin-right: 6px; overflow: hidden; }
  .inbar i { display: block; height: 100%; }
  .inbar .amber { background: var(--amber); }
  .inbar .green { background: var(--forest-2); }
  .caveats { margin: 0; padding-left: 1.2em; color: var(--ink-2); }
  .err { color: var(--fire); }
  .btn.ghost { width: fit-content; font-size: .9rem; }
  /* The SVGs scale to the column, so on a phone their 11px text renders near 6px.
     Larger user-unit sizes keep labels readable at that scale. */
  @media (max-width: 640px) {
    .tick, .axis, .barlabel { font-size: 17px; }
    .dry th, .dry td { padding: .3em .35em; }
  }
</style>
