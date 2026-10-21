// Elevation from AWS Terrain Tiles (Mapzen/Tilezen "terrarium" PNGs, public on
// S3). Used for pointer readouts, pixel inspection and transect profiles. Tiles
// are fetched once and cached; if they can't be reached the caller falls back to
// the app's local 68 m DEM grid and says so.
export const TERRARIUM_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
export const SAMPLE_ZOOM = 14;   // tile pixel ~8.9 m at Upcountry Maui's latitude

/** Terrarium encoding: metres = R*256 + G + B/256 - 32768. */
export const decode = (r, g, b) => r * 256 + g + b / 256 - 32768;

/** Fractional Web Mercator tile coordinates of a lon/lat at zoom z. */
export function tileXY(lon, lat, z) {
  const n = 2 ** z, rad = (lat * Math.PI) / 180;
  return [((lon + 180) / 360) * n, ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n];
}

/** Ground size of one tile pixel in metres. */
export const pixelMetres = (lat, z) => (40075016.686 * Math.cos((lat * Math.PI) / 180)) / (256 * 2 ** z);

export function createSampler({ zoom = SAMPLE_ZOOM, url = TERRARIUM_URL, load = loadTile } = {}) {
  const cache = new Map();
  function tile(x, y) {
    const key = `${x}/${y}`;
    if (!cache.has(key)) cache.set(key, load(url.replace('{z}', zoom).replace('{x}', x).replace('{y}', y)).catch((e) => { cache.delete(key); throw e; }));
    return cache.get(key);
  }
  /** Bilinear elevation (m) at lon/lat; rejects if the tile can't load. */
  async function at(lon, lat) {
    const [fx, fy] = tileXY(lon, lat, zoom);
    const px = fx * 256 - 0.5, py = fy * 256 - 0.5;
    const x0 = Math.floor(px), y0 = Math.floor(py), tx = px - x0, ty = py - y0;
    const get = async (gx, gy) => {
      const data = await tile(Math.floor(gx / 256), Math.floor(gy / 256));
      return data[((gy % 256) + 256) % 256 * 256 + (((gx % 256) + 256) % 256)];
    };
    const [a, b, c, d] = await Promise.all([get(x0, y0), get(x0 + 1, y0), get(x0, y0 + 1), get(x0 + 1, y0 + 1)]);
    return a * (1 - tx) * (1 - ty) + b * tx * (1 - ty) + c * (1 - tx) * ty + d * tx * ty;
  }
  return { at, zoom };
}

/** Browser loader: PNG -> Float32Array of 256x256 metres. */
async function loadTile(href) {
  const res = await fetch(href);
  if (!res.ok) throw new Error(`terrain tile ${res.status}`);
  const bmp = await createImageBitmap(await res.blob());
  const c = new OffscreenCanvas(256, 256);
  const ctx = c.getContext('2d');
  ctx.drawImage(bmp, 0, 0);
  const px = ctx.getImageData(0, 0, 256, 256).data;
  const out = new Float32Array(256 * 256);
  for (let i = 0; i < out.length; i++) out[i] = decode(px[i * 4], px[i * 4 + 1], px[i * 4 + 2]);
  return out;
}
