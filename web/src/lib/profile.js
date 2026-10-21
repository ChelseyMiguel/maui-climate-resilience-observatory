// Transect maths: evenly spaced samples along a great-circle-short line and the
// slope statistics the profile panel reports. Pure, so tests/js can check it.

const R = 6371008.8;
export function distanceM([lon1, lat1], [lon2, lat2]) {
  const f1 = (lat1 * Math.PI) / 180, f2 = (lat2 * Math.PI) / 180;
  const df = f2 - f1, dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(df / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** n+1 points from a to b (linear in lon/lat; under 1 m error over a few km). */
export function samplePoints(a, b, n) {
  const total = distanceM(a, b);
  return Array.from({ length: n + 1 }, (_, i) => {
    const t = i / n;
    return { lon: a[0] + (b[0] - a[0]) * t, lat: a[1] + (b[1] - a[1]) * t, d: total * t };
  });
}

/** Rise, fall, range and slope (percent) from [{d, z}] with z in metres. */
export function slopeStats(pts) {
  const ok = pts.filter((p) => Number.isFinite(p.z));
  if (ok.length < 2) return null;
  let rise = 0, fall = 0, maxSlope = 0;
  for (let i = 1; i < ok.length; i++) {
    const dz = ok[i].z - ok[i - 1].z, dd = ok[i].d - ok[i - 1].d;
    if (dz > 0) rise += dz; else fall -= dz;
    if (dd > 0) maxSlope = Math.max(maxSlope, Math.abs(dz / dd) * 100);
  }
  const zs = ok.map((p) => p.z), len = ok[ok.length - 1].d - ok[0].d;
  return {
    lengthM: len, min: Math.min(...zs), max: Math.max(...zs), rise, fall,
    netChange: ok[ok.length - 1].z - ok[0].z,
    meanSlopePct: len > 0 ? (Math.abs(ok[ok.length - 1].z - ok[0].z) / len) * 100 : 0, maxSlopePct: maxSlope,
  };
}
