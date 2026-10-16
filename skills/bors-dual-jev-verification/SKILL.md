---
name: bors-dual-jev-verification
description: Legacy Jev-specific verification workflow retained for fallback and migration comparison. On 2026-10-10 the owner requested Jev-to-Laya migration; do not treat this skill as the canonical mandatory workflow until the actual Qoder/Laya integration is verified.
---

# Bors dual-jev verification (legacy fallback)

> **Status as of 2026-10-10:** the owner requested replacing Jev-based decisions/browser checks with Laya. This file documents the previous Jev workflow and must not override that newer direction. Keep it for fallback and comparison until Laya passes equivalent end-to-end tests; do not claim migration is complete from this note alone.

## Overview

For current work, live UI verification is still required, but Jev is no longer the automatic canonical decision layer. Prefer the verified Laya integration once available; until then use the existing Playwright/CDP browser checks and mark the Laya migration `UNVERIFIED`. Use the Jev steps below only when explicitly validating the legacy path or comparing a migration.

## Preconditions

- Repo root: wherever this clone lives — resolve it with `git rev-parse --show-toplevel`.
  The path has moved between machines before, so never assume it.
- Shell is Git Bash on Windows: give Windows paths as `/c/...`, and set `MSYS_NO_PATHCONV=1`
  for commands whose arguments look like flags (`taskkill /PID`).
- Dev server on 8002 running the current code:
  `PYTHONIOENCODING=utf-8 py -3.14 -m uvicorn app:app --host 127.0.0.1 --port 8002`
- The installed app holds port 8001 and is what users see; prove the release delta there
  separately (`tools/inapp_update.py --apply`).
- `TYPESAFE_API_KEY` must be in the environment or `pilot_ctl.py` exits immediately.

## Step 1 - prose arbiter (jev-pilot)

```
PYTHONIOENCODING=utf-8 py -3.14 tools/pilot_ctl.py arbitrate \
  --context "وضعیت، فقط نثر" \
  --option "a=شرح گزینهٔ اول" --option "b=شرح گزینهٔ دوم"
```

Rules (enforced by the tool, not by convention):

- **Prose only.** `_refuse_if_code` rejects source code and over-long strings; no source
  code may ever be sent to the service.
- At least two `--option KEY=PROSE` pairs are required.
- Output is one JSON line: `{"winner", "confidence", "probabilities", "risk"}`.
- Sibling modes `stuck` and `guard` share the same no-code gate.
- Low confidence is not a failure: report the number and decide. Do not re-roll until the
  answer is pleasing.

## Step 2 - live browser check (jev-browser)

```
JEV_CHROME="$LOCALAPPDATA/ms-playwright/chromium-<build>/chrome-win64/chrome.exe" \
MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/jev_ui_check.mts \
  --url http://127.0.0.1:8002/ --route '#/market' \
  --widths 1920 --out _audit/x.json --wait 3500
```

- `MSYS_NO_PATHCONV=1` is mandatory: without it Git Bash rewrites `#/market` into a
  filesystem path and the route 404s.
- Hash-router routes: `#/`, `#/market`, `#/technical/<symbol>`, `#/fundamental/<symbol>`,
  `#/strategy-tree`.
- Options: `--widths 1366,1920`, `--testids pulse-verdict,pulse-hemat`,
  `--click-text "برچسب الف||برچسب ب"` (double-pipe separated, for menu buttons),
  `--out _audit/*.json`, `--wait <ms>` (default 14000 - raise it for cold scans),
  `--height`, `--scroll`, `--show` for a visible window.
- Login is injected through `bors_auth_session` in sessionStorage; never type the password.
- Nothing leaves this project to an external service: the tool imports only
  `ensureChromium`, `observe`, `executeActions` from the jev-browser package - never the
  `jev_run` loop (it needs a Gateway key this machine does not have).
- If the build number is gone (Playwright upgrades change it), list
  `$LOCALAPPDATA/ms-playwright/` and use the current
  `chromium-*/chrome-win64/chrome.exe`.

## Reporting

- A unit of work is done only when step 1 AND step 2 passed. Give both results with numbers:
  the confidence returned, and what the browser actually showed.
- When only one ran, state plainly which one is missing and why.
- Charts and visible text are proven in pixels, not in jsdom: a passing vitest suite does not
  substitute for step 2.

## Related project tools (not part of the two-jev gate)

- Guards: `dev/version_anchor_guard.py`, `dev/tape_filters_v1034.py`, `dev/run_all_tests.py`
  (stop dev servers first; CI has no tracked bank so the data section must SKIP).
- Delta proof on the installed app: `py -3.14 tools/inapp_update.py --apply`.
