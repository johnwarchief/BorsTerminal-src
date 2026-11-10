# Phase 4.9.1 — Plan C: Backfill, Seed Candidate, Parity & Final CI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill the six short-history symbols and active freshness gaps, build a new Seed Candidate with full provenance and a release gate, prove Go/Python and product parity, produce the eight deliverables, and record the final CI run.

**Architecture:** Reuse `tools/phase48/backfill_reference.py` for idempotent, provenance-tracked backfill with a new `--since` window. Build the candidate from a new copy, materialize validity from Plan B ledgers, compress with round-trip proof, and gate release on reference-derived rows. Copy and parameterize the proven Phase 4.9 parity/product harnesses.

**Tech Stack:** Python 3.12, SQLite, Go 1.26, LZMA/gzip, GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-11-10-phase49-full-verification-design.md](../specs/2026-11-10-phase49-full-verification-design.md)

## Global Constraints

- Old candidate `_audit/phase49-finalization/seed/market.db` is read-only; new candidate is a new path.
- Only missing dates are inserted; existing rows are never overwritten; second run inserts 0.
- Reference-derived rows carry provenance and are counted in `seed_manifest.reference_derived_rows`.
- Seed remains a Candidate; no release, tag, or merge in this phase.
- No fabricated candles; no raw/adjusted mixing; no threshold changes.
- Final CI must run on the final HEAD; old runs are not evidence.

---

### Task C1: Add `--since` to the backfill tool with tests

**Files:**
- Modify: `tools/phase48/backfill_reference.py`
- Create: `dev/test_phase49_backfill_since.py`

**Interfaces:**
- `load_ref_daily(path, symbols, since=None)` ignores reference rows with `date < since`.
- `apply_backfill(..., since=None)` and CLI `apply --since YYYY-MM-DD`.

- [ ] **Step 1: Write the failing test**

Create `dev/test_phase49_backfill_since.py` based on the existing `dev/test_phase48_backfill_history_v1.py` fixture pattern. The key assertions:
```python
#!/usr/bin/env python3
"""Prove --since inserts only recent missing dates and stays idempotent."""
import gzip
import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "phase48"))
import backfill_reference as B  # noqa: E402


def make_db(path):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE price_history(
        symbol TEXT,date TEXT,open REAL,high REAL,low REAL,close REAL,
        volume REAL,last REAL,value REAL,src TEXT)""")
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-01',10,10,10,10,1,10,NULL,'legacy-unknown')")
    con.commit(); con.close()


def make_ref(path):
    rows = [
        {"symbol": "الف", "asset_id": 1, "type": "type0", "adjust": "raw",
         "resolution": "D", "date": "2025-12-30", "open": 9, "high": 9,
         "low": 9, "close": 9, "volume": 1},
        {"symbol": "الف", "asset_id": 1, "type": "type0", "adjust": "raw",
         "resolution": "D", "date": "2026-01-02", "open": 10, "high": 10,
         "low": 10, "close": 10, "volume": 1},
    ]
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.db"); make_db(src)
    ref = os.path.join(tmp, "bars.ndjson.gz"); make_ref(ref)
    work = os.path.join(tmp, "work")
    rep = B.apply_backfill(src, work, ref, ["الف"], "test-since", since="2026-01-01")
    assert rep["totals"]["inserted"] == 1, rep["totals"]
    con = sqlite3.connect(os.path.join(work, "market.db"))
    dates = [r[0] for r in con.execute("SELECT date FROM price_history WHERE symbol='الف' ORDER BY date")]
    assert dates == ["2026-01-01", "2026-01-02"], dates
    con.close()
    rep2 = B.apply_backfill(src, work, ref, ["الف"], "test-since-2",
                            reuse_work=True, since="2026-01-01")
    assert rep2["totals"]["inserted"] == 0, rep2["totals"]
    print("BACKFILL SINCE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python dev/test_phase49_backfill_since.py`
Expected: `TypeError: apply_backfill() got an unexpected keyword argument 'since'`.

- [ ] **Step 3: Implement**

In `tools/phase48/backfill_reference.py`:
- Add `since=None` to `load_ref_daily(path, symbols, since=None)` and skip:
```python
            if since and str(r.get("date") or "") < since:
                continue
```
- Add `since=None` to `apply_backfill(...)`, pass it to `load_ref_daily`.
- Add `a.add_argument("--since", default="")` to the `apply` subparser and pass `args.since or None`.

