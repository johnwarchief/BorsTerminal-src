# CODAL No-ADB Auto-Update + Client (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily no-ADB CODAL pipeline that fetches only the needed data (Cat 1/3/6, 7 requests), validates it in a staging DB, merges it into the local DB, materializes FTS, builds and signs a small snapshot + calendar + meta, auto-publishes it to a stable data tag, and lets the installed app auto-check, notify and merge it without ADB.

**Architecture:** `dev/codal_auto_update.py` orchestrates the existing `codal_fetcher` discovery/direct extraction, a new `dev/codal_validation.py` gate, `api._sync_codal._apply_codal_merge` for the merge, `scripts/build_codal_snapshot.py` for the lzma+meta, minisign for the signature, and a thin `gh release upload` publisher. The client reads only `codal.meta.json` and the signed assets from GitHub; it never calls `search.codal.ir` and never needs ADB.

**Tech Stack:** Python 3.12+ / SQLite / requests / minisign / GitHub CLI, PowerShell Task Scheduler, FastAPI, React 18 + TypeScript + Zod + Vitest.

**Spec:** `docs/superpowers/specs/2026-10-26-codal-fundamental-auto-update-design.md` (Appendix 3: source decision, 7–8 request budget, strict universe, calendar, schema drift).

## Global Constraints

- Branch `mission/fts-indicator-engineering`; no push, no main/release tags.
- Steady-state **no ADB**. ADB is only for a one-time bulk/backfill (outside this daily pipeline).
- Daily discovery: Cat 1 = 3 pages, Cat 3 = 3 pages, Cat 6/calendar = 1 request; pause 1.5–2.0s; 2 extraction workers; on 429 back off 30/60/120s then stop; never probe during a ban.
- Staging DB first; no merge and no publish unless every gate passes. Keep a last-known-good snapshot; a failed run leaves the previous one untouched.
- The owner authorized automatic data upload. The minisign private key and GitHub token live outside the repo (env/Credential Manager); if missing, stop before upload and alert.
- Client: only the signed snapshot/meta/calendar; never CODAL directly; show a notification and apply automatically; keep the manual button.
- Tests use temp DBs and a fake `gh`; never write the operational `market.db`, never call CODAL/GitHub in tests.
- No third-party data source (Rahavard/TradersArena/brsapi/NADPCO). No fabricated data; N/A on failure.
- Register new test suites in `dev/run_all_tests.py`; stage only mission files.

---

## File Structure

- `codal_fetcher.py` — add per-category `cats`/`pages_per_cat` to `feed_sync`; keep direct report/Excel extraction; no ADB in `POLITE` mode.
- `dev/codal_fts_updater.py` — fix the 26/21 FS INSERT drift (Task 1).
- `dev/codal_validation.py` — staging gates (new).
- `dev/codal_auto_update.py` — orchestrator: lock, staging, fetch, validate, merge, materialize, snapshot, sign, publish, status (new).
- `scripts/build_codal_snapshot.py` — emit `codal.meta.json` + sha256/row counts/periods (modify).
- `scripts/publish_codal_snapshot.py` — atomic-ish `gh release upload` to `data-codal`, last-known-good, rollback, kill switch (new).
- `scripts/schedule_codal_auto_update.ps1` — Task Scheduler daily 18:30, StartWhenAvailable, IgnoreNew, restart (new).
- `dev/calendar_fetcher.py` — Cat 6 one-month + merge mode; `static/calendar/cache.json` / `calendar.json` asset (modify).
- `api/_sync_codal.py` — data-tag URLs, meta check, calendar asset, auto-download trigger, status (modify).
- `app.py` — startup freshness check only; no blocking (modify).
- `frontend/src/features/fundamental/routes/FundamentalPage.tsx`, `api/useCodalAutoUpdate.ts`, `ui/FtsScreenTable.tsx` — auto-update hook, banner/toast, freshness, auto refresh (modify/new).
- Tests: `dev/test_fts_updater_schema_v11.py`, `dev/test_codal_validation_v11.py`, `dev/test_codal_auto_update_v11.py`, `dev/test_codal_snapshot_meta_v11.py`, `dev/test_codal_publish_v11.py`, `dev/test_codal_schedule_v11.py`, `dev/test_calendar_merge_v11.py`, `dev/test_codal_client_meta_v11.py`, `frontend/src/__tests__/codal-auto-update.spec.tsx`.
- `dev/run_all_tests.py`, `docs/AGENT-INDEX.md`.

---

### Task 1: Fix the updater's 26/21 schema drift

**Files:**
- Modify: `dev/codal_fts_updater.py` (`save_annual` INSERT)
- Test: `dev/test_fts_updater_schema_v11.py`

**Interfaces:**
- `save_annual(conn, L, vals, meta, unit)` must insert one `financial_statements` row with all 26 columns, including `is_audited`, `is_consolidated`, `fiscal_year`, `unit_norm`, `has_operating_sales`.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_fts_updater_schema_v11.py
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "dev"))
import codal_fetcher as cf
from codal_fts_updater import save_annual

c = sqlite3.connect(":memory:")
cf.create_schema(c); cf.migrate_schema(c)
L = {"TracingNo": 900001, "Symbol": "TEST", "CompanyName": "تست",
     "Title": "صورت مالی سالانه حسابرسی شده", "LetterCode": "x",
     "PublishDateTime": "1405/07/01", "Url": "/Reports/Decision.aspx?x"}
vals = {k: 100.0 for k in cf.FS_KEYS}
vals.update({"revenue": 1000.0, "gross_profit": 500.0, "net_profit": 200.0,
             "basic_eps": 10.0})
