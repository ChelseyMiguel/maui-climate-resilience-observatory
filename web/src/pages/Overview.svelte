<script>
  // Every figure on this page is sourced; nothing is a forecast.
  const FACTS = [
    { value: '2022', label: 'Maui County’s worst drought year of 2018–2024: the highest average drought index, and 20 weeks of D4 “exceptional” drought',
      source: 'U.S. Drought Monitor' },
    { value: '42.7%', label: 'of the Pukalani study area browned between the 2019 and 2022 dry seasons',
      source: 'Author’s Sentinel-2 analysis' },
    { value: 'Aug 8, 2023', label: 'Olinda, Kula and Pulehu fires burned in Upcountry Maui',
      source: 'National Interagency Fire Center' },
  ];

  const CARDS = [
    { href: '/explore', title: 'Vegetation Change', icon: 'leaf',
      text: 'Where greenness and moisture dropped between the 2019 and 2022 dry seasons, at 10 m — and how much of each place it covers.' },
    { href: '/insights', title: 'Drought Conditions', icon: 'sun',
      text: 'Weekly drought for Maui County alongside vegetation for the study area, with a dry-season comparison you can export.' },
    { href: '/explore', title: 'Infrastructure & Access', icon: 'pin',
      text: 'Fire and EMS stations, a hospital, and schools from the Hawaiʻi Statewide GIS Program — locations only, with their source dates.' },
    { href: '/viewer', title: 'GLOBE Site Reconstruction', icon: 'globe',
      text: 'Step inside a citizen-science land cover site: six NASA GLOBE Observer photos rebuilt into a 360° view.' },
  ];
</script>

<section class="hero">
  <div class="wrap grid">
    <div>
      <p class="eyebrow">Rural Hawaiʻi Climate Resilience Observatory</p>
      <h1>See environmental change.<br />Understand community vulnerability.</h1>
      <p class="lede">
        An interactive research dashboard for Upcountry Maui — Pukalani, Makawao and Kula — that puts
        historical vegetation change, drought, and community context side by side, with every source and
        caveat in plain view.
      </p>
      <div class="cta">
        <a class="btn" href="/explore">Open the Map Explorer</a>
        <a class="btn ghost" href="/insights">Region Insights</a>
        <a class="btn ghost" href="/viewer">Step into a site</a>
      </div>
    </div>
    <svg class="contours" viewBox="0 0 400 300" aria-hidden="true">
      {#each Array(9) as _, i}
        <path d="M{-20 + i * 6},{260 - i * 22} C{90 + i * 8},{200 - i * 26} {200 - i * 4},{230 - i * 30} {420},{150 - i * 16}"
              fill="none" stroke="currentColor" stroke-width="1" opacity={0.18 + i * 0.07} />
      {/each}
    </svg>
  </div>
</section>

<section class="wrap why">
  <h2>Why start in rural Upcountry Maui</h2>
  <p>
    Upcountry is rural, on the drier leeward slopes of Haleakalā, and much of its former plantation land is now
    unmanaged grass — the land-use shift the USDA Forest Service’s LCMS records as agriculture falling 60% across
    Maui County since 2018. The 2022 drought, the browning that followed, and the August 2023 fires all happened
    here, which makes it a place to <em>look carefully</em> at what satellite and citizen-science records can and
    cannot tell a community.
  </p>
  <ul class="facts">
    {#each FACTS as f}
      <li class="card">
        <b>{f.value}</b>
        <span>{f.label}</span>
        <small class="muted">Source: {f.source}</small>
      </li>
    {/each}
  </ul>
  <p class="small muted">
    The study area itself did not burn — the nearest perimeter, Olinda, is about 1.5 km outside it. Browning is
    shown as the landscape the fires burned near, not as the cause of any fire.
  </p>
</section>

<section class="wrap">
  <h2>Explore</h2>
  <ul class="cards">
    {#each CARDS as c}
      <li>
        <a class="card feature" href={c.href}>
          <span class="ico" aria-hidden="true">
            {#if c.icon === 'leaf'}<svg viewBox="0 0 24 24"><path d="M5 19c0-8 6-14 15-14-1 9-7 15-15 14Zm0 0 7-7" /></svg>
            {:else if c.icon === 'sun'}<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" /></svg>
            {:else if c.icon === 'pin'}<svg viewBox="0 0 24 24"><path d="M12 21s7-6.3 7-12a7 7 0 1 0-14 0c0 5.7 7 12 7 12Z" /><circle cx="12" cy="9" r="2.5" /></svg>
            {:else}<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18" /></svg>{/if}
          </span>
          <h3>{c.title}</h3>
          <p>{c.text}</p>
          <span class="go">Open →</span>
        </a>
      </li>
    {/each}
  </ul>
</section>

<section class="wrap isnot">
  <div class="card">
    <h2>What this is — and isn’t</h2>
    <div class="two">
      <div>
        <h3>It is</h3>
        <ul>
          <li>A record of <b>historical</b> vegetation change, drought and fire extents.</li>
          <li>Transparent: every layer shows its source, period and uncertainty.</li>
          <li>A starting point for planning questions and classroom discussion.</li>
        </ul>
      </div>
      <div>
        <h3>It is not</h3>
        <ul>
          <li>A forecast, a fire-risk score, or an official hazard designation.</li>
          <li>An alert, evacuation route, or status of any road, school or shelter.</li>
          <li>Proof that browning causes or predicts fire.</li>
        </ul>
      </div>
    </div>
    <p class="small"><a href="/methods">How the analysis works →</a> · <a href="/sources">Every data source →</a></p>
  </div>
</section>

<style>
  .hero { background: linear-gradient(180deg, var(--card), var(--paper)); border-bottom: 1px solid var(--line); padding: 56px 0 40px; }
  .grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 32px; align-items: center; }
  .lede { font-size: 1.15rem; color: var(--ink-2); max-width: 38em; }
  .cta { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
  .contours { width: 100%; color: var(--teal); }
  section.wrap { margin-top: 32px; }
  .facts { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 18px 0 10px; }
  .facts li { display: flex; flex-direction: column; gap: 4px; }
  .facts b { font-family: var(--serif); font-size: 1.8rem; color: var(--forest); }
  .cards { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  .feature { display: flex; flex-direction: column; height: 100%; text-decoration: none; color: inherit; transition: border-color .15s, transform .15s; }
  .feature:hover { border-color: var(--forest); transform: translateY(-2px); }
  .feature p { color: var(--ink-2); font-size: .95rem; flex: 1; }
  .ico svg { width: 30px; height: 30px; fill: none; stroke: var(--teal); stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  .go { color: var(--teal); font-weight: 600; font-size: .9rem; }
  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .isnot ul { padding-left: 1.1em; }
  @media (max-width: 900px) {
    .grid, .two { grid-template-columns: 1fr; }
    .contours { display: none; }
    .facts { grid-template-columns: 1fr; }
    .cards { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 560px) { .cards { grid-template-columns: 1fr; } }
</style>
