// Statistics for the Analysis workspace. Pure functions, mirrored on
// lib/relationships.py so the browser reproduces the study's published numbers
// (tests/js/analysis.test.mjs recomputes r = -0.467 from the committed CSVs).

/** `YYYY-MM` minus `back` months. */
export function shiftMonth(month, back) {
  const total = +month.slice(0, 4) * 12 + +month.slice(5, 7) - 1 - back;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, '0')}`;
}

/** Pearson r and least-squares line; nulls when undefined (n < 3 or no variance). */
export function pearson(xs, ys) {
  const n = xs.length;
  if (n < 3) return { r: null, n, slope: null, intercept: null };
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (!sxx || !syy) return { r: null, n, slope: null, intercept: null };
  const slope = sxy / sxx;
  return { r: sxy / Math.sqrt(sxx * syy), n, slope, intercept: my - slope * mx };
}

/** Pair each y month with the x value `lag` months earlier (as pair_months). */
export function lagPairs(xByMonth, yByMonth, lag = 0) {
  const out = [];
  for (const month of [...yByMonth.keys()].sort()) {
    const src = shiftMonth(month, lag);
    if (xByMonth.has(src) && yByMonth.get(month) !== null && xByMonth.get(src) !== null) {
      out.push({ month, x: xByMonth.get(src), y: yByMonth.get(month) });
    }
  }
  return out;
}

/** Anomaly z-score per month against a calendar-month climatology over
 * [y0, y1] (the study: 2019-2021, sample SD). Months whose calendar month has
 * fewer than two base values, or zero spread, get null. */
export function climatologyZ(byMonth, [y0, y1] = [2019, 2021]) {
  const base = new Map();
  for (const [m, v] of byMonth) {
    const y = +m.slice(0, 4);
    if (v === null || y < y0 || y > y1) continue;
    const k = m.slice(5, 7);
    base.set(k, [...(base.get(k) ?? []), v]);
  }
  const stats = new Map([...base].map(([k, vs]) => {
    if (vs.length < 2) return [k, null];
    const mean = vs.reduce((a, b) => a + b, 0) / vs.length;
    const sd = Math.sqrt(vs.reduce((a, v) => a + (v - mean) ** 2, 0) / (vs.length - 1));
    return [k, sd > 0 ? { mean, sd } : null];
  }));
  return new Map([...byMonth].map(([m, v]) => {
    const s = stats.get(m.slice(5, 7));
    return [m, v === null || !s ? null : (v - s.mean) / s.sd];
  }));
}

/** Sum over the `k` months ending at each month; null unless all k exist. */
export function rollingSum(byMonth, k) {
  return new Map([...byMonth.keys()].map((m) => {
    let s = 0;
    for (let i = 0; i < k; i++) {
      const v = byMonth.get(shiftMonth(m, i));
      if (v === null || v === undefined) return [m, null];
      s += v;
    }
    return [m, s];
  }));
}

/** Departure from the all-years mean of the same calendar month. */
export function monthlyAnomaly(byMonth) {
  const acc = new Map();
  for (const [m, v] of byMonth) if (v !== null) acc.set(m.slice(5, 7), [...(acc.get(m.slice(5, 7)) ?? []), v]);
  const mean = new Map([...acc].map(([k, vs]) => [k, vs.reduce((a, b) => a + b, 0) / vs.length]));
  return new Map([...byMonth].map(([m, v]) => [m, v === null ? null : v - mean.get(m.slice(5, 7))]));
}

/** Per-bin count, median y and share of y below `threshold`, for x in [edges[i], edges[i+1]). */
export function binStats(xs, ys, edges, threshold) {
  const bins = edges.slice(0, -1).map((lo, i) => ({ lo, hi: edges[i + 1], ys: [] }));
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i], y = ys[i];
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const b = bins.find((bb) => x >= bb.lo && x < bb.hi);
    if (b) b.ys.push(y);
  }
  return bins.map(({ lo, hi, ys: v }) => {
    const s = Float64Array.from(v).sort();
    const median = s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null;
    return { lo, hi, n: s.length, median, shareBelow: s.length ? v.filter((y) => y < Math.fround(threshold)).length / s.length : null };
  });
}

/** Share of valid pixels below `threshold` in square blocks of `block` pixels.
 * Blocks with under half their pixels valid are null (edge of the AOI circle). */
export function blockShare(values, width, height, block, threshold) {
  const t = Math.fround(threshold);
  const cols = Math.ceil(width / block), rows = Math.ceil(height / block);
  const z = Array.from({ length: rows }, () => new Array(cols).fill(null));
  for (let br = 0; br < rows; br++) {
    for (let bc = 0; bc < cols; bc++) {
      let valid = 0, below = 0, cells = 0;
      for (let r = br * block; r < Math.min(height, (br + 1) * block); r++) {
        for (let c = bc * block; c < Math.min(width, (bc + 1) * block); c++) {
          cells++;
          const v = values[r * width + c];
          if (Number.isNaN(v)) continue;
          valid++;
          if (v < t) below++;
        }
      }
      if (valid * 2 >= cells) z[br][bc] = below / valid;
    }
  }
  return { cols, rows, z };
}
