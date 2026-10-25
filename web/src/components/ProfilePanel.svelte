<script>
  // Elevation profile along a user-drawn transect, with the change value of the
  // 10 m pixel under each sample beneath it on the same distance axis. Elevation
  // is terrain; dNDVI is a spectral index, they share an x axis, never a y axis.
  import { createEventDispatcher } from 'svelte';
  import { classify } from '../lib/threshold.js';
  import { toCsv } from '../lib/series.js';

  export let profile = null;     // { points: [{ d, lon, lat, z, v }], stats, source, loading, error }
  export let threshold = -0.1;
  export let label = 'dNDVI';

  const dispatch = createEventDispatcher();
  const W = 1000, L = 56, R = 14, T = 16, EH = 120, GAP = 26, VH = 70, AX = 22;
  const H = T + EH + GAP + VH + AX;
  const COLORS = { browning: '#d08a3c', stable: '#5d676d', greening: '#40a8a0' };

  $: pts = profile?.points ?? [];
  $: dMax = pts.length ? pts[pts.length - 1].d : 1;
  $: x = (d) => L + (d / dMax) * (W - L - R);
  $: zs = pts.map((p) => p.z).filter(Number.isFinite);
  $: zLo = zs.length ? Math.floor(Math.min(...zs) / 50) * 50 : 0;
  $: zHi = zs.length ? Math.ceil(Math.max(...zs) / 50) * 50 + (Math.max(...zs) === Math.min(...zs) ? 50 : 0) : 1;
  $: yz = (z) => T + EH - ((z - zLo) / (zHi - zLo || 1)) * EH;
  const VLO = -0.6, VHI = 0.4, vTop = T + EH + GAP;
  const yv = (v) => vTop + VH - ((Math.max(VLO, Math.min(VHI, v)) - VLO) / (VHI - VLO)) * VH;
  $: elevPath = pts.reduce((s, p, i) => (Number.isFinite(p.z) ? s + `${s && Number.isFinite(pts[i - 1]?.z) ? 'L' : 'M'}${x(p.d).toFixed(1)},${yz(p.z).toFixed(1)}` : s), '');
  $: inRaster = pts.filter((p) => p.v !== null);
  $: browned = inRaster.filter((p) => classify(p.v, threshold) === 'browning').length;
  $: barW = Math.max(1, (W - L - R) / Math.max(1, pts.length) - 0.5);
  $: dTicks = niceTicks(dMax / 1000).map((k) => k * 1000);
  function niceTicks(km) {
    const step = km > 6 ? 2 : km > 3 ? 1 : km > 1.2 ? 0.5 : km > 0.5 ? 0.2 : 0.1;
    const out = [];
    for (let k = 0; k <= km + 1e-9; k += step) out.push(+k.toFixed(2));
    return out;
  }

  let hover = null, svgEl;
  function move(e) {
    if (!pts.length) return;
    const p = svgEl.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
    const sx = p.matrixTransform(svgEl.getScreenCTM().inverse()).x;
    const i = Math.round(((sx - L) / (W - L - R)) * (pts.length - 1));
    hover = i >= 0 && i < pts.length ? i : null;
    dispatch('hover', hover === null ? null : pts[hover]);
  }
  function leave() { hover = null; dispatch('hover', null); }

  function csv() {
    const rows = pts.map((p) => ({ distance_m: Math.round(p.d * 10) / 10, lon: p.lon.toFixed(6), lat: p.lat.toFixed(6),
      elevation_m: Number.isFinite(p.z) ? Math.round(p.z * 10) / 10 : null, [label.toLowerCase()]: p.v === null ? null : +p.v.toFixed(4),
      class_at_threshold: p.v === null ? null : classify(p.v, threshold) }));
    const blob = new Blob([toCsv(rows, Object.keys(rows[0]))], { type: 'text/csv' });
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'transect_profile.csv' });
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
</script>

