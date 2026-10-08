<script>
  import { onMount } from 'svelte';
  import { DATASETS } from '../lib/sources.ts';
  import { infrastructureCatalog } from '../lib/adapters.ts';

  let catalog = [];
  onMount(async () => { try { catalog = await infrastructureCatalog(); } catch { catalog = []; } });
</script>

<section class="wrap page">
  <p class="eyebrow">Data Sources</p>
  <h1>Where every layer comes from</h1>
  <p class="lede">Each dataset’s provider, resolution, coverage, period, how current it is, licence and a direct link.
    Links were checked to resolve. Where exact licence terms weren’t confirmed, the table says
    “see provider terms” rather than guess.</p>

  <div class="tablewrap card">
    <table>
      <thead>
        <tr><th>Dataset</th><th>Provider</th><th>Resolution</th><th>Coverage</th><th>Period</th><th>Currency</th><th>Licence</th></tr>
      </thead>
      <tbody>
        {#each DATASETS as d}
          <tr>
            <td>
              <a href={d.link} target="_blank" rel="noopener noreferrer">{d.name}</a><br />
              <span class="tag {d.provenance === 'project-analysis' ? 'analysis' : 'public'}">
                {d.provenance === 'project-analysis' ? 'Author’s analysis' : 'Verified public'}</span>
              {#if d.caveat}<p class="cav">{d.caveat}</p>{/if}
            </td>
            <td>{d.provider}</td><td>{d.spatialResolution}</td><td>{d.coverage}</td>
            <td>{d.temporal}</td><td>{d.currency}</td><td>{d.license}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <h2 class="section">Hawaiʻi Statewide GIS layers in use</h2>
  <p class="small muted">How current each layer is, quoted from the publisher’s own layer description.</p>
  {#if catalog.length}
    <div class="card">
      <table>
        <thead><tr><th>Layer</th><th>Features in Upcountry</th><th>Currency</th><th>Endpoint</th></tr></thead>
        <tbody>
          {#each catalog as c}
            <tr><td>{c.title}</td><td>{c.count}</td><td>{c.currency ?? 'not stated'}</td>
              <td><a href={c.source} target="_blank" rel="noopener noreferrer">service</a></td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="card muted">Layer catalogue unavailable — run <code>scripts/fetch_context_layers.py</code>.</p>
  {/if}

  <h2 class="section">Candidate sources not yet connected</h2>
  <ul>
    <li><b>NOAA / NWS observations and red-flag warnings</b> — would add weather context; not integrated, and warnings would need to be clearly historical.</li>
    <li><b>Maui County GIS: roads, evacuation zones, shelters</b> — deliberately not shown until an authoritative, current source is verified. Out-of-date evacuation or shelter data on a disaster page could mislead.</li>
    <li><b>Per-place vegetation series for Makawao and Kula</b> — script ready (<code>scripts/gee/region_timeseries.js</code>); needs to be run in Earth Engine.</li>
  </ul>
</section>

<style>
  .page { padding-top: 34px; }
  .lede { color: var(--ink-2); max-width: 46em; }
  .tablewrap { overflow-x: auto; padding: 4px; margin-top: 16px; }
  table { min-width: 900px; font-size: .9rem; }
  .cav { margin: 4px 0 0; font-size: .8rem; color: var(--muted); }
  .section { margin-top: 32px; }
</style>
