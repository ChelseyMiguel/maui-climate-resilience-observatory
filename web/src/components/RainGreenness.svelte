<script>
  // Rain and greenness. Every number comes from lib/rainfall.py; this only draws.
  // Four rainfall products are shown because no single global product resolves
  // Upcountry Maui's steep rainfall gradient: where they agree, trust the signal.
  import { onMount } from 'svelte';
  import LineChart from './LineChart.svelte';
  import { rainfall } from '../lib/adapters.ts';
  import { toCsv, downloadCsv } from '../lib/csv.ts';

  // Categorical, fixed order, validated (dataviz validate_palette.js on #fffdf8):
  // aqua is below 3:1 contrast, so every series also has its own dash and the
  // values are in the data table.
  const PRODUCTS = [
    { key: 'chirps', label: 'CHIRPS', color: '#2a78d6' },
    { key: 'terraclimate', label: 'TerraClimate', color: '#eb6834', dash: '6 4' },
    { key: 'imerg', label: 'IMERG', color: '#1baf7a', dash: '2 3' },
    { key: 'era5land', label: 'ERA5-Land', color: '#6250d6', dash: '10 3 2 3' },
  ];
  const FIRE = [{ date: '2023-08-08', label: 'Aug 8, 2023 fires' }];

  let data = null, error = null, strict = false;
  onMount(async () => {
    try { data = await rainfall(); } catch (e) { error = e.message; }
  });

  const minus = (n, d = 2) => (n < 0 ? '−' : '+') + Math.abs(n).toFixed(d);
  const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

  // One bar per window: the median r across the four products, with a whisker
  // from the lowest to the highest product. A short whisker = the products agree.
  function summarise(rows) {
    return rows.map((w) => {
      const rs = PRODUCTS.map((p) => w.products[p.key].r).filter((r) => r !== null);
      return { months: w.months, mid: rs.length ? median(rs) : null, lo: Math.min(...rs), hi: Math.max(...rs), n: rs.length };
    });
  }
  $: series = data ? PRODUCTS.map((p) => ({ ...p, points: data.monthly.filter((m) => m[p.key] !== null).map((m) => ({ date: `${m.month}-01`, value: m[p.key] })) })) : [];
  $: bars = data ? summarise(strict ? data.windowsNdviDeseasonalised : data.windowsNdvi) : [];
  $: best = bars.filter((b) => b.mid !== null).reduce((a, b) => (b.mid > a.mid ? b : a), { mid: -Infinity });
  $: one = bars.find((b) => b.months === 1);
  $: dsci3 = data ? summarise(data.windowsDsci).find((b) => b.months === 3) : null;
  $: agreeLo = data ? Math.min(...data.agreement.map((a) => a.r)) : null;
  $: agreeHi = data ? Math.max(...data.agreement.map((a) => a.r)) : null;

  const W = 600, H = 220, L = 56, R = 16, T = 16, B = 44, Y_LO = -0.2, Y_HI = 1;
  const y = (r) => T + ((Y_HI - r) / (Y_HI - Y_LO)) * (H - T - B);
  $: slot = (W - L - R) / Math.max(bars.length, 1);

  function exportCsv() {
    downloadCsv('pukalani_rainfall_monthly.csv', toCsv(data.monthly, [
      { header: 'month', value: (m) => m.month },
      ...PRODUCTS.map((p) => ({ header: `${p.key}_mm`, value: (m) => m[p.key]?.toFixed(1) })),
    ], [
      'Monthly rainfall at the Pukalani study-area centre, 2018-2024. Rural Hawaii Climate Resilience Observatory (student research project).',
      'Sources: CHIRPS daily (UCSB-CHG), TerraClimate (U. Idaho), IMERG monthly V07 (NASA GPM), ERA5-Land monthly (ECMWF), via Google Earth Engine.',
      ...data.notes,
    ]));
  }
</script>

