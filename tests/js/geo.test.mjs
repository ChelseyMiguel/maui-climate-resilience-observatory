// Run with:  node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";

import {
  dsciLabel, elevationColor, makeProjection, polygonsOf, sampleElevation, toCanvas,
} from "../../web/src/lib/geo.js";

const BBOX = { west: -156.45, south: 20.70, east: -156.24, north: 20.88 };

test("projection puts the box centre at the origin, north at -z, east at +x", () => {
  const p = makeProjection(BBOX);
  assert.deepEqual(p.toLocal(p.lon0, p.lat0), [0, -0]);
  const [, zNorth] = p.toLocal(p.lon0, BBOX.north);
  const [xEast] = p.toLocal(BBOX.east, p.lat0);
  assert.ok(zNorth < 0, "north must be -z");
  assert.ok(xEast > 0, "east must be +x");
});

test("projection extent matches real distances (~21.9 km x ~20.0 km)", () => {
  const p = makeProjection(BBOX);
  assert.ok(Math.abs(p.widthKm - 21.86) < 0.1, `width ${p.widthKm}`);
  assert.ok(Math.abs(p.heightKm - 20.04) < 0.1, `height ${p.heightKm}`);
});

test("bilinear sampling hits corners exactly and interpolates between them", () => {
  const meta = { bbox: { west: 0, east: 1, south: 0, north: 1 }, width: 2, height: 2 };
  const grid = [100, 200, 300, 400]; // row 0 is NORTH: NW=100 NE=200 SW=300 SE=400
  assert.equal(sampleElevation(grid, meta, 0, 1), 100);  // NW
  assert.equal(sampleElevation(grid, meta, 1, 0), 400);  // SE
  assert.equal(sampleElevation(grid, meta, 0.5, 0.5), 250);
  assert.equal(sampleElevation(grid, meta, 2, 0.5), null); // outside
});

test("canvas mapping: north-west corner is (0,0), south-east is (w,h)", () => {
  assert.deepEqual(toCanvas(BBOX, 2048, 1877, BBOX.west, BBOX.north), [0, 0]);
  const [x, y] = toCanvas(BBOX, 2048, 1877, BBOX.east, BBOX.south);
  assert.ok(Math.abs(x - 2048) < 1e-6 && Math.abs(y - 1877) < 1e-6);
});

test("elevation tint is continuous and clamps at both ends", () => {
  assert.deepEqual(elevationColor(-50), elevationColor(0));
  assert.deepEqual(elevationColor(5000), elevationColor(3100));
  const a = elevationColor(399), b = elevationColor(401);
  assert.ok(a.every((v, i) => Math.abs(v - b[i]) <= 2), "no jump across a stop");
});

test("drought bands read in order", () => {
  assert.equal(dsciLabel(0), "little or no drought");
  assert.equal(dsciLabel(135), "moderate");   // the week of the 2023 fires
  assert.equal(dsciLabel(214), "severe");     // 2022 annual mean
  assert.equal(dsciLabel(307), "extreme");    // the record peak
});

test("polygonsOf handles both geometry kinds and junk", () => {
  const ring = [[0, 0], [0, 1], [1, 1], [0, 0]];
  assert.equal(polygonsOf({ type: "Polygon", coordinates: [ring] }).length, 1);
  assert.equal(polygonsOf({ type: "MultiPolygon", coordinates: [[ring], [ring]] }).length, 2);
  assert.deepEqual(polygonsOf(null), []);
  assert.deepEqual(polygonsOf({ type: "Point", coordinates: [0, 0] }), []);
});