meta = {"period": "12", "end": "1404/12/29"}
save_annual(c, L, vals, meta, "میلیون ریال")
row = c.execute("SELECT COUNT(*), is_audited, is_consolidated, fiscal_year, "
                "unit_norm FROM financial_statements WHERE tracing_no=900001").fetchone()
assert row[0] == 1 and row[2] == 0 and row[3] == "1404", row
print("OK updater schema")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_fts_updater_schema_v11.py`
Expected: `OperationalError: table financial_statements has 26 columns but 21 values were supplied`.

- [ ] **Step 3: Fix `save_annual`**

Replace the positional INSERT with an explicit column list. Use the existing tuple for the first 21 columns and append the derived five:

```python
cols = ("tracing_no, symbol, company_name, title, report_kind, period_months, "
        "period_end, publish_date, revenue, gross_profit, operating_profit, "
        "net_profit, total_assets, total_liabilities, total_equity, capital, "
        "retained_earnings, basic_eps, unit, url, fetched_at, is_audited, "
        "is_consolidated, fiscal_year, unit_norm, has_operating_sales")
sql = "INSERT OR REPLACE INTO financial_statements (%s) VALUES (%s)" % (
    cols, ",".join("?" * 26))
derived = (1 if cf._is_audited(L.get("Title")) else 0,
           1 if cf._is_consolidated(L.get("Title")) else 0,
           str(meta.get("end") or "")[:4] or None,
           cf._classify_unit(unit),
           None)
conn.execute(sql, tuple(row_values) + derived)
```

`row_values` is the existing 21-value tuple in `save_annual` (do not change its order). The function `cf._is_audited`/`_is_consolidated`/`_classify_unit` exist; if a name differs, use the `codal_fetcher` function that `FS_INSERT` already uses.

- [ ] **Step 4: Run the test and the updater's local mode**

Run: `python dev/test_fts_updater_schema_v11.py` → `OK updater schema`.
Run: `python dev/codal_fts_updater.py --mode local --materialize` on a **temp DB copy** (pass `--db`); expected exit 0.
Do not run it on the live `market.db` in this task.

- [ ] **Step 5: Commit**

```bash
git add dev/codal_fts_updater.py dev/test_fts_updater_schema_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "fix(codal): make updater FS INSERT match the 26-column schema"
```

---

### Task 2: Staging validation gates

**Files:**
- Create: `dev/codal_validation.py`
- Test: `dev/test_codal_validation_v11.py`

**Interfaces:**
- `validate_staging(main_db: str, staging_db: str, last_good: dict|None) -> dict` returns `{"ok": bool, "errors": list[str], "warnings": list[str], "stats": dict}`.
- Checks: tables exist; latest periods advance or stay equal; total rows not below 95% of main per table; no duplicate `tracing_no`; no negative revenue; no `gross_profit > revenue`; no empty URL/publish date on new rows; no future period (`> 1405`); counts/periods in `stats`.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_codal_validation_v11.py
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
from codal_validation import validate_staging

def mk(path, fs_rows, ms_rows):
    c = sqlite3.connect(path)
    c.executescript("""
      CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT,
        title TEXT, publish_date TEXT, url TEXT);
      CREATE TABLE financial_statements (tracing_no INTEGER PRIMARY KEY, symbol TEXT,
        title TEXT, period_end TEXT, revenue REAL, gross_profit REAL, url TEXT,
        publish_date TEXT);
      CREATE TABLE monthly_sales (tracing_no INTEGER PRIMARY KEY, symbol TEXT,
        title TEXT, period_end TEXT, ytd_revenue REAL, url TEXT, publish_date TEXT);
    """)
    c.executemany("INSERT INTO financial_statements VALUES (?,?,?,?,?,?,?,?)", fs_rows)
    c.executemany("INSERT INTO monthly_sales VALUES (?,?,?,?,?,?,?)", ms_rows)
    c.commit(); c.close()

main = os.path.join(os.environ["TEMP"], "codal_val_main.db")
stg = os.path.join(os.environ["TEMP"], "codal_val_stg.db")
for p in (main, stg):
    if os.path.exists(p): os.remove(p)
mk(main, [(1,"A","t","1404/12/29",100,50,"u","1405/07/01")],
   [(10,"A","t","1405/06/31",100,"u","1405/07/01")])
mk(stg, [(1,"A","t","1404/12/29",100,50,"u","1405/07/01"),
         (2,"B","t","1405/06/31",200,80,"u","1405/07/02")],
   [(10,"A","t","1405/06/31",100,"u","1405/07/01")])
r = validate_staging(main, stg, None)
assert r["ok"] is True, r
c = sqlite3.connect(stg)
c.execute("INSERT INTO financial_statements VALUES (3,'C','t','1405/06/31',-5,1,'u','1405/07/02')")
c.commit(); c.close()
r2 = validate_staging(main, stg, None)
assert r2["ok"] is False and any("negative_revenue" in e for e in r2["errors"]), r2
for p in (main, stg): os.remove(p)
print("OK validation gates")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_codal_validation_v11.py`
Expected: `ModuleNotFoundError: No module named 'codal_validation'`.

- [ ] **Step 3: Implement the gates**