<div class="rg">
  <h2>Rain and greenness</h2>
  <p class="small">Rainfall measured from space by four independent products, at the grid square containing the study
    area. Drought indices are built partly from rain, so this checks the drought story against a measurement.</p>

  {#if error}
    <p class="err" role="alert">Couldn’t load rainfall: {error}</p>
  {:else if !data}
    <p class="muted" aria-busy="true">Loading…</p>
  {:else}
    <LineChart title="Monthly rainfall at the study area (mm)" from="2018-01-01" to="2024-12-31"
      yMin={0} yMax={360} yTicks={[0, 100, 200, 300]} yLabel="mm" format={(v) => v.toFixed(0)}
      markers={FIRE} {series} />
    <p class="small muted">The four products rise and fall together (r between {agreeLo.toFixed(2)} and
      {agreeHi.toFixed(2)} for every pair) but disagree on amounts, IMERG most of all. That is why no single
      product’s millimetres are quoted here.</p>

    {#if best.months !== undefined && one}
      <p class="stat"><b>Rain over the last {best.months} months</b> matches this month’s greenness best
        (median r = {minus(best.mid)} across the four products), against {minus(one.mid)} for one month alone{strict ? ', with the seasonal cycle removed' : ''}.</p>
    {/if}

    <figure class="chart">
      <figcaption>
        <span class="title">How well does recent rain match greenness?</span>
        <span class="seg" role="group" aria-label="Seasonal cycle">
          <button aria-pressed={!strict} class:on={!strict} on:click={() => (strict = false)}>As measured</button>
          <button aria-pressed={strict} class:on={strict} on:click={() => (strict = true)}>Seasonal cycle removed</button>
        </span>
      </figcaption>
      <svg viewBox="0 0 {W} {H}" role="img"
           aria-label="Correlation between NDVI and rain summed over 1 to 12 months, median of four products with their range.">
        {#each [0, 0.5, 1] as v}
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} class={v === 0 ? 'zero' : 'grid'} />
          <text x={L - 8} y={y(v) + 4} class="tick end">{v.toFixed(1)}</text>
        {/each}
        {#each bars as b, i}
          {@const cx = L + slot * (i + 0.5)}
          {#if b.mid !== null}
            <rect x={cx - 20} width="40" y={b.mid >= 0 ? y(b.mid) : y(0)} height={Math.max(Math.abs(y(b.mid) - y(0)), 1)}
                  class="bar" class:best={b.months === best.months}>
              <title>{b.months} month{b.months > 1 ? 's' : ''}: median r {minus(b.mid)}, range {minus(b.lo)} to {minus(b.hi)} across {b.n} products</title>
            </rect>
            <line x1={cx} x2={cx} y1={y(b.lo)} y2={y(b.hi)} class="whisker" />
            <line x1={cx - 7} x2={cx + 7} y1={y(b.lo)} y2={y(b.lo)} class="whisker" />
            <line x1={cx - 7} x2={cx + 7} y1={y(b.hi)} y2={y(b.hi)} class="whisker" />
          {/if}
          <text x={cx} y={H - B + 16} class="tick mid">{b.months}</text>
        {/each}
        <text x={(L + W - R) / 2} y={H - 6} class="axis mid">Months of rain summed</text>
        <text x="14" y={(T + H - B) / 2} class="axis mid" transform="rotate(-90 14 {(T + H - B) / 2})">r with NDVI</text>
      </svg>
      <p class="small muted">Bar: median correlation of the four products. Whisker: lowest to highest product.
        {strict ? 'Each series’ normal wet-winter, dry-summer pattern is subtracted first, so only wetter- or drier-than-usual months count.' : 'Rain and greenness share a seasonal cycle, which inflates these; switch to “Seasonal cycle removed” for the stricter test.'}</p>
    </figure>

    {#if dsci3?.mid != null}
      <p class="small">The county drought index tracks <b>three months</b> of rain (median r = {minus(dsci3.mid)}) far
        better than one month, which is why drought matches greenness more closely than a single month’s rain does.</p>
    {/if}

    <ul class="caveats small">{#each data.notes as n}<li>{n}</li>{/each}</ul>
    <button class="btn ghost" on:click={exportCsv}>Download monthly rainfall CSV</button>
  {/if}
</div>

<style>
  .rg { display: grid; gap: 12px; }
  h2 { margin: 0; }
  .stat { margin: 0; background: var(--paper-2); border-left: 3px solid var(--teal); padding: 8px 12px; border-radius: 0; }
  .chart { margin: 0; }
  figcaption { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 6px 14px; margin-bottom: 4px; }
  .title { font-weight: 700; color: var(--forest); }
  .seg { display: inline-flex; border: 1px solid var(--line); border-radius: 0; overflow: hidden; }
  .seg button { border: 0; background: var(--card); padding: .35em .8em; font-weight: 600; color: var(--ink-2); font-size: .85rem; }
  .seg button + button { border-left: 1px solid var(--line); }
  .seg button.on { background: var(--forest); color: #111; }
  svg[role='img'] { width: 100%; height: auto; display: block; background: var(--card); border: 1px solid var(--line); border-radius: 0; }
  .grid { stroke: #252c31; }
  .zero { stroke: var(--ink-2); stroke-width: 1.5; }
  .tick { fill: var(--muted); font-size: 11px; }
  .axis { fill: var(--ink-2); font-size: 11.5px; }
  .end { text-anchor: end; }
  .mid { text-anchor: middle; }
  .bar { fill: #3e7f88; }
  .bar.best { fill: var(--teal); }
  .whisker { stroke: var(--ink); stroke-width: 1.5; }
  .caveats { margin: 0; padding-left: 1.2em; color: var(--ink-2); }
  .err { color: var(--fire); }
  .btn.ghost { width: fit-content; font-size: .9rem; }
  @media (max-width: 640px) { .tick, .axis { font-size: 17px; } }
</style>
