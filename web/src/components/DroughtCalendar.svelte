<script>
  // Seven years of Maui County drought, one cell per week. Colour is ONE
  // sequential hue (more drought = darker), the U.S. Drought Monitor's DSCI;
  // weeks with any D4 "exceptional" drought also carry a white dot, so the
  // worst weeks read by shape as well as shade. The fire week is outlined.
  import { onMount } from 'svelte';
  import { droughtWeeks } from '../lib/adapters.ts';

  let weeks = [], error = null, hover = null, showTable = false;
  onMount(async () => {
    try { weeks = await droughtWeeks(); } catch (e) { error = e.message; }
  });

  const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const FIRE_WEEK = '2023-08-08';
  const MAX = 350;
  const CELL = 12, GAP = 2, STEP = CELL + GAP, L = 44, T = 22;
  const W = L + 53 * STEP + 8, H = T + YEARS.length * STEP + 6;

  // Panel grey to bright amber: lightness rises monotonically with DSCI.
  const LO = [34, 39, 44], HI = [242, 156, 52];
  const colour = (v) => {
    const t = Math.max(0, Math.min(1, v / MAX));
    return `rgb(${LO.map((c, i) => Math.round(c + (HI[i] - c) * t)).join(',')})`;
  };
  const dayOfYear = (d) => (Date.parse(d) - Date.UTC(+d.slice(0, 4), 0, 1)) / 86400000;
  const col = (d) => Math.min(52, Math.floor(dayOfYear(d) / 7));

  $: cells = weeks.filter((w) => YEARS.includes(+w.date.slice(0, 4)))
    .map((w) => ({ ...w, x: L + col(w.date) * STEP, y: T + YEARS.indexOf(+w.date.slice(0, 4)) * STEP }));
  // The fire week is the first weekly report on or after 8 Aug 2023.
  $: fireCell = cells.find((c) => c.date >= FIRE_WEEK);
  $: summary = YEARS.map((y) => {
    const ws = weeks.filter((w) => w.date.startsWith(String(y)));
    return {
      year: y, n: ws.length,
      mean: ws.length ? ws.reduce((a, w) => a + w.dsci, 0) / ws.length : 0,
      d4: ws.filter((w) => w.d4 > 0).length,
      maxD4: Math.max(0, ...ws.map((w) => w.d4)),
    };
  });
  $: worst = summary.reduce((a, b) => (b.mean > a.mean ? b : a), summary[0]);
  const pct = (v) => `${Math.round(v)}%`;

  // One handler for the whole grid (as in LineChart): find the week under the pointer.
  function onMove(e) {
    const svg = e.currentTarget;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const { x, y } = pt.matrixTransform(svg.getScreenCTM().inverse());
    hover = cells.find((c) => x >= c.x && x < c.x + STEP && y >= c.y && y < c.y + STEP) ?? null;
  }
</script>

