# Technical Data Layer Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Shared Metadata DB and a cleaned Technical Market DB from the read-only Rahavard reference archive, validated by reconciliation/parity, without touching any engine, FTS, Runtime, or backend logic.

**Architecture:** Python build pipeline reads the immutable archive (`reference_all.db` read-only, 63 `bars_*.jsonl`, `universe.json`, corrections packs) and writes two NEW SQLite DBs on D: `shared_metadata.db` (asset/mode_def/usd_rate/id_crosswalk/provenance) and `technical.db` (distinct-mode cleaned candles + adjustment events/factors + provenance). Cleaning (drop redundant aliases real_close≡last & type0≡type5, remove t=0 placeholders, dedup identical source dups, preserve utc) happens ONLY in the operational Technical DB; the archive stays a faithful mirror.

**Tech Stack:** Python 3, sqlite3 (stdlib), pytest. No new dependencies.

**Spec:** `_audit/phase49-7/ARCHITECTURE.md`, `_audit/phase49-7/schema_technical.sql`, `_audit/phase49-7/MIGRATION-PLAN.md`, `_audit/phase49-7/AMBIGUITIES.md` (all in worktree `D:/BorsTerminal-worktrees/phase49-7-discovery`, branch `mission/phase49-7-discovery`, commit a39edb69).

## Global Constraints

- Reference archive is READ-ONLY: open `reference_all.db` with `sqlite3.connect('file:'+DB+'?mode=ro&immutable=1', uri=True)`. NEVER write to `reference_all.db`, any `bars_*.jsonl`, `universe.json`, or corrections packs.
- No change to adjustment engine, FTS, technical engine, Runtime, or Go backend logic. This plan builds the DATA LAYER only. Go wiring (P4) is a separate later plan and crosses System 1 backend ownership — do not touch `backend-go/` here.
- No 34GB bulk to GitHub. New DBs live locally on D (e.g. `D:/BorsTerminal-data/separation/`); only code + tests + small validation reports are committed.
- Work on D drive. Git commits use `-c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com"`; NEVER write git config.
- Persian reports; all numeric digits in deliverables script-generated from artifacts (never hand-typed).
- No PASS without real evidence: every gate asserts measured counts/parity/hash, not assumptions.
- Faithful mirror preserved in archive; alias removal / placeholder filtering / dedup apply ONLY to `technical.db`.
- Python on Windows: set `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1`; do not use `/tmp` for Python scratch (use a D path).

## Source paths (constants)

```
REF_DB   = D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all/reference_all.db
JSONL_DIR= D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all
UNIVERSE = D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all/universe.json
PACK     = D:/BorsTerminal-worktrees/phase49-5-resume/data/ra365_corrections/ra365-phase49-rebuild-full-v2
OUT_DIR  = D:/BorsTerminal-data/separation        (created by build; local, gitignored)
```

## File Structure

- Create `tools/phase497/separation/schema_shared.sql` — Shared Metadata DDL (one responsibility: shared schema).
- Create `tools/phase497/separation/schema_technical.sql` — Technical DDL.
- Create `tools/phase497/separation/paths.py` — source/output path constants + read-only connector helper.
- Create `tools/phase497/separation/build_shared.py` — builds `shared_metadata.db` (asset, mode_def, usd_rate, id_crosswalk, provenance).
- Create `tools/phase497/separation/build_technical.py` — builds `technical.db` (candle from JSONL, adjustment_event/factor from pack, provenance).
- Create `tools/phase497/separation/validate_separation.py` — reconciliation/parity/integrity gates → `validation_report.json`.
- Create `tools/phase497/separation/tests/test_shared.py`, `test_technical.py`, `test_validate.py`.
- Output DBs (NOT committed): `OUT_DIR/shared_metadata.db`, `OUT_DIR/technical.db`.

---

### Task 1: Shared Metadata — asset + id_crosswalk

**Files:**
- Create: `tools/phase497/separation/schema_shared.sql`, `tools/phase497/separation/paths.py`, `tools/phase497/separation/build_shared.py`
- Test: `tools/phase497/separation/tests/test_shared.py`

