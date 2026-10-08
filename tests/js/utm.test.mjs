// Run with:  node --test "tests/js/*.test.mjs"   (Node 24 strips TS types itself)
import test from "node:test";
import assert from "node:assert/strict";
import { centralMeridian, fromUtm, toUtm } from "../../web/src/lib/utm.ts";

const ZONE = 4; // EPSG:32604, UTM zone 4N — the projection of the dNDVI/dNBR rasters

test("zone 4's central meridian is 159 W", () => {
  assert.equal(centralMeridian(4), -159);
});

test("on the central meridian at the equator: easting 500 000, northing 0", () => {
  const [e, n] = toUtm(0, -159, ZONE);
  assert.ok(Math.abs(e - 500000) < 1e-6 && Math.abs(n) < 1e-6);
});

test("the raster's centre converts back to the study-area point", () => {
  // dndvi_2019_2022.tif: E 774820..777810, N 2305080..2308080 (10 m pixels),
  // exported by GEE as a 1.5 km buffer around (20.838722, -156.344856).
  const [lat, lon] = fromUtm((774820 + 777810) / 2, (2305080 + 2308080) / 2, ZONE);
  const metresOff = Math.hypot((lat - 20.838722) * 111320,
                               (lon + 156.344856) * 111320 * Math.cos((lat * Math.PI) / 180));
  assert.ok(metresOff < 15, `centre is ${metresOff.toFixed(1)} m from the study-area point`);
});

test("forward then inverse round-trips to under a millimetre across Maui", () => {
  for (const [lat, lon] of [[20.8387, -156.3449], [20.7097, -156.2533], [20.9, -156.7]]) {
    const [e, n] = toUtm(lat, lon, ZONE);
    const [lat2, lon2] = fromUtm(e, n, ZONE);
    assert.ok(Math.abs(lat - lat2) * 111320 < 0.001, `lat ${lat}`);
    assert.ok(Math.abs(lon - lon2) * 111320 < 0.001, `lon ${lon}`);
  }
});

test("1 km of easting is ~1 km on the ground near Pukalani", () => {
  const [lat1, lon1] = fromUtm(776000, 2306500, ZONE);
  const [lat2, lon2] = fromUtm(777000, 2306500, ZONE);
  const km = Math.hypot((lat2 - lat1) * 111.32,
                        (lon2 - lon1) * 111.32 * Math.cos((lat1 * Math.PI) / 180));
  // UTM scale factor here (~1.0006 that far from the central meridian) keeps it near 1.
  assert.ok(Math.abs(km - 1) < 0.002, `${km} km`);
});