```python
# dev/codal_validation.py (complete checks; no network)
import sqlite3

TABLES = ("codal_notices", "financial_statements", "monthly_sales")


def _one(conn, sql, args=()):
    row = conn.execute(sql, args).fetchone()
    return row[0] if row else None


def validate_staging(main_db, staging_db, last_good=None):
    errors, warnings, stats = [], [], {}
    main = sqlite3.connect(main_db); stg = sqlite3.connect(staging_db)
    try:
        for t in TABLES:
            n_main = _one(main, "SELECT COUNT(*) FROM %s" % t) or 0
            n_stg = _one(stg, "SELECT COUNT(*) FROM %s" % t) or 0
            stats[t] = {"main": n_main, "staging": n_stg}
            if n_main and n_stg < int(n_main * 0.95):
                errors.append("%s_coverage_drop" % t)
            if _one(stg, "SELECT COUNT(*) FROM (SELECT tracing_no FROM %s "
                         "GROUP BY tracing_no HAVING COUNT(*)>1)" % t):
                errors.append("%s_duplicate_tracing_no" % t)
        stats["fs_latest"] = _one(stg, "SELECT MAX(period_end) FROM financial_statements")
        stats["ms_latest"] = _one(stg, "SELECT MAX(period_end) FROM monthly_sales")
        main_fs = _one(main, "SELECT MAX(period_end) FROM financial_statements")
        main_ms = _one(main, "SELECT MAX(period_end) FROM monthly_sales")
        if main_fs and stats["fs_latest"] and str(stats["fs_latest"]) < str(main_fs):
            errors.append("fs_period_regressed")
        if main_ms and stats["ms_latest"] and str(stats["ms_latest"]) < str(main_ms):
            errors.append("ms_period_regressed")
        for t in ("financial_statements", "monthly_sales"):
            for tn, sym, rev, gp, url, pub in stg.execute(
                    "SELECT tracing_no, symbol, revenue, gross_profit, url, publish_date FROM %s" % t):
                if rev is not None and rev < 0:
                    errors.append("%s:%s:negative_revenue" % (t, tn))
                if gp is not None and rev is not None and gp > rev:
                    errors.append("%s:%s:gross_gt_revenue" % (t, tn))
                if not url or not pub:
                    errors.append("%s:%s:missing_provenance" % (t, tn))
        for pe, in stg.execute("SELECT period_end FROM financial_statements"):
            if pe and str(pe)[:4] > "1405":
                errors.append("future_period:%s" % pe)
        if last_good:
            warnings.append("last_good_checked")
    finally:
        main.close(); stg.close()
    return {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}
```

- [ ] **Step 4: Run the test**

Run: `python dev/test_codal_validation_v11.py` → `OK validation gates`.

- [ ] **Step 5: Commit**

```bash
git add dev/codal_validation.py dev/test_codal_validation_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): add staging validation gates"
```

---

### Task 3: Daily no-ADB orchestrator (dry-run first)

**Files:**
- Modify: `codal_fetcher.py` (`feed_sync` gains `cats`/`pages_per_cat`; `POLITE` no ADB)
- Create: `dev/codal_auto_update.py`
- Test: `dev/test_codal_auto_update_v11.py`

**Interfaces:**
- `feed_sync(mode="update", optimized=True, catchup=None, cats=None, pages_per_cat=None)`; defaults `cats=["1","3"]`, `pages_per_cat` fallback 8 (optimized) / 50.
- `run(mode="daily", dry_run=False, db_path=None) -> dict` returns `{"ok", "mode", "staged", "validation", "snapshot", "published", "errors"}`.
- Status file `codal_auto_status.json`; lock file `codal_auto.lock`; kill switch `codal_auto_pause`.

- [ ] **Step 1: Write the failing test (dry-run, no network)**

```python
# dev/test_codal_auto_update_v11.py
import os, sqlite3, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
import codal_fetcher as cf
import codal_auto_update as A

tmp = tempfile.mkdtemp(prefix="codal_auto_")
main = os.path.join(tmp, "market.db")
c = sqlite3.connect(main); cf.create_schema(c); cf.migrate_schema(c); c.commit(); c.close()

def fake_fetch(staging_db, **_):
    c = sqlite3.connect(staging_db)
    c.execute("INSERT OR REPLACE INTO financial_statements "
              "(tracing_no,symbol,title,period_end,period_months,revenue,gross_profit,url,publish_date) "
              "VALUES (1,'A','سالانه','1404/12/29',12,100,50,'u','1405/07/01')")
    c.commit(); c.close()

A._fetch = fake_fetch
A.STATUS = os.path.join(tmp, "codal_auto_status.json")
A.LOCK = os.path.join(tmp, "codal_auto.lock")
r = A.run(mode="daily", dry_run=True, db_path=main, staging_dir=tmp)
assert r["ok"] is True and r["published"] is False, r
print("OK orchestrator dry-run")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_codal_auto_update_v11.py`
Expected: `ModuleNotFoundError`/`AttributeError`.

- [ ] **Step 3: Implement the fetcher parameters and the orchestrator**

`codal_fetcher.feed_sync`:

```python
def feed_sync(mode="update", optimized=False, catchup=None, cats=None,
              pages_per_cat=None):
    ...
    cats = list(cats or ["1", "3"])
    def _pages(cat):
        return int((pages_per_cat or {}).get(cat, 8 if optimized else 50))
    total_pages = sum(_pages(c) for c in cats)
    ...
    for cat in cats:
        page = 1
        while page <= _pages(cat):
            ...
```

`dev/codal_auto_update.py` core:

```python
import json, os, shutil, sqlite3, sys, subprocess, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import codal_fetcher as cf
from codal_validation import validate_staging
from build_codal_snapshot import build_snapshot
from publish_codal_snapshot import publish
from api._sync_codal import _apply_codal_merge

LOCK = os.path.join(ROOT, "codal_auto.lock")
PAUSE = os.path.join(ROOT, "codal_auto_pause")
STATUS = os.path.join(ROOT, "codal_auto_status.json")


def _write_status(**kw):
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(kw, f, ensure_ascii=False)


def _staging_copy(main_db, staging_db):
    src = sqlite3.connect(main_db); dst = sqlite3.connect(staging_db)
    src.backup(dst); dst.close(); src.close()


def _fetch(staging_db, mode="daily"):
    old = cf.DB_PATH
    cf.DB_PATH = staging_db
    cf.POLITE = True
    try:
        cf.feed_sync("update", optimized=True, cats=["1", "3"],
                     pages_per_cat={"1": 3, "3": 3})
    finally:
        cf.DB_PATH = old


def run(mode="daily", dry_run=False, db_path=None, staging_dir=None):
    db_path = db_path or os.path.join(ROOT, "market.db")
    staging_dir = staging_dir or db_path + ".staging"
    if os.path.exists(PAUSE):
        return {"ok": False, "errors": ["paused"], "published": False}
    fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    staging = os.path.join(staging_dir, "staging.db")
    os.makedirs(staging_dir, exist_ok=True)
    try:
        _write_status(stage="staging", mode=mode)
        _staging_copy(db_path, staging)
        _write_status(stage="fetching", mode=mode)
        _fetch(staging, mode)
        _write_status(stage="validating", mode=mode)
        val = validate_staging(db_path, staging, None)
        if not val["ok"]:
            _write_status(stage="validation_failed", errors=val["errors"])
            return {"ok": False, "errors": val["errors"], "published": False,
                    "validation": val}
        if dry_run:
            return {"ok": True, "published": False, "validation": val,
                    "staged": True}
        _write_status(stage="merging", mode=mode)
        _apply_codal_merge(db_path, staging)
        subprocess.run([sys.executable, os.path.join(ROOT, "dev", "codal_fts_updater.py"),
                        "--mode", "local", "--materialize"], check=True)
        lzma = os.path.join(staging_dir, "codal.db.lzma")
        meta_path = os.path.join(staging_dir, "codal.meta.json")
        build_snapshot(db_path, lzma, meta_path)
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sign_setup.py"),
                        lzma], check=True)
        pub = publish(lzma, lzma + ".sig", meta_path, tag="data-codal", dry_run=False)
        _write_status(stage="done", mode=mode, published=bool(pub.get("uploaded")))
        return {"ok": True, "published": bool(pub.get("uploaded")),
                "validation": val, "publish": pub}
    finally:
        try: os.remove(LOCK)
        except OSError: pass
```

- [ ] **Step 4: Run the dry-run test and a validation-failure test**

Run: `python dev/test_codal_auto_update_v11.py` → `OK orchestrator dry-run`.
Add a second assertion: a fake fetch that writes a negative revenue → `run` returns `ok=False`, `published=False`, and no merge (check the main DB row count unchanged). Run again.

- [ ] **Step 5: Commit**

```bash
git add codal_fetcher.py dev/codal_auto_update.py dev/test_codal_auto_update_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): add staging-first no-ADB auto-update orchestrator"
```

---

### Task 4: Snapshot meta (sha256, periods, counts)

**Files:**
- Modify: `scripts/build_codal_snapshot.py`
- Test: `dev/test_codal_snapshot_meta_v11.py`

**Interfaces:**
- `build_snapshot(db_path, out_lzma, out_meta) -> dict` returns the meta; writes `codal.meta.json` with `schema_version`, `published_at` (UTC ISO), `latest_financial_period`, `latest_monthly_period`, `row_counts` (three tables), `sha256`, `size`, `min_client_version`, `calendar_version`.
- The lzma remains the three CODAL tables only.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_codal_snapshot_meta_v11.py
import json, os, sqlite3, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_codal_snapshot import build_snapshot
import codal_fetcher as cf

tmp = tempfile.mkdtemp(prefix="codal_snap_")
db = os.path.join(tmp, "market.db")
c = sqlite3.connect(db); cf.create_schema(c); cf.migrate_schema(c)
c.execute("INSERT INTO financial_statements (tracing_no,symbol,title,period_end,period_months) "
          "VALUES (1,'A','t','1405/06/31',12)")
c.execute("INSERT INTO monthly_sales (tracing_no,symbol,title,period_end) "
          "VALUES (2,'A','t','1405/07/30')")
c.commit(); c.close()
meta = build_snapshot(db, os.path.join(tmp, "codal.db.lzma"),
                      os.path.join(tmp, "codal.meta.json"))
