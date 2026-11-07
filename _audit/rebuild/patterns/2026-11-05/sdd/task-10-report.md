# Task 10 report — Wiring, regression, full suite and live acceptance

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, no push)
- Base: `18f4c458` — `fix(technical): واحد درصد الگوها، برچسب تب ۱۱px و برچسب‌های مشترک`
- Commit: `1f339a5c` — `feat(technical): اتصال الگوها به میزکار و رگرسیون دوقلو`
- Identity: `johnwarchief <johnwarchief@users.noreply.github.com>`
- Committed files (exactly these two):
  - `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/doubleRegression.test.ts` (new)

The pre-existing unstaged plan change and untracked audit/plan files were left untouched and uncommitted.

## What landed (R-PAT-26, controller ruling replaces the brief's step 1)

Detection runs where the series lives — `KLineChartWrapper.tsx`, right after the `bars` memo:

- one effect maps the aggregated `KLineData[]` to `EngineCandle[]` (`timestamp/open/high/low/close/volume`),
- calls `setChartCandles(engineCandles)`,
- calls `setDetectedPatterns(engineCandles.length >= 30 ? detectAllPatterns(engineCandles) : [])`,
- skips recomputation when the `bars` array identity is unchanged (`lastPatternBarsRef`).

No new fetch, no detection in `TechnicalWorkspace`. Because the effect sits on the post-aggregation `bars`, detection follows the timeframe (daily/weekly/monthly), which the live run confirms (different row sets per timeframe).

## Regression test

`model/patterns/__tests__/doubleRegression.test.ts` — the brief's double-tap stability test: 160 synthetic candles, precision and source profiles, ids compared across repeated invocations for both profiles.

## Verification (verbatim counts)

`cd frontend-v2 && npx tsc --noEmit` → clean, no output.

`npx vitest run` →

```
 Test Files  83 passed (83)
      Tests  649 passed (649)
   Start at  17:03:55
   Duration  106.23s
```

Baseline was 648 tests / 82 files; the new regression file adds 1 test / 1 file (649 / 83), zero regressions.

`npm run build` → `✓ built in 11.99s`; `dist/assets/index-BQIXYiVx.js 1,048.97 kB │ gzip: 311.53 kB`. Only the pre-existing chunk-size warning (>500 kB).

## Live acceptance

Servers (only these two were started and both were stopped afterwards; ports were free beforehand):

- backend: `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data PYTHONUNBUFFERED=1 python -m uvicorn app:app --host 127.0.0.1 --port 8110`
- dist: `cd D:/BorsTerminal-tmp/s4b-browser && PORT=7093 node serve-dist.js`
- driver: Playwright-core + Edge headless, script `D:/BorsTerminal-tmp/s4b-browser/patterns-capture.js` (outside the repo)

Coverage: رنيك، فولاد، خساپا × {1D, 1W} × {1366×768, 1920×1080} × {brass, warm} = **24 combinations, all captured** (no skipped combo, no selector error, each opened technical page → switched timeframe → opened left drawer via the collapsed-bar toggle → selected the «الگوها» tab, verified `aria-selected=true`).

Evidence: `_audit/rebuild/patterns/2026-11-05/measure.json` + `screenshots/` (48 PNGs: whole window and `kline-chart-wrapper` chart area per combination; 24 + 24).

Rows per kind (tab rows, identical across viewport and theme; the visible list is capped at 20 and no combo exceeded it):

| symbol | tf | rows | kinds |
|---|---|---|---|
| رنيك | 1D | 7 | HEAD_SHOULDERS 2, DOUBLE_TOP 4, FLAG_BULL 1 |
| رنيك | 1W | 1 | DOUBLE_BOTTOM 1 |
| فولاد | 1D | 8 | INVERSE_HEAD_SHOULDERS 1, DOUBLE_TOP 3, DOUBLE_BOTTOM 3, FLAG_BULL 1 |
| فولاد | 1W | 2 | WEDGE_RISING 1, DOUBLE_TOP 1 |
| خساپا | 1D | 1 | TRIANGLE_SYM 1 |
| خساپا | 1W | 0 | — (16 weekly bars < the 30-bar gate, expected) |

First rows (1366 brass, same at 1920/warm): e.g. فولاد 1D — «سر و شانهٔ معکوس / بازگشتی · تأییدشده / —», then «سقف دوقلو / بازگشتی · باطل‌شده / —» ×2. The «قواعد» section is present in all 24 captures; the chart canvas rendered in all 24 (6 canvases each, no blank chart).

Store-level kind counts are not reachable from the production bundle via `page.evaluate`, so per-kind numbers above come from the tab's `pattern-row-*` testids and row labels as instructed; the store was seeded with the same rows the tab renders.

### Card text and formation copy

All 24 captures show the empty-forming state: «الگوی در حال تشکیل نیست». Across these 24 series/timeframes no pattern is currently `forming` — every listed pattern is تأییدشده or باطل‌شده — so neither a formation percentage nor «نمونهٔ کافی نیست» surfaced live. This is a data outcome under the spec (the card shows the last forming pattern), not a wiring failure: rows exist and change per timeframe. The formatting copy remains covered by unit tests only.

### Console errors (acceptance criterion NOT met literally)

`pageerror`: none. However the browser console logs 404s on every technical-page load, from three endpoints that do not exist in this checkout's `app.py` (confirmed in `/openapi.json`; the technical page queries them on mount). 18 HTTP 4xx responses over 6 page loads (3 per symbol page), one deduped console message:

```
Failed to load resource: the server responded with a status of 404 (Not Found)
```

Exact URLs (all prefixed `/api/chart/<symbol>/`): `forecast?horizon=12&model=small&adjustment=3`, `edge?swing_period=5`, `indicators`. These are pre-existing and unrelated to patterns — pattern data comes from `/api/chart-db/<symbol>` (200) — but they violate "console errors must be zero" in this sanctioned environment. Recorded verbatim in `measure.json` under `consoleErrors` and `network4xx`.

## Untested / limitations

- Double-tap chart overlay not exercised live: `activeUserIndicators` is empty by default (no `enableDefaultIndicators` call), so `PatternStoryOverlay` stays inactive in a fresh session. The tab (this task's surface) was fully exercised.
- Formation percentage / «نمونهٔ کافی نیست» copy not observed live (no forming pattern in any of the 24 captures); unit-tested in Task 9.
- Cross-family overlap preference and all pattern geometry are unchanged from HEAD; this task only wires detection, so the existing 649-test suite is the coverage for them.
- One acceptance literal is unmet: zero console errors, blocked by the three missing backend routes listed above. Everything else in the brief's step 4 was captured.