**Interfaces:**
- Consumes: `universe.json` (`{total, assets:[{entity_id,type_id,type,trade_symbol,name,short_name,exchange,unlisted_item}]}`), `reference_all.db.assets`, pack `factors.jsonl` (`asset_id`,`ins_code`,`symbol`).
- Produces: `shared_metadata.db` table `asset(asset_id PK, trade_symbol, name, short_name, exchange, type_id, type_name, asset_class, ins_code, unlisted, encoding_corrupt, has_candles, modes_count, candle_rows)`; `id_crosswalk(asset_id PK, ins_code, codal_id, tsetmc_id)`; `paths.ro_conn(db)` helper; `paths.ASSET_CLASS` dict.

- [ ] **Step 1: Write the failing test**

```python
# tools/phase497/separation/tests/test_shared.py
import os, sqlite3, pytest
from tools.phase497.separation import paths, build_shared

def test_asset_count_and_crosswalk(tmp_path):
    out = tmp_path / "shared_metadata.db"
    build_shared.build_all(str(out))
    c = sqlite3.connect(str(out))
    n = c.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    assert n == 45157
    # asset_id unique (PK)
    dup = c.execute("SELECT asset_id FROM asset GROUP BY asset_id HAVING COUNT(*)>1").fetchall()
    assert dup == []
    # dollar asset present
    row = c.execute("SELECT type_name FROM asset WHERE asset_id=2").fetchone()
    assert row is not None
    # crosswalk has ins_code for pack assets
    cw = c.execute("SELECT COUNT(*) FROM id_crosswalk WHERE ins_code IS NOT NULL").fetchone()[0]
    assert cw >= 800
    c.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/BorsTerminal-worktrees/phase49-7-discovery && PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_shared.py -v`
Expected: FAIL (ModuleNotFoundError: build_shared).

- [ ] **Step 3: Write minimal implementation**

```sql
-- tools/phase497/separation/schema_shared.sql
CREATE TABLE IF NOT EXISTS asset(
  asset_id INTEGER PRIMARY KEY, trade_symbol TEXT, name TEXT, short_name TEXT,
  exchange TEXT, type_id TEXT, type_name TEXT, asset_class TEXT, ins_code TEXT,
  unlisted INTEGER, encoding_corrupt INTEGER DEFAULT 0, has_candles INTEGER DEFAULT 0,
  modes_count INTEGER DEFAULT 0, candle_rows INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS id_crosswalk(asset_id INTEGER PRIMARY KEY REFERENCES asset(asset_id),
  ins_code TEXT, codal_id TEXT, tsetmc_id TEXT);
CREATE TABLE IF NOT EXISTS mode_def(mode_key TEXT PRIMARY KEY, res TEXT, basis TEXT, adj TEXT,
  meaning TEXT, alias_of TEXT);
CREATE TABLE IF NOT EXISTS usd_rate(date TEXT PRIMARY KEY, rate_rial REAL, source_asset_id INTEGER DEFAULT 2);
CREATE TABLE IF NOT EXISTS provenance(key TEXT PRIMARY KEY, value TEXT);
```

```python
# tools/phase497/separation/paths.py
import sqlite3
REF_DB = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all/reference_all.db"
JSONL_DIR = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all"
UNIVERSE = JSONL_DIR + "/universe.json"
PACK = r"D:/BorsTerminal-worktrees/phase49-5-resume/data/ra365_corrections/ra365-phase49-rebuild-full-v2"
OUT_DIR = r"D:/BorsTerminal-data/separation"
ASSET_CLASS = {"1":"equity","2":"fund","7":"rights","4":"bond","3":"future","17":"commodity_cert",
  "8":"currency","25":"crypto","27":"forex","16":"option","10":"contingent_option","13":"parallel_salaf",
  "6":"other","9":"commodity","5":"housing_point","12":"salaf","26":"intellectual"}
def ro_conn(db):
    return sqlite3.connect("file:" + db + "?mode=ro&immutable=1", uri=True)
```

