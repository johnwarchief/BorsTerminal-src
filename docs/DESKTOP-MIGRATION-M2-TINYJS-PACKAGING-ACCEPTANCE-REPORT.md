# BorsTerminal — TinyJS M2 Packaging, Installer & Installed-Product Acceptance

- **Date:** 2026-10-25
- **Branch:** `mission/tinyjs-m2-packaging-acceptance-2026-10-25` (published on `origin`; no PR or merge)
- **Base:** `7caae40` (verified M1.5 report commit)
- **Commits:** `d48dad3` (packaging + harness), `2f168bf` (DB audit), `e0e60c6` (updater harness fix), `810c001` (acceptance evidence), `265a041` (report), `487630e` (test-scope note + evidence hashes), `b3a90e0` (changed-file index); mission branch pushed to `origin`
- **Verdict:** **`PARTIAL — EXPLICIT BLOCKERS`**
- **`M2_ACCEPTANCE_PASS` is not declared.** No real Windows installer was built, no binary is signed, and the in-app update could not replace the running package. Portable-package acceptance is strong; install/update/uninstall acceptance is not.

## 1. Executive summary

A relocatable TinyJS package was built with a self-contained Python/FastAPI sidecar (PyInstaller 6.22.3 onedir, Python 3.12.10). Copied outside the repository and launched from its own directory, it started without the repo `.venv`, resolved the bundled `resources/sidecar/BorsTerminalSidecar.exe`, extracted its bundled `market.db.lzma` into an isolated data directory, and rendered the real cached market board, technical chart (timeframe/adjustment/symbol switch to `آباد`), FTS/fundamental card and market-status page.

The package passed the live loopback guard matrix (13 executions × 5 cases = 65/65, including `Origin: null` → 403), normal window close under load, a shell-root crash with zero orphans and recovery on the same database, and a backend-death test with a visible error window and natural WebView2 teardown.

It did **not** pass the product gates that require distribution machinery:

- **Installer:** no NSIS, WiX, ISCC, signtool, osslsigncode or 7-Zip is installed; only `iexpress.exe` and `makecab.exe` exist. No installer was built or run. Install/uninstall/reinstall are **BLOCKED**.
- **Signing:** all binaries report `NotSigned`; no certificate or private key was read. Authenticity is **BLOCKED**.
- **WebView2:** no bootstrapper is shipped; the host runtime 155.0.4283.62 is required. Missing-runtime behavior is **NOT_MEASURED** (removing the system runtime would be a destructive system-wide change and was not authorized).
- **Updater:** `tiny.app.update.check()` worked (0.3.0 → 0.3.1 over loopback), but `install()` failed because the running PyInstaller sidecar holds `resources/sidecar/_internal/base_library.zip` (`EBUSY`). TinyJS rolled the swap back byte-for-byte (`changed_count: 0`), but no successful update was achieved. Update install is **FAIL**; rollback and checksum refusal are **PASS**.
- **Stability/temp cleanup:** one of three cold runs hit a WebView2 lazy-chunk import failure despite an HTTP 200; first-run extraction leaves `market.db.part-shm` / `.part-wal` residue. Both are **FAIL** for a clean acceptance.

The production application was not migrated and `main` was not changed. No merge, tag, release or force-push was performed; the M2 mission branch was pushed to `origin` without a PR/merge. pywebview remains the operational fallback.

## 2. Scope, controls and non-claims

