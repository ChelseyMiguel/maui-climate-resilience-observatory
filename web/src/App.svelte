<script>
  // Upcountry Maui in 3D, with the 2023 fires, the drought record, and the
  // browning analysis together. A companion to the 360-degree site viewer at "/".
  //
  // Discipline carried over from docs/evidence-claims.md: everything here is
  // labelled with its scale and source, and the page states plainly what the
  // data does NOT show — the study area did not burn, and nothing here is a
  // fire-risk score or an alert.
  import { onMount } from 'svelte';
  import Terrain3D from './lib/Terrain3D.svelte';
  import Timeline from './lib/Timeline.svelte';
  import { loadAll } from './lib/api.js';

  let data = null;
  let error = null;
  let map;
  let selected = null;
  let show = { browning: true, fires: true, sites: true, study: true };
  let exaggeration = 2;

  onMount(async () => {
    try {
      data = await loadAll();
    } catch (e) {
      error = e.message;
    }
  });

  $: fires2023 = data
    ? data.fires.features
        .filter((f) => f.properties.year === 2023)
        .map((f) => f.properties)
        .sort((a, b) => b.acres - a.acres)
    : [];

  function select(pin) {
    selected = pin;
    map?.focus(pin.lat, pin.lon);
  }

  const pct = (f) => (f === null || f === undefined ? null : Math.round(f * 100));
  const acres = (a) => (a ? Math.round(a).toLocaleString() : '?');

  // Every link below was checked to resolve to the live page (Oct 2026).
  const RESOURCES = [
    { href: 'https://www.mauicounty.gov/983/MEMA-Alerts', name: 'MEMA Alerts',
      why: 'Sign up for official Maui County emergency alerts' },
    { href: 'https://www.mauicounty.gov/70/Emergency-Management-Agency', name: 'Maui Emergency Management Agency',
      why: 'The county agency for emergencies and evacuations' },
    { href: 'https://www.mauicounty.gov/190/Emergency-Preparedness', name: 'Maui County: Emergency Preparedness',
      why: 'Household and family planning' },
    { href: 'https://www.hwmo.org/', name: 'Hawaiʻi Wildfire Management Organization',
      why: 'Local wildfire prevention, Firewise, and community programs' },
    { href: 'https://dod.hawaii.gov/hiema/', name: 'Hawaiʻi Emergency Management Agency',
      why: 'State-level emergency information' },
    { href: 'https://www.ready.gov/wildfires', name: 'Ready.gov — Wildfires',
      why: 'What to do before, during, and after a wildfire' },
    { href: 'https://www.wildlandfirersg.org/', name: 'Ready, Set, Go!',
      why: 'Preparing your home and family to evacuate early' },
  ];
</script>

<header>
  <div>
    <h1>Upcountry Maui in 3D</h1>
    <span class="sub">Drought, browning, and the August 2023 fires</span>
  </div>
  <a class="back" href="/">← 360° site viewer</a>
</header>