assert meta["latest_financial_period"] == "1405/06/31", meta
assert meta["latest_monthly_period"] == "1405/07/30", meta
assert meta["row_counts"]["financial_statements"] == 1, meta
assert len(meta["sha256"]) == 64 and meta["size"] > 0, meta
assert json.load(open(os.path.join(tmp, "codal.meta.json"), encoding="utf-8"))["sha256"] == meta["sha256"]
print("OK snapshot meta")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_codal_snapshot_meta_v11.py`
Expected: `ImportError: build_snapshot`.

- [ ] **Step 3: Refactor `scripts/build_codal_snapshot.py`**

Move the current `main` body into `build_snapshot(db_path, out_lzma, out_meta)`; keep the schema copy/integrity/VACUUM/lzma. After the lzma:

```python
import hashlib, json, datetime
size = os.path.getsize(out_lzma)
sha = hashlib.sha256(open(out_lzma, "rb").read()).hexdigest()
src = sqlite3.connect(db_path)
meta = {
    "schema_version": 1,
    "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "latest_financial_period": src.execute("SELECT MAX(period_end) FROM financial_statements").fetchone()[0],
    "latest_monthly_period": src.execute("SELECT MAX(period_end) FROM monthly_sales").fetchone()[0],
    "row_counts": {t: src.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                   for t in TABLES},
    "sha256": sha, "size": size,
    "min_client_version": "1.0.99",
    "calendar_version": "",
}
src.close()
with open(out_meta, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
return meta
```

Keep `main()` as an argparse wrapper calling `build_snapshot`.

- [ ] **Step 4: Run the test**

Run: `python dev/test_codal_snapshot_meta_v11.py` → `OK snapshot meta`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_codal_snapshot.py dev/test_codal_snapshot_meta_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): emit signed-snapshot metadata next to the lzma"
```

---

### Task 5: Publish to the stable data tag with last-known-good and rollback

**Files:**
- Create: `scripts/publish_codal_snapshot.py`
- Test: `dev/test_codal_publish_v11.py`

**Interfaces:**
- `publish(lzma, sig, meta, tag="data-codal", dry_run=False) -> dict` uploads `codal.db.lzma`, `codal.db.lzma.sig`, `codal.meta.json`, `calendar.json` (if present) with `gh release upload <tag> ... --clobber`; creates the prerelease tag if missing.
- `keep_last_good(lzma, meta, calendar)` copies to `last_good/`; `rollback(...)` re-uploads those files.
- Test uses a fake `gh` executable in a temp PATH; no network.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_codal_publish_v11.py
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import publish_codal_snapshot as P

tmp = tempfile.mkdtemp(prefix="codal_pub_")
gh = os.path.join(tmp, "gh.py")
open(gh, "w", encoding="utf-8").write(
    "import sys, pathlib\n"
    "pathlib.Path(r'%s').write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n" % os.path.join(tmp, "args.txt"))
os.environ["PATH"] = tmp + os.pathsep + os.environ.get("PATH", "")
os.environ["BORS_GH"] = sys.executable + " " + gh
P.LAST = os.path.join(tmp, "last_good")
lzma = os.path.join(tmp, "codal.db.lzma"); open(lzma, "wb").write(b"x")
sig = lzma + ".sig"; open(sig, "w").write("sig")
meta = os.path.join(tmp, "codal.meta.json"); open(meta, "w").write("{}")
r = P.publish(lzma, sig, meta, tag="data-codal", dry_run=True)
assert r["uploaded"] is False and r["dry_run"] is True, r
r2 = P.publish(lzma, sig, meta, tag="data-codal", dry_run=False)
assert r2["uploaded"] is True, r2
print("OK publish dry-run/live (fake gh)")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_codal_publish_v11.py`
Expected: `ImportError`/`AttributeError` for `publish`.

- [ ] **Step 3: Implement publish, last-known-good, and rollback**

```python
# scripts/publish_codal_snapshot.py
import json
import os
import shlex
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "johnwarchief/BorsTerminal"
LAST = os.path.join(ROOT, "last_good")


def _gh():
    return shlex.split(os.environ.get("BORS_GH", "gh"))


def keep_last_good(files):
    os.makedirs(LAST, exist_ok=True)
    for f in files:
        if os.path.isfile(f):
            shutil.copy2(f, os.path.join(LAST, os.path.basename(f)))


def publish(lzma, sig, meta, tag="data-codal", dry_run=False):
    files = [lzma, sig, meta]
    cal = os.path.join(ROOT, "static", "calendar", "cache.json")
    if os.path.isfile(cal):
        files.append(cal)
    if dry_run:
        return {"uploaded": False, "dry_run": True, "tag": tag, "files": files}
    gh = _gh()
    exists = subprocess.run(
        gh + ["release", "view", tag, "--repo", REPO],
        capture_output=True, text=True).returncode == 0
    if not exists:
        subprocess.run(
            gh + ["release", "create", tag, "--repo", REPO,
                  "--title", "CODAL data (latest)", "--prerelease",
                  "--notes", "Automatic CODAL snapshot"], check=True)
    subprocess.run(
        gh + ["release", "upload", tag, *files, "--repo", REPO, "--clobber"],
        check=True)
    keep_last_good(files)
    return {"uploaded": True, "dry_run": False, "tag": tag, "files": files}


def rollback(tag="data-codal"):
    files = [os.path.join(LAST, n) for n in
             ("codal.db.lzma", "codal.db.lzma.sig", "codal.meta.json")]
    files = [f for f in files if os.path.isfile(f)]
    subprocess.run(_gh() + ["release", "upload", tag, *files,
                            "--repo", REPO, "--clobber"], check=True)
    return {"rolled_back": True, "files": files}
```

- [ ] **Step 4: Run the fake-gh test**

Run: `python dev/test_codal_publish_v11.py`
Expected: `OK publish dry-run/live (fake gh)`; the fake `gh` receives `release upload data-codal ... --clobber`.

- [ ] **Step 5: Commit**

```bash
git add scripts/publish_codal_snapshot.py dev/test_codal_publish_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): publish signed snapshot to the data-codal tag"
```

---

### Task 6: Task Scheduler + startup catch-up

**Files:**
- Create: `scripts/schedule_codal_auto_update.ps1`
- Modify: `api/_sync_codal.py` (pure `should_auto_update` + startup hook)
- Test: `dev/test_codal_schedule_v11.py`

**Interfaces:**
- `should_auto_update(last_success_iso: str|None, now: datetime, max_age_hours=24) -> bool`.
- The PS1 registers `BorsCodalAutoUpdate`: daily 18:30, `StartWhenAvailable`, `MultipleInstances IgnoreNew`, `ExecutionTimeLimit 2h`, `RestartCount 2`; action `python dev/codal_auto_update.py --mode daily`; `-Remove`.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_codal_schedule_v11.py
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from datetime import datetime, timedelta
from api._sync_codal import should_auto_update
now = datetime(2026, 10, 26, 19, 0)
assert should_auto_update(None, now) is True
assert should_auto_update((now - timedelta(hours=25)).isoformat(), now) is True
assert should_auto_update((now - timedelta(hours=2)).isoformat(), now) is False
src = open(os.path.join(ROOT, "scripts", "schedule_codal_auto_update.ps1"), encoding="utf-8").read()
for token in ("BorsCodalAutoUpdate", "18:30", "StartWhenAvailable", "IgnoreNew", "codal_auto_update.py"):
    assert token in src, token
print("OK schedule/catch-up")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_codal_schedule_v11.py`
Expected: `ImportError: cannot import name 'should_auto_update'`.