- All acceptance runs used a **relocated package copy** at `%TEMP%\bors_m2_accept\BorsTerminal`, not an installer installation. This proves relocatability and bundled-sidecar startup; it does not prove installer install/uninstall.
- Every run used an isolated `BORS_WORK_DIR` and explicit `BORS_DB`; the operational repository database was never opened by the package. Network fetch loops and the Codal worker were disabled (`BORS_NO_FETCH_LOOPS=1`, `BORS_CODAL_AUTO=0`). Displayed market data is a **real cached snapshot, not live data**.
- No `Origin: null`, Host/Origin, loopback or CORS relaxation was added. The guard test hits the sidecar the shell actually launched.
- No installer tool was installed, no system-wide change was made, and no certificate/private key was read.
- The update test used a **separate** package build with a loopback update URL and an unsigned local manifest. It is not a production update feed.
- Timings come from a single-core Windows 10 host (2 logical / 1 physical CPU, 3.88 GB RAM). They are descriptive; no improvement percentage is claimed and p95 is not reported for n < 20.
- The WebView2 user-data cache lives under `%APPDATA%\com.borsterminal.m2tinyjs\WebView2` and is shared across runs; it was not purged. These are not fully cold OS/WebView2 runs.
- No successful in-app update, no uninstall, no signed installer and no missing-WebView2 run exist. Those are not claimed as passes.

## 3. Provenance, remote and base audit

The remote/base state was audited read-only before any M2 build or code change:

| Item | Value |
|---|---|
| Remote | `origin https://github.com/johnwarchief/BorsTerminal-src.git` (single remote) |
| M1.5 report commit | `7caae4007f7997fddc8ea5eaf48797e14cb3e144` |
| M1 baseline | `b5f5f6c4f4dab11b3a5547feba5a7a124d79304c` |
| `origin/main` after fetch | `036cdfa917555d58530e8c79c52d7ae07e0a750f` |
| `origin/main` vs M1 baseline | 5 commits ahead; delta is `docs`, `artifacts/ra365/r26`, `tools/ra365_round26_*`; no SPA/backend source |
| M1.5 branch on remote | **No** |
| M2 branch on remote | **Yes** — `mission/tinyjs-m2-packaging-acceptance-2026-10-25` (pushed; no PR/merge) |
| Merge base | `b5f5f6c` |
| Is `7caae40` an ancestor of `origin/main`? | **No** |
| Local `main` | `d580306` (pre-existing clone, behind origin/main; untouched) |
| M2 branch base | `7caae40` |

The M2 branch was created from the verified M1.5 report, not from the five newer `origin/main` commits. No rebase, merge, force-push or branch rewrite was performed. The mission branch and its commits were published on `origin`; `origin/main` remains `036cdfa` and no push destination beyond `origin` is assumed.

**Source/evidence files changed in M2** (`git diff --name-only 7caae40..HEAD`; working tree clean):

- `.gitignore` (ignore generated sidecar/resources/build output)
- `prototypes/tinyjs-m2/src/backend/main.js` (installed sidecar resolution, isolated work/DB env)
- `prototypes/tinyjs-m2/tinyjs.json` (prototype version 0.3.0)
- `prototypes/tinyjs-m2/packaging/m2_sidecar.py`, `m2_sidecar.spec` (packaged sidecar)
- `tools/desktop-migration/phase_d_tinyjs.py` (installed mode, safe window discovery, grace, crash/backend-death modes)
- `tools/desktop-migration/phase_d/m2_update_probe.js` (real update API probe)
- `tools/desktop-migration/m2_close_test.py`, `m2_update_test.py`, `m2_prepare_update.py`
- `docs/DESKTOP-MIGRATION-M2-TINYJS-PACKAGING-ACCEPTANCE-REPORT.md`
- `artifacts/desktop-migration/m2/**` (summaries, screenshots, logs, manifests, hashes)

No production SPA, `app.py`, `api/`, `bors_config.py`, CandleEdge technical, FTS or adjustment module was changed.

## 4. What was built

- **Sidecar:** `prototypes/tinyjs-m2/packaging/m2_sidecar.py` + `m2_sidecar.spec`, a PyInstaller 6.22.3 **onedir** build of the real FastAPI app. It requires `BORS_WORK_DIR` and an explicit `BORS_DB` inside it, refuses a DB outside that scope, runs the real `bors_entry._preflight()`, binds `127.0.0.1`, prints one `M2_READY` line, and exits on stdin EOF/signal.
- **Seed:** `market.db.lzma` (75.0 MiB) and `market.db.baseline` are copied next to the sidecar exe, not baked into `_internal`. `bors_config.ensure_market_db()` extracts the seed into the isolated work dir on first run.
- **TinyJS package:** `tinyjs.json` version 0.3.0; the shell resolves `resources/sidecar/BorsTerminalSidecar.exe`, sets `BORS_WORK_DIR`/`BORS_DB`/`BORS_PORT=0`, and never falls back to `BORS_PYTHON` or the repo `.venv` when the bundled sidecar exists.
- **Sizes (acceptance copy):**

