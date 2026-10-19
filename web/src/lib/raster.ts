/* The project's change rasters (dNDVI / dNBR) on a lat/lon map.
 *
 * The GeoTIFFs are in UTM zone 4N at 10 m. They are colourised into a canvas and
 * placed with their four corners converted to lon/lat (src/lib/utm.ts). Over the
 * 3 km extent the UTM grid is effectively affine in lon/lat, so corner placement
 * is accurate to well under a pixel — checked: the raster centre lands 2.7 m from
 * the study-area point, against 10 m pixels. */
import { fromArrayBuffer } from 'geotiff';
import { fromUtm, toUtm } from './utm.ts';
import type { RasterLayerMetadata } from './types.ts';

export const BROWNING_THRESHOLD = -0.1;
const UTM_ZONE = 4;

/** Colour-blind-safe diverging ramp (ColorBrewer BrBG): brown = loss, teal = gain. */
const RAMP: [number, [number, number, number]][] = [
  [-0.4, [140, 81, 10]], [-0.2, [216, 179, 101]], [-0.1, [246, 232, 195]],
  [0, [245, 245, 245]], [0.1, [199, 234, 229]], [0.2, [90, 180, 172]], [0.4, [1, 102, 94]],
];

export function rampColor(v: number): [number, number, number] {
  if (v <= RAMP[0][0]) return RAMP[0][1];
  for (let i = 1; i < RAMP.length; i++) {
    if (v <= RAMP[i][0]) {
      const [v0, c0] = RAMP[i - 1], [v1, c1] = RAMP[i];
      const t = (v - v0) / (v1 - v0);
      return c0.map((c, k) => Math.round(c + (c1[k] - c) * t)) as [number, number, number];
    }
  }
  return RAMP[RAMP.length - 1][1];
}
export const RAMP_STOPS = RAMP.map(([v]) => v);

export interface LoadedRaster {
  meta: RasterLayerMetadata;
  values: Float32Array;
  imageUrl: string;
  valueAt(lat: number, lon: number): number | null;
}

const TITLES = { dndvi: 'dNDVI (greenness change)', dnbr: 'dNBR (moisture-sensitive change)' } as const;

export async function loadChangeRaster(id: 'dndvi' | 'dnbr'): Promise<LoadedRaster> {
  const res = await fetch(`/api/layers/raster/${id}`);
  if (!res.ok) throw new Error(`/api/layers/raster/${id}: ${res.status}`);
  const tiff = await fromArrayBuffer(await res.arrayBuffer());
  const image = await tiff.getImage();
  const width = image.getWidth(), height = image.getHeight();
  const [west, south, east, north] = image.getBoundingBox() as [number, number, number, number];
  const pixel = Math.abs(image.getResolution()[0]);
  const raw = (await image.readRasters())[0] as ArrayLike<number>;
  const values = Float32Array.from(raw);

  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(width, height);
  let valid = 0, below = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (Number.isNaN(v)) continue;           // outside the 1.5 km circle: transparent
    valid++;
    if (v < BROWNING_THRESHOLD) below++;
    const [r, g, b] = rampColor(v);
    img.data.set([r, g, b, 235], i * 4);
  }
  ctx.putImageData(img, 0, 0);

  const ll = (e: number, n: number): [number, number] => {
    const [lat, lon] = fromUtm(e, n, UTM_ZONE);
    return [lon, lat];
  };
  const meta: RasterLayerMetadata = {
    id, title: TITLES[id],
    period: 'Dry season (May–Sep) 2022 minus dry season 2019',
    epsg: 32604, pixelMetres: pixel, width, height,
    utmBbox: [west, south, east, north],
    corners: [ll(west, north), ll(east, north), ll(east, south), ll(west, south)],
    shareBelowThreshold: valid ? below / valid : 0,
  };

  return {
    meta, values, imageUrl: canvas.toDataURL('image/png'),
    valueAt(lat, lon) {
      const [e, n] = toUtm(lat, lon, UTM_ZONE);
      const col = Math.floor((e - west) / pixel), row = Math.floor((north - n) / pixel);
      if (col < 0 || row < 0 || col >= width || row >= height) return null;
      const v = values[row * width + col];
      return Number.isNaN(v) ? null : v;
    },
  };
}

/** Severity ramp for the threshold view: pale tan just under the threshold to
 * deep brown at -0.4 and below. Lightness falls monotonically with loss. */
function severityColor(v: number, threshold: number): [number, number, number] {
  const t = Math.max(0, Math.min(1, (threshold - v) / Math.max(0.05, threshold + 0.4)));
  const lo = [246, 196, 120], hi = [120, 52, 6];
  return lo.map((c, k) => Math.round(c + (hi[k] - c) * t)) as [number, number, number];
}

export interface ThresholdView { imageUrl: string; canvas: HTMLCanvasElement; below: number; valid: number; hectares: number }

/** Only the pixels below `threshold`, as an image for the same corners, plus counts. */
export function renderBelow(r: LoadedRaster, threshold: number): ThresholdView {
  const { width, height, pixelMetres } = r.meta;
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(width, height);
  let valid = 0, below = 0;
  for (let i = 0; i < r.values.length; i++) {
    const v = r.values[i];
    if (Number.isNaN(v)) continue;
    valid++;
    if (v >= threshold) continue;
    below++;
    img.data.set([...severityColor(v, threshold), 245], i * 4);
  }
  ctx.putImageData(img, 0, 0);
  return { imageUrl: canvas.toDataURL('image/png'), canvas, below, valid, hectares: (below * pixelMetres * pixelMetres) / 10000 };
}

