<script>
  // 3D View: terrain with the project's layers, a guided tour for presenting the
  // story, and (once exported) real before/after satellite imagery.
  import { onMount, onDestroy } from 'svelte';
  import { fromArrayBuffer } from 'geotiff';
  import Terrain3D from '../lib/Terrain3D.svelte';
  import Timeline from '../lib/Timeline.svelte';
  import { loadAll } from '../lib/api.js';
  import { loadChangeRaster, renderBelow, BROWNING_THRESHOLD } from '../lib/raster.ts';

  let data = null, error = null, map;
  let selected = null;
  let show = { browning: true, fires: true, sites: true, study: true };
  let exaggeration = 2;
  // Pixel-level browning from the dNDVI raster, cut at a user-set threshold. Falls
  // back to the −0.10 patch polygons if the raster can't load.
  let dndvi = null, threshold = BROWNING_THRESHOLD, change = null;

  // Imagery
  let imageryInfo = null, imageryChoice = 'tint', imageryCanvas = null, imageryCache = {}, imageryError = null;

  onMount(async () => {
    try {
      data = await loadAll();
      imageryInfo = await (await fetch('/api/layers/imagery')).json();
      dndvi = await loadChangeRaster('dndvi').catch(() => null);
    } catch (e) { error = e.message; }
  });

  async function setImagery(choice) {
    imageryChoice = choice; imageryError = null;
    if (choice === 'tint') { imageryCanvas = null; return; }
    try {
      if (!imageryCache[choice]) {
        const res = await fetch(`/api/layers/imagery/${choice}`);
        if (!res.ok) throw new Error(`imagery ${choice}: ${res.status}`);
        const img = await (await fromArrayBuffer(await res.arrayBuffer())).getImage();
        const [r, g, b] = await img.readRasters();
        const c = Object.assign(document.createElement('canvas'), { width: img.getWidth(), height: img.getHeight() });
        const ctx = c.getContext('2d');
        const out = ctx.createImageData(c.width, c.height);
        for (let i = 0; i < r.length; i++) out.data.set([r[i], g[i], b[i], 255], i * 4);
        ctx.putImageData(out, 0, 0);
        imageryCache[choice] = c;
      }
      imageryCanvas = imageryCache[choice];
    } catch (e) { imageryError = e.message; imageryChoice = 'tint'; imageryCanvas = null; }
  }

  let frame = 0;
  $: if (dndvi) {
    threshold;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const v = renderBelow(dndvi, threshold);
      change = { canvas: v.canvas, corners: dndvi.meta.corners, hectares: v.hectares, share: v.below / v.valid };
    });
  }

  // ---------- guided tour ----------
  function centroidOf(name) {
    const f = data.fires.features.find((x) => x.properties.name === name && x.properties.year === 2023);
    if (!f) return null;
    const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates[0][0];
    return [ring.reduce((s, p) => s + p[1], 0) / ring.length, ring.reduce((s, p) => s + p[0], 0) / ring.length];
  }

  const midpoint = (a, b) => (a && b ? [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] : a || b);

  $: STEPS = data ? [
    { title: 'Upcountry Maui', at: [20.80, -156.34], view: { distanceKm: 17, headingDeg: 135, pitchDeg: 30 },
      // Scoped to the years actually pulled (2018–2024). D4 occurred in 2019–2022;
      // 2022 had by far the most weeks of it — say that, not "the only year".
      text: `The leeward slopes of Haleakalā above Pukalani, Makawao and Kula. In ${data.drought.worst_year}, Maui County had its worst drought of 2018–2024: the highest average drought index, and ${data.drought.exceptional_weeks?.[data.drought.worst_year]?.weeks ?? 'several'} weeks of D4 “exceptional” drought (U.S. Drought Monitor).` },
    { title: 'The study area', at: [data.studyArea.lat, data.studyArea.lon], view: { distanceKm: 3.4, headingDeg: 150, pitchDeg: 48 },
      text: `Inside this 1.5 km circle, ${Math.round(data.studyArea.browned_fraction * 100)}% of the ground browned between the 2019 and 2022 dry seasons (orange) — 879 patches measured from Sentinel-2.` },
    { title: 'The Olinda fire', at: centroidOf('Olinda'), view: { distanceKm: 5.5, headingDeg: 110, pitchDeg: 40 },
      text: `8 August 2023. The Olinda fire burned about ${Math.round(data.fires.features.find((f) => f.properties.name === 'Olinda').properties.acres).toLocaleString()} acres. Its edge is about ${(data.studyArea.fire.distance_km - data.studyArea.radius_m / 1000).toFixed(1)} km outside the study area — the browned ground itself did not burn.` },
    // Framed on the midpoint of the two perimeters so both are in view. Directions
    // and elevations checked against the terrain grid: Kula burned UPslope of the
    // study area (~730–1,050 m, south-east); Pulehu DOWNslope (~60–410 m, south-west).
    { title: 'Kula and Pulehu', at: midpoint(centroidOf('Kula'), centroidOf('Pulehu')),
      view: { distanceKm: 12, headingDeg: 20, pitchDeg: 42 },
      text: 'The same day, the Kula fire burned upslope to the south-east, between roughly 730 and 1,050 m, and the Pulehu fire burned downslope to the south-west, between roughly 60 and 410 m. Perimeters from the National Interagency Fire Center.' },
    { title: 'A citizen-science site', at: [20.83841, -156.34459], view: { distanceKm: 1.3, headingDeg: 160, pitchDeg: 32 },
      text: 'A NASA GLOBE Observer land cover site inside the study area, visited 8 times in July 2026. Step inside it to see what the ground actually looks like.',
      link: data.sites.find((s) => s.site_name === '04QGJ763065') },
  ].filter((s) => s.at) : [];

  let touring = false, stepIndex = 0, autoplay = false, timer = 0;

  async function go(i) {
    stepIndex = Math.max(0, Math.min(STEPS.length - 1, i));
    const s = STEPS[stepIndex];
    await map?.flyTo(s.at[0], s.at[1], s.view);
    if (autoplay && touring) {
      clearTimeout(timer);
      timer = setTimeout(() => (stepIndex < STEPS.length - 1 ? go(stepIndex + 1) : (autoplay = false)), 5500);
    }
  }
  function startTour(play = false) { touring = true; autoplay = play; selected = null; go(0); }
  function stopTour() { touring = false; autoplay = false; clearTimeout(timer); }
  function onKey(e) {
    if (!touring) return;
    if (e.key === 'Escape') stopTour();
    if (e.key === 'ArrowRight') { autoplay = false; go(stepIndex + 1); }
    if (e.key === 'ArrowLeft') { autoplay = false; go(stepIndex - 1); }
  }
  onDestroy(() => clearTimeout(timer));

  const pct = (f) => (f === null || f === undefined ? null : Math.round(f * 100));
  const acres = (a) => (a ? Math.round(a).toLocaleString() : '?');
  $: fires2023 = data ? data.fires.features.filter((f) => f.properties.year === 2023).map((f) => f.properties).sort((a, b) => b.acres - a.acres) : [];