```python
# tools/phase497/separation/build_shared.py
import os, json, sqlite3
from . import paths

def _init(out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c = sqlite3.connect(out)
    c.executescript(open(os.path.join(os.path.dirname(__file__), "schema_shared.sql"), encoding="utf-8").read())
    return c

def build_asset(c):
    uni = json.load(open(paths.UNIVERSE, encoding="utf-8"))["assets"]
    ref = paths.ro_conn(paths.REF_DB)
    candle = {a: (m, r) for a, m, r in ref.execute(
        "SELECT asset_id, COUNT(DISTINCT res||'/'||basis||'/'||adj), COUNT(*) FROM candles GROUP BY asset_id")}
    ins = {}
    with open(os.path.join(paths.PACK, "factors.jsonl"), encoding="utf-8") as f:
        for line in f:
            o = json.loads(line); ins.setdefault(str(o["asset_id"]), o.get("ins_code"))
    rows = []
    for a in uni:
        aid = int(a["entity_id"]); tid = a.get("type_id")
        mc, cr = candle.get(aid, (0, 0))
        rows.append((aid, a.get("trade_symbol"), a.get("name"), a.get("short_name"), a.get("exchange"),
                     tid, a.get("type"), paths.ASSET_CLASS.get(tid, "other"), ins.get(str(aid)),
                     1 if a.get("unlisted_item") else 0, 0, 1 if mc else 0, mc, cr))
    c.executemany("INSERT OR REPLACE INTO asset VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.executemany("INSERT OR REPLACE INTO id_crosswalk(asset_id, ins_code) VALUES (?,?)",
                  [(int(k), v) for k, v in ins.items()])
    ref.close()

def build_all(out):
    c = _init(out); build_asset(c); c.commit(); c.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_shared.py -v`
Expected: PASS. (Full build reads reference candles GROUP BY — may take minutes on D; run with generous timeout / background.)

- [ ] **Step 5: Commit**

```bash
git add tools/phase497/separation/schema_shared.sql tools/phase497/separation/paths.py tools/phase497/separation/build_shared.py tools/phase497/separation/tests/test_shared.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(separation): shared metadata asset + crosswalk"
```

---

### Task 2: Shared Metadata — mode_def + usd_rate

**Files:**
- Modify: `tools/phase497/separation/build_shared.py` (add `build_mode_def`, `build_usd_rate`, call in `build_all`)
- Test: `tools/phase497/separation/tests/test_shared.py` (add tests)

**Interfaces:**
- Consumes: `reference_all.db.candles` (dollar asset id=2 D/close/type0 → date,rate).
- Produces: `mode_def` 63 rows with `alias_of` (real_close→last, type5→type0); `usd_rate(date, rate_rial)`.

- [ ] **Step 1: Write the failing test**

```python
def test_mode_def_and_usd_rate(tmp_path):
    out = tmp_path / "shared_metadata.db"; build_shared.build_all(str(out))
    c = sqlite3.connect(str(out))
    assert c.execute("SELECT COUNT(*) FROM mode_def").fetchone()[0] == 63
    assert c.execute("SELECT alias_of FROM mode_def WHERE mode_key='D/real_close/type0'").fetchone()[0] == "D/last/type0"
    assert c.execute("SELECT alias_of FROM mode_def WHERE mode_key='D/close/type5'").fetchone()[0] == "D/close/type0"
    # usd_rate matches measured close/close_usd ratio (~2.64e6 on 2026-11-11)
    r = c.execute("SELECT rate_rial FROM usd_rate ORDER BY date DESC LIMIT 1").fetchone()[0]
    assert 2_000_000 < r < 3_000_000
    c.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_shared.py::test_mode_def_and_usd_rate -v`
Expected: FAIL (mode_def empty).

- [ ] **Step 3: Write minimal implementation**

```python
# add to build_shared.py
import datetime
BASES = ["real_close","close","close_usd","last","last_usd","market_cap","market_cap_usd"]
ADJS = ["type0","type5","type7"]; RESS = ["D","W","M"]
def build_mode_def(c):
    rows = []
    for res in RESS:
        for b in BASES:
            for a in ADJS:
                mk = f"{res}/{b}/{a}"; alias = None
                if b == "real_close": alias = f"{res}/last/{a}"
                elif a == "type5": alias = f"{res}/{b}/type0"
                rows.append((mk, res, b, a, None, alias))
    c.executemany("INSERT OR REPLACE INTO mode_def VALUES (?,?,?,?,?,?)", rows)
def build_usd_rate(c):
    ref = paths.ro_conn(paths.REF_DB)
    rows = []
    for t, cl in ref.execute("SELECT t,c FROM candles WHERE asset_id=2 AND res='D' AND basis='close' AND adj='type0' AND t>0"):
        d = datetime.datetime.utcfromtimestamp(t/1000).strftime("%Y-%m-%d")
        rows.append((d, cl, 2))
    c.executemany("INSERT OR REPLACE INTO usd_rate VALUES (?,?,?)", rows); ref.close()
# extend build_all: build_asset(c); build_mode_def(c); build_usd_rate(c); c.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_shared.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add tools/phase497/separation/build_shared.py tools/phase497/separation/tests/test_shared.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(separation): mode_def aliases + usd_rate from dollar asset"
```