{#if error}
  <div class="error" role="alert">Couldn't load the map data: {error}</div>
{:else if !data}
  <div class="loading">Loading terrain, fire perimeters, and sites…</div>
{:else}
  <main>
    <section class="stage">
      <Terrain3D
        bind:this={map}
        terrain={data.terrain}
        browning={data.browning}
        fires={data.fires}
        sites={data.sites}
        studyArea={data.studyArea}
        {show}
        {exaggeration}
        selectedId={selected?.site_id}
        on:select={(e) => select(e.detail)}
      />

      <div class="controls">
        <label><input type="checkbox" bind:checked={show.browning} />
          <span class="sw sw-brown"></span>Browned 2019→2022</label>
        <label><input type="checkbox" bind:checked={show.fires} />
          <span class="sw sw-fire"></span>Fire perimeters</label>
        <label><input type="checkbox" bind:checked={show.sites} />
          <span class="sw sw-site"></span>GLOBE sites</label>
        <label><input type="checkbox" bind:checked={show.study} />
          <span class="sw sw-study"></span>Study area</label>
        <label class="exag">Relief ×{exaggeration}
          <input type="range" min="1" max="4" step="0.5" bind:value={exaggeration} /></label>
      </div>
      <div class="hint">drag to orbit · right-drag to pan · scroll to zoom · click a pin</div>
    </section>

    <aside>
      {#if selected}
        <section class="card site">
          <button class="close" on:click={() => (selected = null)} aria-label="Close">×</button>
          <h2>{selected.label}</h2>
          <div class="muted">{selected.site_name} · {selected.visits} visit{selected.visits === 1 ? '' : 's'}
            · latest {selected.latest}</div>
          {#if pct(selected.browned_fraction) !== null}
            <p><b class="amber">{pct(selected.browned_fraction)}%</b> of this 100 m site browned, 2019→2022
              <span class="muted">(study area overall: {Math.round(data.studyArea.browned_fraction * 100)}%)</span></p>
          {:else}
            <p class="muted">Outside the browning study area — no vegetation measurement here.</p>
          {/if}
          {#if selected.fire?.available}
            <p>Nearest Aug 2023 fire: <b>{selected.fire.nearest_fire}</b>,
              {selected.fire.inside_perimeter ? 'inside its perimeter' : `${selected.fire.distance_km} km away`}.
              <span class="muted">Distance to where fire went — not a risk score.</span></p>
          {/if}
          <a class="open" href={`/?obs=${encodeURIComponent(selected.land_cover_id)}`}>Open the 360° view →</a>
        </section>
      {/if}

      <section class="card">
        <h2>The August 8, 2023 fires</h2>
        <ul class="fires">
          {#each fires2023 as f}
            <li><b>{f.name}</b><span>{acres(f.acres)} acres</span></li>
          {/each}
        </ul>
        <p class="callout">
          <b>The Pukalani study area did not burn.</b> The nearest perimeter, Olinda, starts about
          {(data.studyArea.fire.distance_km - data.studyArea.radius_m / 1000).toFixed(1)} km outside it.
          The browning here describes the drought-stressed landscape around the fires — not the ground
          that burned.
        </p>
        <p class="muted small">Perimeters: National Interagency Fire Center (WFIGS). Dates in Hawaiʻi time.</p>
      </section>

      <section class="card">
        <h2>Drought, then fire</h2>
        <Timeline drought={data.drought.series} ndvi={data.drought.ndvi} worstYear={data.drought.worst_year} />
      </section>

      <section class="card">
        <h2>What this shows — and what it doesn't</h2>
        <ul class="claims">
          <li class="yes">Drought peaked in {data.drought.worst_year}, the year before the fires; study-area greenness bottomed out in Aug 2022.</li>
          <li class="yes">The GLOBE sites near Pukalani sit in a heavily browned part of the study area.</li>
          <li class="no">It does not show that browned ground burned — none of it lies inside a 2023 perimeter.</li>
          <li class="no">It is not a fire-risk map, forecast, or alert.</li>
        </ul>
      </section>

      <section class="card prepare">
        <h2>Be prepared</h2>
        <p class="small">This is a research and education tool, <b>not an emergency alert system</b>. For
          current conditions and evacuation orders, use official sources:</p>
        <ul class="links">
          {#each RESOURCES as r}
            <li><a href={r.href} target="_blank" rel="noopener noreferrer">{r.name}</a>
              <span class="muted small">{r.why}</span></li>
          {/each}
        </ul>
      </section>

      <p class="muted small sources">
        Sources: terrain — AWS Terrain Tiles (USGS 3DEP); fires — NIFC; drought — U.S. Drought Monitor;
        browning — this project's Sentinel-2 analysis; sites — NASA GLOBE Observer.
      </p>
    </aside>
  </main>
{/if}

<style>
  header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 18px; border-bottom: 1px solid var(--line); gap: 12px;
  }
  h1 { font-size: 16px; margin: 0; }
  .sub { color: var(--muted); font-size: 12px; }
  .back { font-size: 13px; text-decoration: none; }
  main { display: grid; grid-template-columns: 1fr 380px; height: calc(100vh - 57px); }
  .stage { position: relative; min-height: 300px; }
  aside { border-left: 1px solid var(--line); overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; position: relative; }
  .card h2 { font-size: 14px; margin: 0 0 8px; }
  .card p { margin: 6px 0; }
  .muted { color: var(--muted); }
  .small { font-size: 12px; }
  .amber { color: var(--amber); }
  .site { border-color: var(--accent); }
  .close { position: absolute; top: 6px; right: 8px; background: none; border: none; font-size: 18px; cursor: pointer; color: var(--muted); }
  .open { display: inline-block; margin-top: 4px; font-weight: 600; }
  .fires { list-style: none; padding: 0; margin: 0 0 8px; }
  .fires li { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dashed var(--line); }
  .fires li span { color: var(--muted); }
  .callout { background: rgba(255, 59, 48, 0.08); border-left: 3px solid var(--fire); padding: 8px 10px; border-radius: 4px; }
  .claims { padding-left: 0; list-style: none; margin: 0; font-size: 13px; }
  .claims li { padding-left: 20px; position: relative; margin: 5px 0; }
  .claims .yes::before { content: '✓'; position: absolute; left: 2px; color: var(--accent); }
  .claims .no::before { content: '✗'; position: absolute; left: 2px; color: var(--fire); }
  .links { padding-left: 0; list-style: none; margin: 6px 0 0; }
  .links li { margin: 7px 0; display: flex; flex-direction: column; }
  .prepare { border-color: #5a2a24; }
  .sources { margin: 0 2px 8px; }
  .controls {
    position: absolute; top: 12px; left: 12px; display: flex; flex-direction: column; gap: 4px;
    background: rgba(16, 22, 26, 0.86); border: 1px solid var(--line); border-radius: 10px;
    padding: 8px 10px; font-size: 12px; backdrop-filter: blur(6px);
  }
  .controls label { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  .sw-brown { background: #e89646; }
  .sw-fire { background: transparent; border: 2px solid var(--fire); }
  .sw-site { background: #ff9f43; border-radius: 50%; }
  .sw-study { border: 2px dashed #fff; }
  .exag { margin-top: 4px; flex-direction: column; align-items: flex-start !important; }
  .hint { position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); font-size: 11px; color: var(--muted); pointer-events: none; }
  .loading, .error { padding: 40px; text-align: center; color: var(--muted); }
  .error { color: #ff6b5e; }
  @media (max-width: 860px) {
    main { grid-template-columns: 1fr; grid-template-rows: 60vh auto; height: auto; }
    aside { border-left: none; border-top: 1px solid var(--line); }
  }
</style>