<section class="panel" aria-label="Transect profile">
  <header>
    <h2>Transect profile</h2>
    {#if pts.length}<button class="b" on:click={csv}>CSV</button>{/if}
    <button class="x" aria-label="Close profile" on:click={() => dispatch('close')}>×</button>
  </header>
  {#if !profile}
    <p class="muted small">Click two points on the map to draw a transect.</p>
  {:else if profile.loading}
    <p class="muted small">Sampling elevation along {Math.round(dMax)} m…</p>
  {:else}
    {#if profile.stats}
      <dl class="kpi">
        <div><dt>Length</dt><dd>{(profile.stats.lengthM / 1000).toFixed(2)} km</dd></div>
        <div><dt>Elevation</dt><dd>{Math.round(profile.stats.min)}–{Math.round(profile.stats.max)} m</dd></div>
        <div><dt>Net change</dt><dd>{profile.stats.netChange >= 0 ? '+' : ''}{Math.round(profile.stats.netChange)} m</dd></div>
        <div><dt>Mean / max slope</dt><dd>{profile.stats.meanSlopePct.toFixed(1)} / {profile.stats.maxSlopePct.toFixed(0)}%</dd></div>
        <div><dt>{label} &lt; {threshold.toFixed(2)}</dt><dd>{inRaster.length ? `${browned}/${inRaster.length} samples` : 'outside raster'}</dd></div>
      </dl>
    {/if}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <svg bind:this={svgEl} viewBox="0 0 {W} {H}" role="img" on:mousemove={move} on:mouseleave={leave}
         aria-label="Elevation in metres and {label} along a {Math.round(dMax)} m transect">
      <rect class="bg" width={W} height={H} />
      <text class="t" x={L} y={T - 4}>Elevation (m) · {profile.source}</text>
      {#each [zLo, (zLo + zHi) / 2, zHi] as z}
        <line class="g" x1={L} x2={W - R} y1={yz(z)} y2={yz(z)} /><text class="yt" x={L - 6} y={yz(z) + 4}>{Math.round(z)}</text>
      {/each}
      <path d={elevPath} class="elev" />
      <text class="t" x={L} y={vTop - 4}>{label} of the 10 m pixel at each sample (2022 − 2019 dry season)</text>
      {#each [-0.4, 0, 0.4] as v}
        <line class="g" class:zero={v === 0} x1={L} x2={W - R} y1={yv(v)} y2={yv(v)} /><text class="yt" x={L - 6} y={yv(v) + 4}>{v.toFixed(1)}</text>
      {/each}
      <line class="thr" x1={L} x2={W - R} y1={yv(threshold)} y2={yv(threshold)} />
      {#each pts as p}
        {#if p.v !== null}
          <rect x={x(p.d) - barW / 2} width={barW} y={Math.min(yv(0), yv(p.v))} height={Math.max(0.5, Math.abs(yv(p.v) - yv(0)))}
                fill={COLORS[classify(p.v, threshold)]} />
        {/if}
      {/each}
      {#if !inRaster.length}<text class="yt none" x={L + 8} y={vTop + VH / 2}>Transect is outside the 1.5 km change raster</text>{/if}
      {#each dTicks as d}
        {#if d <= dMax}<text class="xt" x={x(d)} y={H - 6}>{(d / 1000).toFixed(d % 1000 ? 1 : 0)} km</text>{/if}
      {/each}
      {#if hover !== null}<line class="cross" x1={x(pts[hover].d)} x2={x(pts[hover].d)} y1={T} y2={H - AX} />{/if}
    </svg>
    <div class="read">
      {#if hover !== null}
        {@const p = pts[hover]}
        <span>{(p.d / 1000).toFixed(3)} km</span><span>{p.lat.toFixed(5)}, {p.lon.toFixed(5)}</span>
        <span>{Number.isFinite(p.z) ? `${p.z.toFixed(1)} m` : 'no elevation'}</span>
        <span>{label} {p.v === null ? 'n/a' : p.v.toFixed(3)}{p.v !== null ? ` · ${classify(p.v, threshold)}` : ''}</span>
      {:else}<span class="muted">Hover the profile to locate a sample on the map.</span>{/if}
    </div>
    {#if profile.error}<p class="err small">{profile.error}</p>{/if}
  {/if}
</section>

<style>
  .panel { background: var(--card); border-top: 1px solid var(--line); padding: 8px 14px 10px; }
  header { display: flex; align-items: center; gap: 6px; }
  h2 { margin: 0; border: 0; padding: 0; font-size: .8rem; flex: 1; }
  .x, .b { background: var(--paper-2); border: 1px solid var(--line); color: var(--ink-2); padding: 2px 9px; font-size: .78rem; }
  .kpi { display: grid; grid-template-columns: repeat(5, 1fr); margin: 6px 0; border: 1px solid var(--line); }
  .kpi div { padding: 3px 8px; } .kpi div + div { border-left: 1px solid var(--line); }
  .kpi dt { font-size: .64rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
  .kpi dd { margin: 0; font: 700 .85rem var(--mono); }
  svg[role='img'] { width: 100%; height: auto; display: block; border: 1px solid var(--line); }
  .bg { fill: var(--card); }
  .t { fill: var(--ink); font-size: 11px; font-weight: 600; }
  .yt { fill: var(--muted); font: 10px var(--mono); text-anchor: end; } .yt.none { text-anchor: start; }
  .xt { fill: var(--muted); font: 10px var(--mono); text-anchor: middle; }
  .g { stroke: #252c31; } .g.zero { stroke: var(--muted); }
  .elev { fill: none; stroke: var(--ink); stroke-width: 1.6; }
  .thr { stroke: var(--forest); stroke-dasharray: 4 3; }
  .cross { stroke: var(--forest); }
  .read { display: flex; flex-wrap: wrap; gap: 4px 14px; font: .76rem var(--mono); margin-top: 4px; min-height: 1.5em; }
  .err { color: var(--fire); }
  @media (max-width: 700px) { .kpi { grid-template-columns: repeat(2, 1fr); } }
</style>