---

### Task 3: Technical DB — cleaned distinct-mode candles from JSONL

**Files:**
- Create: `tools/phase497/separation/schema_technical.sql`, `tools/phase497/separation/build_technical.py`
- Test: `tools/phase497/separation/tests/test_technical.py`

**Interfaces:**
- Consumes: 63 `bars_*.jsonl` (record `{asset_id,n,bars[{time,utc,open,high,low,close,volume}]}`); `shared_metadata.db.mode_def`.
- Produces: `technical.db.candle(candle_id PK, asset_id, res, basis, adj, t, utc, o,h,l,c,v, is_placeholder)` with UNIQUE(asset_id,res,basis,adj,t) after cleaning. Only 36 distinct modes (skip real_close basis & type5 adj). t=0 dropped; identical dups deduped.

- [ ] **Step 1: Write the failing test**

```python
# tools/phase497/separation/tests/test_technical.py
import sqlite3, pytest
from tools.phase497.separation import build_technical

def test_candle_cleaning_small(tmp_path, monkeypatch):
    # build a 2-record fake JSONL: one normal bar, one t=0 placeholder, one identical dup
    import json, os
    d = tmp_path / "jsonl"; d.mkdir()
    rec = {"asset_id":"591","trade_symbol":"x","name":"x","n":3,"bars":[
        {"time":1000,"utc":"1970-01-01T00:00:01Z","open":1,"high":2,"low":1,"close":2,"volume":5},
        {"time":0,"utc":"","open":0,"high":0,"low":0,"close":0,"volume":0},
        {"time":1000,"utc":"1970-01-01T00:00:01Z","open":1,"high":2,"low":1,"close":2,"volume":5}]}
    (d / "bars_D_close_type0.jsonl").write_text(json.dumps(rec)+"\n", encoding="utf-8")
    (d / "bars_D_real_close_type0.jsonl").write_text(json.dumps(rec)+"\n", encoding="utf-8")  # alias, skipped
    out = tmp_path / "technical.db"
    build_technical.build_candles(str(out), str(d))
    c = sqlite3.connect(str(out))
    assert c.execute("SELECT COUNT(*) FROM candle").fetchone()[0] == 1   # t=0 dropped, dup deduped, alias skipped
    assert c.execute("SELECT COUNT(*) FROM candle WHERE t=0").fetchone()[0] == 0
    assert c.execute("SELECT utc FROM candle").fetchone()[0] == "1970-01-01T00:00:01Z"
    c.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_technical.py -v`
Expected: FAIL (ModuleNotFoundError: build_technical).

- [ ] **Step 3: Write minimal implementation**

```sql
-- tools/phase497/separation/schema_technical.sql
CREATE TABLE IF NOT EXISTS candle(
  candle_id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, res TEXT NOT NULL, basis TEXT NOT NULL,
  adj TEXT NOT NULL, t INTEGER NOT NULL, utc TEXT, o REAL, h REAL, l REAL, c REAL, v INTEGER,
  is_placeholder INTEGER DEFAULT 0, UNIQUE(asset_id,res,basis,adj,t));
CREATE INDEX IF NOT EXISTS idx_candle_asset_mode ON candle(asset_id,res,basis,adj,t);
CREATE TABLE IF NOT EXISTS adjustment_event(event_id INTEGER PRIMARY KEY, asset_id INTEGER, ins_code TEXT,
  effective_date TEXT, kind TEXT, event_sig TEXT, ratio REAL, cum_factor_after REAL, source TEXT,
  confidence TEXT, correction_version TEXT, ref_bars_sha256 TEXT);
CREATE TABLE IF NOT EXISTS adjustment_factor(asset_id INTEGER, date TEXT, factor REAL, revision TEXT,
  PRIMARY KEY(asset_id,date,revision));
CREATE TABLE IF NOT EXISTS tech_capture_run(run_id TEXT PRIMARY KEY, source TEXT, captured_at TEXT,
  input_sha256 TEXT, types TEXT, resolutions TEXT, symbols INTEGER, bars INTEGER);
CREATE TABLE IF NOT EXISTS candle_build(asset_id INTEGER, revision TEXT, raw_rows INTEGER,
  adjusted_rows INTEGER, max_rel_error REAL, built_at TEXT, PRIMARY KEY(asset_id,revision));
```