- [ ] **Step 4: Run tests**

Run:
```bash
python dev/test_phase49_backfill_since.py
python dev/test_phase48_backfill_history_v1.py
```
Expected: both pass; the Phase 4.8 contract remains intact.

- [ ] **Step 5: Commit**
```bash
git add tools/phase48/backfill_reference.py dev/test_phase49_backfill_since.py
git commit -m "feat(phase49): add --since window to reference backfill"
```

---

### Task C2: Build the backfill plan (six full + active freshness)

**Files:**
- Create: `_audit/phase49-full-verification/stage08_backfill.py`
- Create: `_audit/phase49-full-verification/test_stage08_backfill.py`

**Interfaces:**
- CLI: `--symbol-ledger <csv> --global-last <date> --freshness-days 30 --out-dir <dir>`
- Outputs `symbols-six.csv` and `symbols-freshness.csv`.

- [ ] **Step 1: Write the failing test**

Create `test_stage08_backfill.py`:
```python
#!/usr/bin/env python3
import csv, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage08_backfill as S  # noqa: E402


def main():
    rows = [
        {"symbol": "شنفت", "last_date": "2026-10-11", "final_status": "INSUFFICIENT_EVIDENCE"},
        {"symbol": "الف", "last_date": "2026-11-08", "final_status": "VERIFIED_WITH_EVENTS"},
        {"symbol": "ب", "last_date": "2026-09-01", "final_status": "INSUFFICIENT_EVIDENCE"},
    ]
    tmp = tempfile.mkdtemp()
    six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
    assert six == ["شنفت"], six
    assert fresh == ["الف"], fresh
    print("BACKFILL PLAN TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Implement and test**

Create `stage08_backfill.py`:
```python
#!/usr/bin/env python3
import argparse, csv, os, sys
from datetime import date

SIX = ("شنفت", "فافق", "فخاس", "فولاژ", "لخزر", "مارون")