</script>

<svelte:window on:keydown={onKey} />

{#if error}
  <div class="state err" role="alert">Couldn’t load the 3D view: {error}</div>
{:else if !data}
  <div class="state">Loading terrain, fire perimeters and sites…</div>
{:else}
  <div class="layout">
    <section class="stage">
      <Terrain3D bind:this={map} terrain={data.terrain} browning={data.browning} fires={data.fires}
        sites={data.sites} studyArea={data.studyArea} {show} {exaggeration} imagery={imageryCanvas} {change}
        selectedId={selected?.site_id} on:select={(e) => { selected = e.detail; stopTour(); }} />

      <div class="controls">
        <button class="tourbtn" on:click={() => startTour(true)}>▶ Play the guided tour</button>
        <label><input type="checkbox" bind:checked={show.browning} /> <span class="sw brown"></span>Browned 2019→2022</label>
        {#if change}
          <label class="exag">dNDVI below <b class="num">{threshold.toFixed(2)}</b>
            <input type="range" min="-0.4" max="0" step="0.01" bind:value={threshold} disabled={!show.browning} /></label>
          <p class="note num">{change.hectares.toFixed(1)} ha · {(change.share * 100).toFixed(1)}% of the study area</p>
        {/if}
        <label><input type="checkbox" bind:checked={show.fires} /> <span class="sw fire"></span>Fire perimeters</label>
        <label><input type="checkbox" bind:checked={show.sites} /> <span class="sw site"></span>GLOBE sites</label>
        {#if data.sitesError}<p class="note">GLOBE sites couldn’t load; the rest of the view is unaffected.</p>{/if}
        <label><input type="checkbox" bind:checked={show.study} /> <span class="sw study"></span>Study area</label>
        <label class="exag">Relief ×{exaggeration}<input type="range" min="1" max="4" step="0.5" bind:value={exaggeration} /></label>
        <fieldset class="imagery">
          <legend>Ground</legend>
          <label><input type="radio" name="img" checked={imageryChoice === 'tint'} on:change={() => setImagery('tint')} /> Elevation tint</label>
          {#each imageryInfo?.available ?? [] as im}
            <label><input type="radio" name="img" checked={imageryChoice === im.id} on:change={() => setImagery(im.id)} /> {im.label}</label>
          {/each}
          {#if imageryInfo && !imageryInfo.available.length}
            <p class="hint">Before/after satellite imagery not exported yet — run <code>scripts/gee/imagery_before_after.js</code>.</p>
          {/if}
          {#if imageryError}<p class="hint err">{imageryError}</p>{/if}
        </fieldset>
      </div>

      {#if touring}
        <div class="caption" role="dialog" aria-live="polite" aria-label="Guided tour">
          <p class="eyebrow">Stop {stepIndex + 1} of {STEPS.length}</p>
          <h2>{STEPS[stepIndex].title}</h2>
          <p>{STEPS[stepIndex].text}</p>
          {#if STEPS[stepIndex].link}
            <a class="btn" href={`/viewer?obs=${encodeURIComponent(STEPS[stepIndex].link.land_cover_id)}`}>Step inside the site →</a>
          {/if}
          <div class="tournav">
            <button on:click={() => { autoplay = false; go(stepIndex - 1); }} disabled={stepIndex === 0}>← Back</button>
            <button on:click={() => { autoplay = !autoplay; if (autoplay) go(stepIndex); }}>{autoplay ? 'Pause' : 'Play'}</button>
            <button on:click={() => { autoplay = false; go(stepIndex + 1); }} disabled={stepIndex === STEPS.length - 1}>Next →</button>
            <button on:click={stopTour}>End tour</button>
          </div>
          <p class="keys">← → to step · Esc to end</p>
        </div>
      {/if}
      <div class="hint-bar">drag to orbit · right-drag to pan · scroll to zoom · click a pin</div>
    </section>

    <aside>
      {#if selected}
        <section class="card site">
          <button class="close" on:click={() => (selected = null)} aria-label="Close">×</button>
          <h2>{selected.label}</h2>
          <p class="muted small">{selected.site_name} · {selected.visits} visit{selected.visits === 1 ? '' : 's'} · latest {selected.latest}</p>
          {#if pct(selected.browned_fraction) !== null}
            <p><b>{pct(selected.browned_fraction)}%</b> of this 100 m site browned, 2019→2022
              <span class="muted small">(study area overall {Math.round(data.studyArea.browned_fraction * 100)}%)</span></p>
          {:else}<p class="muted">Outside the browning study area — no vegetation measurement here.</p>{/if}
          {#if selected.fire?.available}
            <p>Nearest Aug 2023 fire: <b>{selected.fire.nearest_fire}</b>,
              {selected.fire.inside_perimeter ? 'inside its perimeter' : `${selected.fire.distance_km} km away`}.
              <span class="muted small">Distance to where fire went — not a risk score.</span></p>
          {/if}
          <a class="btn" href={`/viewer?obs=${encodeURIComponent(selected.land_cover_id)}`}>Open the 360° view →</a>
        </section>
      {/if}
      <section class="card">
        <h2>The August 8, 2023 fires</h2>
        <ul class="fires">{#each fires2023 as f}<li><b>{f.name}</b><span>{acres(f.acres)} acres</span></li>{/each}</ul>
        <p class="callout"><b>The Pukalani study area did not burn.</b> The nearest perimeter, Olinda, starts about
          {(data.studyArea.fire.distance_km - data.studyArea.radius_m / 1000).toFixed(1)} km outside it.</p>
        <p class="muted small">Perimeters: National Interagency Fire Center. Dates in Hawaiʻi time.</p>
      </section>
      <section class="card dark">
        <h2>Drought, then fire</h2>
        <Timeline drought={data.drought.series} ndvi={data.drought.ndvi} worstYear={data.drought.worst_year} />
      </section>
    </aside>
  </div>
{/if}

<style>
  .layout { display: grid; grid-template-columns: 1fr 380px; height: 100%; }
  .stage { position: relative; background: #0f171b; }
  aside { overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; background: var(--paper); border-left: 1px solid var(--line); }
  aside .card { padding: 12px 14px; }
  aside h2 { font-size: 1.05rem; }
  .card.dark { background: #172025; border-color: #26333a; color: #e8eff0; }
  .card.dark h2 { color: #e8eff0; }
  .site { position: relative; border-color: var(--forest); }
  .close { position: absolute; top: 4px; right: 8px; border: 0; background: none; font-size: 1.3rem; color: var(--muted); }
  .fires { list-style: none; padding: 0; margin: 0 0 8px; }
  .fires li { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dashed var(--line); }
  .callout { background: #2a1715; border-left: 3px solid var(--fire); padding: 8px 10px; border-radius: 2px; font-size: .92rem; }
  .controls { position: absolute; top: 12px; left: 12px; z-index: 2; display: flex; flex-direction: column; gap: 4px; width: 230px;
    background: var(--card); border: 1px solid var(--line); border-radius: 2px; padding: 10px 12px; font-size: .85rem; }
  .controls label { display: flex; gap: 6px; align-items: center; }
  .tourbtn { background: var(--forest); color: #111; border: 0; border-radius: 2px; padding: .45em .8em; font-weight: 700; margin-bottom: 4px; }
  .exag { flex-direction: column; align-items: flex-start !important; margin-top: 4px; }
  .imagery { border: 0; border-top: 1px solid var(--line); margin: 6px 0 0; padding: 6px 0 0; }
  .imagery legend { font-weight: 700; color: var(--forest); padding: 0; }
  .hint { font-size: .76rem; color: var(--muted); margin: 4px 0 0; }
  .hint.err { color: var(--fire); }
  .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  .sw.brown { background: #e89646; } .sw.fire { border: 2px solid #ff3b30; } .sw.site { background: #ff9f43; border-radius: 50%; } .sw.study { border: 2px dashed #555; }
  .caption { position: absolute; right: 16px; bottom: 40px; z-index: 3; width: min(420px, calc(100% - 32px));
    background: var(--card); border: 1px solid var(--line); border-radius: 2px; padding: 16px 18px; }
  .caption h2 { font-size: 1.3rem; margin: 2px 0 6px; }
  .caption p { font-size: .95rem; }
  .tournav { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .tournav button { border: 1px solid var(--line); background: var(--card); border-radius: 2px; padding: .3em .7em; font-size: .88rem; }
  .keys { font-size: .75rem; color: var(--muted); margin: 6px 0 0; }
  .caption .btn { font-size: .9rem; }
  .hint-bar { position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); font-size: .75rem; color: #9fb1b8; pointer-events: none; }
  .state { padding: 60px; text-align: center; color: var(--muted); }
  .state.err { color: var(--fire); }
  @media (max-width: 900px) {
    .layout { grid-template-columns: 1fr; grid-template-rows: 62vh auto; }
    .controls { width: auto; right: 12px; }
  }
  .note { font-size: .78rem; color: var(--amber); margin: 0 0 4px 22px; }
</style>
