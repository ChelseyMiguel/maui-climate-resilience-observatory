// Pure helpers for the Map Explorer data panel: binning, joining the study-area
// series by month, and export. No DOM, so tests/js can exercise them directly.

/** Pixel counts in fixed-width bins over [lo, hi); values outside are clamped into the end bins. */
export function histogram(values, lo = -0.6, hi = 0.4, width = 0.02) {
  const n = Math.round((hi - lo) / width);
  const bins = Array.from({ length: n }, (_, i) => ({ x0: +(lo + i * width).toFixed(4), count: 0 }));
  for (const v of values) {
    if (Number.isNaN(v)) continue;
    bins[Math.max(0, Math.min(n - 1, Math.floor((v - lo) / width)))].count++;
  }
  return bins;
}

/** Mean DSCI per calendar month from the weekly U.S. Drought Monitor series. */
export function monthlyDsci(weeks) {
  const acc = new Map();
  for (const w of weeks) {
    const m = w.date.slice(0, 7);
    const a = acc.get(m) ?? [0, 0];
    acc.set(m, [a[0] + w.dsci, a[1] + 1]);
  }
  return new Map([...acc].map(([m, [s, n]]) => [m, Math.round((s / n) * 10) / 10]));
}

export const COLUMNS = ['month', 'ndvi', 'nbr', 'dsci', 'chirps_mm', 'terraclimate_mm', 'imerg_mm', 'era5land_mm'];

/** One row per month across every source; a source with no value that month gives null. */
export function joinMonthly({ ndvi = [], nbr = [], weeks = [], rain = [] }) {
  const dsci = monthlyDsci(weeks);
  const byMonth = (pts) => new Map(pts.map((p) => [p.month, p.value]));
  const nd = byMonth(ndvi), nb = byMonth(nbr);
  const rn = new Map(rain.map((r) => [r.month, r]));
  const months = [...new Set([...nd.keys(), ...nb.keys(), ...dsci.keys(), ...rn.keys()])].sort();
  const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? Math.round(v * 10000) / 10000 : null);
  return months.map((m) => ({
    month: m, ndvi: num(nd.get(m)), nbr: num(nb.get(m)), dsci: num(dsci.get(m)),
    chirps_mm: num(rn.get(m)?.chirps), terraclimate_mm: num(rn.get(m)?.terraclimate),
    imerg_mm: num(rn.get(m)?.imerg), era5land_mm: num(rn.get(m)?.era5land),
  }));
}

export function toCsv(rows, columns = COLUMNS) {
  const cell = (v) => (v === null || v === undefined ? '' : String(v));
  return [columns.join(','), ...rows.map((r) => columns.map((c) => cell(r[c])).join(','))].join('\n') + '\n';
}
