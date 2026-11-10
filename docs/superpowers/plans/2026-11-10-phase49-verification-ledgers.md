# Phase 4.9.1 — Plan B: Reference Capture & Verification Ledgers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture independent Rahavard reference for the agreed universe, then produce the step ledger (8,280 steps + 28 invalid), the symbol ledger (6,103 rows), the anomaly ledger, and the inventory reconciliation.

**Architecture:** Small, testable Python data stages under `_audit/phase49-full-verification/`, driven by a tracked rules file. Each stage reads only copies, writes an intermediate artifact plus a SHA manifest, and never touches production DBs. Status classification is rule-driven and evidence-tiered (`O1/O2/R1/R2/I1`).

**Tech Stack:** Python 3.12, SQLite, Rahavard capture tooling (`capture_rahavard.mjs`, `import_capture.py`), Node 22.

**Spec:** [docs/superpowers/specs/2026-11-10-phase49-full-verification-design.md](../specs/2026-11-10-phase49-full-verification-design.md)

## Global Constraints

- Raw captures never enter Git; they live only under `_audit/phase49-full-verification/captures/`.
- No fabricated candles, factors, or events; missing evidence stays `INSUFFICIENT_EVIDENCE`/`BLOCKED_SOURCE`.
- No threshold changes: `FACTOR_EXACT=1e-3`, `FACTOR_MATERIAL=1e-2`, `OHLC_MATERIAL=5e-2`, `EXACT_EQ=1e-9`, `DEDUPE_RATIO_TOL=1e-2`.
- All work on copies; `market.db` and the old Seed Candidate are read-only.
- Capture runs in the owner's logged-in browser session; never read/store credentials or cookies.

---

### Task B0: Baseline snapshot

**Files:**
- Create: `_audit/phase49-full-verification/stage00_baseline.py`
- Create: `_audit/phase49-full-verification/test_stage00_baseline.py`
- Create: `_audit/phase49-full-verification/evidence/baseline.json`

**Interfaces:**
- CLI: `--db <seed> --pack <v2> --captures <dir> --out <baseline.json>`
- Output records HEAD, DB SHA-256/size, pack manifest counts and file SHAs, capture file SHAs, and tool versions.

- [ ] **Step 1: Write the failing test**

Create `test_stage00_baseline.py`:
```python
#!/usr/bin/env python3
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage00_baseline as S  # noqa: E402


def main():
    rep = S.snapshot(pack=r"data/ra365_corrections/ra365-phase49-rebuild-full-v2",
                     db=r"_audit/phase49-finalization/seed/market.db")
    assert rep["head"] == S.git_head()
    assert rep["pack"]["counts"]["steps"] == 8280, rep["pack"]
    assert len(rep["pack"]["factors_sha256"]) == 64
    assert len(rep["db"]["sha256"]) == 64
    assert rep["db"]["price_history_rows"] == 511139
    assert rep["db"]["symbols_with_history"] == 6103
    print("BASELINE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage00_baseline.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage00_baseline.py`:
```python
#!/usr/bin/env python3
import argparse, hashlib, json, os, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()


def snapshot(pack, db):
    manifest = json.load(open(os.path.join(pack, "manifest.json"), encoding="utf-8"))
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    rows = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    syms = con.execute("SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0]
    validity = dict(con.execute(
        "SELECT status,COUNT(*) FROM history_validity GROUP BY status"))
    con.close()
    return {
        "head": git_head(),
        "pack": {"version": manifest.get("version"),
                 "counts": manifest.get("counts"),
                 "factors_sha256": sha256(os.path.join(pack, "factors.jsonl")),
                 "manifest_sha256": sha256(os.path.join(pack, "manifest.json"))},
        "db": {"sha256": sha256(db), "size": os.path.getsize(db),
               "price_history_rows": rows, "symbols_with_history": syms,
               "validity": validity},
        "python": sys.version,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rep = snapshot(a.pack, a.db)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and write the baseline**

Run:
```bash
python _audit/phase49-full-verification/test_stage00_baseline.py
python _audit/phase49-full-verification/stage00_baseline.py \
  --db _audit/phase49-finalization/seed/market.db \
  --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \
  --out _audit/phase49-full-verification/evidence/baseline.json
