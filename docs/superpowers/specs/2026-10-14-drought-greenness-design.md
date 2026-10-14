# Drought vs. Greenness explorer — design

Written without a Q&A round: the author asked for "your educated guess" and to
skip questions. Everything below is a call made on their behalf; the author
should read it as proposals, not agreements.

## Why

The project's central claim is that the 2022 drought preceded unusually dry
vegetation going into the August 2023 fires. The site charts drought and
vegetation separately but never shows how they relate, so the claim is made in
prose only. A judge should be able to *see* it, and see how much it does and
does not support.

## What

A card on **Region Insights → Pukalani** (the only region with a vegetation
series), built from data already shipped in `data/research/`:

1. **Scatter** — one dot per month (Dec 2018–Dec 2023): x = county-mean DSCI
   that month, y = NDVI or NBR (toggle). 2022 dots are emphasised, 2023 dots are
   hollow, other years are muted. Least-squares line, Pearson r and n shown.
2. **Lag profile** — r between DSCI and the index `k` months later, k = 0…6.
3. **Dry-season by year** — May–Sep mean DSCI and mean index per year, with the
   number of months behind each.
4. Data table + CSV download, like the other cards.

## Non-goals / anti-goals

- No causal language, no forecast, no "risk". It is a correlation of two
  coarse series (county drought vs. a 1.5 km study area).
- Must not display or imply the manuscript's r = -0.47. See below.
- No new runtime dependencies.

## The open number (author must resolve before the video)

`docs/evidence-claims.md` and the brief cite DSCI–NDVI r = -0.47. From the
shipped files the same pairing gives r = -0.69 (n = 61, monthly, lag 0);
removing the month-of-year cycle gives -0.64; May–Sep months only gives -0.76
(n = 25). No variant reproduces -0.47, so the manuscript used a different
pipeline (unknown to this repo). The app therefore states only what it computes,
from the series on the page, and the discrepancy is logged in
`docs/evidence-claims.md` as an open item.

## Constraints

Python ≥ 3.11 stdlib only for the maths (`statistics.correlation`,
`linear_regression`). Svelte 5 legacy syntax, no chart library. Theme tokens
from `web/src/app.css`. All numbers computed server-side and covered by tests;
months without imagery (NDVI -9999) are dropped, never zero-filled.

## Left to the builder

Exact SVG layout, axis ticks, copy wording within the caveats above.