| Component | Bytes | MiB |
|---|---:|---:|
| Shell `BorsTerminalM2TinyJS.exe` | 5,686,711 | 5.4 |
| `launcher.exe` | 2,164,824 | 2.1 |
| `BorsTerminalSidecar.exe` | 14,923,415 | 14.2 |
| Sidecar `_internal` (1,443 files) | 109,547,447 | 104.5 |
| `market.db.lzma` seed | 78,667,800 | 75.0 |
| **Total package (1,448 files)** | **210,990,261** | **201.2** |
| First-run data (DB + user DB + logs) | 282,217,847 | 269.1 |
| **Package + first-run data** | **493,208,108** | **470.3** |
| Update zip 0.3.1 | 137,297,084 | 130.9 |

Hashes: acceptance shell `a51c1dfb…`, sidecar `89c3f90a…`, seed `e7df91dc…`; 0.3.1 shell `a18d30ca…`, zip `9377c5d3…`. Full per-file hashes are in `artifacts/desktop-migration/m2/evidence-manifest.json`.

## 5. Gate matrix

Every status below is limited to the tested scope.

| Gate | Status | Evidence / reason |
|---|---|---|
| Real Python/FastAPI packaging, no dev venv | **PASS** | Bundled PyInstaller onedir sidecar; shell resolves it; installed runs omit `BORS_PYTHON`/`BORS_HEADLESS_ENTRY`; sidecar process is `BorsTerminalSidecar.exe` |
| Installed-style functional slice (real cached data) | **PASS** | Market board, W/H/D chart, adjustment raw, symbol switch `آباد` with company name, FTS/fundamental, market status; screenshots in `installed-smoke/` |
| Loopback Host/Origin security | **PASS** | 13 live executions × 5 cases = **65/65**; `Origin: null` 403 every time |
| Normal close under load | **PASS** | `close2` n=2 and `close-load` n=2: shell exit 0, port closed, 0 survivors after 30 s grace |
| Shell crash + recovery | **PASS** | Root killed after full load: exit 1, 0 survivors, port closed; restart on same work dir passed all stages |
| Backend death | **PASS** | Sidecar killed live: visible `BorsTerminal — startup failed` window; shell exit 0, port closed; WebView2 exited naturally in 1.1 s |
| Real Windows installer | **BLOCKED** | No NSIS/WiX/ISCC/signtool/osslsigncode/7z; only `iexpress`/`makecab`; system-wide install not authorized; no installer built |
| Install / uninstall / reinstall | **BLOCKED** | Depend on the missing installer; only portable relocation/removal was exercised |
| Code signing / authenticity | **BLOCKED** | `Get-AuthenticodeSignature`: **NotSigned** for shell, launcher and sidecar; no signing tool or authorized certificate |
| WebView2 bootstrapper | **BLOCKED** | No bootstrapper is shipped; host runtime 155.0.4283.62 is required |
| WebView2 missing-runtime behavior | **NOT_MEASURED** | Removing the host runtime is destructive/system-wide and was not authorized |
| Update check | **PASS** | Real `tiny.app.update.check()`: 0.3.0 → 0.3.1, notes delivered, over loopback |
| Update install | **FAIL** | Swap blocked by a running-sidecar lock on `_internal/base_library.zip` (`EBUSY`); app remained 0.3.0 |
| Update rollback after failed swap | **PASS** | `changed_count: 0`, no `.update-old`, version still 0.3.0 |
| Update checksum refusal | **PASS** | Wrong sha256 → `checksum mismatch — refusing to install`; `changed_count: 0` |
| Signed HTTPS update feed | **BLOCKED** | Only an unsigned loopback manifest was tested; no Ed25519 public key or HTTPS feed |
| Performance / footprint sampling | **PASS** | Cold n=3, warm n=3; medians/ranges below; p95 omitted for n<20 |
| Temp/data-dir cleanup | **FAIL** | First-run extraction leaves `market.db.part-shm` (32 KB) and `market.db.part-wal` (0 B); no process/port leaks |
| Stability | **FAIL** | 1/3 cold runs failed a `TechnicalPage` lazy dynamic import in WebView2 even though the server logged `200`; not reproduced in warm/close runs |
| Operational DB isolation | **PASS** | All runs isolated; `market.db`/WAL/`user.db` hashes unchanged before and after M2 |