- [ ] **Step 3: Implement the pure freshness check**

```python
# api/_sync_codal.py
def should_auto_update(last_success_iso, now=None, max_age_hours=24):
    import datetime
    now = now or datetime.datetime.now()
    if not last_success_iso:
        return True
    try:
        last = datetime.datetime.fromisoformat(str(last_success_iso))
    except ValueError:
        return True
    return (now - last).total_seconds() > max_age_hours * 3600
```

- [ ] **Step 4: Add the Task Scheduler script**

```powershell
# scripts/schedule_codal_auto_update.ps1
param([switch]$Remove)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Py = ((python -c "import sys;print(sys.executable)") 2>$null)
if (-not $Py) { $Py = "python" }
$Py = "$Py".Trim()
$Id = "BorsCodalAutoUpdate"
if ($Remove) {
  Unregister-ScheduledTask -TaskName $Id -Confirm:$false -ErrorAction SilentlyContinue
  exit 0
}
$action = New-ScheduledTaskAction -Execute $Py `
  -Argument "`"$RepoRoot\dev\codal_auto_update.py`" --mode daily" `
  -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At "18:30"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
  -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
  -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
try {
  $p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
  Register-ScheduledTask -TaskName $Id -Action $action -Trigger $trigger `
    -Settings $settings -Principal $p `
    -Description "BorsTerminal no-ADB CODAL daily update" -Force | Out-Null
} catch {
  $p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $Id -Action $action -Trigger $trigger `
    -Settings $settings -Principal $p `
    -Description "BorsTerminal no-ADB CODAL daily update" -Force | Out-Null
}
```

- [ ] **Step 5: Add the startup catch-up hook (no block)**

```python
# app.py, inside the startup handler after the market sync/screener threads
def _codal_startup_catchup():
    try:
        import api._sync_codal as S
        st = S.read_auto_status()
        if S.should_auto_update(st.get("last_success")):
            import subprocess
            subprocess.Popen([sys.executable, os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "dev", "codal_auto_update.py"), "--mode", "daily"])
    except Exception as e:
        print("[startup] codal catch-up skipped:", e)

threading.Thread(target=_codal_startup_catchup, daemon=True).start()
```

`read_auto_status()` reads `codal_auto_status.json` and returns `{}` on any error; it is added to `api/_sync_codal.py`.

- [ ] **Step 6: Run the test and commit**

Run: `python dev/test_codal_schedule_v11.py` → `OK schedule/catch-up`.

```bash
git add scripts/schedule_codal_auto_update.ps1 api/_sync_codal.py app.py dev/test_codal_schedule_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): schedule the daily no-ADB update and startup catch-up"
```

---

### Task 7: Calendar Cat 6 + merge + client asset

**Files:**
- Modify: `dev/calendar_fetcher.py` (`--cats 6 --months 1 --merge`)
- Create/modify: `static/calendar/cache.json` / `calendar.json` asset
- Modify: `api/chart.py` (`upcoming_assemblies` reads the merged cache; a WORK_DIR override for the client)
- Test: `dev/test_calendar_merge_v11.py`

**Interfaces:**
- `merge_calendar(old: dict, new: dict) -> dict` de-duplicates by `(symbol, cat, date, title)` and preserves existing events; `meta.fetchedAt` updates; `meta.count` recomputed.
- The daily orchestrator calls `python dev/calendar_fetcher.py --cats 6 --months 1 --merge` (1 request; no ADB); the snapshot/publish includes `calendar.json`.

- [ ] **Step 1: Write the failing test**

```python
# dev/test_calendar_merge_v11.py
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
from calendar_merge import merge_calendar
old = {"meta": {"count": 1}, "events": [{"symbol": "A", "cat": "assembly",
       "date": "2026-10-30", "title": "مجمع A"}]}
new = {"meta": {}, "events": [{"symbol": "A", "cat": "assembly",
       "date": "2026-10-30", "title": "مجمع A"},
      {"symbol": "B", "cat": "capitalIncrease", "date": "2026-11-01",
       "title": "افزایش سرمایه B"}]}
m = merge_calendar(old, new)
assert m["meta"]["count"] == 2 and len(m["events"]) == 2, m
print("OK calendar merge")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_calendar_merge_v11.py`
Expected: `ModuleNotFoundError: dev.calendar_merge`.

- [ ] **Step 3: Implement the merge and the `--merge` mode**

```python
# dev/calendar_merge.py
def merge_calendar(old, new):
    seen, events = set(), []
    for ev in (list((old or {}).get("events") or []) +
               list((new or {}).get("events") or [])):
        key = (ev.get("symbol"), ev.get("cat"), ev.get("date"), ev.get("title"))
        if key in seen:
            continue
        seen.add(key)
        events.append(ev)
    meta = dict((old or {}).get("meta") or {})
    meta.update((new or {}).get("meta") or {})
    meta["count"] = len(events)
    return {"meta": meta, "events": events}
