---
name: bors-live-ui-check
description: Legacy Jev-browser live UI check, retained for fallback and comparison during the requested Jev-to-Laya migration. Live browser evidence remains required after frontend changes, but use verified Laya/Playwright/CDP once configured; do not treat this Jev-specific harness as the permanent canonical decision layer.
---

# Bors live UI check (legacy Jev harness)

> **Status as of 2026-10-10:** Jev-to-Laya migration was requested, but is not yet proved. This file documents the legacy Jev harness. Continue requiring live browser evidence, but use the verified Laya/Playwright/CDP path when available. Until then, run a real browser check with the tools that actually work and mark Laya migration `UNVERIFIED`.

## Overview

One pipeline: build, start the right backend, run a real browser check with the available harness, then inspect its output before believing anything. If the legacy Jev harness is used, its environment requirements and failure modes below still apply.

## Step 1 - Fresh bundle first

Run `npm run build` before checking. The harness serves `dist`, so a stale bundle
reproduces bugs that are already fixed in source and sends the whole session
investigating a bug that does not exist. If a live browser error appears, compare the
mtime of `dist/assets` against the source file before treating the error as real.

## Step 2 - Discover the backend port, do not assume it

Read the port from the repo at this moment, not from memory:

- `vite.config` - the `server.proxy` target is the port the frontend actually calls.
- The uvicorn startup log of whichever backend is running.

Ports documented on this machine, all of them real at some point:

| Port | What it was |
|---|---|
| 8001 | the `server.proxy` target; a hand-started dev backend must bind it (`python -m uvicorn app:app --host 127.0.0.1 --port 8001`) |
| 8000 | the default bind of `app.py`, i.e. the installed build's own server - checking here proves shipped behaviour, checking source-build ports proves source behaviour |
| 8003 | reported once for a source backend; **not verified in the session it came from** |
| 8010 | the port the canvas pixel probe served `dist` from |

Wrong-port symptom, and the reason this step exists: every `/api/*` comes back as 500
through the proxy (or hangs), the page renders its shells, and the harness reports the
data-driven parts as absent. That is a missing backend, not a broken component. Report
separately which build the evidence came from: installed `8000`, or source.

## Step 3 - Two environment values are mandatory

```bash
MSYS_NO_PATHCONV=1 \
JEV_CHROME=$LOCALAPPDATA/ms-playwright/chromium-<build>/chrome-win64/chrome.exe \
node tools/jev_ui_check.mts --route '#/market'
```

- `JEV_CHROME` is required. Without it `ensureChromium()` tries to download and dies with
  `Automatic Chromium setup failed or timed out`; the browser is already cached. The
  folder is `chrome-win64`, **not** `chrome-win`; a wrong path gives `executable doesn't
  exist` instead of the download error, which is how to tell a typo from a missing value.
- `MSYS_NO_PATHCONV=1` is required because the shell here is Git Bash. Without it,
  `--route '#/market'` arrives as `#C:/Program Files/Git/market`, the SPA lands inside its
  ErrorBoundary, and every testid reads `null`.
- The router is hash-based. `#/market`, `#/technical`, `#/master`,
  `#/fundamental/<symbol>`, `#/strategy-tree`. A path-style URL renders a *different
  working page* with no error and no console output, so a path-style negative result is
  always invalid.

## Step 4 - Read the JSON before drawing any conclusion

Inspect `href` and `bodyText` in the harness output first, every run, before reading a
single testid:

- `href` shows what the browser was actually given - this is where a mangled route
  becomes visible.
- `bodyText` containing `Unexpected Application Error` means **the harness broke, not the
  component**. On that body, `null` testids carry no information about the feature.
- Only after both look right does an absent testid mean anything about the app.

## Step 5 - Second clicks and tabs

**Marked unverified.** The claims in this section come from a session summary, not from
evidence read in that session. Confirm them on the first run; if the first run
contradicts one, discard it as a rejected guess rather than routing around the
contradiction.

`tools/jev_ui_check.mts` covers a single initial render. For a second click, a tab switch,
or any before/after comparison, use Playwright from Python
(`.../pythoncore-3.14-64/python.exe`) instead:

- Measure the panel's height before and after the click and compare the two numbers; a
  testid being present does not prove a panel opened.
- `:has-text()` is not valid inside `page.evaluate` - it is a Playwright selector, not a
  CSS one, and it throws there.
- Tabs expose `role=tab`, not `button`, so a `button`-based tab query finds nothing while
  the tab is on screen.

## Error -> cause -> fix

| Symptom | Real cause | Fix |
|---|---|---|
| `Automatic Chromium setup failed or timed out` | `JEV_CHROME` unset, harness tries to download | set `JEV_CHROME` to the cached `chrome-win64/chrome.exe` |
| `executable doesn't exist` | `JEV_CHROME` set but wrong, usually `chrome-win` | correct the folder to `chrome-win64` |
| Every testid `null`, `bodyText` = `Unexpected Application Error` | Git Bash rewrote `#/market` | prefix `MSYS_NO_PATHCONV=1` |
| Board page renders, nothing errors, expected element absent | path-style URL against a hash router | use `#/...` |
| All `/api/*` are 500, 46 console errors on a fresh page | no backend on the proxy's port | discover the port (step 2), bind the backend there |
| A bug you already fixed is reported live | stale `dist` | `npm run build` first |
| Tab or panel found not to respond | harness ran one render only, or wrong role selector | step 5 |

## Before saying it is verified

- State which build the evidence came from (installed vs source) and the port used.
- State that `href` and `bodyText` were checked, not assumed.
- Name anything left unproven - the unverified section above, the wheel-zoom path, or any
  screen not opened.
- The owner's rule is that both jev tools run per unit of work: this covers the browser
  half only; the judgment half is `tools/pilot_ctl.py arbitrate`, and no source code may
  be sent to that service.