def plan(rows, global_last, freshness_days, out_dir):
    six = [r["symbol"] for r in rows if r["symbol"] in SIX]
    cutoff = (date.fromisoformat(global_last)
              - __import__("datetime").timedelta(days=freshness_days)).isoformat()
    fresh = [r["symbol"] for r in rows
             if r["symbol"] not in SIX and r.get("last_date")
             and cutoff <= r["last_date"] < global_last]
    os.makedirs(out_dir, exist_ok=True)
    for name, syms in (("symbols-six.csv", six), ("symbols-freshness.csv", fresh)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh); w.writerow(["symbol"]); w.writerows([[s] for s in syms])
    return six, fresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol-ledger", required=True)
    ap.add_argument("--global-last", required=True)
    ap.add_argument("--freshness-days", type=int, default=30)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.symbol_ledger, encoding="utf-8")))
    six, fresh = plan(rows, a.global_last, a.freshness_days, a.out_dir)
    print("six=%d freshness=%d" % (len(six), len(fresh)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run: `python _audit/phase49-full-verification/test_stage08_backfill.py` → OK.

- [ ] **Step 3: Build the real plan**

Run:
```bash
python _audit/phase49-full-verification/stage08_backfill.py \
  --symbol-ledger _audit/phase49-full-verification/ledgers/HISTORY-COVERAGE-LEDGER.csv \
  --global-last 2026-11-10 --freshness-days 30 \
  --out-dir _audit/phase49-full-verification/backfill-plan
```
Expected: six list is exactly the six mandated symbols; freshness list is explicit and excludes the six.

- [ ] **Step 4: Commit**
```bash
git add _audit/phase49-full-verification/stage08_backfill.py _audit/phase49-full-verification/test_stage08_backfill.py
git commit -m "feat(phase49): plan six-symbol and recent-freshness backfill"
```

---

### Task C3: Apply backfill to an isolated copy and prove idempotency

- [ ] **Step 1: Merge normalized reference bars**

Run:
```bash
python - <<'PY'
import gzip, os
srcs = [r"_audit/phase49-full-verification/captures/normalized-full/bars.ndjson.gz",
        r"_audit/phase49-full-verification/captures/normalized-7/bars.ndjson.gz",
        r"_audit/phase49-full-verification/captures/normalized-30/bars.ndjson.gz"]
out = r"_audit/phase49-full-verification/captures/bars-all.ndjson.gz"
seen = set()
with gzip.open(out, "wt", encoding="utf-8") as w:
    for src in srcs:
        if not os.path.exists(src):
            continue
        with gzip.open(src, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                import json
                r = json.loads(line)
                k = (r.get("asset_id"), r.get("resolution"), r.get("type"), r.get("date"))
                if k in seen:
                    continue
                seen.add(k); w.write(line)
print("merged", len(seen), "bars ->", out)
PY
```
Expected: a merged file under `captures/` (ignored), with no duplicate `(asset_id,resolution,type,date)`.

- [ ] **Step 2: Apply the six-symbol full backfill**

Run:
```bash
python tools/phase48/backfill_reference.py apply \
  --src _audit/phase49-finalization/seed/market.db \
  --work _audit/phase49-full-verification/db/backfill \
  --ref _audit/phase49-full-verification/captures/bars-all.ndjson.gz \
  --symbols _audit/phase49-full-verification/backfill-plan/symbols-six.csv \
  --run-id phase49-full-six-2026-11-10 \
  --out _audit/phase49-full-verification/evidence/backfill-six.json \
  --md _audit/phase49-full-verification/evidence/backfill-six.md
```
Expected: inserted > 0; `changed_existing=0`; `invalid=0` or explicitly listed.

- [ ] **Step 3: Apply the freshness window**

Run:
```bash
python tools/phase48/backfill_reference.py apply \
  --src _audit/phase49-finalization/seed/market.db \
  --work _audit/phase49-full-verification/db/backfill \
  --ref _audit/phase49-full-verification/captures/bars-all.ndjson.gz \
  --symbols _audit/phase49-full-verification/backfill-plan/symbols-freshness.csv \
  --run-id phase49-full-fresh-2026-11-10 \
  --since 2026-10-11 \
  --reuse-work \
  --out _audit/phase49-full-verification/evidence/backfill-fresh.json
```
Expected: only dates >= `2026-10-11` inserted; no existing row changed.

- [ ] **Step 4: Prove idempotency**

Re-run both commands with new `--run-id`s and assert `inserted=0` and `changed_existing=0`. Record the counts in `evidence/backfill-idempotency.json`.

- [ ] **Step 5: Verify price basis and provenance**

Before importing, compare reference type0 close with the DB's `last`/`closing` on common dates for the six symbols. If the median relative difference exceeds `OHLC_MATERIAL` (5%), stop and record `PRICE_BASIS_DIFFERENCE`; do not insert a mixed-basis series. The backfill report's `pre` block is the evidence; use it.

Run:
```bash
python - <<'PY'
import json
for f in ("backfill-six.json", "backfill-fresh.json"):
    r = json.load(open(r"_audit/phase49-full-verification/evidence/"+f, encoding="utf-8"))
    print(f, r["totals"], r["non_destructive"])
PY
```
Expected: `changed_existing=0`; inserted rows carry `src=rahavard365` and `backfill_rows` provenance; no raw/adjusted mix (only type0/raw inserted).

- [ ] **Step 6: Commit only evidence (not the DB)**
```bash
git add _audit/phase49-full-verification/evidence/backfill-six.json _audit/phase49-full-verification/evidence/backfill-six.md _audit/phase49-full-verification/evidence/backfill-fresh.json _audit/phase49-full-verification/evidence/backfill-idempotency.json
git commit -m "feat(phase49): apply provenance-tracked backfill on isolated copy"
```

---

### Task C4: Build the new Seed Candidate

**Files:**
- Create: `_audit/phase49-full-verification/stage09_seed_build.py`
- Create: `_audit/phase49-full-verification/test_stage09_seed_build.py`

**Interfaces:**
- CLI: `--base <old candidate> --work <backfilled DB> --pack <v2> --steps <csv> --symbols <csv> --reference-summary <json> --out-dir <seed dir> [--force]`
- Outputs `seed/market.db`, `seed/market.db.lzma`, `seed/market.db.gz`, `FINAL-SEED-MANIFEST.json`.

- [ ] **Step 1: Write the failing test**

Create `_audit/phase49-full-verification/test_stage09_seed_build.py`:
```python
#!/usr/bin/env python3
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage09_seed_build as S  # noqa: E402


def main():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT,src TEXT)")
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-01','rahavard365')")
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-02','legacy-unknown')")
    con.execute("CREATE TABLE backfill_rows(run_id TEXT,symbol TEXT,date TEXT)")
    con.execute("INSERT INTO backfill_rows VALUES('r1','الف','2026-01-01')")
    symbols = [{"symbol": "الف", "final_status": "VERIFIED_WITH_EVENTS",
                "rows": 2, "first_date": "2026-01-01", "last_date": "2026-01-02",
                "factor_steps": 1, "factor_verified": 1,
                "factor_reconstructed": 0, "factor_unverified": 0,
                "ref_coverage": "full", "remaining_blocker": ""}]
    steps = [{"symbol": "الف", "final_status": "VERIFIED_OFFICIAL"}]
    ref = {"capture_sha256": "abc", "source": {"captured_at": "2026-11-10"}}
    pack = {"version": "v2", "file_sha256": {"factors": "f"}}
    rep = S.build_metadata(con, pack, steps, symbols, ref)
    assert rep["reference_derived_rows"] == 1, rep
    assert con.execute("SELECT status FROM history_validity WHERE symbol='الف'").fetchone()[0] == "verified"
    rep2 = S.build_metadata(con, pack, steps, symbols, ref)
    assert rep2["reference_derived_rows"] == rep["reference_derived_rows"]
    assert con.execute("SELECT COUNT(*) FROM history_validity").fetchone()[0] == 1
    print("SEED BUILD TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Implement**

Base the script on `_audit/phase49-finalization/stageE_seed_meta.py` (read it first). Keep its `hashlib`, `json`, `os`, `sqlite3`, `lzma`, `time` imports and add `shutil`. Changes:
- `SEED` becomes `--out-dir/market.db`; copy `--work` to that path when absent or `--force`.
- Recreate `adjust_pack_state`, `history_validity`, `seed_manifest` from the new ledgers, not from the old parity directories.
- `history_validity.status` maps the six mission statuses to the existing three labels and keeps the detailed status in `notes`:
```python
STATUS_MAP = {
    "VERIFIED_WITH_EVENTS": "verified",
    "VERIFIED_NO_APPLICABLE_EVENT": "verified",
    "RECONSTRUCTED_VERIFIED": "reconstructed_verified",
    "CONFLICT": "unverified",
    "BLOCKED_SOURCE": "unverified",
    "INSUFFICIENT_EVIDENCE": "unverified",
}
```
- `reference_derived_rows` is `SELECT COUNT(*) FROM price_history WHERE src='rahavard365'`; it includes the Phase 4.8 rows and the new backfill, so the release gate covers the whole licensed footprint.
- Expose `build_metadata(con, pack, steps, symbols, ref)` as the testable core:
```python
def build_metadata(con, pack, steps, symbols, ref):
    con.execute("""CREATE TABLE IF NOT EXISTS history_validity(
        symbol TEXT PRIMARY KEY, rows INTEGER, first_date TEXT, last_date TEXT,
        reference_coverage TEXT, ref_days INTEGER, ref_first TEXT, ref_last TEXT,
        factor_steps INTEGER, factor_verified INTEGER,
        factor_reconstructed INTEGER, factor_unverified INTEGER,
        raw_open_verified INTEGER, raw_open_corrected INTEGER,
        factor_parity TEXT, adjusted_max_abs REAL, status TEXT, notes TEXT)""")
    con.execute("CREATE TABLE IF NOT EXISTS seed_manifest(key TEXT PRIMARY KEY, value TEXT)")
    counts = {}
    for row in symbols:
        st = STATUS_MAP[row["final_status"]]
        notes = "%s; blocker=%s" % (row["final_status"], row.get("remaining_blocker", ""))
        con.execute("""INSERT OR REPLACE INTO history_validity VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row["symbol"], row.get("rows"), row.get("first_date"),
             row.get("last_date"), row.get("ref_coverage"), None, None, None,
             row.get("factor_steps", 0), row.get("factor_verified", 0),
             row.get("factor_reconstructed", 0), row.get("factor_unverified", 0),
             None, None, None, None, st, notes))
        counts[st] = counts.get(st, 0) + 1
    ref_rows = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE src='rahavard365'").fetchone()[0]
    manifest = {
        "schema": "phase49-full-verification-seed-v1",
        "pack_version": pack.get("version"),
        "pack_factors_sha256": (pack.get("file_sha256") or {}).get("factors", ""),
        "reference_derived_rows": ref_rows,
        "reference_capture_sha256": ref.get("capture_sha256", ""),
        "reference_captured_at": (ref.get("source") or {}).get("captured_at", ""),
        "validity_status_counts": counts,
    }
    con.execute("DELETE FROM seed_manifest")
    for k, v in manifest.items():
        con.execute("INSERT INTO seed_manifest VALUES(?,?)",
                    (k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)))
    return manifest
```
- `seed_manifest` also includes `price_history_rows`, `symbols_with_history`, `pack_reference_sha256`, `open_corrections`, and `provenance` from the real build; `build_metadata` above is the unit-tested core and the full build adds those keys.
- Compress with `lzma.FORMAT_XZ, preset=9|EXTREME`; round-trip SHA; build gzip via `scripts/make_fast_seed.py --force`.
- Emit `FINAL-SEED-MANIFEST.json` with DB/LZMA/gzip SHA, sizes, counts, status counts, integrity, roundtrip, reference-derived rows.
- `PRAGMA integrity_check` and duplicate `(symbol,date)` count; fail if not ok.

- [ ] **Step 3: Run the unit test**

Run: `python _audit/phase49-full-verification/test_stage09_seed_build.py` → OK.

- [ ] **Step 4: Build the real candidate**

Run:
```bash
python _audit/phase49-full-verification/stage09_seed_build.py \
  --base _audit/phase49-finalization/seed/market.db \
  --work _audit/phase49-full-verification/db/backfill/market.db \
  --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \
  --steps _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv \
  --symbols _audit/phase49-full-verification/ledgers/HISTORY-COVERAGE-LEDGER.csv \
  --reference-summary _audit/phase49-full-verification/evidence/capture-summary.json \
  --out-dir _audit/phase49-full-verification/seed
```
Expected: `FINAL-SEED-MANIFEST.json` with integrity `ok`, `roundtrip_ok=true`, `reference_derived_rows>0`, and counts matching the ledgers.

- [ ] **Step 5: Prove integrity, duplicates, user data, restart**

Run:
```bash
python - <<'PY'
import sqlite3, json
p=r"_audit/phase49-full-verification/seed/market.db"
con=sqlite3.connect(p)
print("integrity", con.execute("PRAGMA integrity_check").fetchone()[0])
print("dup", con.execute("SELECT COUNT(*) FROM (SELECT symbol,date FROM price_history GROUP BY symbol,date HAVING COUNT(*)>1)").fetchone()[0])
print("rows", con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0])
print("validity", con.execute("SELECT status,COUNT(*) FROM history_validity GROUP BY status").fetchall())
print("watchlists", con.execute("SELECT COUNT(*) FROM user_watchlists").fetchone()[0])
PY
```
Expected: `ok`, `0`, `511139 + inserted`, validity counts from the ledger, user tables preserved.

- [ ] **Step 6: Commit manifest and evidence (not the DB)**
```bash
git add _audit/phase49-full-verification/stage09_seed_build.py _audit/phase49-full-verification/test_stage09_seed_build.py docs/opportunity-center/phase49/FINAL-SEED-MANIFEST.json _audit/phase49-full-verification/evidence/seed-integrity.json
git commit -m "feat(phase49): build provenance-complete Seed Candidate and manifest"
```

---

### Task C5: Parity and product checks

**Files:**
- Copy/parameterize: `_audit/phase49-full-verification/stageE_engine_parity_new.py`
- Copy/parameterize: `_audit/phase49-full-verification/stageE_product_tests_new.py`
- Create: `_audit/phase49-full-verification/stage10_parity.py` (thin runner that executes both harnesses and writes `evidence/parity.json` / `evidence/product-tests.json`)
- Modify: `backend-go/internal/chart/phase49_parity_test.go` only if the test pack path needs the new candidate (do not weaken assertions).
- Create: `docs/opportunity-center/phase49/FINAL-SEED-MANIFEST.json` (already from C4).

- [ ] **Step 1: Run the Python and Go parity suites**

Run:
```bash
python dev/test_phase49_correction_parity_v1.py
cd backend-go && go test ./internal/chart -run 'TestPhase49|TestAdjustEngine' -v && cd ..
```
Expected: Python 76/76; Go tests PASS. Record output in `evidence/parity-python-go.json`.

- [ ] **Step 2: Run the Phase 4.9 engine/product harnesses against the new candidate**

Copy `_audit/phase49-finalization/stageE_engine_parity.py` and `stageE_product_tests.py` to `_audit/phase49-full-verification/` and change only:
- `DB`/`SEED_DB` → `_audit/phase49-full-verification/seed/market.db`
- `PACK` → `data/ra365_corrections/ra365-phase49-rebuild-full-v2`
- `BIN` → `_audit/phase49-full-verification/borsd.exe` (build with `go build -o ... ./cmd/borsd`)
- `REF` → the merged normalized reference dir
- `BASE` → `_audit/phase49-full-verification/product-test`
Do not change thresholds or expected values. Run:
```bash
python _audit/phase49-full-verification/stageE_engine_parity_new.py
python _audit/phase49-full-verification/stageE_product_tests_new.py
```
Expected: engine parity 30/30; clean extraction, merge, user-data preservation, idempotency, restart, MA, weekly, monthly, chart-db all PASS. If a check fails, stop and root-cause; do not edit the harness to pass.

- [ ] **Step 3: Check API/UI labels**

Add a Go test in `backend-go/internal/chart/handlers_test.go` (or a new test file) that builds a temp DB with `history_validity.status='unverified'` and asserts the `/api/chart-db` response does not claim `verified: true` or `live: true`; if the handler exposes validity, assert it equals `unverified`. Add a source-level Vitest assertion that the chart feature does not render a hard-coded `Live`/`Verified` label without the API status. Run:
```bash
cd backend-go && go test ./internal/chart -run 'ChartDB' -v && cd ..
cd frontend-v2 && npx vitest run src/features/chart && cd ..
```
Expected: PASS; no false Live/Verified label.

- [ ] **Step 4: Record parity and product evidence**

Write `evidence/parity.json` and `evidence/product-tests.json` with pass/fail per check, binary SHA, DB SHA, pack SHA, and the exact commands. Commit.

---

### Task C6: Assemble the eight deliverables

**Files:**
- Create: `_audit/phase49-full-verification/stage11_deliverables.py`
- Create/modify: the eight files under `docs/opportunity-center/phase49/`.

- [ ] **Step 1: Copy/validate the ledgers**

Run:
```bash
python - <<'PY'
import csv, json, os, shutil
src = "_audit/phase49-full-verification"
dst = "docs/opportunity-center/phase49"
shutil.copy2(os.path.join(src, "ledgers", "ADJUSTMENT-EVIDENCE-LEDGER.csv"),
             os.path.join(dst, "ADJUSTMENT-EVIDENCE-LEDGER.csv"))
shutil.copy2(os.path.join(src, "ledgers", "HISTORY-COVERAGE-LEDGER.csv"),
             os.path.join(dst, "HISTORY-COVERAGE-LEDGER.csv"))
shutil.copy2(os.path.join(src, "seed", "FINAL-SEED-MANIFEST.json"),
             os.path.join(dst, "FINAL-SEED-MANIFEST.json"))
steps = list(csv.DictReader(open(os.path.join(dst, "ADJUSTMENT-EVIDENCE-LEDGER.csv"), encoding="utf-8")))
symbols = list(csv.DictReader(open(os.path.join(dst, "HISTORY-COVERAGE-LEDGER.csv"), encoding="utf-8")))
assert len(steps) == 8308, len(steps)
assert len(symbols) == 6103, len(symbols)
blob = json.dumps(json.load(open(os.path.join(dst, "FINAL-SEED-MANIFEST.json"), encoding="utf-8")), ensure_ascii=False)
assert "captures/" not in blob, "manifest must not point at raw capture paths"
print("deliverable ledgers OK", len(steps), len(symbols))
PY
```

- [ ] **Step 2: Write `FULL-VERIFICATION-REPORT.md`**

Required sections:
1. Verdict and the 10 criteria with explicit statuses.
2. Base/HEAD/branch/run IDs.
3. Adjustment counts by status, including the 1,358 reviewed and Volana.
4. Symbol coverage counts, including 6,328/6,103 reconciliation.
5. Backfill counts (six symbols, freshness, inserted, idempotency).
6. Seed SHA/LZMA/gzip, integrity, parity.
7. Solved vs unsolved lists with evidence links.
8. Reproduction commands.
Every number cites `evidence/*.json`.

- [ ] **Step 3: Write `UNVERIFIED-RECONCILIATION.md`**

One section per reconciliation category with a real sample, root cause, effect on DB/adjusted OHLC/API/chart, fix method, before/after evidence, and regression test.

- [ ] **Step 4: Compute the artifact SHA manifest**

Run:
```bash
python - <<'PY'
import hashlib, os
root = "docs/opportunity-center/phase49"
files = ["FULL-VERIFICATION-REPORT.md","ADJUSTMENT-EVIDENCE-LEDGER.csv",
         "HISTORY-COVERAGE-LEDGER.csv","UNVERIFIED-RECONCILIATION.md",
         "PYTHON-CI-MIGRATION.md","CI-FINAL-RESULTS.json",
         "FINAL-SEED-MANIFEST.json"]
out = os.path.join(root, "ARTIFACTS-SHA256-full-verification.txt")
with open(out, "w", encoding="utf-8", newline="\n") as w:
    for f in files:
        p = os.path.join(root, f)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        w.write("%s  %s\n" % (h, f))
print("wrote", out)
PY
```
Expected: eight files (the manifest itself is the eighth) with hashes.

- [ ] **Step 5: Commit**
```bash
git add docs/opportunity-center/phase49 _audit/phase49-full-verification/stage11_deliverables.py
git commit -m "docs(phase49): deliver full verification report, ledgers, and artifact hashes"
```

---

### Task C7: Final local gates

- [ ] **Step 1: Run all local gates**

Run:
```bash
cd backend-go && go vet ./... && go test ./... && cd ..
cd frontend-v2 && npm ci && npm run typecheck && npx vitest run && npm run build && cd ..
python dev/suite_registry_guard.py
python dev/phase49_rules_guard.py
python dev/run_all_tests.py --profile production
python dev/run_all_tests.py --profile data
python dev/version_anchor_guard.py
```
Expected: all green; record the commands and outputs in `evidence/local-gates.json`. Race detector is `NOT_MEASURED` locally (no gcc); CI is the evidence.

- [ ] **Step 2: Verify no raw data or DB is tracked**

Run:
```bash
git status --short
git ls-files _audit/phase49-full-verification/captures
git ls-files _audit/phase49-full-verification/seed
```
Expected: no capture or seed files tracked; only scripts/evidence/docs.

- [ ] **Step 3: Commit**
```bash
git add _audit/phase49-full-verification/evidence/local-gates.json
git commit -m "test(phase49): record local production and data gate results"
```

---

### Task C8: Final CI, report, and push

- [ ] **Step 1: Push the final HEAD**

Run:
```bash
git status --short
git push origin mission/phase49-full-verification-python-ci-2026-11-10
```
Expected: push succeeds; no force push.

- [ ] **Step 2: Wait for CI and fetch results**

Run:
```bash
gh run list --branch mission/phase49-full-verification-python-ci-2026-11-10 --limit 10
python tools/phase49/fetch_ci_results.py
```
Expected: `CI-FINAL-RESULTS.json` records the final SHA and every job. If a Production gate fails, fix the root cause and repeat from the failing task; do not hand-edit results. If `python-legacy` fails, confirm it is report-only and record the failure explicitly.

- [ ] **Step 3: Finalize the verdict**

Update `FULL-VERIFICATION-REPORT.md` with:
- Branch, base SHA, final HEAD.
- Reviewed step counts, verified/reconstructed/verified-no-event/conflict/blocked counts.
- Volana status.
- Backfilled symbols/rows.
- Anomalies resolved.
- 5,188 validity and 6,328 no-evidence status.
- Python test status.
- Production gate status.
- Seed SHA/LZMA SHA.
- Go/Python parity.
- Remaining owner decisions.
Verdict: `PHASE49_COMPLETE_DATA_READY` only if all required criteria pass; otherwise `PARTIAL_WITH_EXPLICIT_BLOCKERS` or `BLOCKED_BY_SOURCE_GAPS`.

- [ ] **Step 4: Regenerate the SHA manifest and commit**

Run the C6 SHA script again, then:
```bash
git add docs/opportunity-center/phase49
git commit -m "docs(phase49): record final CI results and verdict"
git push origin mission/phase49-full-verification-python-ci-2026-11-10
```
Do not merge, tag, or release.

## Plan C Acceptance

- Six-symbol backfill complete; freshness window only; second run inserts 0.
- New Seed Candidate: integrity ok, zero duplicates, user data preserved, SHA/LZMA round-trip, manifest with `reference_derived_rows`.
- Release gate blocks without owner approval.
- Python↔Go parity and product checks recorded.
- Eight deliverables exist with SHA manifest.
- Final CI on final HEAD recorded; verdict honest.
