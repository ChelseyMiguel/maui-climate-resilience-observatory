/* Pure geography helpers for the 3D map. No imports, so they run under plain
 * `node --test` as well as in the browser.
 *
 * The terrain grid is spaced linearly in latitude and longitude (see
 * scripts/fetch_terrain.py), so a flat local projection in kilometres is exact
 * enough: over ~20 km the scale error of treating a degree of longitude as
 * constant is well under 0.1%.
 */

export const KM_PER_DEG_LAT = 111.32;

/* Local projection centred on the box. x = east (km), z = SOUTH (km), three.js
 * looks down -z by default, so north must be -z for "up the screen = north". */
export function makeProjection(bbox) {
  const lon0 = (bbox.west + bbox.east) / 2;
  const lat0 = (bbox.south + bbox.north) / 2;
  const kx = KM_PER_DEG_LAT * Math.cos((lat0 * Math.PI) / 180);
  return {
    lon0, lat0, kx, ky: KM_PER_DEG_LAT,
    widthKm: (bbox.east - bbox.west) * kx,
    heightKm: (bbox.north - bbox.south) * KM_PER_DEG_LAT,
    toLocal(lon, lat) {
      return [(lon - lon0) * kx, -(lat - lat0) * KM_PER_DEG_LAT];
    },
  };
}

/* Bilinear elevation (metres) at lon/lat; null outside the grid. */
export function sampleElevation(grid, meta, lon, lat) {
  const { west, east, south, north } = meta.bbox;
  const W = meta.width, H = meta.height;
  const fx = ((lon - west) / (east - west)) * (W - 1);
  const fy = ((north - lat) / (north - south)) * (H - 1);
  if (fx < 0 || fy < 0 || fx > W - 1 || fy > H - 1) return null;
  const x0 = Math.min(Math.floor(fx), W - 2), y0 = Math.min(Math.floor(fy), H - 2);
  const tx = fx - x0, ty = fy - y0;
  const at = (x, y) => grid[y * W + x];
  return (
    at(x0, y0) * (1 - tx) * (1 - ty) + at(x0 + 1, y0) * tx * (1 - ty) +
    at(x0, y0 + 1) * (1 - tx) * ty + at(x0 + 1, y0 + 1) * tx * ty
  );
}

/* lon/lat -> pixel on a canvas that covers the bbox exactly. */
export function toCanvas(bbox, cw, ch, lon, lat) {
  return [
    ((lon - bbox.west) / (bbox.east - bbox.west)) * cw,
    ((bbox.north - lat) / (bbox.north - bbox.south)) * ch,
  ];
}

/* Hypsometric tint for the base map: sea level green, through dry upland
 * browns, to bare grey near Haleakala's summit. Returns [r, g, b]. */
const STOPS = [
  [0, [62, 110, 74]], [400, [104, 132, 78]], [900, [150, 140, 92]],
  [1600, [146, 116, 88]], [2300, [128, 110, 104]], [3100, [196, 192, 188]],
];
export function elevationColor(m) {
  if (m <= STOPS[0][0]) return STOPS[0][1];
  for (let i = 1; i < STOPS.length; i++) {
    if (m <= STOPS[i][0]) {
      const [m0, c0] = STOPS[i - 1], [m1, c1] = STOPS[i];
      const t = (m - m0) / (m1 - m0);
      return c0.map((v, k) => Math.round(v + (c1[k] - v) * t));
    }
  }
  return STOPS[STOPS.length - 1][1];
}

/* Drought Monitor DSCI is 0-500: the D0-D4 shares weighted 1..5. These bands are
 * a reading aid for the chart, NOT official USDM categories. */
export function dsciLabel(v) {
  if (v < 50) return 'little or no drought';
  if (v < 150) return 'moderate';
  if (v < 250) return 'severe';
  return 'extreme';
}

/* Polygons from GeoJSON geometry as arrays of rings (outer first). */
export function polygonsOf(geometry) {
  if (!geometry) return [];
  if (geometry.type === 'Polygon') return [geometry.coordinates];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates;
  return [];
}
