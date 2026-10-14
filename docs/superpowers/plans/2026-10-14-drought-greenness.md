# Drought vs. Greenness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Show how monthly Maui County drought (DSCI) relates to Pukalani NDVI/NBR as a scatter, a lag profile and a per-year dry-season table.

**Architecture:** A stdlib-only module computes every statistic from the shipped CSVs; one endpoint serves it; one Svelte component draws it inside Region Insights. The UI never computes statistics.

**Tech Stack:** Python 3.11 `statistics`, FastAPI, Svelte 5 (legacy syntax), inline SVG.

**Spec:** `docs/superpowers/specs/2026-10-14-drought-greenness-design.md`

## Global Constraints

- No fabricated data: every number comes from `data/research/*.csv` via the existing loaders.
- No causal/forecast/"risk" wording. No mention of r = -0.47 in the UI.
- NDVI/NBR months with the -9999 sentinel are absent, never zero.
- Theme tokens only (`--forest --teal --amber --fire --muted --card --line`).
- After front-end changes: `cd web && npm run check && npm test && npm run build`, commit `app/static/site/`.

## Review Focus

- A month present in one series but not the other → dropped from pairs, `n` reflects it.
- Fewer than 3 pairs, or zero variance → `r` is `None`, never NaN/crash (JSON can't carry NaN).
- Lag pushes a month before the first DSCI month → that pair is skipped.
- Data file missing → endpoint 503 with the fix, UI shows an empty state, no chart of nothing.
- Dry-season year with <3 usable months → still listed with its `months` count so the reader can discount it.

---

### Task 1: Statistics module

**Files:** Create `lib/relationships.py`; Test `tests/unit/test_relationships.py`

**Produces:**
- `monthly_dsci() -> dict[str, float]` — `YYYY-MM` → mean of that month's weekly DSCI.
- `pair_months(x: Mapping[str, float], y: Mapping[str, float], lag: int = 0) -> list[tuple[str, float, float]]` — `(month_of_y, x[month_of_y - lag], y[month_of_y])`, sorted, only where both exist.
- `correlation(pairs) -> dict` — `{"r": float|None, "n": int, "slope": float|None, "intercept": float|None}`.
- `drought_greenness() -> dict` (lru_cached) — `{"available": bool, "indices": {"ndvi"|"nbr": {"points": [{"month","year","dsci","value"}], "fit": correlation-dict, "lags": [{"lag","r","n"}] for lag 0..6}}, "dry_season": [{"year","months","dsci","ndvi","nbr"}], "notes": [str]}`.

- [ ] **Step 1: Failing tests** — `test_pair_months_drops_unmatched_and_applies_lag`, `test_correlation_perfect_line` (r == 1.0, slope 2, intercept 1), `test_correlation_degenerate_is_none` (constant y; n < 3), `test_monthly_dsci_averages_weeks`, and pinned real-data tests: lag-0 NDVI `r` ≈ -0.690 (±0.002) with `n == 61`; lag-0 NBR ≈ -0.767; NDVI lag-3 `abs(r) < 0.05`; dry-season 2022 has the highest `dsci` and lowest `ndvi` of all years.
- [ ] **Step 2:** `.venv/bin/python -m pytest tests/unit/test_relationships.py -q` → FAIL (module missing).
- [ ] **Step 3:** Implement with `statistics.correlation` / `linear_regression`, catching `StatisticsError`. Dry-season = months 5–9 present in both series.
- [ ] **Step 4:** Run → PASS. `ruff check lib tests`.
- [ ] **Step 5:** Commit.

### Task 2: Endpoint

**Files:** Modify `app/api/routes/layers.py`; Test `tests/unit/test_relationships.py`

**Produces:** `GET /api/layers/drought-greenness` → `drought_greenness()` payload; 503 `detail` naming the missing CSV when `available` is false.

- [ ] **Step 1:** Tests `test_endpoint_matches_module` and `test_endpoint_503_when_series_missing` (monkeypatch `browning.NDVI_PATH` and clear caches).
- [ ] **Step 2:** Run → FAIL. **Step 3:** add the route next to `/drought`. **Step 4:** PASS. **Step 5:** Commit.

### Task 3: Component

**Files:** Create `web/src/components/DroughtGreenness.svelte`; Modify `web/src/lib/adapters.ts`, `web/src/lib/types.ts`, `web/src/pages/Insights.svelte`

**Interfaces:**
- Consumes: `/api/layers/drought-greenness` (Task 2).
- Produces: `droughtGreenness(): Promise<DroughtGreenness>` in `adapters.ts`; `<DroughtGreenness />` with no props, rendered inside `{#if veg.available}` in Insights.

- [ ] **Step 1:** Types + adapter (snake_case → camelCase like `regionInsights`).
- [ ] **Step 2:** Component: NDVI/NBR toggle; scatter (2022 filled amber r=6 + ring, 2023 hollow teal, others muted grey r=4.5, 2px surface ring, regression line, hover tooltip, r and n in the readout); lag bars with zero baseline; dry-season table with inline bars; table toggle; CSV download; empty/error state; caveat paragraph.
- [ ] **Step 3:** `npm run check && npm test` → 0 errors.
- [ ] **Step 4:** Commit.

### Task 4: Verify in a browser, document, ship

- [ ] **Step 1:** `npm run build`; start server; Playwright loads `/insights`, asserts the card renders, 61 scatter dots, 7 lag bars, no console errors; screenshot at 1280 and 390 px; read the screenshots.
- [ ] **Step 2:** Add the open-item section to `docs/evidence-claims.md` and a Methods/Sources note if the page lists analyses.
- [ ] **Step 3:** Full verification (`ruff`, `pytest`, `npm run check/test/build`, committed build identical), commit, push.
