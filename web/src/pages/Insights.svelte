<script>
  // Region Insights. Vegetation numbers exist only where the project's study area
  // actually covers the place (Pukalani, ~81%); Makawao and Kula say so plainly
  // instead of borrowing Pukalani's series. Drought is county-wide and labelled so.
  import { onMount } from 'svelte';
  import LineChart from '../components/LineChart.svelte';
  import DroughtGreenness from '../components/DroughtGreenness.svelte';
  import RainGreenness from '../components/RainGreenness.svelte';
  import NdviBaseline from '../components/NdviBaseline.svelte';
  import { regionInsights } from '../lib/adapters.ts';
  import { toCsv, downloadCsv } from '../lib/csv.ts';

  const REGIONS = [['pukalani', 'Pukalani'], ['makawao', 'Makawao'], ['kula', 'Kula']];
  const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024];
  const FIRE = [{ date: '2023-08-08', label: 'Aug 8, 2023 fires' }];

  let key = new URLSearchParams(location.search).get('region') || 'pukalani';
  let cache = {}, current = null, loading = true, error = null;
  let fromYear = 2018, toYear = 2024;
  let yearA = '2019', yearB = '2022';

  async function load(k) {
    loading = true; error = null;
    try {
      cache[k] ??= await regionInsights(k);
      current = cache[k];
    } catch (e) { error = e.message; }
    loading = false;
  }
  onMount(() => load(key));
  $: if (current?.key !== key && key) load(key);
  $: if (toYear < fromYear) toYear = fromYear;
  $: from = `${fromYear}-01-01`;
  $: to = `${toYear}-12-31`;

  $: veg = current?.vegetation;
  $: dryYears = veg?.available ? Object.keys(veg.drySeasonNdvi) : [];
  $: compare = veg?.available ? ['ndvi', 'nbr'].map((idx) => {
      const table = idx === 'ndvi' ? veg.drySeasonNdvi : veg.drySeasonNbr;
      const a = table[yearA], b = table[yearB];
      return { idx: idx.toUpperCase(), a, b,
               diff: a && b ? b.mean - a.mean : null,
               pct: a && b ? (100 * (b.mean - a.mean)) / a.mean : null };
    }) : [];

  const ATTRIBUTION = 'Browning Viewer (student research project)';

  function exportVegetation() {
    const rows = veg.ndvi.filter((p) => p.date >= from && p.date <= to)
      .map((p) => ({ date: p.date, ndvi: p.value, nbr: veg.nbr.find((q) => q.date === p.date)?.value }));
    downloadCsv(`${key}_vegetation_${fromYear}-${toYear}.csv`, toCsv(rows, [
      { header: 'month', value: (r) => r.date }, { header: 'ndvi_mean', value: (r) => r.ndvi },
      { header: 'nbr_mean', value: (r) => r.nbr },
    ], [
      `${current.name} vegetation, ${fromYear}-${toYear}. ${ATTRIBUTION}.`,
      `Source: author's Sentinel-2 SR Harmonized analysis (Google Earth Engine), cloud-masked monthly medians.`,
      `Area: ${veg.analysisArea}. ${veg.note}`,
      'Months with no usable imagery are omitted, not zero.',
      'Limitations: greenness/moisture indices; not fuel load, fire risk, or a forecast.',
    ]));
  }

  function exportDrought() {
    const rows = current.drought.weekly.filter((p) => p.date >= from && p.date <= to);
    downloadCsv(`maui_county_drought_${fromYear}-${toYear}.csv`, toCsv(rows, [
      { header: 'week', value: (r) => r.date }, { header: 'dsci', value: (r) => r.value },
    ], [
      `Maui County drought (DSCI, 0-500), ${fromYear}-${toYear}. ${ATTRIBUTION}.`,
      'Source: U.S. Drought Monitor, National Drought Mitigation Center (UNL), USDA, NOAA.',
      `Scope: ${current.drought.scope}.`,
      'Limitations: broad-scale expert assessment; not a measurement for any one place.',
    ]));
  }

  function exportComparison() {
    downloadCsv(`${key}_dry_season_${yearA}_vs_${yearB}.csv`, toCsv(compare, [
      { header: 'index', value: (r) => r.idx },
      { header: `mean_${yearA}`, value: (r) => r.a?.mean }, { header: `months_${yearA}`, value: (r) => r.a?.months },
      { header: `mean_${yearB}`, value: (r) => r.b?.mean }, { header: `months_${yearB}`, value: (r) => r.b?.months },
      { header: 'change', value: (r) => r.diff?.toFixed(4) }, { header: 'change_pct', value: (r) => r.pct?.toFixed(1) },
    ], [
      `${current.name}: dry-season (May-Sep) mean, ${yearA} vs ${yearB}. ${ATTRIBUTION}.`,
      `Area: ${veg.analysisArea}. ${veg.note}`,
      'A two-year comparison of one study area is not a trend, and not evidence of fire risk.',
    ]));
  }