**Tests:** no production SPA/backend/technical/FTS/adjustment file changed in M2 (`git diff --name-only 7caae40..HEAD` contains only `.gitignore`, this evidence, `prototypes/tinyjs-m2/`, and `tools/desktop-migration/`). The M1.5 full-suite baseline — 204 files, 2,090 tests, 2,074 passed / 11 failed / 5 skipped, with all 11 failures reproducing identically on clean `origin/main b5f5f6c` — therefore remains the applicable suite baseline. The full suite was **not rerun in M2** (`NOT_MEASURED` for this mission) because no tested production module changed and a full run takes ~32 minutes on this single-core host; the M2 harness was exercised by the live runs above instead. If the owner requires a fresh full-suite run before any packaging decision, it is an outstanding test, not a pass.

## 6. Functional acceptance

The installed-style smoke run (`--visual --d3`) reached:

- market board with 30 rows and freshness `بازار بسته — تابلوی ۱۴۰۵/۰۷/۲۲`;
- technical page, timeframe switch to `W`, adjustment switch from `عملکردی` to `خام`, symbol switch to `آباد` with the real company name and `/api/chart/آباد` 200;
- FTS strategy summary and 5-indicator card with real statement data;
- market-status panel.

Representative screenshots (committed): `installed-smoke/market_rows_visible.png`, `technical_ready.png`, `fundamental_ready.png`, `market_status_ready.png`, `d3_raw_mode.png`, `d3_symbol2_ready.png`.

Cold acceptance reached all stages in 2/3 runs; warm reached all stages in 3/3. One cold run failed before the chart:

> `TypeError: Failed to fetch dynamically imported module: http://127.0.0.1:49739/assets/TechnicalPage-CfX_WJzv.js`, followed by `timeout: chart-area`. The sidecar access log shows that the same asset returned `200 OK` at 13:40:21. Three WebView2 processes were still present 1 s after the shell exited and were killed by the harness; natural exit was not measured. This is recorded as a stability failure, not silently retried.

## 7. Security

The security matrix was run against the live sidecar for every applicable run (smoke, 3 cold, 3 warm, 2 close, 2 close-load, 1 recovery, 1 backend-death):

| Case | Expected | Result |
|---|---:|---|
| Local Host | 200 | 200 |
| Foreign Host (`evil.example`) | 403 | 403 |
| `Origin: null` | 403 | 403 |
| Foreign Origin | 403 | 403 |
| Local Origin | 200 | 200 |

**65/65 cases passed.** No production guard was changed, no permissive CORS was added, and the sidecar bound `127.0.0.1` only.

## 8. Lifecycle, crash and recovery

