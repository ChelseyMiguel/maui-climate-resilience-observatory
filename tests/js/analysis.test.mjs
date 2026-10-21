// Run with:  node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { binStats, blockShare, climatologyZ, lagPairs, monthlyAnomaly, pearson, rollingSum, shiftMonth } from "../../web/src/lib/analysis.js";

const csv = async (name) => (await readFile(new URL(`../../data/research/${name}`, import.meta.url), "utf8"))
  .trim().split("\n").slice(1).map((l) => l.split(","));

test("study result: monthly DSCI vs NDVI anomaly z (2019-21) gives r = -0.467, n = 61", async () => {
  const ndvi = new Map((await csv("pukalani_ndvi_monthly.csv"))
    .filter(([, v]) => +v !== -9999).map(([d, v]) => [d.slice(0, 7), +v]));
  const weeks = new Map();
  for (const [d, v] of await csv("maui_dsci_weekly.csv")) weeks.set(d.slice(0, 7), [...(weeks.get(d.slice(0, 7)) ?? []), +v]);
  const dsci = new Map([...weeks].map(([m, vs]) => [m, vs.reduce((a, b) => a + b, 0) / vs.length]));
  const z = climatologyZ(ndvi, [2019, 2021]);
  const pairs = lagPairs(dsci, z, 0);
  const { r, n } = pearson(pairs.map((p) => p.x), pairs.map((p) => p.y));
  assert.equal(n, 61);
  assert.equal(r.toFixed(3), "-0.467");
  assert.equal(z.get("2022-03").toFixed(1), "-7.4");
  assert.equal(z.get("2022-04").toFixed(1), "-11.3");
});

test("pearson, shift and lag pairing", () => {
  assert.equal(shiftMonth("2022-01", 1), "2021-12");
  assert.equal(shiftMonth("2022-03", 14), "2021-01");
  assert.equal(pearson([1, 2, 3, 4], [2, 4, 6, 8]).r, 1);
  assert.equal(pearson([1, 2], [1, 2]).r, null);
  assert.equal(pearson([1, 1, 1], [1, 2, 3]).r, null);
  const x = new Map([["2022-01", 10], ["2022-02", 20]]), y = new Map([["2022-02", 1], ["2022-03", 2]]);
  assert.deepEqual(lagPairs(x, y, 1), [{ month: "2022-02", x: 10, y: 1 }, { month: "2022-03", x: 20, y: 2 }]);
});

test("rolling sums need every month; anomalies are per calendar month", () => {
  const m = new Map([["2022-01", 1], ["2022-02", 2], ["2022-03", null], ["2022-04", 4], ["2023-01", 3]]);
  const r = rollingSum(m, 2);
  assert.equal(r.get("2022-02"), 3);
  assert.equal(r.get("2022-04"), null);
  assert.equal(monthlyAnomaly(m).get("2023-01"), 1);   // mean of Jan = 2
});

test("bin statistics and block shares", () => {
  const s = binStats([0, 5, 10, 15, 25], [-0.2, 0, -0.3, 0.1, 9], [0, 10, 20], -0.1);
  assert.deepEqual(s.map((b) => b.n), [2, 2]);
  assert.equal(s[0].median, -0.1);
  assert.equal(s[0].shareBelow, 0.5);
  const v = Float32Array.from([-0.2, 0.0, NaN, NaN, -0.3, -0.2, NaN, NaN]);
  const g = blockShare(v, 4, 2, 2, -0.1);
  assert.deepEqual(g.z, [[0.75, null]]);
});