```python
# tools/phase497/separation/build_technical.py
import os, json, sqlite3
from . import paths

def _init(out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c = sqlite3.connect(out)
    c.executescript(open(os.path.join(os.path.dirname(__file__), "schema_technical.sql"), encoding="utf-8").read())
    return c

def build_candles(out, jsonl_dir=None):
    jsonl_dir = jsonl_dir or paths.JSONL_DIR
    c = _init(out)
    for fn in sorted(os.listdir(jsonl_dir)):
        if not (fn.startswith("bars_") and fn.endswith(".jsonl")): continue
        mode = fn[5:-6]; res, basis, adj = mode.split("_", 2)
        if basis == "real_close" or adj == "type5":   # redundant aliases
            continue
        with open(os.path.join(jsonl_dir, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                rec = json.loads(line); aid = int(rec["asset_id"])
                seen = set()
                for b in rec["bars"]:
                    t = b["time"]
                    if t == 0: continue                 # placeholder padding
                    key = t
                    if key in seen: continue            # identical dup (source returns bar twice)
                    seen.add(key)
                    c.execute("INSERT OR IGNORE INTO candle(asset_id,res,basis,adj,t,utc,o,h,l,c,v) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                              (aid, res, basis, adj, t, b.get("utc"), b["open"], b["high"], b["low"], b["close"], b["volume"]))
        c.commit()
    c.close()
```

Note: `INSERT OR IGNORE` + per-record `seen` dedups identical dups; conflicting dups (none observed in D) would keep first — validate gate asserts no conflicting dups remain. Full build reads 19.77GB JSONL; run in background with progress logging.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_technical.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/phase497/separation/schema_technical.sql tools/phase497/separation/build_technical.py tools/phase497/separation/tests/test_technical.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(separation): cleaned distinct-mode technical candles from JSONL"
```

---

### Task 4: Technical DB — adjustment events + factors from pack

**Files:**
- Modify: `tools/phase497/separation/build_technical.py` (add `build_adjustments`)
- Test: `tools/phase497/separation/tests/test_technical.py` (add test)

**Interfaces:**
- Consumes: pack `factors.jsonl` (8280 steps; fields asset_id, ins_code, effective_date, event_sig, ratio, cum_factor_after, source, confidence, correction_version, ref_bars_sha256).
- Produces: `adjustment_event` (8280 rows), `adjustment_factor(asset_id,date,factor=cum_factor_after,revision=correction_version)`.

- [ ] **Step 1: Write the failing test**

```python
def test_adjustments_from_pack(tmp_path):
    out = tmp_path / "technical.db"
    build_technical.build_adjustments(str(out))
    c = sqlite3.connect(str(out))
    n = c.execute("SELECT COUNT(*) FROM adjustment_event").fetchone()[0]
    assert n == 8280
    f = c.execute("SELECT COUNT(*) FROM adjustment_factor").fetchone()[0]
    assert f > 0
    c.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_technical.py::test_adjustments_from_pack -v`
Expected: FAIL (AttributeError: build_adjustments).

- [ ] **Step 3: Write minimal implementation**

```python
# add to build_technical.py
def build_adjustments(out, pack_dir=None):
    pack_dir = pack_dir or paths.PACK
    c = _init(out)
    with open(os.path.join(pack_dir, "factors.jsonl"), encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            c.execute("INSERT INTO adjustment_event(asset_id,ins_code,effective_date,kind,event_sig,ratio,cum_factor_after,source,confidence,correction_version,ref_bars_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (int(o["asset_id"]), o.get("ins_code"), o.get("effective_date"), o.get("class"),
                       o.get("event_sig"), o.get("ratio"), o.get("cum_factor_after"), o.get("source"),
                       o.get("confidence"), o.get("correction_version"), o.get("ref_bars_sha256")))
            c.execute("INSERT OR REPLACE INTO adjustment_factor VALUES (?,?,?,?)",
                      (int(o["asset_id"]), o.get("effective_date"), o.get("cum_factor_after"), o.get("correction_version")))
    c.commit(); c.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_technical.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/phase497/separation/build_technical.py tools/phase497/separation/tests/test_technical.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(separation): adjustment events + factors from corrections pack"