- **Normal close (`close2`, n=2; `close-load`, n=2):** exit code 0, port closed, **0 survivors** after a 30 s natural-exit grace. The close-under-load runs had reached the chart/fundamental pages (ready ~20.8/21.2 s, board ~37.1/39.4 s, chart ~75.4/76.5 s, fundamental ~81.0/82.1 s).
- **Crash:** the shell root was terminated after the full app had loaded (kill at ~137 s). Shell exit 1; the sidecar exited on stdin EOF; the port closed; **0 orphans**. Restarting the same work directory (same DB with WAL) reached ready 8.3 s, board 24.6 s, chart 54.6 s and fundamental 59.0 s, exit 0.
- **Backend death:** killing the sidecar while the app was live surfaced the shell's `BorsTerminal — startup failed` error window (screenshot committed). Shell exit 0, port closed; two WebView2 processes exited naturally in 1.1 s, with zero left.
- **Caveat:** earlier full-suite runs checked only 1 s after exit and found 1–3 WebView2 processes in 3 of 9 runs; those were force-killed, so their natural-exit time is unmeasured. The dedicated close tests with a 30 s grace found none.

## 9. Installer, signing and WebView2 — exact blockers

**Tooling check** (`build/tooling-check.txt`):

```
makensis=NOT_FOUND   ISCC=NOT_FOUND   candle.exe=NOT_FOUND   light.exe=NOT_FOUND
signtool.exe=NOT_FOUND   osslsigncode=NOT_FOUND   7z=NOT_FOUND
iexpress=C:\Windows\System32\iexpress.exe
makecab=C:\Windows\System32\makecab.exe
```

- No NSIS, WiX/ISCC or signing tool is installed. `iexpress`/`makecab` are not a production installer (no uninstall registration, upgrade semantics or signing), and building/running a system-wide installer requires separate authorization. **Installer BLOCKED.**
- `Get-AuthenticodeSignature` reports **NotSigned** on `BorsTerminalM2TinyJS.exe`, `launcher.exe` and `BorsTerminalSidecar.exe`. No certificate or private key was read. **Signing BLOCKED.**
- WebView2 runtime 155.0.4283.62 is present on the host. The package contains no WebView2 bootstrapper. Removing the system runtime to test a missing-runtime machine would be destructive and was not authorized. **Bootstrap BLOCKED; missing runtime NOT_MEASURED.**

## 10. Updater and rollback

A separate 0.3.0u build was produced from commit `d48dad3` with a test-only `"update": { "url": "http://127.0.0.1:8123/manifest.json" }` (not committed to `tinyjs.json`). `tinyjs publish` built 0.3.1 and a 130.9 MiB payload zip; three manifests were served locally:

- **check:** real `tiny.app.update.check()` in the page returned `{available: true, current: "0.3.0", latest: "0.3.1", notes: "M2 updater acceptance (loopback)"}`.
- **install:** the updater downloaded the zip (HTTP 200), extracted it, and began the Windows file shuffle. It failed at:

  > `update swap failed — the current version is intact (cannot replace ...\resources\sidecar\_internal\base_library.zip (file locked?): EBUSY: resource busy or locked)`

  The running PyInstaller sidecar keeps `_internal/base_library.zip` open. After the failure: `version_after: 0.3.0`, `changed_count: 0`, `update_old_files: []`, clean close, 0 survivors. **Rollback PASS; update install FAIL.**
- **checksum:** a 0.3.2 manifest with a wrong sha256 produced `checksum mismatch — refusing to install`; `changed_count: 0`, version 0.3.0. **PASS.**

The updater needs an orchestration change before it can work on this package: stop the sidecar and wait for it to exit before `update.install()`, ship a one-file sidecar (no `_internal` tree to lock), or use a separate updater helper that swaps after the app exits. None of those fixes was applied in M2. The feed was unsigned and loopback-only; a signed HTTPS feed is **BLOCKED**.

## 11. Performance and footprint

Cold = fresh work dir/profile per run and first-run DB extraction. Warm = one shared work dir/profile after an unrecorded warmup. All times are launch → observed stage, milliseconds.

| Stage | Cold n=3 median (min–max) | Warm n=3 median (min–max) |
|---|---:|---:|
| Sidecar ready line | 35,181 (24,582–36,542) | 20,895 (14,590–27,132) |
| Window visible | 38,094 (29,180–49,671) | 24,307 (17,573–32,376) |
| Market board usable | 64,989 (45,232–72,497) | 36,941 (36,156–43,209) |
| Technical chart usable | n=2: 100,036 (85,438–114,633) | 72,982 (67,250–78,272) |
| Fundamental usable | n=2: 105,607 (91,281–119,932) | 78,851 (72,640–84,692) |

