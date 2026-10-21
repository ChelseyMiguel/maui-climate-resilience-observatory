// Run with:  node --test "tests/js/*.test.mjs"
// Scientific baseline: the study's dNDVI raster must give 30,037 of 70,280 valid
// pixels below -0.10 (42.7%), read straight from the committed GeoTIFF.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fromArrayBuffer } from "../../web/node_modules/geotiff/dist-module/geotiff.js";

import { classCounts, classify, countBelow, hectares, RESEARCH_THRESHOLD } from "../../web/src/lib/threshold.js";
import { fromUtm } from "../../web/src/lib/utm.ts";

async function raster(name) {
  const buf = await readFile(new URL(`../../data/research/${name}_2019_2022.tif`, import.meta.url));
  const img = await (await fromArrayBuffer(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength))).getImage();
  return { img, values: Float32Array.from((await img.readRasters())[0]) };
}

test("dNDVI < -0.10 reproduces the documented 30,037 of 70,280 pixels (42.7%)", async () => {
  const { img, values } = await raster("dndvi");
  const { valid, below, share } = countBelow(values, RESEARCH_THRESHOLD);
  assert.equal(valid, 70280);
  assert.equal(below, 30037);
  assert.equal((share * 100).toFixed(1), "42.7");
  assert.equal(Math.abs(img.getResolution()[0]), 10);
  assert.equal(hectares(below, 10).toFixed(1), "300.4");
});

test("the three display classes partition every valid pixel", async () => {
  const { values } = await raster("dndvi");
  const c = classCounts(values, -0.1);
  assert.equal(c.browning, 30037);
  assert.equal(c.browning + c.stable + c.greening, 70280);
  assert.equal(classify(NaN, -0.1), null);
  assert.equal(classify(-0.1, -0.1), "stable");   // strict: exactly -0.10 is not browned
});

test("counts fall monotonically as the threshold is lowered", async () => {
  const { values } = await raster("dndvi");
  let prev = Infinity;
  for (const t of [0, -0.05, -0.1, -0.2, -0.3, -0.4]) {
    const { below } = countBelow(values, t);
    assert.ok(below <= prev, `t=${t}`);
    prev = below;
  }
});

test("raster alignment: the grid centre lands within one pixel of the study-area centre", async () => {
  const { img } = await raster("dndvi");
  const [w, s, e, n] = img.getBoundingBox();
  const [lat, lon] = fromUtm((w + e) / 2, (s + n) / 2, 4);
  const dy = (lat - 20.838722) * 111320, dx = (lon - -156.344856) * 111320 * Math.cos((lat * Math.PI) / 180);
  assert.ok(Math.hypot(dx, dy) < 10, `offset ${Math.hypot(dx, dy).toFixed(1)} m`);
});
