/* WGS84 <-> UTM conversion, so the project's rasters (EPSG:32604, UTM zone 4N)
 * can be placed on a lat/lon map and queried at a clicked point.
 *
 * Standard transverse Mercator series (Snyder, "Map Projections, A Working
 * Manual", USGS Professional Paper 1395, pp. 61-64). Accurate to well under a
 * metre within a UTM zone, far finer than the 10 m pixels it is used for.
 * No imports, so it runs under plain `node --test` as well as in the browser.
 */

const A = 6378137.0;               // WGS84 semi-major axis (m)
const F = 1 / 298.257223563;       // WGS84 flattening
const K0 = 0.9996;                 // UTM scale factor on the central meridian
const E2 = F * (2 - F);            // first eccentricity squared
const EP2 = E2 / (1 - E2);         // second eccentricity squared
const FALSE_EASTING = 500000;

const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

export function centralMeridian(zone: number): number {
  return -183 + 6 * zone;
}

function meridionalArc(phi: number): number {
  return A * (
    (1 - E2 / 4 - (3 * E2 ** 2) / 64 - (5 * E2 ** 3) / 256) * phi -
    ((3 * E2) / 8 + (3 * E2 ** 2) / 32 + (45 * E2 ** 3) / 1024) * Math.sin(2 * phi) +
    ((15 * E2 ** 2) / 256 + (45 * E2 ** 3) / 1024) * Math.sin(4 * phi) -
    ((35 * E2 ** 3) / 3072) * Math.sin(6 * phi)
  );
}

/** lat/lon (degrees) -> [easting, northing] in metres, northern hemisphere. */
export function toUtm(lat: number, lon: number, zone: number): [number, number] {
  const phi = rad(lat);
  const N = A / Math.sqrt(1 - E2 * Math.sin(phi) ** 2);
  const T = Math.tan(phi) ** 2;
  const C = EP2 * Math.cos(phi) ** 2;
  const Aa = Math.cos(phi) * rad(lon - centralMeridian(zone));
  const M = meridionalArc(phi);
  const easting = FALSE_EASTING + K0 * N * (
    Aa + ((1 - T + C) * Aa ** 3) / 6 +
    ((5 - 18 * T + T ** 2 + 72 * C - 58 * EP2) * Aa ** 5) / 120
  );
  const northing = K0 * (M + N * Math.tan(phi) * (
    Aa ** 2 / 2 + ((5 - T + 9 * C + 4 * C ** 2) * Aa ** 4) / 24 +
    ((61 - 58 * T + T ** 2 + 600 * C - 330 * EP2) * Aa ** 6) / 720
  ));
  return [easting, northing];
}

/** [easting, northing] in metres -> [lat, lon] in degrees, northern hemisphere. */
export function fromUtm(easting: number, northing: number, zone: number): [number, number] {
  const M = northing / K0;
  const mu = M / (A * (1 - E2 / 4 - (3 * E2 ** 2) / 64 - (5 * E2 ** 3) / 256));
  const e1 = (1 - Math.sqrt(1 - E2)) / (1 + Math.sqrt(1 - E2));
  const phi1 = mu +
    ((3 * e1) / 2 - (27 * e1 ** 3) / 32) * Math.sin(2 * mu) +
    ((21 * e1 ** 2) / 16 - (55 * e1 ** 4) / 32) * Math.sin(4 * mu) +
    ((151 * e1 ** 3) / 96) * Math.sin(6 * mu) +
    ((1097 * e1 ** 4) / 512) * Math.sin(8 * mu);
  const N1 = A / Math.sqrt(1 - E2 * Math.sin(phi1) ** 2);
  const T1 = Math.tan(phi1) ** 2;
  const C1 = EP2 * Math.cos(phi1) ** 2;
  const R1 = (A * (1 - E2)) / (1 - E2 * Math.sin(phi1) ** 2) ** 1.5;
  const D = (easting - FALSE_EASTING) / (N1 * K0);
  const lat = phi1 - ((N1 * Math.tan(phi1)) / R1) * (
    D ** 2 / 2 - ((5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * EP2) * D ** 4) / 24 +
    ((61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * EP2 - 3 * C1 ** 2) * D ** 6) / 720
  );
  const lon = (
    D - ((1 + 2 * T1 + C1) * D ** 3) / 6 +
    ((5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * EP2 + 24 * T1 ** 2) * D ** 5) / 120
  ) / Math.cos(phi1);
  return [deg(lat), centralMeridian(zone) + deg(lon)];
}
