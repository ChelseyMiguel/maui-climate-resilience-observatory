<script>
  // Was 2022 unusual? Each year's dry-season greenness against a 2000-2018
  // normal (shaded band = normal ± 1 standard deviation). Emphasis chart: the
  // normal-period years are muted, the studied years are teal, 2022 is amber and
  // larger. Hidden entirely until the Landsat export exists.
  import { onMount } from 'svelte';
  import { ndviBaseline } from '../lib/adapters.ts';

  let data = null, hover = null, showTable = false;
  onMount(async () => {
    try { data = await ndviBaseline(); } catch { data = null; }
  });

  const W = 640, H = 260, L = 50, R = 16, T = 16, B = 34, Y0 = 2000, Y1 = 2024;
  $: rows = data?.rows ?? [];
  $: vals = rows.filter((r) => r.ndvi !== null).map((r) => r.ndvi);
  $: lo = data ? Math.floor((Math.min(...vals, data.normal.mean - 2 * data.normal.sd) - 0.02) * 20) / 20 : 0;
  $: hi = data ? Math.ceil((Math.max(...vals, data.normal.mean + 2 * data.normal.sd) + 0.02) * 20) / 20 : 1;
  $: x = (yr) => L + ((yr - Y0) / (Y1 - Y0)) * (W - L - R);
  $: y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  $: ticks = (() => { const out = []; for (let v = lo; v <= hi + 1e-9; v += 0.05) out.push(+v.toFixed(2)); return out; })();
  // Break the line at a missing year rather than bridging it: no data is not a trend.
  $: path = rows.map((r, i) => (r.ndvi === null ? '' : `${i && rows[i - 1].ndvi !== null ? 'L' : 'M'}${x(r.year)},${y(r.ndvi)}`)).join(' ');
  $: y22 = rows.find((r) => r.year === 2022);
  $: firstOli = rows.find((r) => /LANDSAT_8|LANDSAT_9/.test(r.sensors))?.year;
  const kind = (yr) => (yr === 2022 ? 'y2022' : yr >= 2019 ? 'study' : 'normal');
  // 2 -> "2nd", 11 -> "11th", 23 -> "23rd"
  const ordinal = (n) => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th');
  const fmt = (v) => (v < 0 ? '−' : '+') + Math.abs(v).toFixed(1);

  function onMove(e) {
    const svg = e.currentTarget, pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const { x: sx } = pt.matrixTransform(svg.getScreenCTM().inverse());
    const yr = Math.round(Y0 + ((sx - L) / (W - L - R)) * (Y1 - Y0));
    hover = rows.find((r) => r.year === yr && r.ndvi !== null) ?? null;
  }
</script>