```

In `dev/calendar_fetcher.py`, add `ap.add_argument("--merge", action="store_true")`.
Replace the final cache write with:

```python
if args.merge and OUT.exists():
    old = json.loads(OUT.read_text(encoding="utf-8"))
    payload = merge_calendar(old, payload)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
```

The daily orchestrator calls:
`python dev/calendar_fetcher.py --cats 6 --months 1 --merge`
(one Category-6 request; no ADB). The client asset is copied to `calendar.json`
alongside the snapshot; `api/chart.upcoming_assemblies` reads
`WORK_DIR/calendar.json` first, then the bundled `static/calendar/cache.json`.

- [ ] **Step 4: Run the test**

Run: `python dev/test_calendar_merge_v11.py` → `OK calendar merge`.

- [ ] **Step 5: Commit**

```bash
git add dev/calendar_merge.py dev/calendar_fetcher.py api/chart.py dev/test_calendar_merge_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(calendar): merge Category 6 events and ship calendar.json"
```

---

### Task 8: Client meta check, auto-download, notification, freshness

**Files:**
- Modify: `api/_sync_codal.py` (`CODAL_DATA_TAG`, meta/calendar URL, `should_update`, `auto_check`, status)
- Modify: `api/_sync_codal.py` `_codal_db_worker` (download the tag assets; merge calendar)
- Modify: `app.py` (startup `auto_check` thread; no block)
- Create: `frontend/src/features/fundamental/api/useCodalAutoUpdate.ts`
- Modify: `frontend/src/features/fundamental/routes/FundamentalPage.tsx`, `ui/FtsScreenTable.tsx`
- Test: `dev/test_codal_client_meta_v11.py`, `frontend/src/__tests__/codal-auto-update.spec.tsx`

**Interfaces:**
- `CODAL_DATA_TAG = "data-codal"`; `CODAL_DB_URL = f"https://github.com/johnwarchief/BorsTerminal/releases/download/{tag}/codal.db.lzma"`; `CODAL_META_URL = .../codal.meta.json`; `CODAL_CAL_URL = .../calendar.json`.
- `should_update(local_meta: dict|None, remote_meta: dict) -> bool` compares `latest_financial_period`/`latest_monthly_period`/`published_at`.
- `auto_check()` runs in a daemon thread on startup/daily; if `should_update`, starts `_codal_db_worker` and writes `codal_db_status.json`; no CODAL/ADB.
- Frontend hook polls `/api/sync/codal/db-status`; shows a banner/toast (“دادهٔ بنیادی جدید”) and refreshes the screen on `done`; a setting to disable auto-update; the manual button remains.

- [ ] **Step 1: Write the failing Python test**

```python
# dev/test_codal_client_meta_v11.py
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from api._sync_codal import should_update
local = {"latest_financial_period": "1405/06/31", "latest_monthly_period": "1405/06/31"}
remote = {"latest_financial_period": "1405/06/31", "latest_monthly_period": "1405/07/30"}
assert should_update(local, remote) is True
assert should_update(remote, remote) is False
print("OK client meta compare")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `python dev/test_codal_client_meta_v11.py`
Expected: `ImportError: cannot import name 'should_update'`.

- [ ] **Step 3: Implement the data-tag URLs and meta compare**

```python
# api/_sync_codal.py
CODAL_DATA_TAG = "data-codal"
CODAL_BASE = ("https://github.com/johnwarchief/BorsTerminal/releases/download/"
              + CODAL_DATA_TAG)
CODAL_DB_URL = CODAL_BASE + "/codal.db.lzma"
CODAL_META_URL = CODAL_BASE + "/codal.meta.json"
CODAL_CAL_URL = CODAL_BASE + "/calendar.json"
AUTO_STATUS_PATH = os.path.join(WORK_DIR, "codal_auto_status.json")


def read_auto_status():
    try:
        with open(AUTO_STATUS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def should_update(local, remote):
    if not local:
        return True
    for key in ("latest_financial_period", "latest_monthly_period"):
        if str((remote or {}).get(key) or "") > str((local or {}).get(key) or ""):
            return True
    return False


def _local_meta():
    st = read_auto_status()
    return {"latest_financial_period": st.get("latest_financial_period"),
            "latest_monthly_period": st.get("latest_monthly_period")}


def auto_check():
    try:
        r = requests.get(CODAL_META_URL, timeout=(10, 30))
        r.raise_for_status()
        remote = r.json()
    except Exception:
        return {"checked": False, "update": False}
    if should_update(_local_meta(), remote):
        _write_db_status("downloading", 0, "دادهٔ بنیادی جدید — دریافت خودکار")
        _start_db_worker()
        return {"checked": True, "update": True, "meta": remote}
    return {"checked": True, "update": False, "meta": remote}
```

Add `meta`/`freshness` to the `/api/sync/codal/db-status` response. In `_codal_db_worker`, after the signature/integrity merge, download `CODAL_CAL_URL` to `WORK_DIR/calendar.json` (best-effort; a calendar failure must not roll back the CODAL merge). Start `auto_check` in a daemon thread from the `app.py` startup handler, before/after the market sync; it must not block the event loop.

- [ ] **Step 4: Add the frontend hook and banner**

```ts
// frontend/src/features/fundamental/api/useCodalAutoUpdate.ts
import { useEffect, useState } from 'react';
import { http } from '@shared/api/http';

export type CodalDbState = {
  running: boolean; stage: string; percent?: number; detail?: string;
  error?: string; meta?: Record<string, unknown>;
};

export function useCodalAutoUpdate() {
  const [state, setState] = useState<CodalDbState | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = () => http<{ db: CodalDbState }>('/api/sync/codal/db-status')
      .then((r) => { if (alive) setState(r.db); }).catch(() => {});
    tick();
    const id = setInterval(tick, 30000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  return state;
}
```

