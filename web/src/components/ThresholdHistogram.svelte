<script>
  // Distribution of the study area's change values with a draggable threshold
  // marker. Bars are coloured by the three display classes; the marker can be
  // dragged, clicked to, or moved with the arrow keys.
  import { createEventDispatcher } from 'svelte';
  export let bins = [];            // [{ x0, count }] from series.histogram, width 0.02
  export let threshold = -0.1;
  export let label = 'dNDVI';
  export let min = -0.4;
  export let max = 0;

  const dispatch = createEventDispatcher();
  const W = 300, H = 92, B = 16, LO = -0.6, HI = 0.4;
  const X = (v) => ((v - LO) / (HI - LO)) * W;
  $: top = Math.max(1, ...bins.map((b) => b.count));
  $: cls = (x0) => (x0 + 0.01 < threshold ? 'b' : x0 + 0.01 > -threshold ? 'g' : 's');

  let svg, dragging = false;
  function valueAt(e) {
    const r = svg.getBoundingClientRect();
    const v = LO + ((e.clientX - r.left) / r.width) * (HI - LO);
    return Math.round(Math.max(min, Math.min(max, v)) * 100) / 100;
  }
  const set = (v) => dispatch('change', v);
  function down(e) { dragging = true; svg.setPointerCapture(e.pointerId); set(valueAt(e)); }
  function move(e) { if (dragging) set(valueAt(e)); }
  function key(e) {
    const step = e.shiftKey ? 0.05 : 0.01;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') set(Math.max(min, +(threshold - step).toFixed(2)));
    else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') set(Math.min(max, +(threshold + step).toFixed(2)));
    else return;
    e.preventDefault();
  }
</script>

<svg bind:this={svg} viewBox="0 0 {W} {H}" class="hist" role="slider" tabindex="0"
     aria-label="{label} threshold on the histogram" aria-valuemin={min} aria-valuemax={max} aria-valuenow={threshold}
     aria-valuetext="{label} below {threshold.toFixed(2)}"
     on:pointerdown={down} on:pointermove={move} on:pointerup={() => (dragging = false)} on:keydown={key}>
  <rect class="ok" x={X(min)} y="0" width={X(max) - X(min)} height={H - B} />
  {#each bins as b}
    <rect class="bar {cls(b.x0)}" x={X(b.x0) + 0.5} width={X(b.x0 + 0.02) - X(b.x0) - 1}
          y={H - B - (b.count / top) * (H - B - 6)} height={(b.count / top) * (H - B - 6)} />
  {/each}
  <line class="axis" x1="0" x2={W} y1={H - B} y2={H - B} />
  {#each [-0.6, -0.4, -0.2, 0, 0.2, 0.4] as t}
    <line class="axis" x1={X(t)} x2={X(t)} y1={H - B} y2={H - B + 3} />
    <text x={X(t)} y={H - 3} text-anchor={t === -0.6 ? 'start' : t === 0.4 ? 'end' : 'middle'}>{t.toFixed(1)}</text>
  {/each}
  <line class="ref" x1={X(-0.1)} x2={X(-0.1)} y1="0" y2={H - B} />
  <g class="marker" transform="translate({X(threshold)},0)">
    <line y1="0" y2={H - B} />
    <rect x="-4" y="0" width="8" height="9" />
  </g>
</svg>

<style>
  .hist { width: 100%; height: auto; display: block; background: var(--paper); border: 1px solid var(--line); cursor: ew-resize; touch-action: none; }
  .ok { fill: var(--paper-2); }
  .bar.b { fill: #d08a3c; } .bar.s { fill: #5d676d; } .bar.g { fill: #40a8a0; }
  .axis { stroke: var(--muted); }
  text { fill: var(--muted); font: 8px var(--mono); }
  .ref { stroke: var(--ink-2); stroke-dasharray: 2 2; }
  .marker line { stroke: var(--ink); stroke-width: 1.5; }
  .marker rect { fill: var(--forest); stroke: #111; }
</style>