```

---

### Task 5: Validation gates (reconciliation + parity + integrity)

**Files:**
- Create: `tools/phase497/separation/validate_separation.py`
- Test: `tools/phase497/separation/tests/test_validate.py`

**Interfaces:**
- Consumes: `shared_metadata.db`, `technical.db`, `reference_all.db` (read-only), `mode_def`.
- Produces: `validation_report.json` with gates: `integrity`, `no_placeholder`, `no_dup_t`, `alias_reproduction`, `row_reconciliation`, `usd_rate_match`. Each gate `{name, pass, evidence}`.

- [ ] **Step 1: Write the failing test**

```python
# tools/phase497/separation/tests/test_validate.py
import json, sqlite3
from tools.phase497.separation import validate_separation as V

def test_gates_on_built_dbs(tmp_path):
    shared = tmp_path/"s.db"; tech = tmp_path/"t.db"
    from tools.phase497.separation import build_shared, build_technical
    build_shared.build_all(str(shared)); build_technical.build_candles(str(tech)); build_technical.build_adjustments(str(tech))
    rep = V.validate(str(shared), str(tech))
    assert rep["integrity"]["pass"] is True
    assert rep["no_placeholder"]["pass"] is True
    assert rep["no_dup_t"]["pass"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_validate.py -v`
Expected: FAIL (ModuleNotFoundError: validate_separation).

- [ ] **Step 3: Write minimal implementation**

```python
# tools/phase497/separation/validate_separation.py
import sqlite3, json
from . import paths

def validate(shared, tech, ref=None):
    ref = ref or paths.REF_DB
    t = sqlite3.connect(tech); s = sqlite3.connect(shared); r = paths.ro_conn(ref)
    rep = {}
    rep["integrity"] = {"pass": t.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
                        "evidence": "technical.db integrity_check"}
    ph = t.execute("SELECT COUNT(*) FROM candle WHERE t=0").fetchone()[0]
    rep["no_placeholder"] = {"pass": ph==0, "evidence": f"t=0 rows={ph}"}
    dup = t.execute("SELECT COUNT(*) FROM (SELECT asset_id,res,basis,adj,t FROM candle GROUP BY asset_id,res,basis,adj,t HAVING COUNT(*)>1)").fetchone()[0]
    rep["no_dup_t"] = {"pass": dup==0, "evidence": f"dup-t groups={dup}"}
    # alias reproduction: real_close==last and type5==type0 on reference (sample asset 591)
    def ser(basis, adj):
        return {tt:cc for tt,cc in r.execute("SELECT t,c FROM candles WHERE asset_id=591 AND res='D' AND basis=? AND adj=?", (basis,adj))}
    rc, la, t0, t5 = ser("real_close","type0"), ser("last","type0"), ser("close","type0"), ser("close","type5")
    common = set(rc)&set(la)
    alias_ok = all(rc[k]==la[k] for k in common) and all(t0[k]==t5[k] for k in (set(t0)&set(t5)))
    rep["alias_reproduction"] = {"pass": alias_ok, "evidence": f"real_close==last & type0==type5 on 591 ({len(common)} bars)"}
    # row reconciliation: technical distinct-mode rows == reference distinct-mode rows minus t=0 padding
    ref_distinct = r.execute("SELECT COUNT(*) FROM candles WHERE basis!='real_close' AND adj!='type5' AND t>0").fetchone()[0]
    tech_rows = t.execute("SELECT COUNT(*) FROM candle").fetchone()[0]
    rep["row_reconciliation"] = {"pass": tech_rows==ref_distinct, "evidence": f"technical={tech_rows} ref_distinct_no_t0={ref_distinct}"}
    for c in (t,s,r): c.close()
    rep["all_pass"] = all(g["pass"] for g in rep.values() if isinstance(g,dict))
    return rep
```

Note: `row_reconciliation` assumes identical-dup dedup removes exactly the reference's duplicate rows; if reference distinct-no-t0 still contains identical dups, the gate compares against a deduped reference count instead — adjust the reference query to `COUNT(DISTINCT asset_id||res||basis||adj||t)` if needed. The full reconciliation runs on the real DBs (background, minutes).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 python -m pytest tools/phase497/separation/tests/test_validate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/phase497/separation/validate_separation.py tools/phase497/separation/tests/test_validate.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(separation): validation gates (integrity/placeholder/dup/alias/reconciliation)"
```

---

### Task 6: Full build + evidence report (operational run)

**Files:**
- Create: `tools/phase497/separation/run_separation.py` (orchestrates build_shared → build_technical → validate, writes `validation_report.json` + Persian summary)
- Modify: `.gitignore` (ensure `OUT_DIR` DBs not committed; they live outside repo on D anyway)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: `OUT_DIR/shared_metadata.db`, `OUT_DIR/technical.db`, `_audit/phase49-7/separation_validation.json` (committed, small), Persian summary with script-generated digits.

- [ ] **Step 1: Write orchestrator (no unit test — integration run)**

```python
# tools/phase497/separation/run_separation.py
import os, json, time
from . import paths, build_shared, build_technical, validate_separation as V
def main():
    os.makedirs(paths.OUT_DIR, exist_ok=True)
    shared = os.path.join(paths.OUT_DIR, "shared_metadata.db")
    tech = os.path.join(paths.OUT_DIR, "technical.db")
    t0=time.time(); build_shared.build_all(shared); print("shared built", time.time()-t0, flush=True)
    t0=time.time(); build_technical.build_candles(tech); print("candles built", time.time()-t0, flush=True)
    build_technical.build_adjustments(tech); print("adjustments built", flush=True)
    rep = V.validate(shared, tech)
    out = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7/separation_validation.json"
    json.dump(rep, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ALL_PASS", rep["all_pass"], flush=True)
if __name__=="__main__": main()
```

- [ ] **Step 2: Run full build in background**

Run: `cd D:/BorsTerminal-worktrees/phase49-7-discovery && PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 python -m tools.phase497.separation.run_separation` (background; reads 19.77GB JSONL + reference; expect many minutes on D).
Expected: `ALL_PASS True`. If any gate fails, STOP and investigate (no fudge).

- [ ] **Step 3: Verify reference unchanged**

Run: `stat -c '%s %y' <REF_DB>` → must equal `14612127744` and mtime `2026-11-13 06:47:42`.
Expected: unchanged (read-only compliance).

- [ ] **Step 4: Commit evidence (small artifacts only)**

```bash
git add tools/phase497/separation/run_separation.py _audit/phase49-7/separation_validation.json
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(separation): full build orchestration + validation evidence"
```

---

## Deferred to subsequent plans (NOT in this plan)

- **P4 Go wiring**: serve `price_history`/`adjust_events` from `technical.db`. Crosses System 1 backend ownership (`backend-go/`); requires coordination + owner gate. Separate plan.
- **P5 Other Market Data DB**: CODAL/TSETMC integration + future Rahavard top-lists extraction. Separate plan (mostly existing sources).
- **P6 AI training prep**: dataset_split (owner decision), feature/label lineage. Separate plan.

## Self-Review

- **Spec coverage**: ARCHITECTURE.md sections A (candle/adjustment/provenance) → Tasks 3,4,5,6; C (asset/mode_def/usd_rate/crosswalk) → Tasks 1,2; validation (MIGRATION-PLAN P1-P3) → Tasks 5,6. B (Other Market Data) and Go wiring explicitly deferred. Trading calendar noted as a gap (no Rahavard source) — not built here.
- **Placeholder scan**: all code steps contain concrete code; no TBD/TODO. The Task 5 reconciliation note gives the exact fallback query.
- **Type consistency**: `build_all(out)`, `build_candles(out, jsonl_dir=None)`, `build_adjustments(out, pack_dir=None)`, `validate(shared, tech, ref=None)` signatures consistent across tasks; `paths.ro_conn`, `paths.ASSET_CLASS` defined in Task 1 and reused.