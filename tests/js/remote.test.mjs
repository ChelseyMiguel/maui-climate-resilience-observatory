// Run with:  node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { cellOf, decodeLidar, median, ndviColour, worldcoverColour } from "../../web/src/lib/remote.ts";
import { toUtm } from "../../web/src/lib/utm.ts";

test("lidar points decode from the 9-byte layout to metres", () => {
  const v = new DataView(new ArrayBuffer(18));
  v.setUint16(0, 12345, true); v.setUint16(2, 678, true); v.setUint16(4, 15025, true); v.setInt16(6, -12, true); v.setUint8(8, 2);
  v.setUint16(9, 1, true); v.setUint16(11, 2, true); v.setUint16(13, 0, true); v.setInt16(15, 950, true); v.setUint8(17, 1);
  const p = decodeLidar(v, 268);
  assert.equal(p.count, 2);
  assert.ok(Math.abs(p.e[0] - 1234.5) < 1e-3 && Math.abs(p.n[0] - 67.8) < 1e-3);
  assert.ok(Math.abs(p.z[0] - 418.25) < 1e-3);
  assert.ok(Math.abs(p.hag[0] + 0.12) < 1e-6 && Math.abs(p.hag[1] - 9.5) < 1e-6);
  assert.deepEqual(Array.from(p.cls), [2, 1]);
});

test("the committed lidar file decodes to plausible heights", async () => {
  const m = JSON.parse(await readFile(new URL("../../data/research/lidar_manifest.json", import.meta.url), "utf8"));
  const buf = await readFile(new URL("../../data/research/lidar_points.bin", import.meta.url));
  const p = decodeLidar(new DataView(buf.buffer, buf.byteOffset, buf.byteLength), m.points_file.z_min_m);
  assert.equal(p.count, m.points_file.count);
  const zs = Array.from(p.z), es = Array.from(p.e);
  assert.ok(Math.min(...es.slice(0, 5000)) >= 0 && Math.max(...es.slice(0, 5000)) <= 2990);
  assert.ok(median(zs.slice(0, 20000)) > 250 && median(zs.slice(0, 20000)) < 650, "ground ~300-550 m in Pukalani");
});

test("pixel lookup in UTM and geographic grids", () => {
  const utm = { width: 299, height: 300, bounds: [774820, 2305080, 777810, 2308080], geographic: false };
  const [e, n] = toUtm(20.838722, -156.344856, 4);
  const c = cellOf(utm, 20.838722, -156.344856);
  assert.equal(c.col, Math.floor((e - 774820) / 10));
  assert.equal(c.row, Math.floor((2308080 - n) / 10));
  assert.equal(cellOf(utm, 21.5, -156.34), null);
  const geo = { width: 100, height: 50, bounds: [-156.45, 20.70, -156.24, 20.88], geographic: true };
  assert.deepEqual(cellOf(geo, 20.88 - 1e-9, -156.45), { row: 0, col: 0, i: 0 });
});

test("colour scales: NDVI ramp ends, WorldCover classes, unknown class transparent", () => {
  assert.deepEqual(ndviColour(-1), [140, 81, 10]);
  assert.deepEqual(ndviColour(1), [1, 102, 94]);
  assert.deepEqual(worldcoverColour(10), [0, 100, 0, 230]);
  assert.equal(worldcoverColour(255), null);
  assert.equal(median([3, NaN, 1, 2]), 2);
});
