<script>
  // One Analysis-workspace figure: a Plotly chart in the site's dark theme, with
  // a provenance line, a tag saying whether it uses the study's own data or an
  // additional exploratory dataset, and CSV / publication-PNG export.
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { toCsv } from '../lib/series.js';

  export let Plotly;             // the loaded plotly.js module
  export let id;
  export let title;
  export let tag = 'study';      // 'study' | 'exploratory' | 'mixed'
  export let meta = '';          // resolution, coverage, method
  export let data = [];
  export let layout = {};
  export let rows = [];          // CSV rows for export
  export let columns = null;
  export let height = 340;
  export let note = '';

  const dispatch = createEventDispatcher();
  const TAGS = { study: 'Study data', exploratory: 'Exploratory dataset', mixed: 'Study + exploratory' };
  const INK = '#b3bcc1', GRID = '#252c31', BG = '#151a1e';
  let el, ro;

  function themed(l, dark = true) {
    const ink = dark ? INK : '#222', grid = dark ? GRID : '#ddd', bg = dark ? BG : '#fff';
    const axis = (a = {}) => ({ gridcolor: grid, zerolinecolor: dark ? '#4a555c' : '#999', linecolor: dark ? '#4a555c' : '#999',
      tickfont: { family: 'ui-monospace, Menlo, Consolas, monospace', size: 10, color: ink }, ...a,
      title: { font: { size: 11, color: ink }, ...(a.title ?? {}) } });
    const out = {
      ...l, paper_bgcolor: bg, plot_bgcolor: bg, font: { family: 'system-ui, sans-serif', size: 11, color: ink },
      margin: { l: 56, r: 16, t: 10, b: 44, ...(l.margin ?? {}) },
      hoverlabel: { bgcolor: dark ? '#0f1215' : '#fff', bordercolor: dark ? '#4a555c' : '#999', font: { family: 'ui-monospace, Menlo, monospace', size: 11, color: dark ? '#e4e8ea' : '#111' } },
      legend: { orientation: 'h', y: -0.22, font: { size: 10, color: ink }, ...(l.legend ?? {}) },
    };
    for (const k of Object.keys(l)) if (/^[xy]axis\d*$/.test(k)) out[k] = axis(l[k]);
    if (!l.xaxis) out.xaxis = axis(); if (!l.yaxis) out.yaxis = axis();
    if (!dark && l.annotations) out.annotations = l.annotations.map((n) => ({ ...n, bgcolor: '#ffffff', bordercolor: '#999', font: { ...(n.font ?? {}), color: '#111' } }));
    if (l.scene) {
      const s = (a) => ({ ...axis(a), backgroundcolor: bg, showbackground: true });
      out.scene = { ...l.scene, xaxis: s(l.scene.xaxis), yaxis: s(l.scene.yaxis), zaxis: s(l.scene.zaxis) };
    }
    return out;
  }
  const config = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'sendDataToCloud'],
    toImageButtonOptions: { format: 'png', filename: id, scale: 2 } };

  function draw() {
    if (!el || !Plotly) return;
    Plotly.react(el, data, themed(layout), config);
  }
  $: if (el && Plotly) { data; layout; draw(); }

  onMount(() => {
    draw();
    el.on?.('plotly_click', (ev) => dispatch('pick', ev.points?.[0]));
    el.on?.('plotly_relayout', (ev) => dispatch('relayout', ev));
    ro = new ResizeObserver(() => Plotly?.Plots.resize(el));
    ro.observe(el);
  });
  onDestroy(() => { ro?.disconnect(); if (el && Plotly) Plotly.purge(el); });

  function save(blob, name) {
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name });
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  const csv = () => save(new Blob([toCsv(rows, columns ?? Object.keys(rows[0] ?? {}))], { type: 'text/csv' }), `${id}.csv`);
  // Publication figure: light background, 3x scale, title and provenance baked in.
  async function png() {
    const l = themed({ ...layout, title: { text: `${title}<br><sup>${meta}</sup>`, font: { size: 13 }, x: 0.01 },
                       margin: { ...(layout.margin ?? {}), t: 64 } }, false);
    const url = await Plotly.toImage({ data, layout: l }, { format: 'png', width: 1100, height: height + 70, scale: 3 });
    save(await (await fetch(url)).blob(), `${id}.png`);
  }
</script>

<section class="plot" aria-labelledby="{id}-h">
  <header>
    <h3 id="{id}-h">{title}</h3>
    <span class="tag {tag}">{TAGS[tag]}</span>
    <button on:click={csv} disabled={!rows.length}>CSV</button>
    <button on:click={png} disabled={!Plotly}>PNG</button>
  </header>
  {#if meta}<p class="meta">{meta}</p>{/if}
  <div bind:this={el} class="fig" style="height:{height}px" data-plot={id}></div>
  {#if note}<p class="note">{@html note}</p>{/if}
  <slot />
</section>

<style>
  .plot { background: var(--card); border: 1px solid var(--line); padding: 8px 10px 10px; min-width: 0; }
  header { display: flex; align-items: center; gap: 8px; }
  h3 { flex: 1; margin: 0; font: 600 .82rem var(--sans); color: var(--ink); text-transform: uppercase; letter-spacing: .06em; }
  .tag { font: 600 .64rem var(--sans); letter-spacing: .06em; text-transform: uppercase; padding: 1px 6px; border: 1px solid; }
  .tag.study { color: var(--forest); } .tag.exploratory { color: var(--teal); } .tag.mixed { color: var(--amber); }
  button { background: var(--paper-2); border: 1px solid var(--line); color: var(--ink-2); padding: 1px 8px; font-size: .74rem; }
  button:hover:not(:disabled) { border-color: var(--forest); }
  .meta { font-size: .72rem; color: var(--muted); margin: 3px 0 4px; }
  .fig { width: 100%; }
  .note { font-size: .74rem; color: var(--muted); margin: 6px 0 0; }
  :global(.plot .modebar) { background: transparent !important; }
</style>
