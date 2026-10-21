<script>
  // Accessible SVG time-series chart. Each series is drawn with its own colour AND
  // dash pattern (never colour alone), and the same numbers are available as a
  // table for screen readers and anyone who wants the exact values.
  export let title;
  export let series = [];        // [{ label, color, dash?, area?, points: [{date, value}] }]
  export let from;               // 'YYYY-MM-DD'
  export let to;
  export let yMin;
  export let yMax;
  export let yLabel = '';
  export let yTicks = [];
  export let markers = [];       // [{ date, label }]
  export let format = (v) => v.toFixed(3);

  const W = 720, H = 240, L = 48, R = 16, T = 16, B = 30;
  let showTable = false;
  let hover = null;

  $: t0 = Date.parse(from);
  $: t1 = Date.parse(to);
  $: x = (d) => L + ((Date.parse(d) - t0) / (t1 - t0)) * (W - L - R);
  $: y = (v) => H - B - ((Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin)) * (H - B - T);
  $: visible = series.map((s) => ({ ...s, points: s.points.filter((p) => p.date >= from && p.date <= to) }));
  $: years = (() => {
    const out = [];
    for (let yr = new Date(from).getUTCFullYear(); yr <= new Date(to).getUTCFullYear(); yr++) {
      const d = `${yr}-01-01`;
      if (d >= from && d <= to) out.push(yr);
    }
    return out;
  })();

  function pathOf(s) {
    if (!s.points.length) return '';
    const line = s.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.date).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
    return s.area ? `${line} L${x(s.points[s.points.length - 1].date)},${H - B} L${x(s.points[0].date)},${H - B} Z` : line;
  }

  function onMove(e) {
    const svg = e.currentTarget;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const { x: sx } = pt.matrixTransform(svg.getScreenCTM().inverse());
    const t = t0 + ((sx - L) / (W - L - R)) * (t1 - t0);
    const rows = visible.map((s) => {
      let best = null;
      for (const p of s.points) if (!best || Math.abs(Date.parse(p.date) - t) < Math.abs(Date.parse(best.date) - t)) best = p;
      return best && { label: s.label, color: s.color, ...best };
    }).filter(Boolean);
    hover = rows.length ? { x: Math.max(L, Math.min(W - R, sx)), rows } : null;
  }

  $: tableRows = (() => {
    const dates = [...new Set(visible.flatMap((s) => s.points.map((p) => p.date)))].sort();
    return dates.map((d) => [d, ...visible.map((s) => s.points.find((p) => p.date === d)?.value)]);
  })();
</script>

<figure class="chart">
  <figcaption>
    <span class="title">{title}</span>
    <span class="keys">
      {#each visible as s}
        <span class="key"><svg width="22" height="10" aria-hidden="true"><line x1="0" y1="5" x2="22" y2="5"
          stroke={s.color} stroke-width="2.5" stroke-dasharray={s.dash ?? ''} /></svg>{s.label}</span>
      {/each}
    </span>
  </figcaption>

  {#if visible.every((s) => !s.points.length)}
    <p class="empty">No data in the selected date range.</p>
  {:else}
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="{title}, {from} to {to}. Use the data table for exact values."
         on:mousemove={onMove} on:mouseleave={() => (hover = null)}>
      {#each yTicks as v}
        <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} class="grid" />
        <text x={L - 6} y={y(v) + 4} class="tick end">{format(v)}</text>
      {/each}
      {#each years as yr}
        <line x1={x(`${yr}-01-01`)} x2={x(`${yr}-01-01`)} y1={T} y2={H - B} class="grid v" />
        <text x={x(`${yr}-01-01`)} y={H - 10} class="tick mid">{yr}</text>
      {/each}
      {#if yLabel}<text x="12" y={T + 4} class="tick ylabel" transform="rotate(-90 12 {T + 4})" text-anchor="end">{yLabel}</text>{/if}

      {#each visible as s}
        <path d={pathOf(s)} fill={s.area ? s.color : 'none'} fill-opacity={s.area ? 0.25 : 0}
              stroke={s.color} stroke-width={s.area ? 1 : 2} stroke-dasharray={s.dash ?? ''} />
      {/each}

      {#each markers.filter((m) => m.date >= from && m.date <= to) as m}
        <line x1={x(m.date)} x2={x(m.date)} y1={T} y2={H - B} class="marker" />
        <text x={x(m.date) - 4} y={T + 10} class="marker-label">{m.label}</text>
      {/each}

      {#if hover}
        <line x1={hover.x} x2={hover.x} y1={T} y2={H - B} class="cursor" />
      {/if}
    </svg>
    <div class="readout" aria-hidden="true">
      {#if hover}
        {#each hover.rows as r}<span><i style="background:{r.color}"></i>{r.label}: <b>{format(r.value)}</b> ({r.date})</span>{/each}
      {:else}<span class="muted">Hover the chart for values.</span>{/if}
    </div>
  {/if}

  <button class="tablebtn" aria-expanded={showTable} on:click={() => (showTable = !showTable)}>
    {showTable ? 'Hide' : 'Show'} data table
  </button>
  {#if showTable}
    <div class="tablewrap">
      <table>
        <thead><tr><th>Date</th>{#each visible as s}<th>{s.label}</th>{/each}</tr></thead>
        <tbody>{#each tableRows as row}<tr>{#each row as v, i}<td>{i === 0 ? v : v === undefined ? '—' : format(v)}</td>{/each}</tr>{/each}</tbody>
      </table>
    </div>
  {/if}
</figure>

<style>
  .chart { margin: 0; }
  figcaption { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 14px; margin-bottom: 4px; }
  .title { font-weight: 700; color: var(--forest); }
  .keys { display: flex; flex-wrap: wrap; gap: 12px; font-size: .85rem; color: var(--ink-2); }
  .key { display: inline-flex; align-items: center; gap: 6px; }
  svg[role='img'] { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); border-radius: 0; }
  .grid { stroke: #252c31; }
  .grid.v { stroke-dasharray: 2 3; }
  .tick { fill: var(--muted); font-size: 11px; }
  .tick.end { text-anchor: end; }
  .tick.mid { text-anchor: middle; }
  .marker { stroke: var(--fire); stroke-width: 1.5; stroke-dasharray: 5 3; }
  .marker-label { fill: var(--fire); font-size: 11px; font-weight: 700; text-anchor: end; }
  .cursor { stroke: var(--ink-2); stroke-width: 1; }
  .readout { min-height: 1.6em; font-size: .82rem; display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 4px; }
  .readout i { display: inline-block; width: 10px; height: 10px; border-radius: 0; margin-right: 4px; }
  .empty { padding: 30px; text-align: center; color: var(--amber); border: 1px dashed var(--line); border-radius: 0; }
  .tablebtn { margin-top: 4px; background: none; border: 1px solid var(--line); border-radius: 0; padding: .25em .7em; font-size: .82rem; }
  .tablewrap { max-height: 260px; overflow: auto; margin-top: 6px; border: 1px solid var(--line); border-radius: 0; }
  .tablewrap table { font-size: .82rem; }
  .tablewrap th { position: sticky; top: 0; background: var(--paper-2); }
  /* The 720-wide viewBox shrinks to about half on a phone, taking 11px labels to
     about 6px. Larger user-unit sizes keep them near 10px there. */
  @media (max-width: 640px) {
    .tick, .marker-label { font-size: 20px; }
    /* At that size the rotated unit label collides with the top tick; every
       chart title already names the unit. */
    .ylabel { display: none; }
  }
</style>
