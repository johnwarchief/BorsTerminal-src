---
name: canvas-chart-live-pixel-check
description: Live pixel verification of canvas-rendered charts (klinecharts, ECharts, TradingView-style) via Playwright/jev-browser. Use when a change to a canvas chart's scale, axis mapping, overlays, crosshair, or text must be proven visible on screen, when unit tests are green but the chart looks wrong to a user, or when a "nothing moved / scale held" claim needs evidence. DOM testids, store assertions, and vitest prove data was written, not that pixels changed.
---

# Canvas Chart Live Pixel Check

## Overview

Prove chart behavior in actual pixels. Canvas charts paint outside the DOM, so every DOM-level check is indirect evidence; this skill composites the canvas layers, counts colored ink, and uses full-width level lines as the price→pixel map, always with a positive control in the same run.

## Prerequisites (do these first, in order)

1. Rebuild the bundle before probing (`npm run build` or project equivalent). The served port delivers `dist/`, so a stale bundle reproduces already-fixed bugs and you will "discover" a bug that no longer exists. If the harness reports an error, compare bundle and source mtimes before investigating.
2. Serve the app with the correct backend port and use the real route format (e.g. hash-router URLs like `/#/technical`; a path-style URL can render a different page with no error at all).
3. For jev-browser-style harnesses on Windows/Git Bash: point `JEV_CHROME` at the cached `chrome-win64/chrome.exe`, and prefix commands with `MSYS_NO_PATHCONV=1` so `#/route` arguments survive. A mangled URL shows up as "every element absent" — check `href` and `bodyText` in the harness JSON before concluding anything about the app.
4. Run the probe at two viewports (e.g. 1366×900 and 1920×1080). A bad metric was once exposed only at the wider size.

## Core probe: composite layers, count colored ink

A chart pane is usually several stacked `<canvas>` elements. Composite them into one offscreen surface and count saturated pixels per row and per column:

```js
// Run inside page.evaluate. paneSel scopes to one chart pane.
const pane = document.querySelector(paneSel);
const canvases = [...pane.querySelectorAll('canvas')];
const rect = pane.getBoundingClientRect();
const off = document.createElement('canvas');
off.width = Math.round(rect.width); off.height = Math.round(rect.height);
const ctx = off.getContext('2d', { willReadFrequently: true });
for (const c of canvases) ctx.drawImage(c, 0, 0, off.width, off.height);
const { data } = ctx.getImageData(0, 0, off.width, off.height);
const inkRow = new Array(off.height).fill(0);
for (let y = 0; y < off.height; y++) {
  for (let x = 0; x < off.width; x++) {
    const i = (y * off.width + x) * 4;
    const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    // "colored ink": saturated enough and not background-white
    if (max > 60 && (max - min) > 40) inkRow[y]++;
  }
}
```

Calibrate the saturation thresholds per theme (green/red candles on a dark vs light background differ); the principle is count *chromatic* ink, excluding gray gridlines and anti-aliased background.

## Metric rules — three known traps

1. **Do NOT use candle content extent as the vertical scale.** The first/last inked row depends on which candles are visible; a horizontal pan brings in different candles and moves those rows even when the price→pixel mapping is perfectly held. This produced a false "scale jumped" report at 1920×1080 while the guard was working.
2. **Use full-width colored rows as the price→pixel map.** Fixed-price horizontal lines (level lines, band edges) paint one chromatic row across the whole pane. Collect rows whose colored-ink count exceeds ~90% of pane width: that row set *is* the axis mapping. Identical row indices before and after a pan/drag prove the scale held; changed indices measure the rescale.
3. **Crosshair, tooltip, and OHLC text live on a separate canvas layer** that is not stacked at the pane's rect — compositing the pane reports zero text pixels and a corner-text counter reads 0 forever. Prove text-layer behavior with real page screenshots of the region (e.g. idle vs hover: `probe_idle.png` clean, `probe_hover.png` shows the text), not with composited counts.

## Positive control — mandatory in every run

Any "nothing moved" conclusion requires a positive control in the same run, otherwise you have proven nothing about the sensor:

- Short drag (~50px) within the price pane: expected NOT to change the full-width row set (`scaleHeld: true`).
- Deliberately long drag (~700px+): expected to rescale (`scaleRechosen: true`). If this also shows "no change", the probe is blind, not the chart immune.

Synthetic wheel events often do not reach the chart library's zoom handler. If a control path fails to act, report that path explicitly as "not pixel-verified, covered only by unit tests" — do not silently drop it.

## Screenshot hygiene

- Close any open modal/dialog before screenshotting: the blurred backdrop washes out the whole shot and it looks like the chart broke.
- Locate buttons and toggles within their container (scoped `getByRole`), never globally: toolbars reuse the same accessible names (e.g. two "settings" buttons) and a global query hits the wrong one.

## When pixels say "wrong" but unit tests say "green"

A sticky/incorrect axis scale once passed every unit test. To localize it: inject a temporary `console.debug` inside the scale/price→pixel mapping that logs the actual computed values, run the probe while capturing console output, read the values, fix, then remove the debug lines. Never trust a store assertion as proof of what the axis actually did.

## Evidence and reporting

- Commit the probe's JSON report as the evidence artifact (row sets, scaleHeld/scaleRechosen flags, viewport sizes, console excerpts).
- PNGs under audit directories are often gitignored: describe what each screenshot showed in the report text; do not rely on attaching images.
- State which checks ran against the shipped/installed build versus only the dev bundle.

## Workflow checklist

1. Rebuild bundle → start app with correct backend → open correct route at viewport 1.
2. Baseline probe: record full-width row set.
3. Apply the interaction under test (pan, data update, overlay toggle).
4. Re-probe: compare row sets; run short-drag and long-drag controls.
5. For text/crosshair claims: idle + hover screenshots of the region, after closing modals.
6. Repeat at viewport 2.
7. Commit JSON report; list any path left unverified.