- First-run preflight/extraction: **20.61–27.47 s** (cold); warm recorded runs: **8.06–12.10 s** (the warmup that did the extraction took 38.78 s).
- Peak process-tree RSS: cold median **875.0 MB**, warm **940.3 MB** (max 967.8 MB).
- Post-idle RSS: cold median **702.7 MB**, warm **798.2 MB**.
- Short idle CPU sample (3 s, one core, SPA may still poll): cold median **94.8%**, warm **124.1%**. This is **not** steady-state CPU.
- The visual smoke run took 25.2/26.3/50.3/103.7/180.0 s to ready/window/board/chart/fundamental because it pauses for screenshots; it is not used for performance.
- No p95 for n<20. Host is single-core; no improvement claim is made.

## 12. Cleanup and residual defects

- Normal close, crash and backend-death leave **no shell/sidecar process** and **close the port**. WebView2 teardown can take ~1 s; with a 30 s grace it exited naturally in the dedicated tests.
- **Defect:** `_extract_market_db()` renames `market.db.part` to `market.db` but leaves `market.db.part-shm` (32 KB) and `market.db.part-wal` (0 B) in the data directory. Reproduced on every first run and in the recovery copy. No data corruption; it is file residue and should be cleaned in `bors_config` (not changed in M2).
- **Defect:** one cold run failed to load `TechnicalPage-CfX_WJzv.js` in WebView2 while the sidecar returned 200; a user-visible route error with no retry. Warm and close runs did not reproduce it. The probe navigated to the technical route immediately after the first board paint, so this may be load/race-sensitive; it is not proven to be TinyJS-specific.

## 13. Operational DB incident audit (read-only)

The M1.5 report understated the operational DB differences. A read-only audit on copies was recorded in `artifacts/desktop-migration/m2/db-incident-analysis.json`:

- Operational `market.db` sha256 `7cfefddd…`, WAL `9e9e9f0f…`, user `user.db` `7dc3fcad…`; template `07dc34ab…`. `PRAGMA integrity_check` on the copy: `ok`.
- `adjust_cache_meta`: operational 50 vs template 48 (`آباد`, `فولاد` added).
- `adjust_events`: operational 12,716 vs template 12,719; 8 operational-only, 11 template-only, net **−3**; source counts differ by `priceAdjust +1`, `shareChange +1`.
- Pre-fix `tauri-crash`/`tinyjs-crash` work DBs were identical to the template, while old logs recorded `data root: <repo BorsTerminal>`; this proves pre-fix runs targeted the operational repo DB. Exact per-row timing is **NOT_MEASURED** (no DB path in old logs, date-only cache timestamps).
- No restore, rollback or rewrite was performed. After all M2 runs, the operational DB/WAL/user hashes are **unchanged** (`build/operational-db-recheck.txt`). All M2 runs used `BORS_DB`/`BORS_WORK_DIR`.

## 14. Blockers and owner decisions

1. **Installer toolchain:** authorize NSIS or WiX (and a system-wide/per-user install policy) or explicitly accept a portable-folder distribution. Without it, install/uninstall/reinstall and the M2 gate cannot pass.
2. **Code signing:** provide an authorized code-signing certificate/tool, or accept an internal unsigned build. No signature means no authenticity claim.
3. **WebView2 distribution:** choose evergreen prerequisite (current), ship a bootstrapper, or fix a runtime. Missing-runtime behavior remains unmeasured.
4. **Update architecture:** stop the sidecar before the swap, use a one-file sidecar, or use an external updater helper. The current in-app update cannot replace `_internal` while the sidecar runs.
5. **Update feed:** host a signed HTTPS manifest (Ed25519 publicKey) or define the internal distribution trust model.
6. **Defects:** fix the `.part-shm`/`.part-wal` residue; investigate/retry the cold lazy-chunk import failure. Neither was fixed in M2.
7. **Base decision:** the M2 branch is based on `7caae40`, while `origin/main` is `036cdfa` (5 docs/tooling commits ahead). Rebase/merge policy belongs to the owner; no rebase was done.