<figure class="cal">
  <figcaption>
    <span class="title">Seven years of drought, week by week</span>
    <span class="sub">Maui County, U.S. Drought Monitor. Darker = more of the county in deeper drought.</span>
  </figcaption>

  {#if error}
    <p class="err" role="alert">Couldn’t load drought weeks: {error}</p>
  {:else if !weeks.length}
    <p class="muted" aria-busy="true">Loading…</p>
  {:else}
    <div class="scroll">
    <svg viewBox="0 0 {W} {H}" role="img" on:mousemove={onMove} on:mouseleave={() => (hover = null)}
         aria-label="Weekly drought index for Maui County, 2018 to 2024. {worst.year} was the worst year, with {worst.d4} weeks of exceptional drought. Use the table for exact values.">
      {#each MONTHS as m, i}
        <text x={L + (i * 53 / 12) * STEP} y={T - 8} class="tick">{m}</text>
      {/each}
      {#each YEARS as y, i}
        <text x={L - 8} y={T + i * STEP + CELL - 2} class="tick end" class:strong={y === worst.year}>{y}</text>
      {/each}
      {#each cells as c (c.date)}
        <rect x={c.x} y={c.y} width={CELL} height={CELL} fill={colour(c.dsci)} />
        {#if c.d4 > 0}<circle cx={c.x + CELL / 2} cy={c.y + CELL / 2} r="2.2" class="d4" pointer-events="none" />{/if}
      {/each}
      {#if fireCell}
        <rect x={fireCell.x - 1.5} y={fireCell.y - 1.5} width={CELL + 3} height={CELL + 3} class="fire" pointer-events="none" />
      {/if}
      {#if hover}
        <rect x={hover.x - 1} y={hover.y - 1} width={CELL + 2} height={CELL + 2} class="hover" pointer-events="none" />
      {/if}
    </svg>
    </div>
    <p class="swipe muted" aria-hidden="true">Swipe the grid sideways for the rest of the year →</p>

    <div class="readout" aria-hidden="true">
      {#if hover}
        Week of <b>{hover.date}</b> · DSCI <b>{hover.dsci}</b> · severe drought (D2+) over {pct(hover.d2)} of the county
        {#if hover.d4 > 0} · <b>exceptional (D4) over {pct(hover.d4)}</b>{/if}
      {:else}<span class="muted">Hover a week for its numbers.</span>{/if}
    </div>

    <div class="legend">
      <span class="ramp" aria-hidden="true"><i style="background:linear-gradient(90deg,{colour(0)},{colour(MAX)})"></i>
        <span class="ends"><span>0 no drought</span><span>{MAX}</span></span></span>
      <span class="key"><svg width="14" height="14" aria-hidden="true"><rect width="14" height="14" fill={colour(300)} /><circle cx="7" cy="7" r="2.2" class="d4" /></svg>any exceptional (D4) drought that week</span>
      <span class="key"><svg width="16" height="16" aria-hidden="true"><rect x="1.5" y="1.5" width="13" height="13" class="fire" /></svg>Aug 8, 2023 fires</span>
    </div>

    <p class="small">{worst.year} stands out: the highest average drought index of these seven years
      ({Math.round(worst.mean)}) and {worst.d4} weeks with exceptional drought somewhere in the county.
      <span class="muted">County-wide index, not a measurement of any one place; DSCI = 0 (none) to 500 (all of the county in D4).</span></p>

    <button class="tablebtn" aria-expanded={showTable} on:click={() => (showTable = !showTable)}>{showTable ? 'Hide' : 'Show'} yearly table</button>
    {#if showTable}
      <table>
        <thead><tr><th>Year</th><th>Weeks</th><th>Mean DSCI</th><th>Weeks with D4</th><th>Most of county in D4</th></tr></thead>
        <tbody>{#each summary as r}<tr class:hl={r.year === worst.year}><td>{r.year}</td><td>{r.n}</td><td>{Math.round(r.mean)}</td><td>{r.d4}</td><td>{pct(r.maxD4)}</td></tr>{/each}</tbody>
      </table>
    {/if}
  {/if}
</figure>

<style>
  .cal { margin: 0; }
  figcaption { display: flex; flex-direction: column; gap: 2px; margin-bottom: 6px; }
  .title { font-weight: 700; color: var(--forest); font-size: 1.05rem; }
  .sub { color: var(--ink-2); font-size: .9rem; }
  svg[role='img'] { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); border-radius: 0; }
  .tick { fill: var(--muted); font-size: 10px; }
  .tick.end { text-anchor: end; }
  .tick.strong { fill: var(--ink); font-weight: 700; }
  .d4 { fill: #111; }
  .fire { fill: none; stroke: var(--fire); stroke-width: 2; }
  .hover { fill: none; stroke: var(--ink); stroke-width: 1.5; }
  .readout { min-height: 1.6em; font-size: .85rem; margin-top: 4px; }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 18px; align-items: center; font-size: .82rem; color: var(--ink-2); margin: 4px 0 8px; }
  .ramp { display: inline-flex; flex-direction: column; gap: 2px; }
  .ramp i { display: block; width: 160px; height: 10px; border-radius: 0; }
  .ends { display: flex; justify-content: space-between; font-size: .72rem; color: var(--muted); }
  .key { display: inline-flex; align-items: center; gap: 6px; }
  .tablebtn { background: none; border: 1px solid var(--line); border-radius: 0; padding: .25em .7em; font-size: .82rem; }
  table { margin-top: 6px; font-size: .85rem; }
  tr.hl { background: var(--paper-2); font-weight: 600; }
  .err { color: var(--fire); }
  /* 53 weeks cannot shrink to a phone's width and stay legible, so the grid keeps a
     readable size and scrolls sideways inside its own box (the page never does). */
  .scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .swipe { display: none; font-size: .78rem; margin: 2px 0 0; }
  @media (max-width: 640px) {
    .scroll svg[role='img'] { min-width: 660px; }
    .tick { font-size: 12px; }
    .swipe { display: block; }
  }
</style>
