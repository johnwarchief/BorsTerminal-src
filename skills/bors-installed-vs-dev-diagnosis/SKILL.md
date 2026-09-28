---
name: bors-installed-vs-dev-diagnosis
description: Decide whether an empty/zero/null value in the BorsTerminal market board (تابلو) is a data bug or a code bug by diffing the same symbol/field at one instant from the installed app's backend API and the dev backend (127.0.0.1:8002). Use when a column like «الگو», a badge, vol_ratio/tape fields read 0 or null in the installed exe, flag counts differ from dev, or sync looks throttled / numbers never refresh (304 Not Modified).
---

# Installed-vs-Dev Diagnosis (BorsTerminal)

## Overview

When a board value is missing, fetch it from both backends at one instant and diff. Dev has the value while installed returns 0/null ⇒ data/baseline problem — never start by touching the UI. This is the reproducible first layer of «باگِ داده یا باگِ کد».

## Diff procedure

1. Find the endpoint and field feeding the UI value (board rows come from `api/market.py`).
2. Query the dev backend (`http://127.0.0.1:8002`) and the installed app's backend (exe port; read it from the app log/config — do not guess) for the SAME symbol/field at the SAME instant. Sampling at different clock times manufactures false gap alarms.
3. Judge the diff:
   - dev non-null, installed 0/null ⇒ data/baseline. Inspect the installed `market.db` tables and sync state before anything else.
   - both wrong ⇒ engine code (`tape_flags.py`, the query, or the scoring path).
   - installed numbers right but text/labels wrong ⇒ stale display layer, not this skill; verify shipped code via Version.txt + fresh chunks.
4. Normalize scope before counting anything: filter to the current session (`d_even == max`). Whole-DB counts include dead rows — a real case: same flag counted 95 over 5,340 rows but 14 live-session rows.

## Known data-side root-cause patterns

- **Empty `tape_history`**: installed DB 0 rows with `last_ok=None` means the sync never completed (dev copy had ~182k rows). All five «الگو» badges die because `formula_vol_ratio` becomes null.
- **6h retry lock on an aborted fetch**: the retry lock keys on `last_attempt`, not on the result. A fetch aborted mid-run leaves `note='attempt'`, so every restart is «throttled» for up to `TAPE_HIST_RETRY_S` (6*3600) — the pattern column looks dead forever. Locate the current constant by grep (it lived in the sync module `test_tsetmc.py`); the guard in `dev/tape_filters_v1034.py` asserts it stays in sync.
- **Baseline ships empty**: installed apps initialize from `market.db.lzma`. An older baseline can lack `tape_history` even when the dev DB has it — check row counts inside the baseline asset, not just the dev DB.
- **304 Not Modified loop**: repeated `GET /api/market` returning 304 while the site ticks every second ⇒ backend snapshot/TTL freshness, not the UI poll timer.

## Separate tool drift from product bugs

If a research tool crashes (e.g. `KeyError: 'percent_last'` in `tools/tape_flag_yield.py` or `tools/tape_formula_parity.py`), that is the tool lagging `tape_flags.py`, not a product bug. Fix the tool, then cross-check its counts against the live API before believing either.

## Prove fixes with a negative control

- Work on a COPY of the DB, never the real file.
- Replicate the exact installed state (empty table + `note='attempt'` + fresh attempt timestamp), stub the fetch (no real network), and assert: aborted attempt ⇒ retries after the fix; completed attempt ⇒ still throttles.
- Never `git checkout` to undo a control mutation — restore from the copy.

## Acceptance

Prove end-to-end with jev-browser on the fresh build: «الگو» badges (مشکوک / ساعت / جت / کف‌روب) visibly rendered, chips carry counts, console clean. A green local DB count is not acceptance.
