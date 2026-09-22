---
name: bors-architecture
description: Pre-change guard for the BorsTerminal project. Use BEFORE any refactor, file move, folder restructure, dependency add/remove, PyInstaller spec edit, or large rewrite — inspect the project structure, inspect the dependencies, preserve the current architecture, and produce a written plan instead of a blind rewrite. Also use when asked how the codebase is organized, where a feature lives, or whether a change is safe.
---

# bors-architecture — pre-change guard

BorsTerminal is a Persian stock-market desktop terminal (TSETMC board, Codal
fundamentals, technical charts, portfolio management). It has already been through
several large refactors — the `app.py` monolith was split verbatim into `api/*`, and the
legacy static UI was retired in favour of a React SPA. Every one of those was done with a
written audit trail and a guard script, not a blind rewrite. This skill exists so the next
change happens the same way: deliberately, with evidence, and without silently breaking
the frozen build or the layer contract.

The project's own stated rule for risky work is **evidence-based, not blind rebuild**
(see the phase-5 chart audit note in `docs/FTS-7-Phase-Progress.md`). Follow it.

## When to use this skill

- Before moving/renaming/deleting files or folders
- Before adding or removing a dependency (npm, pip, or cargo)
- Before touching `fts_terminal.spec`, `bors_exe.spec`, `installer/bors_setup.iss`
- Before any change described as "refactor", "rewrite", "split", "migrate", "clean up"
- When asked "where does X live" or "is it safe to change Y"

## The four steps

### 1. Inspect the structure

Two independent layers must be understood before touching anything.

**Backend** — FastAPI app in [`app.py`](../../../Desktop/BorsTerminal/app.py:39) that
mounts `/static`, serves the React SPA at `/` with a catch-all fallback, and includes
`api.api_router()`. The route handlers live in the `api/` package, split verbatim out of
the old monolith: `_core`, `market`, `chart`, `selection`, `watchlist`, `fundamental`,
`market_status`, `screener`, `_sync_market`, `_export`, `_sync_codal`, `adb`, `notify`,
`_pipeline`, `engine`, `update`. Core modules at repo root: `bors_config.py`,
`bors_flags.py`, `codal_fetcher.py`, `fts_engine.py`, `mstat_engine.py`,
`watchlist_store.py`, `bors_minisign.py`, `bors_entry.py`, `bootstrap_first_run.py`.
The line-level map of the monolith split is recorded in `MIGRATED_LINES.txt` — read it
before touching the split, it is the audit trail.

**Frontend** — React 18 + TypeScript, Vite 5, Tailwind 4, Zustand 5, TanStack Query v5,
React Router 7, Zod 4, KLineCharts Pro + lightweight-charts v5. Feature-Sliced Design
layers: `app / shared / contracts / widgets / features-{market,fundamental,technical,
portfolio,master}`. The allowed-import matrix is **enforced by ESLint**, not by convention
— see [`frontend/eslint.config.js`](../../../Desktop/BorsTerminal/frontend/eslint.config.js:33)
(`boundaries/element-types` with `default: 'disallow'`, plus a repo-wide `fetch` ban).

### 2. Inspect the dependencies

There are **three** manifests, and they do not agree with each other about what matters:

- [`frontend/package.json`](../../../Desktop/BorsTerminal/frontend/package.json:15) — the
  UI deps. Note the charting libs are pinned-ish and fast-moving (KLineCharts Pro,
  lightweight-charts v5).
- `requirements.txt` — the backend. `numpy==2.0.2` is pinned on purpose: numpy 2.1+
  requires the x86-v2 baseline and **crashes on older CPUs**. Do not "modernise" this pin.
- `frontend/src-tauri/Cargo.toml` — the Tauri shell (currently a secondary packaging path).

Then check the **hidden coupling**: [`fts_terminal.spec`](../../../Desktop/BorsTerminal/fts_terminal.spec:46)
lists `hiddenimports` explicitly because `api_router()` imports modules *inside function
bodies*, so PyInstaller's static scan cannot see them. **Any new `api/*.py` module must be
added to that list or the frozen EXE dies with `ModuleNotFoundError` on the first
request.** This is the single most common way a "small backend refactor" breaks the
release. The spec comments document it in both English and Persian.

### 3. Preserve the current architecture

These invariants exist for reasons that cost real bugs to learn. Do not break them:

- **`fetch` is banned outside `shared/api/http.ts` and `features/*/api/`.** Enforced by
  `no-restricted-syntax` in the ESLint config.
- **Route registration order matters**: `api_router()` is included *before* the SPA
  catch-all so `/api/*` wins. Reversing this silently breaks every API call.
- **`market.db.lzma` ships beside the EXE, not inside it.** Raw `market.db` is ~98 MB; in
  a onefile build it would be fully re-extracted on every launch. The beside-exe contract
  is deliberate.
- **Two independent updaters exist** and must not be collapsed into one: the Tauri
  updater (minisign pubkey in
  [`frontend/src-tauri/tauri.conf.json`](../../../Desktop/BorsTerminal/frontend/src-tauri/tauri.conf.json:46))
  and the in-app Python updater (`api/update` + `bors_minisign.py`).
- **Startup sync runs exactly once per process.** `@app.on_event("startup")` lives in
  `app.py` and not on a sub-router, because FastAPI merges nested router lifespans and a
  handler on a sub-router would fire once per `include_router` level.
- **`ORJSONResponse or JSONResponse`**, never pass `None` to `default_response_class` —
  that turns every route into a 500 `TypeError` when orjson is absent.
- **Guard scripts in `dev/` are the test contract** (`repo_hygiene_v97.py`,
  `soft_warnings_v974.py`, `mstat_local_v975.py`, plus `dev/run_all_tests.py`). A change
  that makes a guard go red has not necessarily broken the guard — it may have exposed a
  real data bug. Investigate before "fixing" the guard.
- **`.gitignore` has intentional exceptions.** `app.py.bak` is deliberately kept tracked
  (it is the audit trail for the `api/` split) and is re-included with `!app.py.bak`. Do
  not "clean it up".
- **Secrets never enter the repo.** `installer/.setup_password.iss`, `adb_config.json`,
  `*.tauri_updater_key*` are all gitignored; the Inno Setup password is read via
  `#include` at build time.

### 4. Plan before a big refactor

Produce a written plan before writing code. The plan must state:

1. What changes, and which of the invariants above it touches
2. Which `hiddenimports` / spec / ESLint-boundary entries must be updated in lockstep
3. Which guard script in `dev/` will prove the change is safe
4. The rollback path (the project keeps `app.py.bak` for exactly this reason)

Prefer a verbatim-move with an audit trail over a rewrite. When the monolith was split,
the bodies were moved *verbatim* and the line spans were recorded in `MIGRATED_LINES.txt`
— that is the template to follow.

## Output format

```markdown
# Change: <one-line description>
## Scope
## Invariants touched
## Lockstep updates (spec / eslint / guards)
## Guard that proves it
## Rollback
```
