<script>
  // The Observatory shell: navigation, the always-visible research-only notice,
  // and a tiny router. The 360° GLOBE site viewer stays its own page (/viewer).
  import { path as currentPath, interceptLinks } from './lib/router.ts';
  import Notice from './components/Notice.svelte';
  import Overview from './pages/Overview.svelte';

  // Pages load on demand: the map libraries (MapLibre ~0.8 MB, three.js ~0.6 MB)
  // are only downloaded when someone opens a page that uses them, so the Overview
  // stays fast. The Overview itself ships in the main bundle.
  const PAGES = {
    '/': () => Promise.resolve({ default: Overview }),
    '/explore': () => import('./pages/Explore.svelte'),
    '/insights': () => import('./pages/Insights.svelte'),
    '/map': () => import('./pages/Map3D.svelte'),
    '/methods': () => import('./pages/Methods.svelte'),
    '/sources': () => import('./pages/Sources.svelte'),
    '/about': () => import('./pages/About.svelte'),
  };
  const NAV = [
    ['/', 'Overview'], ['/explore', 'Map Explorer'], ['/insights', 'Region Insights'],
    ['/map', '3D View'], ['/viewer', 'Site Viewer'], ['/methods', 'Methods'],
    ['/sources', 'Sources'], ['/about', 'About'],
  ];
  const TITLES = {
    '/': 'Overview', '/explore': 'Map Explorer', '/insights': 'Region Insights', '/map': '3D View',
    '/methods': 'Methods & Transparency', '/sources': 'Data Sources', '/about': 'About',
  };

  let menuOpen = false;
  $: loader = PAGES[$currentPath];
  $: pagePromise = loader ? loader() : null;
  $: fullBleed = $currentPath === '/explore' || $currentPath === '/map';
  $: document.title = `${TITLES[$currentPath] ?? 'Not found'} · Rural Hawaiʻi Climate Resilience Observatory`;
  $: $currentPath, (menuOpen = false);
</script>

<svelte:window on:click={interceptLinks} />

<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <div class="bar">
    <a class="brand" href="/">
      <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
        <path d="M2 24c5-7 9-10 14-10s9 3 14 10" fill="none" stroke="currentColor" stroke-width="2"/>
        <path d="M6 24c4-4 7-6 10-6s6 2 10 6" fill="none" stroke="currentColor" stroke-width="1.4" opacity=".6"/>
        <circle cx="16" cy="8" r="3.2" fill="currentColor"/>
      </svg>
      <span><b>Climate Resilience Observatory</b><small>Rural Hawaiʻi · Upcountry Maui</small></span>
    </a>
    <button class="menu" aria-expanded={menuOpen} aria-controls="nav" on:click={() => (menuOpen = !menuOpen)}>
      Menu
    </button>
    <nav id="nav" class:open={menuOpen} aria-label="Main">
      {#each NAV as [href, label]}
        <a {href} aria-current={$currentPath === href ? 'page' : undefined}>{label}</a>
      {/each}
    </nav>
  </div>
  {#if !fullBleed}<div class="wrap noticebar"><Notice compact /></div>{/if}
</header>

<main id="main" class:fullBleed tabindex="-1">
  {#if pagePromise}
    {#await pagePromise}
      <div class="wrap pageload" aria-busy="true">Loading…</div>
    {:then mod}
      <svelte:component this={mod.default} />
    {:catch err}
      <section class="wrap notfound" role="alert"><h1>Couldn’t load this page</h1><p>{err.message}</p></section>
    {/await}
  {:else}
    <section class="wrap notfound">
      <h1>Page not found</h1>
      <p><a href="/">Back to the overview</a></p>
    </section>
  {/if}
</main>

{#if !fullBleed}
  <footer class="wrap">
    <p class="small muted">An independent, student-led research and education project. Data from NASA GLOBE,
      the National Interagency Fire Center, the U.S. Drought Monitor, the USDA Forest Service, the Hawaiʻi
      Statewide GIS Program, and the author’s own Sentinel-2 analysis — see <a href="/sources">Sources</a>.
      No institutional endorsement is implied.</p>
  </footer>
{/if}

<style>
  .skip { position: absolute; left: -999px; top: 0; background: var(--forest); color: #111; padding: .5em 1em; z-index: 10; }
  .skip:focus { left: 8px; top: 8px; }
  header.site { background: var(--card); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }
  .bar { display: flex; align-items: center; gap: 18px; padding: 10px 22px; max-width: 1400px; margin: 0 auto; }
  .brand { display: flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; }
  .brand span { display: flex; flex-direction: column; line-height: 1.15; }
  .brand b { font-family: var(--serif); font-size: 1.05rem; }
  .brand small { color: var(--muted); font-size: .75rem; }
  nav { display: flex; flex-wrap: wrap; gap: 2px; margin-left: auto; }
  nav a { padding: .4em .7em; border-radius: 2px; color: var(--ink-2); text-decoration: none; font-size: .92rem; }
  nav a:hover { background: var(--paper-2); color: var(--forest); }
  nav a[aria-current='page'] { background: none; color: var(--ink); box-shadow: inset 0 -2px 0 var(--forest); }
  .menu { display: none; margin-left: auto; border: 1px solid var(--line); background: var(--card); border-radius: 2px; padding: .35em .8em; }
  .noticebar { padding-bottom: 10px; }
  main { outline: none; }
  main.fullBleed { height: calc(100vh - 57px); }
  footer { padding: 28px 22px 40px; border-top: 1px solid var(--line); margin-top: 48px; }
  .notfound { padding: 60px 22px; }
  .pageload { padding: 60px 22px; color: var(--muted); }
  /* Eight links need ~1100 px on one line; below that, collapse to a menu
     rather than wrapping onto a second row. */
  @media (max-width: 1120px) {
    .menu { display: block; }
    nav { display: none; position: absolute; top: 100%; left: 0; right: 0; background: var(--card);
          flex-direction: column; padding: 8px 14px 14px; border-bottom: 1px solid var(--line); }
    nav.open { display: flex; }
  }
</style>
