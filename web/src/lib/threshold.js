// Threshold arithmetic for the dNDVI / dNBR change rasters, shared by the Map
// Explorer, the 3D view and the Analysis workspace. Pure (no DOM) so tests/js can
// check it against the real GeoTIFFs. The research rule is strict: a pixel is
// "browned" when its change value is < -0.10, compared in float32 as stored.

export const RESEARCH_THRESHOLD = -0.1;

/** Count valid (non-NaN) pixels and those strictly below `threshold`. */
export function countBelow(values, threshold) {
  const t = Math.fround(threshold);
  let valid = 0, below = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (Number.isNaN(v)) continue;
    valid++;
    if (v < t) below++;
  }
  return { valid, below, share: valid ? below / valid : 0 };
}

/** Three display classes. The greening cut-off mirrors the browning one (+|t|);
 * it is a display choice, not part of the study's method. */
export function classify(v, threshold) {
  if (Number.isNaN(v)) return null;
  if (v < Math.fround(threshold)) return 'browning';
  if (v > Math.fround(-threshold)) return 'greening';
  return 'stable';
}

export function classCounts(values, threshold) {
  const out = { browning: 0, stable: 0, greening: 0 };
  for (let i = 0; i < values.length; i++) {
    const c = classify(values[i], threshold);
    if (c) out[c]++;
  }
  return out;
}

/** Hectares for a pixel count at a square pixel size in metres. */
export const hectares = (pixels, pixelMetres) => (pixels * pixelMetres * pixelMetres) / 10000;
