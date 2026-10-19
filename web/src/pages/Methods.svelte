<section class="wrap page">
  <p class="eyebrow">Methods & Transparency</p>
  <h1>How the numbers are made — and where they can mislead</h1>
  <p class="lede">Every layer in the Observatory is either the author’s own analysis or a verified public dataset.
    <b>There is no simulated or demo data</b>: where something isn’t available, the app shows an empty state.</p>

  <div class="grid">
    <article class="card">
      <h2>Satellite data</h2>
      <p><b>Sentinel-2 Surface Reflectance (Harmonized)</b>, Copernicus / ESA, processed in Google Earth Engine.
        10 m pixels; a satellite pass every few days.</p>
      <p><b>Cloud masking:</b> each scene’s Scene Classification layer removes saturated pixels (class 1), cloud
        shadow (3), medium and high cloud (8, 9) and cirrus (10). Scenes over 60% cloudy are skipped.</p>
    </article>

    <article class="card">
      <h2>Indices</h2>
      <p class="formula">NDVI = (NIR − Red) / (NIR + Red)</p>
      <p>Sentinel-2 bands B8 (near-infrared) and B4 (red). Higher = greener, denser vegetation.</p>
      <p class="formula">NBR = (NIR − SWIR2) / (NIR + SWIR2)</p>
      <p>Bands B8 and B12. Shortwave infrared responds to plant water content, so NBR is more sensitive to drying.</p>
    </article>

    <article class="card">
      <h2>Change and baselines</h2>
      <p><b>dNDVI / dNBR</b> = median of the 2022 dry season (May–September) minus the median of the 2019 dry
        season. Comparing the <em>same season</em> in both years avoids mistaking normal seasonal drying for change.</p>
      <p>A pixel counts as <b>browned</b> when dNDVI &lt; −0.10. In the 1.5 km study area that is 42.7% of valid
        pixels, grouped into 879 patches (298.6 ha).</p>
      <p><b>Monthly series:</b> monthly medians, then the area mean. Anomalies are z-scores against a per-calendar-month
        2019–2021 baseline — August is compared with other Augusts.</p>
    </article>

    <article class="card">
      <h2>GLOBE sites</h2>
      <p>Each NASA GLOBE Observer land cover observation is six photos (N, E, S, W, up, down) documenting a 100 m site.
        The app reports the <b>share of that 100 m footprint</b> that browned, and the range it spans across the
        recorded GPS error (3 m to over 1 km) — not whether one GPS point fell inside a patch, which is fragile.</p>
    </article>
  </div>

  <h2 class="section">Caveats</h2>
  <ul class="caveats">
    <li><b>Seasonal variation.</b> Leeward Maui greens in winter and browns every summer. Only same-season comparisons are meaningful.</li>
    <li><b>Sensor and cloud artefacts.</b> Residual cloud edges, haze and shadow can lower an index; 11 months had no usable imagery at all.</li>
    <li><b>Greenness is not fuel.</b> NDVI measures how green the canopy looks, not how much dry material is on the ground. Browned grass may be less or more flammable depending on amount and continuity.</li>
    <li><b>Many causes.</b> A drop in greenness can come from drought, grazing, mowing, clearing or land-use change.</li>
    <li><b>Scale mismatch.</b> The vegetation analysis covers a 1.5 km circle; drought is county-wide; LCMS is county totals. Numbers at different scales are not compared as if they were the same place.</li>
    <li><b>The study area did not burn.</b> The nearest 2023 perimeter (Olinda) is ~1.5 km outside it. Nothing here shows that browned ground burned, or that browning predicts fire.</li>
    <li><b>Uncertainty.</b> Every map value comes with its period and source; GLOBE sites carry their GPS accuracy.</li>
  </ul>

  <h2 class="section">Hazard, exposure, vulnerability, preparedness</h2>
  <div class="defs">
    <div class="card"><h3>Hazard</h3><p>A process that can cause harm — here, wildfire and drought. The Observatory shows <em>past</em> drought and fire extents, not future hazard.</p></div>
    <div class="card"><h3>Exposure</h3><p>What is located where a hazard could reach: homes, schools, stations. The map shows locations only.</p></div>
    <div class="card"><h3>Vulnerability</h3><p>How badly people or places are affected when exposed — shaped by income, access, health, housing. Not modelled here, and no composite score is computed.</p></div>
    <div class="card"><h3>Preparedness</h3><p>What communities and agencies do in advance. Official sources only: <a href="https://www.mauicounty.gov/190/Emergency-Preparedness" target="_blank" rel="noopener noreferrer">Maui County Emergency Preparedness</a>.</p></div>
  </div>

  <h2 class="section">Verified vs. simulated layers</h2>
  <table>
    <thead><tr><th>Layer</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>dNDVI / dNBR, browning patches, monthly series</td><td><span class="tag analysis">Author’s analysis</span></td></tr>
      <tr><td>GLOBE sites, fire perimeters, drought maps & index, LCMS, terrain, facilities, place boundaries</td><td><span class="tag public">Verified public source</span></td></tr>
      <tr><td>Anything simulated, synthetic or demo</td><td>None — not used anywhere</td></tr>
    </tbody>
  </table>

  <h2 class="section">Reproducibility</h2>
  <div class="card">
    <ul class="repro">
      <li><code>gee_export_ndvi.js</code>, <code>gee_export_nbr.js</code> — the original Earth Engine exports (author)</li>
      <li><code>scripts/gee/fire_perimeter_browning.js</code> — the same method inside each 2023 perimeter vs. a 1 km unburned ring</li>
      <li><code>scripts/gee/region_timeseries.js</code> — monthly NDVI/NBR for Pukalani, Makawao and Kula boundaries</li>
      <li><code>scripts/gee/lcms_site_sample.js</code>, <code>scripts/gee/site_timeseries.js</code> — per-site LCMS classes and curves</li>
      <li><code>scripts/fetch_*.py</code> — fire perimeters, drought maps and index, terrain, facilities and boundaries</li>
      <li><code>docs/evidence-claims.md</code> — what can and cannot be claimed from each source</li>
      <li><code>docs/sfm-experiment.md</code> — why 3D reconstruction from GLOBE photos failed</li>
    </ul>
  </div>
</section>

<style>
  .page { padding-top: 34px; }
  .lede { color: var(--ink-2); max-width: 46em; font-size: 1.08rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; }
  .formula { font-family: var(--serif); font-size: 1.15rem; color: var(--forest); background: var(--paper-2); padding: 6px 10px; border-radius: 2px; display: inline-block; }
  .section { margin-top: 36px; }
  .caveats { padding-left: 1.2em; max-width: 52em; }
  .caveats li { margin: 6px 0; }
  .defs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .defs p { font-size: .92rem; margin: 0; }
  .repro { margin: 0; padding-left: 1.2em; }
  .repro li { margin: 4px 0; }
  @media (max-width: 900px) { .grid, .defs { grid-template-columns: 1fr; } }
</style>
