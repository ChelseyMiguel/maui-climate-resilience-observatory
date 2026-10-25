<script>
  // Study-area data panel for the Map Explorer: vegetation, drought and rainfall
  // stacked on one shared time axis, so a dry spell can be followed from rain to
  // drought index to greenness by eye. One crosshair reads every panel at once.
  // Each panel keeps its own units; nothing is rescaled onto a shared axis.
  import { createEventDispatcher } from 'svelte';
  import { COLUMNS, toCsv, brushResult } from '../lib/series.js';

  export let rows = [];          // joinMonthly() output
  export let year = null;        // the Map Explorer's year, shaded on the chart
  export let error = null;

  const dispatch = createEventDispatcher();

  // Categorical palette validated for this project (#2a78d6 #eb6834 #1baf7a #6250d6),
  // always paired with a dash pattern.
  const PANELS = [
    { key: 'veg', title: 'Vegetation index · study area', unit: '', fmt: (v) => v.toFixed(3),
      series: [{ col: 'ndvi', label: 'NDVI', color: '#1baf7a' }, { col: 'nbr', label: 'NBR', color: '#eb6834', dash: '6 4' }] },
    { key: 'dsci', title: 'Drought index (DSCI) · Maui County', unit: '0–500', fmt: (v) => v.toFixed(0), area: true, min: 0,
      series: [{ col: 'dsci', label: 'DSCI', color: '#e0a345' }] },
    { key: 'rain', title: 'Rainfall · four gridded products', unit: 'mm / month', fmt: (v) => v.toFixed(0), min: 0,
      series: [{ col: 'chirps_mm', label: 'CHIRPS', color: '#2a78d6' }, { col: 'terraclimate_mm', label: 'TerraClimate', color: '#eb6834', dash: '6 4' },
               { col: 'imerg_mm', label: 'IMERG', color: '#1baf7a', dash: '2 3' }, { col: 'era5land_mm', label: 'ERA5-Land', color: '#6250d6', dash: '10 3 2 3' }] },
  ];
  let on = Object.fromEntries(PANELS.flatMap((p) => p.series.map((s) => [s.col, true])));

  $: months = rows.map((r) => r.month);
  // Bindable, so the Map Explorer can share the period with the Analysis workspace.
  export let from = '', to = '';
  $: if (months.length && (!months.includes(from) || !months.includes(to))) { from = months[0]; to = months[months.length - 1]; }
  $: view = rows.filter((r) => r.month >= from && r.month <= to);
  // A zoom shrinks the series; drop a hover index that now points past its end.
  $: if (hover !== null && hover >= view.length) hover = null;

  const W = 1000, L = 52, R = 14, PH = 64, GAP = 30, TOP = 18, AX = 22;
  $: H = TOP + PANELS.length * (PH + GAP) - GAP + AX;
  $: n = Math.max(1, view.length - 1);
  $: x = (i) => L + (i / n) * (W - L - R);

  function scale(p, rs) {
    const vals = rs.flatMap((r) => p.series.filter((s) => on[s.col]).map((s) => r[s.col])).filter((v) => v !== null);
    if (!vals.length) return null;
    let lo = p.min ?? Math.min(...vals), hi = Math.max(...vals);
    if (p.min === undefined) { const pad = (hi - lo) * 0.08 || 0.05; lo -= pad; hi += pad; }
    if (hi === lo) hi = lo + 1;
    return { lo, hi };
  }
  const ticks = (s) => [s.lo, (s.lo + s.hi) / 2, s.hi];

  function pathOf(col, sc, top, area) {
    let d = '', pen = false;
    view.forEach((r, i) => {
      const v = r[col];
      if (v === null) { pen = false; return; }           // a gap stays a gap
      const yy = top + PH - ((v - sc.lo) / (sc.hi - sc.lo)) * PH;
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${yy.toFixed(1)}`;
      pen = true;
    });
    if (area && d) {
      const idx = view.map((r, i) => (r[col] === null ? -1 : i)).filter((i) => i >= 0);
      d += `L${x(idx[idx.length - 1])},${top + PH}L${x(idx[0])},${top + PH}Z`;
    }
    return d;
  }

  $: layout = PANELS.map((p, k) => ({ ...p, top: TOP + k * (PH + GAP), sc: scale(p, view), on: { ...on } }));
  $: yearIdx = view.map((r, i) => (r.month.startsWith(String(year)) ? i : -1)).filter((i) => i >= 0);
  $: fireIdx = view.findIndex((r) => r.month === '2023-08');
  $: yearTicks = view.map((r, i) => (r.month.endsWith('-01') ? i : -1)).filter((i) => i >= 0);

  let hover = null, brush = null;   // brush: [startIndex, endIndex] while dragging
  let svgEl;
  function indexAt(e) {
    const pt = svgEl.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const sx = pt.matrixTransform(svgEl.getScreenCTM().inverse()).x;
    return Math.max(0, Math.min(view.length - 1, Math.round(((sx - L) / (W - L - R)) * n)));
  }
  function move(e) {
    const i = indexAt(e);
    hover = i;
    if (brush) brush = [brush[0], i];
  }
  function down(e) { if (e.button === 0) { brush = [indexAt(e), indexAt(e)]; svgEl.setPointerCapture(e.pointerId); } }
  // Drag across months to zoom to them; click a month to set the map's year.
  function up() {
    if (!brush) return;
    const res = brushResult(view.map((r) => r.month), brush[0], brush[1]);
    brush = null;
    if (res.from) { from = res.from; to = res.to; }
    else if (res.year) dispatch('pickyear', res.year);
  }
  function key(e) {
    if (e.key === 'ArrowRight') hover = Math.min(view.length - 1, (hover ?? -1) + 1);
    else if (e.key === 'ArrowLeft') hover = Math.max(0, (hover ?? view.length) - 1);
    else return;
    e.preventDefault();
  }

  function save(blob, name) {
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name });
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  const stem = () => `pukalani_study_area_${from}_${to}`;
  const csv = () => save(new Blob([toCsv(view)], { type: 'text/csv' }), `${stem()}.csv`);
  const json = () => save(new Blob([JSON.stringify({ columns: COLUMNS, rows: view, sources: SOURCES }, null, 1)], { type: 'application/json' }), `${stem()}.json`);
  function png() {
    const clone = svgEl.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    style.textContent = `text{font:11px system-ui,sans-serif;fill:#b3bcc1}.t{fill:#e4e8ea;font-weight:600}.g{stroke:#252c31}.bg{fill:#151a1e}.yr{fill:#e07b2c;fill-opacity:.12}.fire{stroke:#ff6a5c}`;
    clone.prepend(style);
    const img = new Image();
    img.onload = () => {
      const c = Object.assign(document.createElement('canvas'), { width: W * 2, height: H * 2 });
      const ctx = c.getContext('2d'); ctx.scale(2, 2); ctx.drawImage(img, 0, 0, W, H);
      c.toBlob((b) => save(b, `${stem()}.png`));
    };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(clone));
  }
  const SOURCES = {
    ndvi_nbr: 'Author’s Sentinel-2 analysis, 1.5 km study area, monthly mean',
    dsci: 'U.S. Drought Monitor, Maui County, monthly mean of weekly DSCI',
    rainfall: 'CHIRPS, TerraClimate, IMERG V07, ERA5-Land via Google Earth Engine, pixel at study-area centre',
  };
</script>

<section class="panel" aria-label="Study-area data over time">
  <header>
    <h2>Pukalani study area · monthly data</h2>
    <button class="x" aria-label="Close data panel" on:click={() => dispatch('close')}>×</button>
  </header>

  {#if error}
    <p class="err">Couldn’t load the series: {error}</p>
  {:else if !rows.length}
    <p class="muted">Loading series…</p>
  {:else}
    <div class="controls">
      <fieldset>
        <legend>Range</legend>
        <label>From <select bind:value={from}>{#each months as m}<option value={m} disabled={m > to}>{m}</option>{/each}</select></label>
        <label>To <select bind:value={to}>{#each months as m}<option value={m} disabled={m < from}>{m}</option>{/each}</select></label>
        <button class="b" on:click={() => { from = months[0]; to = months[months.length - 1]; }}>All</button>
        <button class="b" on:click={() => { from = '2021-06'; to = '2023-12'; }}>Drought + fires</button>
      </fieldset>
      <fieldset>
        <legend>Series</legend>
        {#each PANELS as p}{#each p.series as s}
          <label class="s"><input type="checkbox" bind:checked={on[s.col]} />
            <svg width="22" height="8" aria-hidden="true"><line x1="0" y1="4" x2="22" y2="4" stroke={s.color} stroke-width="2.5" stroke-dasharray={s.dash ?? ''} /></svg>{s.label}</label>
        {/each}{/each}
      </fieldset>
      <fieldset>
        <legend>Download</legend>
        <button class="b" on:click={csv}>CSV</button><button class="b" on:click={json}>JSON</button><button class="b" on:click={png}>PNG</button>
      </fieldset>
    </div>

    <div class="plot">
      <!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions -->
      <svg bind:this={svgEl} viewBox="0 0 {W} {H}" role="img" tabindex="0"
           aria-label="NDVI and NBR, drought index and rainfall by month, {from} to {to}. Arrow keys step through months."
           on:pointermove={move} on:pointerdown={down} on:pointerup={up} on:mouseleave={() => (hover = null)} on:keydown={key}>
        <rect class="bg" x="0" y="0" width={W} height={H} />
        {#if yearIdx.length}
          <rect class="yr" x={x(yearIdx[0]) - 3} y={TOP} width={Math.max(6, x(yearIdx[yearIdx.length - 1]) - x(yearIdx[0]) + 6)} height={H - TOP - AX} />
        {/if}
        {#each layout as p}
          <text class="t" x={L} y={p.top - 2}>{p.title}{p.unit ? ` (${p.unit})` : ''}</text>
          {#if p.sc}
            {#each ticks(p.sc) as tv}
              {@const yy = p.top + PH - ((tv - p.sc.lo) / (p.sc.hi - p.sc.lo)) * PH}
              <line class="g" x1={L} x2={W - R} y1={yy} y2={yy} />
              <text class="yt" x={L - 6} y={yy + 4}>{p.fmt(tv)}</text>
            {/each}
            {#each p.series as s}
              {#if p.on[s.col]}
                <path d={pathOf(s.col, p.sc, p.top, p.area)} fill={p.area ? s.color : 'none'} fill-opacity={p.area ? 0.35 : 0}
                      stroke={s.color} stroke-width="1.8" stroke-dasharray={s.dash ?? ''} />
              {/if}
            {/each}
          {:else}
            <text class="yt none" x={L + 8} y={p.top + PH / 2}>No series selected or no data in this range</text>
          {/if}
        {/each}
        {#if fireIdx >= 0}
          <line class="fire" x1={x(fireIdx)} x2={x(fireIdx)} y1={TOP} y2={H - AX} stroke-dasharray="4 3" />
          <text class="fl" x={x(fireIdx) - 4} y={TOP + 10}>Aug 2023 fires</text>
        {/if}
        {#each yearTicks as i}
          <line class="g" x1={x(i)} x2={x(i)} y1={H - AX} y2={H - AX + 4} />
          <text class="xt" x={x(i)} y={H - 6}>{view[i].month.slice(0, 4)}</text>
        {/each}
        {#if brush}
          <rect class="brush" x={x(Math.min(...brush))} y={TOP} width={Math.max(1, x(Math.max(...brush)) - x(Math.min(...brush)))} height={H - TOP - AX} />
        {/if}
        {#if hover !== null && view[hover]}
          <line class="cross" x1={x(hover)} x2={x(hover)} y1={TOP} y2={H - AX} />
        {/if}
      </svg>

      <div class="read" aria-live="polite">
        {#if hover !== null && view[hover]}
          {@const r = view[hover]}
          <b>{r.month}</b>
          {#each PANELS as p}{#each p.series as s}{#if on[s.col]}
            <span><i style="background:{s.color}"></i>{s.label} {r[s.col] === null ? 'n/a' : p.fmt(r[s.col])}</span>
          {/if}{/each}{/each}
        {:else}
          <span class="muted">Hover or use the arrow keys to read every month. Drag to zoom to a period; click a month to set the map’s year (shaded: {year}).</span>
        {/if}
      </div>
    </div>
    <p class="note">NDVI/NBR: author’s Sentinel-2 study-area means (Dec 2018–Dec 2023). DSCI: county-wide, monthly mean of the weekly U.S. Drought Monitor index.
      Rainfall: one coarse pixel (5–11 km) at the study-area centre, so the four products disagree; trust what they share. A gap means no data that month.</p>
  {/if}
</section>

<style>
  .panel { background: var(--card); border-top: 1px solid var(--line); padding: 8px 14px 10px; max-height: 50vh; overflow-y: auto; }
  header { display: flex; align-items: center; }
  h2 { margin: 0; border: 0; padding: 0; font-size: .8rem; flex: 1; }
  .x { background: none; border: 1px solid var(--line); color: var(--ink-2); width: 26px; height: 26px; line-height: 1; font-size: 1.1rem; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 6px 0; font-size: .82rem; }
  fieldset { border: 0; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; }
  legend { float: left; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-size: .7rem; margin-right: 4px; }
  select { background: var(--paper-2); border: 1px solid var(--line); padding: 1px 4px; font-family: var(--mono); font-size: .8rem; }
  .b { background: var(--paper-2); border: 1px solid var(--line); padding: 2px 9px; font-size: .78rem; }
  .b:hover { border-color: var(--forest); }
  .s { display: inline-flex; gap: 4px; align-items: center; }
  svg[role='img'] { width: 100%; height: auto; display: block; border: 1px solid var(--line); }
  .bg { fill: var(--card); }
  .t { fill: var(--ink); font-size: 11px; font-weight: 600; }
  .yt { fill: var(--muted); font: 10px var(--mono); text-anchor: end; }
  .yt.none { text-anchor: start; }
  .xt { fill: var(--muted); font: 10px var(--mono); text-anchor: middle; }
  .g { stroke: #252c31; }
  .yr { fill: var(--forest); fill-opacity: .12; }
  .fire { stroke: var(--fire); stroke-width: 1.4; }
  .fl { fill: var(--fire); font-size: 10px; text-anchor: end; }
  .cross { stroke: var(--ink); stroke-width: 1; }
  .brush { fill: var(--forest); fill-opacity: .18; stroke: var(--forest); }
  svg[role='img'] { cursor: crosshair; touch-action: none; }
  .read { min-height: 1.7em; display: flex; flex-wrap: wrap; gap: 4px 14px; font: .78rem var(--mono); margin-top: 4px; }
  .read i { display: inline-block; width: 9px; height: 9px; margin-right: 4px; }
  .note { font-size: .72rem; color: var(--muted); margin: 4px 0 0; }
  .err { color: var(--fire); }
</style>