In `FundamentalPage.tsx`:
```tsx
const codal = useCodalAutoUpdate();
const [codalNotice, setCodalNotice] = useState(false);
useEffect(() => {
  if (codal?.stage === 'done') {
    setCodalNotice(true);
    void screen.refetch();
  }
}, [codal?.stage, screen]);
// render:
{codalNotice ? <div role="status">دادهٔ بنیادی به‌روز شد</div> : null}
{codal?.running ? <div role="status">
  {codal.stage === 'downloading'
    ? `دریافت دادهٔ بنیادی ${Math.round(codal.percent ?? 0)}٪`
    : 'در حال به‌روزرسانی دادهٔ بنیادی…'}
</div> : null}
{codal?.error ? <div role="alert">{codal.error}</div> : null}
```

The `FtsScreenTable` header shows the last update date/period from `codal.meta`; the manual
`fts-db-update` button stays. The hook/test mocks `http` and asserts the “دادهٔ بنیادی به‌روز شد”
and error states.

- [ ] **Step 5: Run the Python and frontend tests**

Run: `python dev/test_codal_client_meta_v11.py` → `OK client meta compare`.
Run: `cd frontend && npx vitest run src/__tests__/codal-auto-update.spec.tsx`.

- [ ] **Step 6: Commit**

```bash
git add api/_sync_codal.py app.py frontend/src/features/fundamental/api/useCodalAutoUpdate.ts frontend/src/features/fundamental/routes/FundamentalPage.tsx frontend/src/features/fundamental/ui/FtsScreenTable.tsx frontend/src/__tests__/codal-auto-update.spec.tsx dev/test_codal_client_meta_v11.py
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): auto-check and auto-merge the signed snapshot in the client"
```

**Client safety:** the worker must download to a temp file, verify minisign (`bors_minisign.verify_minisign` with `UPDATE_PUBKEY`), decompress, `integrity_check`, verify the three tables, then `_apply_codal_merge`; on any failure delete the temp files and keep the current data. The calendar asset is written to `WORK_DIR/calendar.json` and read via the `api/chart` WORK_DIR override.

---

### Task 9: Status, audit, gates, docs

**Files:**
- Modify: `api/_sync_codal.py` (`db-status` includes `meta`, `stage`, `freshness`)
- Create/modify: `dev/run_all_tests.py` suites, `docs/AGENT-INDEX.md`
- Test: all suites

- [ ] **Step 1: Add `codal_auto_status.json`/status fields**

The orchestrator writes `stage`, `mode`, `started_at`, `last_success`, `last_error`, `latest_periods`, `validation`, `published`; the client reads the last success. The UI shows “آخرین به‌روزرسانی بنیادی: … · آخرین دوره: …”.

- [ ] **Step 2: Register and run the gate**

Add to `dev/run_all_tests.py`:
```python
('dev/test_fts_updater_schema_v11.py', 'codal updater 26-col schema'),
('dev/test_codal_validation_v11.py', 'codal staging validation gates'),
('dev/test_codal_auto_update_v11.py', 'codal no-ADB orchestrator dry-run'),
('dev/test_codal_snapshot_meta_v11.py', 'codal snapshot meta'),
('dev/test_codal_publish_v11.py', 'codal publish dry-run/last-good'),
('dev/test_codal_schedule_v11.py', 'codal scheduler + startup catch-up'),
('dev/test_calendar_merge_v11.py', 'calendar Cat6 merge'),
('dev/test_codal_client_meta_v11.py', 'codal client meta compare'),
```

Run: `python dev/run_all_tests.py` and `cd frontend && npx vitest run`.
Run the live dry-run: `python dev/codal_auto_update.py --mode daily --dry-run` (no merge/publish) on a copy; record the request count/stages in `_audit/`.

- [ ] **Step 3: Regenerate `docs/AGENT-INDEX.md`**

Run: `python tools/build_agent_index.py`.

- [ ] **Step 4: Commit**

```bash
git add api/_sync_codal.py app.py dev/codal_auto_update.py dev/codal_validation.py dev/codal_fts_updater.py scripts/build_codal_snapshot.py scripts/publish_codal_snapshot.py scripts/schedule_codal_auto_update.ps1 dev/calendar_fetcher.py dev/calendar_merge.py static/calendar/cache.json frontend/src/features/fundamental/api/useCodalAutoUpdate.ts frontend/src/features/fundamental/routes/FundamentalPage.tsx frontend/src/features/fundamental/ui/FtsScreenTable.tsx dev/test_*.py frontend/src/__tests__/codal-auto-update.spec.tsx dev/run_all_tests.py docs/AGENT-INDEX.md
git -c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com commit -m "feat(codal): no-ADB daily pipeline, signed snapshot publish and client auto-update"
```

---

## Self-Review Checklist

- [ ] Spec Appendix 3 requirements: 7-request daily, no ADB steady-state, staging, validation, last-known-good, auto-publish, client notification/auto-merge, calendar Cat6, updater schema fix, no third-party.
- [ ] No placeholders; every task has a test and a commit.
- [ ] Names consistent: `feed_sync(cats, pages_per_cat)`, `validate_staging`, `run`, `build_snapshot`, `publish`, `should_auto_update`, `merge_calendar`.
- [ ] Tests use temp DBs/fake gh; no CODAL/GitHub/ADB calls.
- [ ] Failure leaves the previous snapshot and local data untouched.

## Execution Handoff

Choose: **Subagent-Driven (recommended)** or **Inline Execution**.
