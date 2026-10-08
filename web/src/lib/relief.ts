/* Shaded-relief base map computed from the project's own terrain grid, so the
 * Explorer needs no third-party map tiles: it works offline and carries no tile
 * usage terms. Standard hillshade (sun from the north-west, 45 degrees up)
 * blended with a light elevation tint. */

export interface TerrainGrid {
  meta: { width: number; height: number; bbox: { west: number; east: number; south: number; north: number } };
  grid: Int16Array;
}

const TINT: [number, [number, number, number]][] = [
  [0, [214, 226, 205]], [500, [222, 220, 190]], [1200, [226, 210, 180]],
  [2000, [214, 200, 186]], [3100, [236, 234, 230]],
];

function tint(m: number): [number, number, number] {
  if (m <= TINT[0][0]) return TINT[0][1];
  for (let i = 1; i < TINT.length; i++) {
    if (m <= TINT[i][0]) {
      const [m0, c0] = TINT[i - 1], [m1, c1] = TINT[i];
      const t = (m - m0) / (m1 - m0);
      return c0.map((c, k) => c + (c1[k] - c) * t) as [number, number, number];
    }
  }
  return TINT[TINT.length - 1][1];
}

export function hillshade(dzdx: number, dzdy: number, azimuthDeg = 315, altitudeDeg = 45): number {
  const zenith = ((90 - altitudeDeg) * Math.PI) / 180;
  const azimuth = ((360 - azimuthDeg + 90) % 360) * (Math.PI / 180);
  const slope = Math.atan(Math.hypot(dzdx, dzdy));
  let aspect = Math.atan2(dzdy, -dzdx);
  if (aspect < 0) aspect += 2 * Math.PI;
  const v = Math.cos(zenith) * Math.cos(slope) + Math.sin(zenith) * Math.sin(slope) * Math.cos(azimuth - aspect);
  return Math.max(0, Math.min(1, v));
}

export function reliefDataUrl({ meta, grid }: TerrainGrid): string {
  const { width: W, height: H, bbox } = meta;
  const lat0 = (bbox.north + bbox.south) / 2;
  const cellX = ((bbox.east - bbox.west) / (W - 1)) * 111_320 * Math.cos((lat0 * Math.PI) / 180);
  const cellY = ((bbox.north - bbox.south) / (H - 1)) * 111_320;
  const at = (x: number, y: number) => grid[Math.min(H - 1, Math.max(0, y)) * W + Math.min(W - 1, Math.max(0, x))];

  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const z = at(x, y);
      const i = (y * W + x) * 4;
      if (z <= 0) { img.data.set([196, 218, 228, 255], i); continue; }   // ocean
      // Rows run north to south, so +y in the grid is southward.
      const dzdx = (at(x + 1, y) - at(x - 1, y)) / (2 * cellX);
      const dzdy = (at(x, y - 1) - at(x, y + 1)) / (2 * cellY);
      const shade = 0.55 + 0.6 * (hillshade(dzdx, dzdy) - 0.5);
      const [r, g, b] = tint(z);
      img.data.set([r * shade, g * shade, b * shade, 255].map((v) => Math.max(0, Math.min(255, v))), i);
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL('image/png');
}
