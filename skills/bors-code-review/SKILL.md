---
name: bors-code-review
description: Post-implementation review for the BorsTerminal project. Use AFTER code is written and BEFORE it is committed — review security, bugs, race conditions, edge cases, performance, and tests, each against this project's specific failure modes. Also use when the user asks to review a diff, check a change, or audit a feature.
---

# bors-code-review — post-implementation review

BorsTerminal has a documented history of subtle bugs that a generic review would miss:
options misclassified as shares so a real trade looked like zero volume; a rounding step
that made a traded stock look untraded; a PyInstaller static-scan blind spot that killed
the frozen EXE on the first request. This review is calibrated to those failure modes
rather than to generic checklist items.

Review in six passes. Each pass has the project-specific question to answer, not just the
topic name.

## 1. Security

- Does the installer password stay out of the repo? `installer/.setup_password.iss` is
  gitignored and read via `#include` in
  [`installer/bors_setup.iss`](../../../Desktop/BorsTerminal/installer/bors_setup.iss:6).
  Never log it, never write it into a tracked file, never bundle it into a build artifact
  that gets uploaded.
- Minisign key handling: the Tauri updater pubkey is public in
  [`frontend/src-tauri/tauri.conf.json`](../../../Desktop/BorsTerminal/frontend/src-tauri/tauri.conf.json:48);
  the *private* key must never be near the build. Check `*.tauri_updater_key*` stays
  gitignored.
- SQL: `market.db` is queried from `api/*` and `mstat_engine.py`. Check for string-built
  SQL, especially in any new filter/screener path.
- Device control paths: `api/adb` and `codal_fetcher.rotate_ip_via_adb` drive a real
  physical device over ADB. Confirm a toggle endpoint cannot be triggered by an
  unauthenticated caller and that state changes are logged.
- Bundled secrets: if `fts_terminal.spec` `datas` gained an entry, confirm it is not a
  credential. The spec already conditionally bundles `.setup_password.iss` — that is
  intentional and scoped.

## 2. Bugs

- **PyInstaller blind spot.** `api_router()` imports modules *inside function bodies*, so
  the static scan cannot see them. If the change added or renamed any module under `api/`
  or at root, it MUST be added to `hiddenimports` in
  [`fts_terminal.spec`](../../../Desktop/BorsTerminal/fts_terminal.spec:46). This is the
  highest-probability regression in the whole project.
- **orjson fallback.** `default_response_class=(ORJSONResponse or JSONResponse)` — never
  pass `None`.
- **numpy CPU baseline.** `numpy==2.0.2` is pinned because 2.1+ requires the x86-v2
  baseline and crashes on older CPUs. A transitive bump breaks the app on the user's
  machine, not in CI.
- **Frozen-mode path resolution.** `app.py` resolves `static/` and `frontend/dist` via
  `sys._MEIPASS` when frozen. New path logic must handle both frozen and dev modes.
- **Route order.** `api_router()` is registered before the SPA catch-all; new routes must
  not be mounted after it.

## 3. Race conditions

- Startup market sync runs **once per process** via `@app.on_event("startup")` in
  [`app.py`](../../../Desktop/BorsTerminal/app.py:11). It lives there and not on a
  sub-router because FastAPI merges nested router lifespans — a handler on a sub-router
  fires once per `include_router` level. Do not "fix" this by moving it.
- Watchlist star/sync state is read and written from multiple UI features; check for
  read-modify-write over the store without a single writer.
- Codal control toggles (`codal_control.json`) are written by the fetcher and read by the
  API — confirm the toggle path does not race with an in-flight fetch.
- uvicorn reload/restart semantics: the running server holds old code in memory until
  restart, so a code change is not live until the process restarts. Say so explicitly in
  the review verdict instead of claiming "fixed".

## 4. Edge cases

The project's guards encode a data contract — these are the cases that actually bit:

- **No data is never a green/red zero.** NULL depth ⇒ `depth_available: False`; no
  datapoint ⇒ `ready: False`; a separate "unknown basis" bucket exists. Never let a NULL
  become a plausible-looking number.
- **No data ≠ weak.** If 52 weeks cannot be built, `weak` is `None` and no warning is
  shown. Do not turn `None` into a failing score.
- **Unit and rounding traps.** Volume displayed in billions of shares once made a
  genuinely traded stock look untraded (`round(9959/1e9, 4) = 0.0`). Any new displayed
  quantity needs a raw-count fallback (`trades > 0`), not just a rounded magnitude.
- **Options vs shares.** TSETMC now returns options in `paperType=1` responses; the
  classifier separates them by name as a defence. New paper-type logic must not regress
  this.
- **Persian/RTL concerns**: Persian digits, RTL layout, and the `faDigits` handling. Any
  new numeric input or output path must handle Persian digits.
- **Flat price ⇒ neutral ⇒ warn**, intentionally, including fixed-income funds.

## 5. Performance

- **Constant query count is a hard contract.** The seven market-status panels are built
  with exactly 7 SQL queries regardless of symbol count (609 symbols → still 7 queries).
  A new panel must not introduce per-symbol queries.
- GZip middleware compresses responses >1 KB at level 5 (`/api/market` drops 4.2 MB →
  ~450 KB). Do not disable it or raise the threshold.
- Tables use TanStack Virtual — new grid rows must stay virtualized, not rendered in a
  plain map.
- `market.db` is ~98 MB; avoid loading full tables into memory.

## 6. Tests

- Which guard in `dev/` covers this change? `repo_hygiene_v97.py` (dead-code and
  structure), `soft_warnings_v974.py` (70 checks), `mstat_local_v975.py` (140 checks,
  runs on both curated data and real `market.db`). Run the relevant one.
- Frontend changes: `npm test` (Vitest + Testing Library) and `npm run lint` — the
  boundaries plugin is part of the test surface, not a nicety.
- A guard going red is a finding, not necessarily a defect. The options/rounding bugs
  were *discovered* by a red guard. Read the raw data before deciding whether the guard
  or the code is wrong.

## Output format

```markdown
# Review: <change>
## Verdict: APPROVE | APPROVE WITH NOTES | CHANGES REQUIRED
## Security
## Bugs
## Race conditions
## Edge cases
## Performance
## Tests
## Must-fix before commit
```

State the verdict plainly. If the change is safe but the running server needs a restart
for it to take effect, say that in the verdict rather than implying it is already live.