## 15. Reproduction

All build outputs and the 137 MB zip are generated and ignored. From the repository root (with `.venv` containing PyInstaller 6.22.3 and TinyJS 0.65.0):

```text
# sidecar: onedir PyInstaller spec, seed copied beside the exe
prototypes\tinyjs-m2\packaging\m2_sidecar.spec
copy market.db.lzma + market.db.baseline next to BorsTerminalSidecar.exe
copy the sidecar folder to prototypes\tinyjs-m2\resources\sidecar

# package
cd prototypes\tinyjs-m2
_tools\tinyjs\tinyjs.cmd build

# installed-style acceptance (isolated DB/work dir; no venv on the child)
python tools\desktop-migration\phase_d_tinyjs.py --installed --label <label> --mode cold --runs 3 ^
  --exe <install-root>\BorsTerminalM2TinyJS.exe --out-dir artifacts\desktop-migration\m2\<label>

# updater (test build only)
# add "update": {"url": "http://127.0.0.1:8123/manifest.json"} to tinyjs.json temporarily
_tools\tinyjs\tinyjs.cmd publish --notes "M2 updater acceptance (loopback)"
python tools\desktop-migration\m2_prepare_update.py --published-manifest dist\publish\manifest.json ...
python tools\desktop-migration\m2_update_test.py --mode install|checksum|rollback ...
```

The package never received `BORS_PYTHON`, `BORS_HEADLESS_ENTRY` or a dev interpreter. The loopback update URL was test-only and was reverted in `tinyjs.json` after the builds; it is not part of the committed source.

## 16. Evidence index

Committed under `artifacts/desktop-migration/m2/` (65 files, 4.3 MB; the acceptance evidence commit `810c001` added 45 files; hashes in `evidence-manifest.json`):

| Path | Content |
|---|---|
| `acceptance-results.json` | Gate matrix with exact statuses and blockers |
| `build/package-manifest.json` | Package sizes, file counts, hashes, seed/baseline |
| `build/build-provenance.json` | Source commits, build commands, exe/zip hashes, tools |
| `build/tooling-check.txt`, `build/signing-status.txt` | Installer/signing availability; NotSigned results |
| `build/security-matrix-summary.json` | 13 executions, 65/65 cases |
| `build/operational-db-recheck.txt` | Unchanged operational DB/WAL/user hashes |
| `performance.json` | Cold/warm medians, ranges, RSS/CPU, caveats |
| `installed-smoke/` | Functional screenshots and summary (visual/D3) |
| `installed-cold/`, `installed-warm/` | Cold/warm summaries and the cold failure |
| `close2/`, `close-load/` | Normal close with 30 s grace |
| `crash/`, `recover/` | Root-kill orphans and same-DB restart |
| `backend-death/` | Error-window screenshot and 1.1 s WebView2 natural exit |
| `update-install/`, `update-checksum/` | Real updater check/install failure/rollback/checksum |
| `db-incident-analysis.json` | Read-only operational DB incident audit |

Raw 200 MB builds, `dist/`, `resources/sidecar/` and the 137 MB update zip are **not committed**; their hashes are in the build evidence.

## 17. Final status

**`PARTIAL — EXPLICIT BLOCKERS`**

The TinyJS package is a credible portable application candidate: it starts a real bundled Python backend without the development venv, preserves the security guard, renders the real cached product slice, closes and crashes cleanly, and recovers on the same data. It is **not** yet an installable, signed, updatable Windows product. Installer, signing, WebView2 bootstrap, a signed update feed and a successful in-app update remain blocked or failed, so `M2_ACCEPTANCE_PASS` is not declared and no production migration is authorized.
