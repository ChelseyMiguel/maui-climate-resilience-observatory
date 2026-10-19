// Run with:  node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";

import { histogram, joinMonthly, monthlyDsci, toCsv } from "../../web/src/lib/series.js";

test("histogram bins, clamps the ends and skips NaN", () => {
  const b = histogram(Float32Array.from([-0.95, -0.11, -0.09, 0.0, 0.9, NaN]), -0.2, 0.2, 0.1);
  assert.deepEqual(b.map((x) => x.x0), [-0.2, -0.1, 0, 0.1]);
  assert.deepEqual(b.map((x) => x.count), [2, 1, 1, 1]);
});

test("monthly DSCI is the mean of that month's weeks", () => {
  const m = monthlyDsci([{ date: "2022-03-01", dsci: 100 }, { date: "2022-03-08", dsci: 201 }, { date: "2022-04-05", dsci: 7 }]);
  assert.equal(m.get("2022-03"), 150.5);
  assert.equal(m.get("2022-04"), 7);
});

test("join keeps every month and uses null for gaps", () => {
  const rows = joinMonthly({
    ndvi: [{ month: "2022-03", value: 0.41234567 }],
    weeks: [{ date: "2022-04-05", dsci: 7 }],
    rain: [{ month: "2022-03", chirps: 12.5, terraclimate: null, imerg: 3, era5land: NaN }],
  });
  assert.deepEqual(rows.map((r) => r.month), ["2022-03", "2022-04"]);
  assert.equal(rows[0].ndvi, 0.4123);
  assert.equal(rows[0].terraclimate_mm, null);
  assert.equal(rows[0].era5land_mm, null);
  assert.equal(rows[1].ndvi, null);
  assert.equal(toCsv(rows, ["month", "ndvi", "dsci"]), "month,ndvi,dsci\n2022-03,0.4123,\n2022-04,,7\n");
});