{#if data}
<div class="card nb">
  <h2>Was 2022 unusual? 25 years of dry-season greenness</h2>
  <p class="small">May–September Landsat NDVI over the same 1.5 km study area, each year read against the
    {data.normal.years[0]}–{data.normal.years[1]} normal, before the years this project studies.</p>

  {#if y22?.z != null}
    <p class="stat"><b>2022 was the {y22.rank_lowest === 1 ? 'lowest' : `${ordinal(y22.rank_lowest)} lowest`}</b>
      of {data.years_with_data} years ({fmt(y22.z)} standard deviations from the normal).</p>
  {/if}

  <figure class="chart">
    <svg viewBox="0 0 {W} {H}" role="img" on:mousemove={onMove} on:mouseleave={() => (hover = null)}
         aria-label="Dry-season NDVI 2000 to 2024 against the 2000 to 2018 normal. Use the table for exact values.">
      <rect x={L} width={W - L - R} y={y(data.normal.mean + data.normal.sd)}
            height={y(data.normal.mean - data.normal.sd) - y(data.normal.mean + data.normal.sd)} class="band" />
      <line x1={L} x2={W - R} y1={y(data.normal.mean)} y2={y(data.normal.mean)} class="mean" />
      {#each ticks as v}<text x={L - 8} y={y(v) + 4} class="tick end">{v.toFixed(2)}</text>{/each}
      {#each [2000, 2005, 2010, 2015, 2020, 2024] as yr}<text x={x(yr)} y={H - 12} class="tick mid">{yr}</text>{/each}
      {#if firstOli}
        <line x1={x(firstOli) - 6} x2={x(firstOli) - 6} y1={T} y2={H - B} class="sensor" />
        <text x={x(firstOli) - 2} y={T + 10} class="tick">Landsat 8 →</text>
      {/if}
      <path d={path} class="line" />
      {#each rows.filter((r) => r.ndvi !== null) as r (r.year)}
        <circle cx={x(r.year)} cy={y(r.ndvi)} r={r.year === 2022 ? 6 : 4.5} class={'pt ' + kind(r.year)} class:few={r.few_scenes} />
      {/each}
      {#if hover}<circle cx={x(hover.year)} cy={y(hover.ndvi)} r="10" class="halo" />{/if}
    </svg>
    <div class="readout" aria-hidden="true">
      {#if hover}<b>{hover.year}</b> · NDVI {hover.ndvi.toFixed(3)} · {fmt(hover.z)} SD · {hover.n_scenes} clear scenes ({hover.sensors.replace(/LANDSAT_/g, 'L')}){hover.few_scenes ? ' · few scenes, less reliable' : ''}
      {:else}<span class="muted">Hover a year.</span>{/if}
    </div>
    <div class="keys">
      <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="4.5" class="pt normal" /></svg>normal period</span>
      <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="4.5" class="pt study" /></svg>2019–2024</span>
      <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" class="pt y2022" /></svg>2022</span>
      <span><svg width="22" height="12" aria-hidden="true"><rect width="22" height="12" class="band" /></svg>normal ± 1 SD</span>
      <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="4.5" class="pt normal few" /></svg>fewer than 3 clear scenes</span>
    </div>
  </figure>

  <ul class="caveats small">{#each data.notes as n}<li>{n}</li>{/each}</ul>
  <button class="tablebtn" aria-expanded={showTable} on:click={() => (showTable = !showTable)}>{showTable ? 'Hide' : 'Show'} data table</button>
  {#if showTable}
    <div class="tablewrap"><table>
      <thead><tr><th>Year</th><th>NDVI</th><th>SD from normal</th><th>Scenes</th><th>Sensors</th></tr></thead>
      <tbody>{#each rows as r}<tr class:hl={r.year === 2022}><td>{r.year}</td><td>{r.ndvi?.toFixed(3) ?? '—'}</td><td>{r.z == null ? '—' : fmt(r.z)}</td><td>{r.n_scenes}</td><td>{r.sensors || '—'}</td></tr>{/each}</tbody>
    </table></div>
  {/if}
</div>
{/if}

<style>
  .nb { display: grid; gap: 10px; }
  h2 { margin: 0; }
  .stat { margin: 0; background: var(--paper-2); border-left: 3px solid var(--teal); padding: 8px 12px; border-radius: 4px; }
  .chart { margin: 0; }
  svg[role='img'] { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); border-radius: 8px; }
  .band { fill: #d9e8e3; }
  .mean { stroke: var(--teal); stroke-width: 1.5; stroke-dasharray: 5 4; }
  .sensor { stroke: var(--muted); stroke-dasharray: 2 3; }
  .line { fill: none; stroke: #b8beb9; stroke-width: 1.5; }
  .pt { stroke: var(--card); stroke-width: 2; }
  .pt.normal { fill: #6b766f; }
  .pt.study { fill: var(--teal); }
  .pt.y2022 { fill: var(--amber); }
  .pt.few { fill-opacity: .35; stroke: #6b766f; stroke-width: 1.2; }
  .halo { fill: none; stroke: var(--ink); stroke-width: 1.5; }
  .tick { fill: var(--muted); font-size: 11px; }
  .end { text-anchor: end; }
  .mid { text-anchor: middle; }
  .readout { min-height: 1.6em; font-size: .85rem; margin-top: 4px; }
  .keys { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: .8rem; color: var(--ink-2); }
  .keys span { display: inline-flex; align-items: center; gap: 5px; }
  .caveats { margin: 0; padding-left: 1.2em; color: var(--ink-2); }
  .tablebtn { width: fit-content; background: none; border: 1px solid var(--line); border-radius: 6px; padding: .25em .7em; font-size: .82rem; }
  .tablewrap { max-height: 260px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; }
  tr.hl { background: var(--paper-2); font-weight: 600; }
  @media (max-width: 640px) { .tick { font-size: 19px; } }
</style>
