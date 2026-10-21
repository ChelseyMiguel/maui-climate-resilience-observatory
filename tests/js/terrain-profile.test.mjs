// Run with:  node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";

import { createSampler, decode, pixelMetres, tileXY } from "../../web/src/lib/terrarium.js";
import { distanceM, samplePoints, slopeStats } from "../../web/src/lib/profile.js";

test("terrarium decoding matches the published formula", () => {
  assert.equal(decode(128, 0, 0), 0);
  assert.equal(decode(131, 232, 128), 1000.5);
});

test("tile maths: Pukalani at z14 and the ~9 m pixel", () => {
  const [x, y] = tileXY(-156.344856, 20.838722, 14);
  assert.equal(Math.floor(x), 1076);
  assert.equal(Math.floor(y), 7221);   // (1 - asinh(tan φ)/π)/2 · 2^14 = 7221.99
  assert.ok(Math.abs(pixelMetres(20.84, 14) - 8.92) < 0.05);
});

test("sampler interpolates bilinearly and caches tiles", async () => {
  let loads = 0;
  // A synthetic tile whose elevation equals the pixel column: a 1 m/px ramp.
  const load = async () => { loads++; return Float32Array.from({ length: 65536 }, (_, i) => i % 256); };
  const s = createSampler({ zoom: 14, load });
  const [fx] = tileXY(-156.344856, 20.838722, 14);
  const z = await s.at(-156.344856, 20.838722);
  const expected = ((fx * 256 - 0.5) % 256 + 256) % 256;
  assert.ok(Math.abs(z - expected) < 1e-6);
  await s.at(-156.344856, 20.838722);
  assert.ok(loads <= 4);
});

test("a failed tile rejects and is retried next time, not cached", async () => {
  let n = 0;
  const s = createSampler({ load: async () => { n++; throw new Error("offline"); } });
  await assert.rejects(s.at(-156.34, 20.84), /offline/);
  await assert.rejects(s.at(-156.34, 20.84), /offline/);
  assert.ok(n >= 2);
});

test("profile sampling and slope statistics", () => {
  const a = [-156.35, 20.83], b = [-156.33, 20.85];
  const d = distanceM(a, b);
  assert.ok(Math.abs(d - 3036) < 15, `distance ${d}`);
  const pts = samplePoints(a, b, 4);
  assert.equal(pts.length, 5);
  assert.equal(pts[4].d, d);
  const s = slopeStats([{ d: 0, z: 100 }, { d: 100, z: 110 }, { d: 200, z: 105 }, { d: 300, z: NaN }]);
  assert.deepEqual([s.rise, s.fall, s.netChange, s.min, s.max], [10, 5, 5, 100, 110]);
  assert.equal(s.maxSlopePct, 10);
  assert.equal(slopeStats([{ d: 0, z: NaN }]), null);
});
