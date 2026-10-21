/* Loaders and renderers for the remote-sensing products built by
 * scripts/remote_sensing/ (Sentinel-2 composites, lidar, WorldCover) and the
 * imagery served by /api/layers/imagery. Every product is optional: a missing
 * one resolves to null and the page says so. */
import { fromArrayBuffer } from 'geotiff';
import { fromUtm, toUtm } from './utm.ts';

export const BBOX = { west: -156.45, south: 20.70, east: -156.24, north: 20.88 };
export const BBOX_CORNERS: [number, number][] = [
  [BBOX.west, BBOX.north], [BBOX.east, BBOX.north], [BBOX.east, BBOX.south], [BBOX.west, BBOX.south]];

export interface ImageryItem {
  id: string; label: string; period: string; format: 'jpg' | 'tif';
  scenes?: number | null; dates?: [string, string] | null; source?: string | null; bands?: string | null;
}

export async function imageryIndex(): Promise<ImageryItem[]> {
  const r = await fetch('/api/layers/imagery');
  if (!r.ok) return [];
  return (await r.json()).available ?? [];
}

/** A canvas of an imagery item (JPEG from the AWS pipeline or a GEE GeoTIFF). */
export async function imageryCanvas(item: ImageryItem): Promise<HTMLCanvasElement> {
  const url = `/api/layers/imagery/${item.id}`;
  if (item.format === 'jpg') {
    const img = new Image();
    img.src = url;
    await img.decode();
    const c = Object.assign(document.createElement('canvas'), { width: img.naturalWidth, height: img.naturalHeight });
    c.getContext('2d')!.drawImage(img, 0, 0);
    return c;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${item.id}: ${res.status}`);
  const tif = await (await fromArrayBuffer(await res.arrayBuffer())).getImage();
  const [r, g, b] = (await tif.readRasters()) as unknown as ArrayLike<number>[];
  const c = Object.assign(document.createElement('canvas'), { width: tif.getWidth(), height: tif.getHeight() });
  const ctx = c.getContext('2d')!;
  const out = ctx.createImageData(c.width, c.height);
  for (let i = 0; i < r.length; i++) out.data.set([r[i], g[i], b[i], 255], i * 4);
  ctx.putImageData(out, 0, 0);
  return c;
}

export interface Bands {
  width: number; height: number; bands: Float32Array[]; names: string[];
  /** Native bounds: UTM metres (EPSG:32604) or degrees (EPSG:4326). */
  bounds: [number, number, number, number]; geographic: boolean; res: number;
  corners: [number, number][];
}

/** Every band of a served GeoTIFF, as Float32Arrays (NaN = no data). */
export async function loadBands(name: string, names: string[] = []): Promise<Bands | null> {
  const res = await fetch(`/api/layers/raster/${name}`);
  if (!res.ok) return null;
  const tif = await (await fromArrayBuffer(await res.arrayBuffer())).getImage();
  const width = tif.getWidth(), height = tif.getHeight();
  const bounds = tif.getBoundingBox() as [number, number, number, number];
  const geographic = Math.abs(bounds[0]) <= 180 && Math.abs(bounds[2]) <= 180;
  const rasters = (await tif.readRasters()) as unknown as ArrayLike<number>[];
  const nodata = tif.getGDALNoData();
  const bands = rasters.map((r) => {
    const a = Float32Array.from(r);
    if (nodata !== null && !Number.isNaN(nodata)) for (let i = 0; i < a.length; i++) if (a[i] === nodata) a[i] = NaN;
    return a;
  });
  const ll = (x: number, y: number): [number, number] => {
    if (geographic) return [x, y];
    const [lat, lon] = fromUtm(x, y, 4);
    return [lon, lat];
  };
  const [w, s, e, n] = bounds;
  return {
    width, height, bands, names: names.length ? names : bands.map((_, i) => `band ${i + 1}`), bounds, geographic,
    res: Math.abs(tif.getResolution()[0]), corners: [ll(w, n), ll(e, n), ll(e, s), ll(w, s)],
  };
}

/** Row/column of a lon/lat in a Bands grid, or null outside. */
export function cellOf(b: Bands, lat: number, lon: number): { row: number; col: number; i: number } | null {
  const [x, y] = b.geographic ? [lon, lat] : (toUtm(lat, lon, 4) as [number, number]);
  const [w, , e, n] = b.bounds;
  const col = Math.floor(((x - w) / (e - w)) * b.width);
  const row = Math.floor(((n - y) / (n - b.bounds[1])) * b.height);
  if (col < 0 || row < 0 || col >= b.width || row >= b.height) return null;
  return { row, col, i: row * b.width + col };
}

type RGBA = [number, number, number, number];
/** Paint one band into a canvas with a colour function (null = transparent). */
export function paint(values: Float32Array, width: number, height: number, colour: (v: number) => RGBA | null,
                      canvas: HTMLCanvasElement = document.createElement('canvas')): HTMLCanvasElement {
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(width, height);
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (Number.isNaN(v)) continue;
    const c = colour(v);
    if (c) img.data.set(c, i * 4);
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

function ramp(stops: [number, [number, number, number]][]) {
  return (v: number): [number, number, number] => {
    if (v <= stops[0][0]) return stops[0][1];
    for (let i = 1; i < stops.length; i++) {
      if (v <= stops[i][0]) {
        const [v0, c0] = stops[i - 1], [v1, c1] = stops[i];
        const t = (v - v0) / (v1 - v0);
        return c0.map((c, k) => Math.round(c + (c1[k] - c) * t)) as [number, number, number];
      }
    }
    return stops[stops.length - 1][1];
  };
}
/** NDVI 0..0.8: bare/brown to dense green (sequential, colour-blind safe ordering). */
export const NDVI_STOPS: [number, [number, number, number]][] = [
  [0.0, [140, 81, 10]], [0.2, [216, 179, 101]], [0.35, [246, 232, 195]], [0.5, [128, 205, 193]], [0.65, [53, 151, 143]], [0.8, [1, 102, 94]]];
export const ndviColour = ramp(NDVI_STOPS);
/** Canopy height 0..25 m (viridis-like). */
export const CHM_STOPS: [number, [number, number, number]][] = [
  [0, [68, 1, 84]], [2, [59, 82, 139]], [5, [33, 145, 140]], [10, [94, 201, 98]], [20, [253, 231, 37]]];
export const chmColour = ramp(CHM_STOPS);

export const WORLDCOVER: Record<number, [string, string]> = {
  10: ['Tree cover', '#006400'], 20: ['Shrubland', '#ffbb22'], 30: ['Grassland', '#ffff4c'], 40: ['Cropland', '#f096ff'],
  50: ['Built-up', '#fa0000'], 60: ['Bare / sparse vegetation', '#b4b4b4'], 70: ['Snow and ice', '#f0f0f0'],
  80: ['Permanent water', '#0064c8'], 90: ['Herbaceous wetland', '#0096a0'], 95: ['Mangroves', '#00cf75'], 100: ['Moss and lichen', '#fae6a0'],
};
const hex = (h: string): [number, number, number] => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
export const worldcoverColour = (v: number): RGBA | null => (WORLDCOVER[v] ? [...hex(WORLDCOVER[v][1]), 230] : null);

export async function remoteManifest(): Promise<any> {
  const r = await fetch('/api/layers/remote-sensing');
  return r.ok ? r.json() : {};
}

/** Thinned lidar points (scripts/remote_sensing/lidar_canopy.py): 9 bytes each,
 * uint16 easting/northing in dm from the box's SW corner, uint16 z in cm above
 * z_min, int16 height above ground in cm, uint8 class. Decoded to metres. */
export interface LidarPoints { e: Float32Array; n: Float32Array; z: Float32Array; hag: Float32Array; cls: Uint8Array; count: number }
export async function lidarPoints(zMin: number): Promise<LidarPoints | null> {
  const r = await fetch('/api/layers/lidar-points');
  if (!r.ok) return null;
  return decodeLidar(new DataView(await r.arrayBuffer()), zMin);
}
export function decodeLidar(v: DataView, zMin: number): LidarPoints {
  const count = Math.floor(v.byteLength / 9);
  const out = { e: new Float32Array(count), n: new Float32Array(count), z: new Float32Array(count), hag: new Float32Array(count), cls: new Uint8Array(count), count };
  for (let i = 0, o = 0; i < count; i++, o += 9) {
    out.e[i] = v.getUint16(o, true) / 10; out.n[i] = v.getUint16(o + 2, true) / 10;
    out.z[i] = zMin + v.getUint16(o + 4, true) / 100; out.hag[i] = v.getInt16(o + 6, true) / 100; out.cls[i] = v.getUint8(o + 8);
  }
  return out;
}

/** Median of the finite values of an array (data-quality indicators). */
export function median(a: ArrayLike<number>): number | null {
  const v = Array.from(a).filter(Number.isFinite).sort((x, y) => x - y);
  if (!v.length) return null;
  return v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
}