```
Expected: SHA-256 and counts match the spec's measured baseline.

- [ ] **Step 5: Commit**
```bash
git add _audit/phase49-full-verification/stage00_baseline.py _audit/phase49-full-verification/test_stage00_baseline.py _audit/phase49-full-verification/evidence/baseline.json
git commit -m "feat(phase49): snapshot baseline pack, DB, and counts"
```

---

### Task B0b: Stage manifest helper

**Files:**
- Create: `dev/phase49_manifest.py`
- Create: `dev/test_phase49_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `dev/test_phase49_manifest.py`:
```python
#!/usr/bin/env python3
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phase49_manifest as M  # noqa: E402


def main():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "in.txt")
    open(p, "w", encoding="utf-8").write("x")
    out = os.path.join(tmp, "manifest.json")
    M.write_manifest("stage-test", [p], [], {"rows": 1}, out)
    d = json.load(open(out, encoding="utf-8"))
    assert d["stage"] == "stage-test"
    assert len(d["inputs"][p]) == 64
    assert d["counts"]["rows"] == 1
    print("MANIFEST TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Implement**

Create `dev/phase49_manifest.py`:
```python
#!/usr/bin/env python3
import hashlib, json, os, time


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(stage, inputs, outputs, counts, out_path):
    payload = {
        "stage": stage,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {p: sha256(p) for p in inputs if os.path.isfile(p)},
        "outputs": {p: sha256(p) for p in outputs if os.path.isfile(p)},
        "counts": counts,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return payload
```

- [ ] **Step 3: Run and wire**

Run: `python dev/test_phase49_manifest.py` → `MANIFEST TESTS OK`.
Every stage's `main` calls `write_manifest` with its inputs, outputs, and row counts, writing to `evidence/<stage>.manifest.json`. Add the call to B0, B2, B3, B5, B6, B7, B8, B9, and the Plan C stages.

- [ ] **Step 4: Commit**
```bash
git add dev/phase49_manifest.py dev/test_phase49_manifest.py
git commit -m "feat(phase49): add stage manifest helper with input/output hashes"
```

---

### Task B1: Shared symbol identity module

**Files:**
- Create: `dev/symbol_identity.py`
- Create: `dev/test_symbol_identity.py`

**Interfaces:**
- `key(text) -> str` normalizes Arabic/Persian kaf/yeh, removes separators, lowercases.
- `load_instruments(con) -> dict[str, dict]` maps normalized `l_val18` to `{symbol, ins_code, isin, paper_type, name, updated_at}`; duplicate keys prefer rows with ISIN, then `paper_type in (1,2,8)`, then latest `updated_at`, then ins_code.

- [ ] **Step 1: Write the failing test**

Create `dev/test_symbol_identity.py`:
```python
#!/usr/bin/env python3
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import symbol_identity as SI  # noqa: E402


def main():
    assert SI.key("كگل") == SI.key("کگل")
    assert SI.key("شبندر ") == SI.key("شبندر")
    assert SI.key("آب\u200cس") == SI.key("آبس")
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE instruments(
        ins_code TEXT, l_val18 TEXT, l_val30 TEXT, paper_type INTEGER,
        isin TEXT, updated_at TEXT)""")
    con.execute("INSERT INTO instruments VALUES('1','كگل','الف',1,NULL,'2026-01-01')")
    con.execute("INSERT INTO instruments VALUES('2','کگل','ب',1,'I','2025-01-01')")
    con.execute("INSERT INTO instruments VALUES('3','فولاد','ج',8,NULL,'2026-02-01')")
    con.commit()
    m = SI.load_instruments(con)
    assert m[SI.key("کگل")]["ins_code"] == "2", m
    assert m[SI.key("فولاد")]["ins_code"] == "3"
    con.close()
    os.unlink(path)
    print("SYMBOL IDENTITY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python dev/test_symbol_identity.py`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `dev/symbol_identity.py`:
```python
#!/usr/bin/env python3
"""One normalization rule for symbol identity across ledgers and events."""
from __future__ import annotations

KEY_TABLE = str.maketrans({"\u064a": "\u06cc", "\u0643": "\u06a9", "\u0649": "\u06cc"})
KEY_SEPS = (" ", "\u00a0", "\u200c", "\u200f", "\u200e", "\u202f")


def key(text) -> str:
    s = "" if text is None else str(text)
    for sep in KEY_SEPS:
        s = s.replace(sep, "")
    return s.translate(KEY_TABLE).lower()


def load_instruments(con) -> dict:
    out = {}
    for r in con.execute(
            "SELECT ins_code,l_val18,l_val30,paper_type,isin,updated_at "
            "FROM instruments ORDER BY ins_code"):
        raw = r[1]
        if not raw or not str(raw).strip():
            continue
        k = key(raw)
        cand = (0 if r[4] else 1, 0 if r[3] in (1, 2, 8) else 1,
                str(r[5] or ""), str(r[0]))
        cur = out.get(k)
        curk = (0 if cur and cur["isin"] else 1,
                0 if cur and cur["paper_type"] in (1, 2, 8) else 1,
                str(cur["updated_at"] or "") if cur else "",
                cur["ins_code"] if cur else "")
        if cur is None or cand > curk:
            out[k] = {"symbol": str(raw).strip(), "ins_code": str(r[0]),
                      "name": r[2], "paper_type": r[3], "isin": r[4],
                      "updated_at": r[5]}
    return out
```

- [ ] **Step 4: Cross-check against the frozen selector**

Append to the test:
```python
    import importlib.util
    p = os.path.join(HERE, "..", "tools", "phase45", "select_symbols.py")
    spec = importlib.util.spec_from_file_location("select_symbols", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for s in ("كگل", "کگل", "شبندر ", "آب\u200cس"):
        assert mod.key(s) == SI.key(s), s
```
Run: `python dev/test_symbol_identity.py`; expected `SYMBOL IDENTITY TESTS OK`.

- [ ] **Step 5: Commit**
```bash
git add dev/symbol_identity.py dev/test_symbol_identity.py
git commit -m "feat(phase49): add shared symbol identity normalization and tests"
```

---

### Task B2: Capture plan builder

**Files:**
- Create: `_audit/phase49-full-verification/stage01_capture_plan.py`
- Create: `_audit/phase49-full-verification/test_stage01_capture_plan.py`

**Interfaces:**
- CLI: `--db <market.db> --pack <v2 pack> --live-pack <ra365-live40-v1> --out-dir <dir> [--min-span-days 365]`
- Outputs:
  - `symbols.json` — list of `{asset_id, symbol, ins_code, basis: "real_close", source}` for capture.
  - `capture-unmapped.json` — symbols with no asset_id, with `reason`.
  - `capture-plan.json` — counts by source and the exact union.

- [ ] **Step 1: Write the failing test**

Create `_audit/phase49-full-verification/test_stage01_capture_plan.py`:
```python
#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage01_capture_plan as S  # noqa: E402


def make_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_history(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT)")
    con.execute("CREATE TABLE instruments(ins_code TEXT,l_val18 TEXT,l_val30 TEXT,paper_type INTEGER,isin TEXT,updated_at TEXT)")
    con.execute("INSERT INTO instruments VALUES('11','الف','الف',1,NULL,'2026-01-01')")
    con.execute("INSERT INTO price_history VALUES('الف','2020-01-01',1,1,1,1,1,1,NULL,'x')")
    con.execute("INSERT INTO price_history VALUES('الف','2021-01-01',1,1,1,1,1,1,NULL,'x')")
    con.execute("INSERT INTO price_history VALUES('ب','2026-01-01',1,1,1,1,1,1,NULL,'x')")
    con.commit(); con.close()


def make_pack(path, rows):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "factors.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "market.db"); make_db(db)
    pack = os.path.join(tmp, "pack"); make_pack(pack, [
        {"symbol": "الف", "asset_id": "1", "validity": "unverified"},
        {"symbol": "ب", "asset_id": "2", "validity": "verified"}])
    live = os.path.join(tmp, "live"); make_pack(live, [
        {"symbol": "الف", "asset_id": "1"}, {"symbol": "ب", "asset_id": "2"},
        {"symbol": "ج", "asset_id": "3"}])
    out = os.path.join(tmp, "out"); os.makedirs(out)
    S.build(db, pack, live, out, min_span_days=365)
    syms = {s["symbol"]: s for s in json.load(open(os.path.join(out, "symbols.json"), encoding="utf-8"))}
    assert "الف" in syms and "ب" not in syms and "ج" not in syms, syms
    assert syms["الف"]["asset_id"] == 1
    plan = json.load(open(os.path.join(out, "capture-plan.json"), encoding="utf-8"))
    assert plan["counts"]["pack_unverified"] == 1
    assert plan["counts"]["long_history"] == 1
    print("CAPTURE PLAN TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: symbol `ج` is not in the DB, so it must not be selected; only pack-unverified and long-history symbols are in scope.

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage01_capture_plan.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage01_capture_plan.py` with:
```python
#!/usr/bin/env python3
import argparse, json, os, sqlite3, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "dev"))
from symbol_identity import key, load_instruments  # noqa: E402

SIX = ("شنفت", "فافق", "فخاس", "فولاژ", "لخزر", "مارون")


def load_pack(path):
    rows = []
    with open(os.path.join(path, "factors.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def asset_map(rows):
    out, ambiguous = {}, set()
    for r in rows:
        k = key(r.get("symbol"))
        aid = r.get("asset_id")
        if not k or aid in (None, ""):
            continue
        if k in out and str(out[k]) != str(aid):
            ambiguous.add(k)
        out.setdefault(k, aid)
    return out, ambiguous


def long_history(db, min_span_days):
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    out = {}
    for sym, first, last in con.execute(
            "SELECT symbol, MIN(date), MAX(date) FROM price_history GROUP BY symbol"):
        try:
            span = (date.fromisoformat(str(last)) - date.fromisoformat(str(first))).days
        except ValueError:
            continue
        if span >= min_span_days:
            out[sym] = span
    con.close()
    return out


def build(db, pack, live_pack, out_dir, min_span_days=365, extra=None):
    pack_rows = load_pack(pack)
    unverified = {r["symbol"] for r in pack_rows
                  if r.get("validity") == "unverified"}
    long_syms = long_history(db, min_span_days)
    wanted = set(unverified) | set(long_syms) | set(SIX) | set(extra or [])
    live_map, ambiguous = asset_map(load_pack(live_pack))
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    inst = load_instruments(con); con.close()
    symbols, unmapped = [], []
    for sym in sorted(wanted):
        k = key(sym)
        aid = live_map.get(k)
        ins = inst.get(k, {})
        if aid is None:
            unmapped.append({"symbol": sym, "reason": "NO_ASSET_ID"})
            continue
        sources = []
        if sym in unverified: sources.append("pack-unverified")
        if sym in long_syms: sources.append("long-history")
        if sym in SIX: sources.append("short-history-six")
        symbols.append({"asset_id": int(aid) if str(aid).isdigit() else aid,
                        "symbol": sym, "ins_code": ins.get("ins_code", ""),
                        "basis": "real_close", "source": ",".join(sources)})
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "symbols.json"), "w", encoding="utf-8") as fh:
        json.dump(symbols, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "capture-unmapped.json"), "w", encoding="utf-8") as fh:
        json.dump(unmapped, fh, ensure_ascii=False, indent=1)
    plan = {"counts": {"pack_unverified": len(unverified),
                       "long_history": len(long_syms),
                       "short_history_six": len(SIX),
                       "union": len(wanted),
                       "mapped": len(symbols), "unmapped": len(unmapped),
                       "ambiguous_asset_keys": sorted(ambiguous)},
            "min_span_days": min_span_days}
    with open(os.path.join(out_dir, "capture-plan.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--live-pack", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--min-span-days", type=int, default=365)
    ap.add_argument("--extra-symbols", default="")
    a = ap.parse_args()
    extra = (json.load(open(a.extra_symbols, encoding="utf-8"))
             if a.extra_symbols else [])
    plan = build(a.db, a.pack, a.live_pack, a.out_dir, a.min_span_days, extra)
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

Run: `python _audit/phase49-full-verification/test_stage01_capture_plan.py`
Expected: `CAPTURE PLAN TESTS OK`.

- [ ] **Step 5: Build the real plan**

Run:
```bash
python _audit/phase49-full-verification/stage01_capture_plan.py \
  --db _audit/phase49-finalization/seed/market.db \
  --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \
  --live-pack data/ra365_corrections/ra365-live40-v1 \
  --out-dir _audit/phase49-full-verification/capture-plan
```
Expected: `capture-plan.json` with the exact union and `capture-unmapped.json` listing only truly unmapped symbols. Do not guess asset IDs; unmapped symbols stay `NO_ASSET_ID`.

- [ ] **Step 6: Commit**
```bash
git add _audit/phase49-full-verification/stage01_capture_plan.py _audit/phase49-full-verification/test_stage01_capture_plan.py
git commit -m "feat(phase49): build capture plan from pack, history, and live asset map"
```

---

### Task B3: Import reference and build the factor index

**Files:**
- Create: `_audit/phase49-full-verification/stage02_import_reference.py`
- Create: `_audit/phase49-full-verification/test_stage02_import_reference.py`

**Interfaces:**
- CLI: `--capture <capture.json> --normalized <dir> --out <reference-index.json>`
- Calls `tools/phase45/rahavard/import_capture.py --in <capture> --out <normalized>`.
- Output index per symbol: `{type0: {first,last,n}, type7: {first,last,n}, factor_changes: [{date, factor, ratio_change}]}`.

- [ ] **Step 1: Write the failing test**

Create `test_stage02_import_reference.py`:
```python
#!/usr/bin/env python3
import gzip
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage02_import_reference as S  # noqa: E402


def main():
    rows = [
        {"symbol": "الف", "asset_id": 1, "type": "type0", "adjust": "raw",
         "resolution": "D", "date": "2020-01-01", "close": 100},
        {"symbol": "الف", "asset_id": 1, "type": "type0", "adjust": "raw",
         "resolution": "D", "date": "2020-01-02", "close": 100},
        {"symbol": "الف", "asset_id": 1, "type": "type7", "adjust": "adjusted",
         "resolution": "D", "date": "2020-01-01", "close": 100},
        {"symbol": "الف", "asset_id": 1, "type": "type7", "adjust": "adjusted",
         "resolution": "D", "date": "2020-01-02", "close": 90},
    ]
    idx = S.build_index(rows)
    ch = idx["الف"]["factor_changes"]
    assert len(ch) == 1, ch
    assert ch[0]["date"] == "2020-01-02"
    assert abs(ch[0]["factor"] - 0.9) < 1e-12
    print("REFERENCE INDEX TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage02_import_reference.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage02_import_reference.py`:
```python
#!/usr/bin/env python3
import argparse, gzip, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMPORT = os.path.join(ROOT, "tools", "phase45", "rahavard", "import_capture.py")
FACTOR_EXACT = 1e-3


def build_index(rows):
    raw, adj = {}, {}
    for r in rows:
        if str(r.get("resolution")) != "D":
            continue
        if r.get("type") == "type0" or r.get("adjust") == "raw":
            raw.setdefault(r["symbol"], {})[r["date"]] = float(r["close"])
        elif r.get("type") == "type7" or r.get("adjust") == "adjusted":
            adj.setdefault(r["symbol"], {})[r["date"]] = float(r["close"])
    out = {}
    for sym in sorted(set(raw) | set(adj)):
        rr, aa = raw.get(sym, {}), adj.get(sym, {})
        common = sorted(set(rr) & set(aa))
        factors = []
        prev = None
        changes = []
        for d in common:
            if rr[d] == 0:
                continue
            f = aa[d] / rr[d]
            factors.append((d, f))
            if prev is not None and abs(f / prev - 1.0) > FACTOR_EXACT:
                changes.append({"date": d, "factor": f,
                                "ratio_change": f / prev})
            prev = f
        out[sym] = {
            "type0": {"first": min(rr) if rr else None,
                      "last": max(rr) if rr else None, "n": len(rr)},
            "type7": {"first": min(aa) if aa else None,
                      "last": max(aa) if aa else None, "n": len(aa)},
            "factor_changes": changes,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", required=True)
    ap.add_argument("--normalized", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.normalized, exist_ok=True)
    subprocess.check_call([sys.executable, IMPORT, "--in", a.capture,
                           "--out", a.normalized])
    rows = []
    with gzip.open(os.path.join(a.normalized, "bars.ndjson.gz"), "rt",
                   encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    idx = build_index(rows)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=1)
    print("reference index: %d symbols -> %s" % (len(idx), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and import the existing captures**

Run:
```bash
python _audit/phase49-full-verification/test_stage02_import_reference.py
python _audit/phase49-full-verification/stage02_import_reference.py \
  --capture _audit/phase49-finalization/rahavard/capture-30.json \
  --normalized _audit/phase49-full-verification/captures/normalized-30 \
  --out _audit/phase49-full-verification/evidence/reference-index-30.json
python _audit/phase49-full-verification/stage02_import_reference.py \
  --capture _audit/phase49-finalization/rahavard/capture-7.json \
  --normalized _audit/phase49-full-verification/captures/normalized-7 \
  --out _audit/phase49-full-verification/evidence/reference-index-7.json
```
Expected: both indexes print 30 and 7 symbols.

- [ ] **Step 5: Commit**
```bash
git add _audit/phase49-full-verification/stage02_import_reference.py _audit/phase49-full-verification/test_stage02_import_reference.py
git commit -m "feat(phase49): import reference captures and build factor-change index"
```

---

### Task B4: Status rules file and guard

**Files:**
- Create: `dev/phase49_status_rules.json`
- Create: `dev/phase49_rules_guard.py`
- Create: `dev/test_phase49_rules_guard.py`

**Interfaces:**
- Rules JSON contains tolerances, step/symbol status precedence, evidence tiers, coverage rules, and the 13 reconciliation categories.
- Guard parses existing constants from `stageC_reference_parity.py` and `adjustment_corrections.py` and fails on any mismatch.

- [ ] **Step 1: Write the failing test**

Create `dev/test_phase49_rules_guard.py`:
```python
#!/usr/bin/env python3
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phase49_rules_guard as G  # noqa: E402


def main():
    rules = G.load_rules()
    assert rules["tolerances"]["FACTOR_EXACT"] == 1e-3
    assert rules["tolerances"]["FACTOR_MATERIAL"] == 1e-2
    assert rules["tolerances"]["OHLC_MATERIAL"] == 5e-2
    assert rules["tolerances"]["EXACT_EQ"] == 1e-9
    assert rules["tolerances"]["DEDUPE_RATIO_TOL"] == 1e-2
    assert len(rules["reconciliation_categories"]) == 13
    assert G.validate_sources(rules) == []
    bad = json.loads(json.dumps(rules)); bad["tolerances"]["FACTOR_EXACT"] = 0.002
    assert any("FACTOR_EXACT" in e for e in G.validate_sources(bad))
    print("STATUS RULES TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python dev/test_phase49_rules_guard.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `dev/phase49_status_rules.json`:
```json
{
 "schema": 1,
 "tolerances": {
  "EXACT_EQ": 1e-9,
  "FACTOR_EXACT": 0.001,
  "FACTOR_MATERIAL": 0.01,
  "OHLC_MATERIAL": 0.05,
  "DEDUPE_RATIO_TOL": 0.01
 },
 "evidence_tiers": ["O1", "O2", "R1", "R2", "I1"],
 "step_status_precedence": [
  "CONFLICT_RATIO", "CONFLICT_DATE", "CONFLICT_DUPLICATE", "CONFLICT_CHAIN",
  "BLOCKED_SOURCE", "INSUFFICIENT_EVIDENCE",
  "PARTIAL_OFFICIAL", "PARTIAL_REFERENCE",
  "RECONSTRUCTED_AUDITED",
  "VERIFIED_MULTI_SOURCE", "VERIFIED_OFFICIAL", "VERIFIED_REFERENCE",
  "INVALID_DROPPED"
 ],
 "symbol_status_precedence": [
  "CONFLICT", "BLOCKED_SOURCE", "INSUFFICIENT_EVIDENCE",
  "RECONSTRUCTED_VERIFIED", "VERIFIED_WITH_EVENTS",
  "VERIFIED_NO_APPLICABLE_EVENT"
 ],
 "coverage": {
  "official_absence_requires_ingest_proof": true,
  "reference_no_event_requires_full_window": true,
  "price_continuity_alone_is_not_evidence": true
 },
 "reconciliation_categories": [
  "SOURCE_MISMATCH", "PRICE_BASIS_DIFFERENCE", "CORPORATE_ACTION_MISSING",
  "EVENT_DATE_MISMATCH", "EVENT_RATIO_MISMATCH", "SYMBOL_IDENTITY_MISMATCH",
  "MISSING_HISTORY", "CALENDAR_GAP", "SOURCE_REVISION", "PRECISION_OR_ROUNDING",
  "INVALID_SOURCE_RECORD", "VERIFIED_NO_EVENT", "UNRESOLVED_SOURCE_GAP"
 ]
}
```

Create `dev/phase49_rules_guard.py`:
```python
#!/usr/bin/env python3
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, "dev", "phase49_status_rules.json")
PARITY = os.path.join(ROOT, "_audit", "phase49-finalization", "stageC_reference_parity.py")
CORR = os.path.join(ROOT, "adjustment_corrections.py")


def load_rules():
    return json.load(open(RULES, encoding="utf-8"))


def _floats(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, float)}


def _assign_float(path, name):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == name and \
                        isinstance(n.value, ast.Constant):
                    return float(n.value.value)
    return None


def validate_sources(rules):
    errors = []
    t = rules["tolerances"]
    floats = _floats(PARITY)
    for name, value in (("FACTOR_EXACT", 0.001), ("FACTOR_MATERIAL", 0.01),
                        ("OHLC_MATERIAL", 0.05), ("EXACT_EQ", 1e-9)):
        if abs(t[name] - value) > 0:
            errors.append("%s differs from Phase 4.9 constant %r" % (name, value))
        if not any(abs(f - value) <= 0 for f in floats):
            errors.append("%s value %r not found in %s" % (name, value, PARITY))
    dedupe = _assign_float(CORR, "NEAR_DEDUPE_RATIO_TOL")
    if dedupe is None or abs(t["DEDUPE_RATIO_TOL"] - dedupe) > 0:
        errors.append("DEDUPE_RATIO_TOL differs from adjustment_corrections")
    if len(rules.get("reconciliation_categories", [])) != 13:
        errors.append("reconciliation_categories must contain 13 entries")
    return errors


def main():
    rules = load_rules()
    errors = validate_sources(rules)
    if errors:
        print("STATUS RULES GUARD FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("STATUS RULES GUARD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: `1e-9` may be stored as `1e-09` in the source; the float comparison is exact. If the parity script does not contain `1e-9` as a float literal, add `EXACT_EQ` source explicitly. The test will reveal it; adjust the source list, never the threshold.

- [ ] **Step 4: Run tests**

Run:
```bash
python dev/test_phase49_rules_guard.py
python dev/phase49_rules_guard.py
```
Expected: `STATUS RULES TESTS OK` and `STATUS RULES GUARD OK`.

- [ ] **Step 5: Commit**
```bash
git add dev/phase49_status_rules.json dev/phase49_rules_guard.py dev/test_phase49_rules_guard.py
git commit -m "feat(phase49): pin status rules to the existing parity tolerances"
```

---

### Task B5: Step ledger classification

**Files:**
- Create: `_audit/phase49-full-verification/stage03_step_ledger.py`
- Create: `_audit/phase49-full-verification/test_stage03_step_ledger.py`

**Interfaces:**
- CLI: `--db <db> --pack <v2 pack> --reference <index.json> --rules <json> --out <csv>`
- Output rows: `symbol, ins_code, asset_id, effective_date, action, ratio, prod_ratio, ref_ratio, cum_factor_after, provenance, method, evidence_tier, evidence_ref, comparison_result, discrepancy_cause, final_status, risk_score, notes`.
- Functions: `load_steps(pack)`, `load_official(db)`, `classify(step, official, ref, rules)`.

- [ ] **Step 1: Write the failing test**

Create `test_stage03_step_ledger.py`:
```python
#!/usr/bin/env python3
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage03_step_ledger as S  # noqa: E402

RULES = {"tolerances": {"EXACT_EQ": 1e-9, "FACTOR_EXACT": 1e-3,
                         "FACTOR_MATERIAL": 1e-2}}


def step(ratio=0.9, date="2020-01-02"):
    return {"symbol": "الف", "effective_date": date, "ratio": ratio,
            "prod_ratio": ratio, "ref_ratio": ratio,
            "cum_factor_after": 0.9, "prov_kind": "pack",
            "method": "multi_field_step_inference",
            "fields_used": "open,high,low,close", "validity": "unverified"}


def main():
    off = {("الف", "2020-01-02"): [{"ratio": 0.9, "tier": "O1"}]}
    ref = {"الف": {"factor_changes": [{"date": "2020-01-02", "factor": 0.9}]}}
    r = S.classify(step(), off, ref, RULES)
    assert r["final_status"] == "VERIFIED_MULTI_SOURCE", r
    off_bad = {("الف", "2020-01-02"): [{"ratio": 0.5, "tier": "O1"}]}
    r = S.classify(step(), off_bad, {"الف": {"factor_changes": []}}, RULES)
    assert r["final_status"] == "CONFLICT_RATIO", r
    r = S.classify(step(), {}, {"الف": {"factor_changes": []}}, RULES)
    assert r["final_status"] == "RECONSTRUCTED_AUDITED", r
    r = S.classify(step(ratio=1.2), {}, {}, RULES)
    assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
    print("STEP LEDGER TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage03_step_ledger.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage03_step_ledger.py` with:
```python
#!/usr/bin/env python3
import argparse, csv, json, os, sqlite3, sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "dev"))
from symbol_identity import key  # noqa: E402


def _d(s):
    return date.fromisoformat(str(s)[:10])


def _num(s):
    return int(str(s)[:8])


def load_steps(pack):
    out = []
    with open(os.path.join(pack, "factors.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    manifest = json.load(open(os.path.join(pack, "manifest.json"), encoding="utf-8"))
    for r in manifest.get("dropped_steps", []):
        r = dict(r); r["validity"] = "invalid_dropped"
        out.append(r)
    return out


def load_official(db):
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    out = {}
    for sym, d_even, ratio in con.execute(
            "SELECT symbol,d_even,ratio FROM price_adjust_events"):
        try:
            ds = "%04d-%02d-%02d" % (d_even // 10000, (d_even // 100) % 100, d_even % 100)
        except Exception:
            continue
        out.setdefault((key(sym), ds), []).append({"ratio": float(ratio), "tier": "O1"})
    for sym, d_even, old, new in con.execute(
            "SELECT symbol,d_even,shares_old,shares_new FROM share_change_events"):
        if not old or not new:
            continue
        ds = "%04d-%02d-%02d" % (d_even // 10000, (d_even // 100) % 100, d_even % 100)
        out.setdefault((key(sym), ds), []).append({"ratio": float(old) / float(new), "tier": "O1"})
    con.close()
    return out


def classify(step, official, reference, rules):
    t = rules["tolerances"]
    sym = key(step.get("symbol"))
    ds = str(step.get("effective_date"))[:10]
    ratio = float(step.get("ratio") or 0)
    ev = official.get((sym, ds), [])
    ref_changes = reference.get(step.get("symbol"), {}).get("factor_changes", [])
    ref = next((c for c in ref_changes
                if 0 <= (_d(c["date"]) - _d(ds)).days <= 5), None)
    tiers, refs = [], []
    if ev:
        tiers.append("O1"); refs.append("price_adjust/share_change:%s" % ds)
    if ref:
        tiers.append("R1"); refs.append("capture:%s" % ref["date"])
    status, cause, comparison = "INSUFFICIENT_EVIDENCE", "", "NO_EVIDENCE"
    if ev:
        best = min(ev, key=lambda e: abs(e["ratio"] / ratio - 1.0))
        err = abs(best["ratio"] / ratio - 1.0)
        if err <= t["FACTOR_EXACT"]:
            status, comparison = ("VERIFIED_MULTI_SOURCE" if ref else "VERIFIED_OFFICIAL"), "MATCH"
        elif err <= t["FACTOR_MATERIAL"]:
            status, comparison = "PARTIAL_OFFICIAL", "PARTIAL"
        else:
            status, comparison, cause = "CONFLICT_RATIO", "MISMATCH", "EVENT_RATIO_MISMATCH"
    elif ref:
        err = abs(ref["factor"] / ratio - 1.0)
        if err <= t["FACTOR_EXACT"]:
            status, comparison = "VERIFIED_REFERENCE", "MATCH"
        elif err <= t["FACTOR_MATERIAL"]:
            status, comparison = "PARTIAL_REFERENCE", "PARTIAL"
        else:
            status, comparison, cause = "CONFLICT_RATIO", "MISMATCH", "EVENT_RATIO_MISMATCH"
    else:
        ok = (0 < ratio <= 1 and step.get("method")
              and step.get("fields_used") and step.get("cum_factor_after"))
        if ok:
            status = "RECONSTRUCTED_AUDITED"
        else:
            status = "INSUFFICIENT_EVIDENCE"
    if step.get("validity") == "invalid_dropped":
        status = "INVALID_DROPPED"
    return {"final_status": status, "evidence_tier": "+".join(tiers) or "I1",
            "evidence_ref": ";".join(refs), "comparison_result": comparison,
            "discrepancy_cause": cause,
            "risk_score": round(abs(1.0 - ratio), 8), "notes": step.get("reason", "")}


FIELDS = ["symbol", "ins_code", "asset_id", "effective_date", "action", "ratio",
          "prod_ratio", "ref_ratio", "cum_factor_after", "provenance", "method",
          "evidence_tier", "evidence_ref", "comparison_result",
          "discrepancy_cause", "final_status", "risk_score", "notes"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--reference", action="append", default=[])
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rules = json.load(open(a.rules, encoding="utf-8"))
    ref = {}
    for p in a.reference:
        ref.update(json.load(open(p, encoding="utf-8")))
    official = load_official(a.db)
    rows = []
    for step in load_steps(a.pack):
        c = classify(step, official, ref, rules)
        rows.append({**{k: step.get(k) for k in
                        ("symbol", "ins_code", "asset_id", "effective_date",
                         "action", "ratio", "prod_ratio", "ref_ratio",
                         "cum_factor_after", "prov_kind", "method")},
                     "provenance": step.get("prov_kind"),
                     **c})
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in FIELDS})
    print("step ledger: %d rows -> %s" % (len(rows), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3b: Add CODAL corroboration and reconstruction-chain audit**

Add to `stage03_step_ledger.py`:
```python
CORP_ACTION_WORDS = ("افزایش سرمایه", "سود نقدی", "حق تقدم", "تعدیل", "درصد")


def load_notices(db):
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    out = {}
    for sym, d, title, url in con.execute(
            "SELECT symbol,publish_date,title,url FROM codal_notices"):
        ds = str(d or "")[:10]
        if not ds:
            continue
        out.setdefault((key(sym), ds), []).append(
            {"title": title, "url": url, "tier": "O2"})
    con.close()
    return out


def notice_near(notices, sym, ds, days=10):
    from datetime import date, timedelta
    d0 = date.fromisoformat(ds)
    for (k, nd), items in notices.items():
        if k != key(sym):
            continue
        try:
            delta = abs((date.fromisoformat(nd) - d0).days)
        except ValueError:
            continue
        if delta <= days and any(w in str(i.get("title") or "")
                                 for i in items for w in CORP_ACTION_WORDS):
            return items[0]
    return None


def audit_reconstruction(steps):
    by_symbol = {}
    for s in steps:
        by_symbol.setdefault(key(s.get("symbol")), []).append(s)
    audit = {}
    for sym, rows in by_symbol.items():
        rows.sort(key=lambda s: str(s.get("effective_date")))
        seen = set()
        prev_cum = None
        for s in rows:
            d = str(s.get("effective_date"))
            ok, why = True, []
            if d in seen:
                ok, _ = False, why.append("duplicate-date")
            seen.add(d)
            try:
                ratio = float(s.get("ratio"))
            except (TypeError, ValueError):
                ok, _ = False, why.append("bad-ratio")
                ratio = None
            if ratio is not None and not (0 < ratio <= 1):
                ok, _ = False, why.append("ratio-out-of-range")
            cum = s.get("cum_factor_after")
            if prev_cum is not None and cum is not None and float(cum) > float(prev_cum) + 1e-12:
                ok, _ = False, why.append("cum-factor-increase")
            if not (s.get("method") and s.get("fields_used") and s.get("prov_kind")):
                ok, _ = False, why.append("missing-provenance")
            if cum is not None:
                prev_cum = cum
            audit[(sym, d)] = {"ok": ok, "notes": why}
    return audit
```
In `classify`, add `notices=None` and after the tier check:
```python
    n = notice_near(notices or {}, step.get("symbol"), ds) if notices else None
    if n:
        tiers.append("O2"); refs.append("codal:%s" % n.get("url"))
```
This only adds corroboration; it never changes the status alone, matching the evidence hierarchy. In `main`, build `audit = audit_reconstruction(all_steps)`, pass `audit.get((key(step["symbol"]), str(step["effective_date"])[:10]))` into `classify`, and when no O1/R1 evidence exists use `audit["ok"]` to choose `RECONSTRUCTED_AUDITED` (true) or `CONFLICT_CHAIN` (false).

- [ ] **Step 4: Run tests and build the real ledger**

Run:
```bash
python _audit/phase49-full-verification/test_stage03_step_ledger.py
python _audit/phase49-full-verification/stage03_step_ledger.py \
  --db _audit/phase49-finalization/seed/market.db \
  --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \
  --reference _audit/phase49-full-verification/evidence/reference-index-30.json \
  --reference _audit/phase49-full-verification/evidence/reference-index-7.json \
  --rules dev/phase49_status_rules.json \
  --out _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv
```
Expected: 8,280 valid rows + the manifest's `dropped_steps` (28) = 8,308 rows. Verify the counts with:
```bash
python - <<'PY'
import csv, collections
rows=list(csv.DictReader(open(r"_audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv", encoding="utf-8")))
print(len(rows)); print(collections.Counter(r["final_status"] for r in rows))
PY
```
Record the counts in `evidence/step-ledger-counts.json`. If the valid count is not 8,280, stop and reconcile the pack manifest; do not proceed.

- [ ] **Step 5: Commit**
```bash
git add _audit/phase49-full-verification/stage03_step_ledger.py _audit/phase49-full-verification/test_stage03_step_ledger.py _audit/phase49-full-verification/evidence/step-ledger-counts.json
git commit -m "feat(phase49): classify all adjustment steps with evidence tiers"
```

---

### Task B6: Volana root-cause

**Files:**
- Create: `_audit/phase49-full-verification/stage04_volana_rootcause.py`
- Create: `_audit/phase49-full-verification/test_stage04_volana_rootcause.py`

- [ ] **Step 1: Write the failing test**

Create `test_stage04_volana_rootcause.py`:
```python
#!/usr/bin/env python3
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage04_volana_rootcause as S  # noqa: E402


def main():
    steps = [
        {"symbol": "ولانا", "effective_date": "2020-01-02", "ratio": 0.9,
         "ref_ratio": 0.9, "validity": "unverified"},
        {"symbol": "ولانا", "effective_date": "2021-01-02", "ratio": 0.95,
         "ref_ratio": 0.96, "validity": "unverified"},
        {"symbol": "ولانا", "effective_date": "2022-01-02", "ratio": 0.8,
         "ref_ratio": 0.8, "validity": "unverified"},
    ]
    out = S.rootcause(steps)
    assert out["count"] == 3, out
    assert out["max_rel_error"] > 0.001, out
    assert out["steps"][1]["cause"] == "EVENT_RATIO_MISMATCH"
    print("VOLANA TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage04_volana_rootcause.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage04_volana_rootcause.py`:
```python
#!/usr/bin/env python3
import argparse, json, sys

EXACT = 1e-3


def rootcause(steps):
    steps = [s for s in steps if s.get("symbol") == "ولانا"
             and s.get("validity") == "unverified"]
    out = []
    for s in steps:
        p, r = float(s.get("ratio") or 0), float(s.get("ref_ratio") or 0)
        err = abs(r / p - 1.0) if p else 1.0
        cause = "MATCH"
        if err > EXACT:
            cause = "EVENT_RATIO_MISMATCH"
        out.append({"effective_date": s.get("effective_date"),
                    "product_ratio": p, "reference_ratio": r,
                    "relative_error": err, "cause": cause})
    return {"symbol": "ولانا", "count": len(out),
            "max_rel_error": max((s["relative_error"] for s in out), default=0),
            "steps": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    steps = [json.loads(l) for l in open(a.steps, encoding="utf-8") if l.strip()]
    rep = rootcause(steps)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and real analysis**

Run:
```bash
python _audit/phase49-full-verification/test_stage04_volana_rootcause.py
python _audit/phase49-full-verification/stage04_volana_rootcause.py \
  --steps data/ra365_corrections/ra365-phase49-rebuild-full-v2/factors.jsonl \
  --out _audit/phase49-full-verification/evidence/volana-rootcause.json
```
Expected: exactly 3 steps; max relative error ~0.198%; causes recorded without changing the 0.1% threshold.

- [ ] **Step 5: Commit**
```bash
git add _audit/phase49-full-verification/stage04_volana_rootcause.py _audit/phase49-full-verification/test_stage04_volana_rootcause.py _audit/phase49-full-verification/evidence/volana-rootcause.json
git commit -m "feat(phase49): root-cause the three Volana unverified steps"
```

---

### Task B7: Symbol ledger (6,103 rows)

**Files:**
- Create: `_audit/phase49-full-verification/stage05_symbol_ledger.py`
- Create: `_audit/phase49-full-verification/test_stage05_symbol_ledger.py`

**Interfaces:**
- CLI: `--db <db> --steps <step-ledger.csv> --reference <index.json> --out <csv>`
- Output one row per `price_history` symbol with the spec's fields.

- [ ] **Step 1: Write the failing test**

Create `test_stage05_symbol_ledger.py`:
```python
#!/usr/bin/env python3
import os, sqlite3, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage05_symbol_ledger as S  # noqa: E402


def main():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT,open REAL,high REAL,low REAL,close REAL,volume REAL,last REAL,value REAL,src TEXT)")
    con.execute("CREATE TABLE instruments(ins_code TEXT,l_val18 TEXT,l_val30 TEXT,paper_type INTEGER,isin TEXT,updated_at TEXT)")
    con.execute("INSERT INTO instruments VALUES('1','الف','الف',1,NULL,'2026-01-01')")
    for d, o in (("2026-01-01", 10), ("2026-01-02", 10), ("2026-01-04", 11)):
        con.execute("INSERT INTO price_history VALUES('الف',?,?,?,?,?,1,?,NULL,'legacy-unknown')",
                    (d, o, o, o, o, o))
    con.commit()
    row = S.symbol_row(con, "الف", steps={}, reference={}, calendar={"2026-01-01","2026-01-02","2026-01-03","2026-01-04"})
    assert row["symbol"] == "الف" and row["ins_code"] == "1"
    assert row["rows"] == 3 and row["gaps"] == 1, row
    assert row["final_status"] in ("INSUFFICIENT_EVIDENCE", "VERIFIED_NO_APPLICABLE_EVENT")
    con.close(); os.unlink(p)
    print("SYMBOL LEDGER TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage05_symbol_ledger.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage05_symbol_ledger.py` with:
```python
#!/usr/bin/env python3
import argparse, csv, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "dev"))
from symbol_identity import key  # noqa: E402

FIELDS = ["symbol", "ins_code", "asset_id", "instrument_status", "first_date",
          "last_date", "rows", "trading_sessions", "source_coverage",
          "raw_ohlc_valid", "adjusted_available", "evidence_tier",
          "event_coverage", "ref_coverage", "ref_days", "ref_first", "ref_last",
          "factor_steps", "factor_verified", "factor_reconstructed",
          "factor_unverified", "stale_status", "gaps", "anomalies",
          "verification_method", "final_status", "remaining_blocker"]


_IDENT_CACHE = {}


def _ident(con):
    cache_key = id(con)
    if cache_key in _IDENT_CACHE:
        return _IDENT_CACHE[cache_key]
    out = {}
    for ins_code, name in con.execute(
            "SELECT ins_code,l_val18 FROM instruments "
            "WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>''"):
        out.setdefault(key(name), str(ins_code))
    _IDENT_CACHE[cache_key] = out
    return out


def symbol_row(con, symbol, steps, reference, calendar, asset_map=None,
               official_counts=None):
    r = con.execute(
        "SELECT COUNT(*),MIN(date),MAX(date),"
        "SUM(CASE WHEN COALESCE(volume,0)=0 THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN low IS NOT NULL AND high IS NOT NULL AND low>high THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN close IS NOT NULL AND low IS NOT NULL AND high IS NOT NULL "
        "AND (close<low OR close>high) THEN 1 ELSE 0 END) "
        "FROM price_history WHERE symbol=?", (symbol,)).fetchone()
    rows, first, last, zero_vol, bad_hl, bad_close = r
    if not rows:
        return None
    dates = {x[0] for x in con.execute(
        "SELECT date FROM price_history WHERE symbol=?", (symbol,))}
    gaps = len({d for d in calendar if first <= d <= last} - dates)
    sources = dict(con.execute(
        "SELECT COALESCE(src,'legacy-unknown'),COUNT(*) FROM price_history "
        "WHERE symbol=? GROUP BY 1", (symbol,)))
    ins_code = _ident(con).get(key(symbol), "")
    instrument_status = ""
    if ins_code:
        try:
            st_row = con.execute(
                "SELECT c_etaval_title FROM instrument_state WHERE ins_code=? "
                "ORDER BY d_even DESC LIMIT 1", (ins_code,)).fetchone()
            instrument_status = st_row[0] if st_row and st_row[0] else ""
        except sqlite3.OperationalError:
            instrument_status = ""
    counts = (official_counts or {}).get(key(symbol), {})
    statuses = {s.get("final_status") for s in steps}
    if statuses:
        if statuses & {"CONFLICT_RATIO", "CONFLICT_DATE", "CONFLICT_DUPLICATE", "CONFLICT_CHAIN"}:
            final = "CONFLICT"
        elif "BLOCKED_SOURCE" in statuses:
            final = "BLOCKED_SOURCE"
        elif "INSUFFICIENT_EVIDENCE" in statuses or any(
                str(s).startswith("PARTIAL_") for s in statuses):
            final = "INSUFFICIENT_EVIDENCE"
        elif "RECONSTRUCTED_AUDITED" in statuses:
            final = "RECONSTRUCTED_VERIFIED"
        else:
            final = "VERIFIED_WITH_EVENTS"
    else:
        ref = reference.get(symbol, {})
        t0, t7 = ref.get("type0", {}), ref.get("type7", {})
        full = bool(t0.get("first") and t7.get("first") and t0["first"] <= first
                    and t7["first"] <= first and t0.get("last")
                    and t7.get("last") and t0["last"] >= last and t7["last"] >= last)
        final = ("VERIFIED_NO_APPLICABLE_EVENT"
                 if full and not ref.get("factor_changes")
                 else "INSUFFICIENT_EVIDENCE")
    behind = len([d for d in calendar if d > last])
    stale = "fresh" if last == max(calendar) else ("stale" if behind > 21 else "recent")
    if instrument_status and any(w in instrument_status for w in ("توقف", "معلق")):
        stale = "halted"
    blocker = "" if final.startswith("VERIFIED_") else final
    event_cov = ("pack" if steps else "none")
    if counts:
        event_cov = "%s;O1=%d;O2=%d" % (
            event_cov, counts.get("o1", 0), counts.get("o2", 0))
    ref = reference.get(symbol, {})
    f_steps = len(steps)
    f_verified = sum(1 for s in steps if s.get("final_status") in (
        "VERIFIED_OFFICIAL", "VERIFIED_MULTI_SOURCE", "VERIFIED_REFERENCE"))
    f_recon = sum(1 for s in steps if s.get("final_status") == "RECONSTRUCTED_AUDITED")
    return {
        "symbol": symbol, "ins_code": ins_code,
        "asset_id": (asset_map or {}).get(key(symbol), ""),
        "instrument_status": instrument_status, "first_date": first,
        "last_date": last, "rows": rows, "trading_sessions": len(dates),
        "source_coverage": json.dumps(sources, ensure_ascii=False),
        "raw_ohlc_valid": "ok" if not (bad_hl or bad_close) else "invalid",
        "adjusted_available": "pack" if steps else "none",
        "evidence_tier": "I1" if steps else ("R1" if final.startswith("VERIFIED_") else ""),
        "event_coverage": event_cov,
        "ref_coverage": "full" if ref else "none",
        "ref_days": (ref.get("type0") or {}).get("n", 0),
        "ref_first": (ref.get("type0") or {}).get("first", ""),
        "ref_last": (ref.get("type0") or {}).get("last", ""),
        "factor_steps": f_steps, "factor_verified": f_verified,
        "factor_reconstructed": f_recon,
        "factor_unverified": f_steps - f_verified - f_recon,
        "stale_status": stale, "gaps": gaps,
        "anomalies": zero_vol + bad_hl + bad_close,
        "verification_method": "step-ledger" if steps else "reference-window",
        "final_status": final, "remaining_blocker": blocker,
    }
```

CLI:
```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--reference", action="append", default=[])
    ap.add_argument("--asset-map", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ref = {}
    for p in a.reference:
        ref.update(json.load(open(p, encoding="utf-8")))
    asset_map = {}
    if a.asset_map:
        for s in json.load(open(a.asset_map, encoding="utf-8")):
            asset_map[key(s.get("symbol"))] = s.get("asset_id", "")
    steps = {}
    for r in csv.DictReader(open(a.steps, encoding="utf-8")):
        steps.setdefault(r["symbol"], []).append(r)
    con = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    calendar = {r[0] for r in con.execute("SELECT DISTINCT date FROM price_history")}
    syms = [r[0] for r in con.execute(
        "SELECT symbol FROM price_history GROUP BY symbol ORDER BY symbol")]
    official = {}
    for table, field in (("price_adjust_events", "o1"),
                         ("share_change_events", "o1"),
                         ("codal_notices", "o2")):
        try:
            for sym, n in con.execute(
                    "SELECT symbol,COUNT(*) FROM %s GROUP BY symbol" % table):
                official.setdefault(key(sym), {})[field] = \
                    official.setdefault(key(sym), {}).get(field, 0) + n
        except sqlite3.OperationalError:
            pass
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
        for sym in syms:
            row = symbol_row(con, sym, steps.get(sym, []), ref, calendar,
                             asset_map=asset_map, official_counts=official)
            if row:
                w.writerow(row)
    con.close()
    print("symbol ledger: %d rows -> %s" % (len(syms), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and real ledger**

Run:
```bash
python _audit/phase49-full-verification/test_stage05_symbol_ledger.py
python _audit/phase49-full-verification/stage05_symbol_ledger.py \
  --db _audit/phase49-finalization/seed/market.db \
  --steps _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv \
  --reference _audit/phase49-full-verification/evidence/reference-index-30.json \
  --reference _audit/phase49-full-verification/evidence/reference-index-7.json \
  --asset-map _audit/phase49-full-verification/capture-plan/symbols.json \
  --out _audit/phase49-full-verification/ledgers/HISTORY-COVERAGE-LEDGER.csv
```
Expected: exactly 6,103 rows. Record counts per status in `evidence/symbol-ledger-counts.json`.

- [ ] **Step 5: Commit**
```bash
git add _audit/phase49-full-verification/stage05_symbol_ledger.py _audit/phase49-full-verification/test_stage05_symbol_ledger.py _audit/phase49-full-verification/evidence/symbol-ledger-counts.json
git commit -m "feat(phase49): build per-symbol history coverage ledger"
```

---

### Task B8: Anomaly ledger

**Files:**
- Create: `_audit/phase49-full-verification/stage06_anomaly_ledger.py`
- Create: `_audit/phase49-full-verification/test_stage06_anomaly_ledger.py`

- [ ] **Step 1: Write the failing test**

Create `test_stage06_anomaly_ledger.py`:
```python
#!/usr/bin/env python3
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage06_anomaly_ledger as S  # noqa: E402


def main():
    rows = [
        {"symbol": "A", "date": "2020-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1},
        {"symbol": "A", "date": "2020-01-02", "open": 10, "high": 9, "low": 11, "close": 10, "volume": 1},
        {"symbol": "A", "date": "2020-01-03", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 0},
    ]
    out = S.detect(rows, prev_close={"A": 10})
    kinds = {a["kind"] for a in out}
    assert "INVALID_OHLC" in kinds and "ZERO_VOLUME" in kinds, out
    assert all(a["category"] for a in out)
    print("ANOMALY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python _audit/phase49-full-verification/test_stage06_anomaly_ledger.py`
Expected: module missing.

- [ ] **Step 3: Implement**

Create `stage06_anomaly_ledger.py`:
```python
#!/usr/bin/env python3
import argparse, csv, json, sqlite3, sys

CATEGORY = {
    "INVALID_OHLC": "INVALID_SOURCE_RECORD",
    "ZERO_FIELDS": "INVALID_SOURCE_RECORD",
    "OPEN_EQ_PREV_CLOSE": "PRICE_BASIS_DIFFERENCE",
    "ZERO_VOLUME": "CALENDAR_GAP",
    "DUPLICATE_DATE": "INVALID_SOURCE_RECORD",
}


def detect(rows, prev_close):
    out = []
    seen = set()
    for r in rows:
        sym, d = r["symbol"], r["date"]
        o, h, l, c = (r.get("open"), r.get("high"), r.get("low"), r.get("close"))
        if (sym, d) in seen:
            out.append({"symbol": sym, "date": d, "kind": "DUPLICATE_DATE",
                        "category": CATEGORY["DUPLICATE_DATE"]})
        seen.add((sym, d))
        if None in (o, h, l, c) or h < l or (h and l and not (l <= c <= h)):
            out.append({"symbol": sym, "date": d, "kind": "INVALID_OHLC",
                        "category": CATEGORY["INVALID_OHLC"]})
        if o == h == l == c == 0:
            out.append({"symbol": sym, "date": d, "kind": "ZERO_FIELDS",
                        "category": CATEGORY["ZERO_FIELDS"]})
        if o is not None and prev_close.get(sym) is not None and abs(o - prev_close[sym]) < 1e-9:
            out.append({"symbol": sym, "date": d, "kind": "OPEN_EQ_PREV_CLOSE",
                        "category": CATEGORY["OPEN_EQ_PREV_CLOSE"]})
        if not r.get("volume"):
            out.append({"symbol": sym, "date": d, "kind": "ZERO_VOLUME",
                        "category": CATEGORY["ZERO_VOLUME"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    con = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT symbol,date,open,high,low,close,volume FROM price_history ORDER BY symbol,date")]
    prev = {}
    for r in rows:
        prev.setdefault(r["symbol"], r["close"])
        r["prev_close"] = prev[r["symbol"]]
        if r["close"] is not None:
            prev[r["symbol"]] = r["close"]
    out = detect(rows, {r["symbol"]: r.get("prev_close") for r in rows})
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "date", "kind", "category"])
        w.writeheader(); w.writerows(out)
    print("anomalies: %d -> %s" % (len(out), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and real ledger**

Run:
```bash
python _audit/phase49-full-verification/test_stage06_anomaly_ledger.py
python _audit/phase49-full-verification/stage06_anomaly_ledger.py \
  --db _audit/phase49-finalization/seed/market.db \
  --out _audit/phase49-full-verification/ledgers/anomaly-ledger.csv
```
Expected: every anomaly row has a category from the 13-category list; counts are recorded in `evidence/anomaly-counts.json`.

- [ ] **Step 5: Commit**
```bash
git add _audit/phase49-full-verification/stage06_anomaly_ledger.py _audit/phase49-full-verification/test_stage06_anomaly_ledger.py _audit/phase49-full-verification/evidence/anomaly-counts.json
git commit -m "feat(phase49): classify OHLC and gap anomalies with reconciliation categories"
```

---

### Task B9: Inventory reconciliation

**Files:**
- Create: `_audit/phase49-full-verification/stage07_inventory_reconcile.py`
- Create: `_audit/phase49-full-verification/test_stage07_inventory_reconcile.py`

- [ ] **Step 1: Write the failing test**

Create `test_stage07_inventory_reconcile.py`:
```python
#!/usr/bin/env python3
import os, sqlite3, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage07_inventory_reconcile as S  # noqa: E402


def main():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT)")
    con.execute("CREATE TABLE instruments(ins_code TEXT,l_val18 TEXT)")
    con.execute("INSERT INTO instruments VALUES('1','الف')")
    con.execute("INSERT INTO instruments VALUES('2','ب')")
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-01')")
    con.execute("INSERT INTO price_history VALUES('ج','2026-01-01')")
    con.commit()
    r = S.reconcile(con)
    assert r["history_symbols"] == 2 and r["instruments"] == 2
    assert r["history_outside_instruments"] == 1
    assert r["instruments_without_history"] == 1
    con.close(); os.unlink(p)
    print("INVENTORY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Implement and run**

Create `stage07_inventory_reconcile.py` with:
```python
#!/usr/bin/env python3
import argparse, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "dev"))
from symbol_identity import key  # noqa: E402


def reconcile(con, pack_symbols=None):
    hist = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM price_history")}
    hist_keys = {key(s) for s in hist}
    inst_keys = {}
    for ins_code, name in con.execute(
            "SELECT ins_code,l_val18 FROM instruments "
            "WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>''"):
        inst_keys.setdefault(key(name), str(ins_code))
    rep = {
        "history_symbols": len(hist),
        "instruments": con.execute("SELECT COUNT(*) FROM instruments").fetchone()[0],
        "instruments_named": len(inst_keys),
        "history_outside_instruments": len(hist_keys - set(inst_keys)),
        "instruments_without_history": len(set(inst_keys) - hist_keys),
        "duplicate_instrument_names": con.execute(
            "SELECT COUNT(*) FROM (SELECT l_val18 FROM instruments "
            "WHERE TRIM(COALESCE(l_val18,''))<>'' GROUP BY l_val18 "
            "HAVING COUNT(*)>1)").fetchone()[0],
    }
    if pack_symbols is not None:
        pack_keys = {key(s) for s in pack_symbols}
        rep["pack_symbols"] = len(pack_keys)
        rep["history_symbols_without_pack_steps"] = len(hist_keys - pack_keys)
        rep["pack_symbols_without_history"] = len(pack_keys - hist_keys)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pack_symbols = None
    if a.pack:
        pack_symbols = set()
        with open(os.path.join(a.pack, "factors.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    pack_symbols.add(json.loads(line).get("symbol"))
    con = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    rep = reconcile(con, pack_symbols); con.close()
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run:
```bash
python _audit/phase49-full-verification/test_stage07_inventory_reconcile.py
python _audit/phase49-full-verification/stage07_inventory_reconcile.py \
  --db _audit/phase49-finalization/seed/market.db \
  --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \
  --out _audit/phase49-full-verification/evidence/inventory-reconcile.json
```
Expected: explains 6,103 history symbols, 5,944 instruments, and the gaps. It must also compute the report's 6,328 no-evidence count using the pack step set and record the definition used. If `history_symbols_without_pack_steps` is not 6,328, reconcile the definition explicitly (pack steps vs product events) in the JSON `notes`; do not force the number.

- [ ] **Step 3: Commit**
```bash
git add _audit/phase49-full-verification/stage07_inventory_reconcile.py _audit/phase49-full-verification/test_stage07_inventory_reconcile.py _audit/phase49-full-verification/evidence/inventory-reconcile.json
git commit -m "feat(phase49): reconcile symbol, instrument, and history inventory counts"
```

---

### Task B10: Execute capture and import (owner session checkpoint)

- [ ] **Step 1: Preflight**

Run:
```bash
python _audit/phase49-full-verification/stage01_capture_plan.py ...  # as in B2
python - <<'PY'
import json
p=json.load(open(r"_audit/phase49-full-verification/capture-plan/capture-plan.json",encoding="utf-8"))
print(json.dumps(p["counts"],ensure_ascii=False,indent=1))
PY
```
Expected: mapped + unmapped = union; unmapped list is explicit.

- [ ] **Step 2: Start capture in the owner's logged-in browser**

Use the bundled Node path if `node` is not on PATH. Run:
```bash
node tools/phase45/rahavard/capture_rahavard.mjs \
  --symbols _audit/phase49-full-verification/capture-plan/symbols.json \
  --out _audit/phase49-full-verification/captures/capture-full.json \
  --port 9333 --countback 100000 --from 1990-01-01 --to 2026-11-10 \
  --delay-ms 400 --retries 3
```
- If exit code 3: stop; ask the owner to log in; do not request or store credentials.
- If exit code 4: stop; ask the owner to open the browser with `--launch`; do not guess.
- If partial failures: rerun only the failed symbols with a new `symbols.json`; never mark a failed symbol verified.

- [ ] **Step 3: Import and index**

Run as in B3 with `--capture .../capture-full.json` and `--normalized .../normalized-full`, then merge indexes:
```bash
python - <<'PY'
import json
out = {}
for p in (r"_audit/phase49-full-verification/evidence/reference-index-30.json",
          r"_audit/phase49-full-verification/evidence/reference-index-7.json",
          r"_audit/phase49-full-verification/evidence/reference-index-full.json"):
    try:
        out.update(json.load(open(p, encoding="utf-8")))
    except FileNotFoundError:
        pass
dst = r"_audit/phase49-full-verification/evidence/reference-index-all.json"
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("merged reference index:", len(out), "->", dst)
PY
```
Use the bundled Node path from the local toolchain memory if `node` is not on PATH; do not install a new runtime.

- [ ] **Step 4: Record capture metadata**

Create `_audit/phase49-full-verification/evidence/capture-summary.json` with SHA-256, source, captured_at, series count, row count, normalization method, and failure list. Do not include raw series.

- [ ] **Step 5: Commit only the summary and indexes**
```bash
git add _audit/phase49-full-verification/evidence/capture-summary.json _audit/phase49-full-verification/evidence/reference-index-all.json
git commit -m "docs(phase49): record reference capture provenance and factor index"
```

---

### Task B11: Rebuild ledgers with full reference and record counts

- [ ] **Step 1: Re-run B5/B7/B8 against the full reference index**

Run the three stage commands with `--reference _audit/phase49-full-verification/evidence/reference-index-all.json` (plus the existing 30/7 indexes if the full capture doesn't include them; merge first).

- [ ] **Step 2: Verify the mandatory counts**

Run:
```bash
python - <<'PY'
import csv, collections
for f in ("ADJUSTMENT-EVIDENCE-LEDGER.csv", "HISTORY-COVERAGE-LEDGER.csv"):
    rows=list(csv.DictReader(open(r"_audit/phase49-full-verification/ledgers/"+f,encoding="utf-8")))
    print(f, len(rows))
    if "final_status" in rows[0]:
        print(collections.Counter(r["final_status"] for r in rows))
PY
```
Expected: step ledger 8,308 rows (8,280 valid + 28 invalid); symbol ledger 6,103 rows. Record the status counts in `evidence/ledger-counts.json`.

- [ ] **Step 3: Commit the ledgers and counts**
```bash
git add _audit/phase49-full-verification/evidence/ledger-counts.json
git commit -m "docs(phase49): record full-reference ledger counts and statuses"
```

## Plan B Acceptance

- `python dev/test_symbol_identity.py` → OK.
- `python dev/phase49_rules_guard.py` → OK.
- Capture summary exists with SHA and counts; no raw capture in `git status`.
- Step ledger: 8,280 valid + 28 invalid; every row has `final_status` and evidence tier.
- Symbol ledger: 6,103 rows; every row has `final_status` and `remaining_blocker`.
- Anomaly ledger: every row has one of the 13 categories.
- Inventory reconciliation explains 6,103 / 5,944 / 1,306 / 1,468 / 1,343 / 6,328.