</script>

<section class="wrap head">
  <p class="eyebrow">Region Insights</p>
  <h1>How vegetation and drought changed, place by place</h1>
  <p class="lede">Choose a place. Each chart states its own area, period and source, and shows only what was actually measured there.</p>

  <div class="controls">
    <div class="tabs" role="tablist" aria-label="Region">
      {#each REGIONS as [k, label]}
        <button role="tab" aria-selected={key === k} class:on={key === k} on:click={() => (key = k)}>{label}</button>
      {/each}
    </div>
    <label>From <select bind:value={fromYear}>{#each YEARS as y}<option value={y}>{y}</option>{/each}</select></label>
    <label>to <select bind:value={toYear}>{#each YEARS.filter((y) => y >= fromYear) as y}<option value={y}>{y}</option>{/each}</select></label>
  </div>
</section>

<section class="wrap body">
  {#if error}
    <p class="card err" role="alert">Couldn’t load {key}: {error}</p>
  {:else if !current || current.key !== key}
    <!-- Never show one place's numbers under another place's tab while loading. -->
    <div class="card skeleton" aria-busy="true">Loading {REGIONS.find(([k]) => k === key)?.[1] ?? ''}…</div>
  {:else if current}
    <div class="summary card">
      <h2>{current.name}</h2>
      <p class="muted small">{current.kind} · {current.landKm2} km² · GEOID {current.geoid}</p>
      {#if current.fire.available}
        <p>{current.fire.overlapsRegion
          ? `The ${current.fire.nearestFire} fire (Aug 2023) burned within this place’s boundary.`
          : `Nearest Aug 2023 fire: ${current.fire.nearestFire}, about ${current.fire.distanceKm} km from this place’s boundary.`}
          <span class="muted small">Source: NIFC perimeters. Distance to where fire went, not a risk score.</span></p>
      {/if}
    </div>

    <div class="card">
      <h2>Vegetation</h2>
      {#if veg.available}
        <p class="note">{veg.note}</p>
        <LineChart title="Monthly vegetation index (study-area mean)" {from} {to}
          yMin={0} yMax={0.7} yTicks={[0, 0.2, 0.4, 0.6]} yLabel="index"
          markers={FIRE}
          series={[
            { label: 'NDVI (greenness)', color: '#2f5d3d', points: veg.ndvi },
            { label: 'NBR (moisture-sensitive)', color: '#1f6f73', dash: '6 4', points: veg.nbr },
          ]} />
        <p class="method small muted">Sentinel-2 surface reflectance, 10 m; scene-classification cloud mask (cloud, shadow,
          cirrus, saturated pixels removed); monthly median, then area mean. 11 months between Dec 2018 and Dec 2023 had no
          usable imagery and are gaps, not zeros. Units: dimensionless index (−1 to 1).</p>
        <button class="btn ghost" on:click={exportVegetation}>Download vegetation CSV</button>
      {:else}
        <div class="emptystate">
          <b>Vegetation data not available for {current.name}.</b>
          <p>{veg.reason}</p>
          <p class="small muted">Not substituted with Pukalani’s numbers: a 1.5 km circle cannot stand in for a
            {current.landKm2} km² place it barely touches.</p>
        </div>
      {/if}
    </div>

    {#if veg.available}
      <div class="card">
        <h2>Dry-season comparison</h2>
        <p class="small">Mean of the May–September months for each year. “Months” shows how many dry-season months had
          usable imagery (5 = complete).</p>
        <div class="pick">
          <label>Compare <select bind:value={yearA}>{#each dryYears as y}<option>{y}</option>{/each}</select></label>
          <label>with <select bind:value={yearB}>{#each dryYears as y}<option>{y}</option>{/each}</select></label>
        </div>
        <table>
          <thead><tr><th>Index</th><th>{yearA}</th><th>{yearB}</th><th>Change</th></tr></thead>
          <tbody>
            {#each compare as r}
              <tr>
                <td>{r.idx}</td>
                <td>{r.a ? r.a.mean.toFixed(3) : 'n/a'} <span class="muted small">({r.a?.months ?? 0} mo)</span></td>
                <td>{r.b ? r.b.mean.toFixed(3) : 'n/a'} <span class="muted small">({r.b?.months ?? 0} mo)</span></td>
                <td>{r.diff === null ? 'n/a' : `${r.diff >= 0 ? '+' : ''}${r.diff.toFixed(3)} (${r.pct >= 0 ? '+' : ''}${r.pct.toFixed(0)}%)`}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="small muted">One study area, two years: a comparison, not a trend, and not evidence of fire risk. Change
          in greenness can reflect rainfall, grazing, mowing or land use as well as drought.</p>
        <button class="btn ghost" on:click={exportComparison}>Download comparison CSV</button>
      </div>
    {/if}

    {#if veg.available}
      <div class="card"><DroughtGreenness /></div>
      <div class="card"><RainGreenness /></div>
      <NdviBaseline />
    {/if}

    <div class="card">
      <h2>Drought</h2>
      <p class="note">{current.drought.scope}. {current.drought.source}.</p>
      <LineChart title="Drought Severity and Coverage Index, weekly" {from} {to}
        yMin={0} yMax={350} yTicks={[0, 100, 200, 300]} yLabel="DSCI" format={(v) => v.toFixed(0)}
        markers={FIRE}
        series={[{ label: 'Maui County DSCI', color: '#9c5b12', area: true, points: current.drought.weekly }]} />
      <p class="method small muted">DSCI weights the share of the county in each drought category: 0 = none, 500 = all of
        it in D4 exceptional drought. Weekly; expert-blended from many indicators.</p>
      <button class="btn ghost" on:click={exportDrought}>Download drought CSV</button>
    </div>
  {/if}
</section>

<style>
  .head { padding-top: 34px; }
  .lede { color: var(--ink-2); max-width: 44em; }
  .controls { display: flex; flex-wrap: wrap; gap: 12px 18px; align-items: center; margin-top: 10px; }
  .tabs { display: flex; border: 1px solid var(--line); border-radius: 0; overflow: hidden; }
  .tabs button { border: 0; background: var(--card); padding: .5em 1.1em; font-weight: 600; color: var(--ink-2); }
  .tabs button + button { border-left: 1px solid var(--line); }
  .tabs button.on { background: var(--forest); color: #111; }
  select { border: 1px solid var(--line); border-radius: 0; padding: .3em .5em; background: var(--card); }
  .body { display: grid; gap: 16px; margin-top: 20px; }
  .body > :global(*) { min-width: 0; }
  .note { background: var(--paper-2); border-left: 3px solid var(--teal); padding: 8px 12px; border-radius: 0; font-size: .92rem; }
  .method { margin-top: 8px; }
  .emptystate { border: 1px dashed var(--line); border-radius: 0; padding: 18px; background: var(--paper); }
  .pick { display: flex; gap: 14px; margin: 8px 0 12px; }
  .btn.ghost { margin-top: 10px; font-size: .9rem; }
  .err { color: var(--fire); }
  .skeleton { min-height: 160px; display: grid; place-items: center; color: var(--muted);
    background: var(--card); border: 1px solid var(--line); }
</style>
