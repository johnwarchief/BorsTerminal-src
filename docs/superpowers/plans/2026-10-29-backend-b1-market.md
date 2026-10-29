# B1 — بازار (تابلو) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve `/api/market`, `/api/market/delta` and `/api/market/sync-state` from Go with row-for-row, key-for-key parity against the Python backend on a frozen database, a payload no larger than Python's, and p95 no worse than 0.5× Python's.

**Architecture:** A read-only Go pipeline mirrors Python's: one SQL frame (the exact `_BOARD_SQL` text, extracted mechanically from `api/market.py`), vectorised derivations on a column frame (percent, powers, day-over-day, client split), the seven tape filters ported one-to-one, a per-row screening verdict, then assembly and an in-process cache whose body/ETag/headers match Python's observable behaviour. Delta is a mirror-diff journal; `sync-state` reads the same `market_sync.json` Python writes. The Python source stays the reference: every rule is copied from it, and every deviation must be proven by the parity harness, never by opinion.

**Tech Stack:** Go 1.26 (stdlib only in new packages; SQLite through the existing `internal/db` handle), `encoding/json`, `net/http`; Python 3.14 only for the golden-vector generator and the parity oracle.

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` (§۸ B1، §۹ B-G1، §۱۰، §۱۲)

## Global Constraints

- **Python is the reference.** Any disagreement is fixed in Go; a deliberate Python behaviour change is its own ruling with tests on both sides. Never edit the comparator or the goldens to make a case pass.
- **B0 invariants stay:** `market.db` is opened read-only (`mode=ro`); only `user.db` may be written, and only by the tape-history recorder (Task 7). No loops, no network, no scheduler in the Go server.
- **Routes and field names are frozen.** Additive fields only. `drop_unused` (77 keys/row) is the default body; `?fields=all` (100 keys/row) is the audit body and must not touch the cache or the delta mirror.
- **Same rows, same order** as Python: `ORDER BY m.d_even DESC, i.l_val18 ASC`, then `drop_duplicates(ins_code, keep=first)`.
- **Null honesty:** NaN/±Inf are dropped by the slim pass, never turned into 0; every column in Python's `_KEEP_NULL` keeps its null. Strings are byte-exact.
- **Rounding matches Python:** `round(x, 2)` / pandas `.round()` = half-to-even. Use `math.RoundToEven` with the same multiplication order (Task 3 has the exact helper).
- **Nothing writes `market.db`.** Window tables (`board_hist_v`, `board_hist_fv`) are read when present; when absent the same CTE text runs inline (read-only). They are read, not rebuilt, because the Python backend still owns the sync loop and rebuilds them on every signature change; inlining them on every request would cost the 1.5 s the cache exists to avoid. This premise dies at B2, when Go takes the loops — the plan to rebuild them belongs to that task, not this one.
- **Persian text:** literal UTF-8, no CJK/accented Latin; digits inside Persian copy via `chr(0x06F0+d)` only.
- **Commit discipline:** one commit per task, Persian message via heredoc without backticks; stage the named files only; never stage `_audit/FTS_TREND_COMPARE.csv` or `tools/market_state_probe.mts`; push only `mission/4-axes-2026-10-10`, never `main`.
- **No release, no traffic switch** in this plan. B1 ends with a green parity gate and a written report; the vite proxy for these three routes changes only after the owner reads that report.

---

### Task 1: Fixture, golden oracle, and SQL extractor

**Files:**
- Create: `tools/parity/make_board_fixture.py`
- Create: `tools/parity/gen_board_golden.py`
- Create: `tools/parity/extract_board_sql.py`
- Create: `backend-go/internal/board/testdata/fixture/market.db`, `user.db` (generated)
- Create: `backend-go/internal/board/testdata/golden/market.json`, `market_all.json`, `delta_negative.json`, `delta_mirror.json`, `sync_state.json` (generated)
- Create: `backend-go/internal/store/sql_text.go` (generated)
- Create: `dev/test_board_fixture_v1120.py` (guard: fixture reproducibility + golden freshness)

**Interfaces:**
- Produces: a committed 30-symbol fixture database and Python-oracle JSON bodies that later tasks assert against; `store.BoardSQL(dataDir)`-ready SQL text constants `store.HistVSQL`, `store.HistFvSQL`, `store.HistFvSlotSQL`, `store.BoardSQLBase`.

- [ ] **Step 1: Write the fixture generator**

`tools/parity/make_board_fixture.py` — build a small SQLite DB with only the columns the board query reads, and 30 rows that each pin one rule. Full code:

```python
#!/usr/bin/env python
"""فیکسچرِ تابلو برایِ تستِ Go — ۳۰ نماد، هر ردیف یک قاعده را قفل می‌کند.

خروجی: backend-go/internal/board/testdata/fixture/{market.db,user.db}
هیچ دادهٔ واقعی در آن نیست؛ همهٔ اعداد ساختگی و عمداً لبه‌ای‌اند.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "fixture")

DDL = """
CREATE TABLE market_watch (
  ins_code TEXT PRIMARY KEY, p_closing REAL, p_last REAL, q_tot_tran REAL,
  z_tot_tran REAL, price_yesterday REAL, q_tot_cap REAL, price_change REAL,
  d_even INTEGER, h_even INTEGER, pe REAL, eps REAL, price_max REAL,
  price_min REAL, price_first REAL, buy_q_vol REAL, buy_q_val REAL,
  buy_q_cnt REAL, sell_q_vol REAL, sell_q_val REAL, sell_q_cnt REAL,
  buy_q1_vol REAL, buy_q1_px REAL, sell_q1_vol REAL, sell_q1_px REAL,
  buy_q1_cnt REAL, allowed_min REAL, allowed_max REAL, fetched_at TEXT,
  market_cap REAL, market_cap_src TEXT);
CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_name TEXT);
CREATE TABLE boards (ins_code TEXT PRIMARY KEY, board TEXT);
CREATE TABLE client_type (ins_code TEXT, d_even INTEGER, buy_i_vol REAL, buy_n_vol REAL,
  sell_i_vol REAL, sell_n_vol REAL, buy_count_i REAL, sell_count_i REAL);
CREATE TABLE client_type_value (ins_code TEXT, d_even INTEGER, kind TEXT,
  buy_i_val REAL, buy_n_val REAL, sell_i_val REAL, sell_n_val REAL);
CREATE TABLE instrument_state (ins_code TEXT, c_etaval TEXT, c_etaval_title TEXT,
  d_even INTEGER, last_h_even INTEGER);
CREATE TABLE supervision_state (ins_code TEXT PRIMARY KEY, under_supervision_title TEXT,
  reason_count INTEGER, reasons TEXT);
CREATE TABLE stop_reasons (symbol TEXT PRIMARY KEY, vaziyat_desc TEXT,
  last_date_change TEXT, dalils TEXT);
CREATE TABLE tse_inst_stat (ins_code TEXT PRIMARY KEY, is5 REAL, is6 REAL);
CREATE TABLE price_history (symbol TEXT, date TEXT, high REAL, low REAL, close REAL, volume REAL);
CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, price_max REAL, price_min REAL,
  q_tot_tran REAL, market_cap REAL);
CREATE TABLE tape_history (ins_code TEXT, d_even INTEGER, price_min REAL, price_max REAL,
  q_tot_tran5j REAL);
CREATE TABLE tape_ih_slot (ins_code TEXT, slot INTEGER, d_even INTEGER, price_min REAL,
  price_max REAL, q_tot_tran5j REAL);
CREATE TABLE tape_history_state (id INTEGER PRIMARY KEY, newest_d_even INTEGER);
"""

DAY = 20261014


def hist_dates(n=60):
    # ۶۰ تاریخِ کاریِ ساختگی، نزولی‌ناپذیر لازم نیست؛ فقط یکتا و کوچک‌تر از DAY.
    import datetime as dt
    base = dt.date(2026, 7, 1)
    out = []
    for i in range(n):
        d = base + dt.timedelta(days=i)
        out.append(d.strftime("%Y-%m-%d"))
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    db = os.path.join(OUT, "market.db")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.executescript(DDL)
    dates = hist_dates(60)
    rows = []
    # (symbol, name, sector, close, last, qty, trades, py, chg, d_even, h_even,
    #  pmin, pmax, pfirst, tmin, tmax, buy_i, sell_i, bcnt, scnt, is5, is6,
    #  ctv(bi,bn,si,sn), mcap, mcap_src, board, st_title, stop, sup)
    rows.append(("عادی01", "عادی یک", "فلزات", 1000.0, 1100.0, 500000, 120, 1000.0, 100.0, DAY, 123000,
                 990.0, 1150.0, 1000.0, 900.0, 1150.0, 300000, 200000, 60, 40, None, 1.0e9,
                 (10e6, 5e6, 8e6, 6e6), 5.0e12, "mw", "بازار", None, None, None))
    rows.append(("پایین02", "پایین دو", "فلزات", 500.0, 495.0, 100000, 30, 500.0, -5.0, DAY, 121500,
                 480.0, 520.0, 500.0, 450.0, 520.0, 50000, 60000, 10, 12, None, 2.0e8,
                 (1e6, 2e6, 3e6, 1e6), 1.0e12, "mw", "بازار", None, None, None))
    rows.append(("نگهبان03", "نگهبان سه", "خودرو", 2000.0, 2100.0, 80000, 55, 1.0, 100.0, DAY, 122000,
                 1900.0, 2200.0, 2000.0, 1800.0, 2200.0, 30000, 20000, 7, 8, None, None,
                 (None, None, None, None), None, None, "بازار", None, None, None))
    rows.append(("بی‌معامله04", "بی معامله", "خودرو", 1500.0, 1500.0, 0, 0, 1500.0, 0.0, DAY, 120000,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, None, 0.0,
                 (0.0, 0.0, 0.0, 0.0), 0.0, "mw", "بازار", None, None, None))
    rows.append(("سخت05", "سخت پنج", "بانک", 3000.0, 3300.0, 900000, 400, 2000.0, 1000.0, DAY - 1, 122500,
                 2900.0, 3400.0, 3000.0, 2800.0, 3400.0, 400000, 100000, 90, 20, 5.0e8, 1.0e9,
                 (5e6, 1e6, 2e6, 8e6), 9.0e12, "mw", "بازار", "مجاز", None, None))
    rows.append(("پول‌هوشمند06", "پول هوشمند", "بانک", 4000.0, 4100.0, 2000000, 250, 3800.0, 200.0, DAY, 123500,
                 3900.0, 4200.0, 4000.0, 3700.0, 4200.0, 1200000, 900000, 200, 150, None, 3.0e8,
                 (9e6, 1e6, 5e6, 4e6), 2.0e13, "mw", "بازار", "مجاز-متوقف", None, None))
    rows.append(("متوقف07", "متوقف هفت", "بانک", 1000.0, 1000.0, 1000, 3, 1000.0, 0.0, DAY, 110000,
                 990.0, 1010.0, 1000.0, 900.0, 1100.0, 10, 20, 1, 2, None, None,
                 (None, None, None, None), 1.0e11, "mw", "بازار", None, "متوقف", None))
    rows.append(("ممنوع08", "ممنوع هشت", "بانک", 1200.0, 1200.0, 2000, 4, 1200.0, 0.0, DAY, 100000,
                 1190.0, 1210.0, 1200.0, 1100.0, 1300.0, 15, 25, 2, 3, None, None,
                 (None, None, None, None), 2.0e11, "mw", "بازار", "ممنوع", None, None))
    rows.append(("کدبه‌کد09", "کد به کد", "سیمان", 800.0, 810.0, 3000000, 500, 700.0, 100.0, DAY, 123900,
                 780.0, 830.0, 800.0, 700.0, 850.0, 2500000, 2400000, 300, 280, None, 4.0e8,
                 (12e6, 2e6, 10e6, 8e6), 3.0e12, "mw", "بازار", None, None, None))
    rows.append(("کف‌روبی10", "کف روبی", "سیمان", 600.0, 450.0, 200000, 80, 600.0, -150.0, DAY, 124000,
                 450.0, 700.0, 600.0, 450.0, 700.0, 90000, 50000, 40, 30, None, None,
                 (2e6, 1e6, 3e6, 2e6), 6.0e11, "mw", "بازار", None, None, None))
    rows.append(("کم‌سابقه11", "کم سابقه", "سیمان", 900.0, 950.0, 150000, 40, 900.0, 50.0, DAY, 121000,
                 880.0, 960.0, 900.0, 850.0, 980.0, 70000, 65000, 12, 11, None, None,
                 (3e6, 1e6, 2e6, 2e6), 9.0e11, "mw", "بازار", None, None, None))
    # ۱۰ ردیف سادهٔ دیگر تا «ترتیب/حذف/تکرار» هم پوشش بگیرد.
    for i in range(12, 30):
        code = "ساده%02d" % i
        rows.append((code, "ساده %d" % i, "سایر", 100.0 + i, 100.5 + i, 10000 + i, 10 + i,
                     100.0 + i, 0.5, DAY, 120000 + i, 99.0 + i, 102.0 + i, 100.0 + i,
                     90.0 + i, 110.0 + i, 6000, 5000, 5, 4, None, None,
                     (1e6, 1e6, 1e6, 1e6), 1.0e11 + i, "mw", "بازار", None, None, None))

    for r in rows:
        (sym, name, sector, pc, pl, qty, tno, py, chg, d_even, h_even, pmin, pmax, pfirst,
         tmin, tmax, bi, si, bc, sc, is5, is6, ctv, mcap, msrc, board, st_title, stop, sup) = r
        code = "INS-" + sym
        con.execute(
            "INSERT INTO market_watch(ins_code,p_closing,p_last,q_tot_tran,z_tot_tran,"
            "price_yesterday,q_tot_cap,price_change,d_even,h_even,pe,eps,price_max,price_min,"
            "price_first,buy_q_vol,buy_q_val,buy_q_cnt,sell_q_vol,sell_q_val,sell_q_cnt,"
            "buy_q1_vol,buy_q1_px,sell_q1_vol,sell_q1_px,buy_q1_cnt,allowed_min,allowed_max,"
            "fetched_at,market_cap,market_cap_src) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (code, pc, pl, qty, tno, py, pc * qty, chg, d_even, h_even, 7.5, 100.0,
             pmax, pmin, pfirst, 1000.0, 1.0e7, 10.0, 900.0, 9.0e6, 9.0,
             500.0, pl, 400.0, pl - 10.0, 2.0, tmin, tmax, "2026-10-14 12:00:00", mcap, msrc))
        con.execute("INSERT INTO instruments VALUES(?,?,?,?)", (code, sym, name, sector))
        con.execute("INSERT INTO boards VALUES(?,?)", (code, board))
        con.execute("INSERT INTO client_type VALUES(?,?,?,?,?,?,?,?)",
                    (code, DAY - 1, bi, 0.0, si, 0.0, bc, sc))
        if ctv is not None:
            con.execute("INSERT INTO client_type_value VALUES(?,?,?,?,?,?,?)",
                        (code, DAY - 1, "native", *ctv))
        con.execute("INSERT INTO tse_inst_stat VALUES(?,?,?)", (code, is5, is6))
        if st_title is not None:
            con.execute("INSERT INTO instrument_state VALUES(?,?,?,?,?)",
                        (code, "A", st_title, DAY - 1, 90000))
        if sup is not None:
            con.execute("INSERT INTO supervision_state VALUES(?,?,?,?)",
                        (code, sup, 1, "[]"))
        if stop is not None:
            con.execute("INSERT INTO stop_reasons VALUES(?,?,?,?)",
                        (sym, stop, "2026-10-13", "[]"))
        for k, dt in enumerate(dates):
            con.execute("INSERT INTO price_history VALUES(?,?,?,?,?,?)",
                        (sym, dt, pmax, pmin, pc, float(k + 1) * 1000.0))
        for k in range(60):
            con.execute("INSERT INTO tape_history VALUES(?,?,?,?,?)",
                        (code, DAY - k, pmin, pmax, 1000.0 + k))
            con.execute("INSERT INTO tape_ih_slot VALUES(?,?,?,?,?,?)",
                        (code, k, DAY - k, pmin, pmax, 1000.0 + k))
    # نمادی که در market_watch نیست ولی در instruments هست ⇒ هرگز نباید در تابلو بیاید.
    con.execute("INSERT INTO instruments VALUES(?,?,?,?)", ("INS-غایب", "غایب", "غایب", "سایر"))
    con.execute("INSERT INTO tape_history_state VALUES(1, ?)", (DAY - 60,))
    con.commit()
    con.close()

    user = os.path.join(OUT, "user.db")
    if os.path.exists(user):
        os.remove(user)
    sqlite3.connect(user).close()

    print("fixture rows: %d -> %s" % (len(rows), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it and verify the shape**

Run: `python tools/parity/make_board_fixture.py`
Expected: `fixture rows: 30 -> .../testdata/fixture`

Run: `python -c "import sqlite3; c=sqlite3.connect(r'backend-go/internal/board/testdata/fixture/market.db'); print(c.execute('select count(*) from market_watch').fetchone()[0]); print(c.execute('select count(*) from price_history').fetchone()[0])"`
Expected: `30` and `1800`

- [ ] **Step 3: Write the golden oracle**

`tools/parity/gen_board_golden.py` — imports the Python board builder against a *copy* of the fixture and writes the oracle bodies. It must not touch `market.db` of the repo, must not loop, and must restore `sys.modules` state by running in a fresh process:

```python
#!/usr/bin/env python
"""اوراکلِ طلاییِ B1: بدنۀ واقعیِ پایتون رویِ فیکسچر، برایِ تستِ Go.

بیرون از مخزن (پوشهٔ موقت) اجرا می‌شود؛ پنجره‌هایِ board_hist_* را همان پایتون
درِ کپی می‌سازد. خروجی: golden/market.json, market_all.json, delta_negative.json,
delta_mirror.json, sync_state.json
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "golden")


class Req:
    headers = {}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bors-b1-golden-")
    for name in ("market.db", "user.db"):
        shutil.copy2(os.path.join(FIX, name), os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ["BORS_CODAL_OFFLINE"] = "1"
    sys.path.insert(0, ROOT)
    import api.market as M  # noqa: E402  (پس از تنظیمِ متغیرها)

    os.makedirs(OUT, exist_ok=True)

    def save(name, resp):
        if isinstance(resp, dict):
            data = resp
            body = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        else:
            body = resp.body
            data = json.loads(body)
        path = os.path.join(OUT, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        print(name, len(body), "bytes", len(data.get("data") or data.get("rows") or []), "rows")

    save("market.json", M._build_market_response(Req(), drop_unused=True, store_cache=True))
    save("market_all.json", M._build_market_response(Req(), drop_unused=False, store_cache=False))
    save("delta_negative.json", M.get_market_delta(since=-1))
    save("delta_mirror.json", M.get_market_delta(since=int(json.load(open(os.path.join(OUT, "market.json"), encoding="utf-8"))["rev"])))
    save("sync_state.json", M.market_sync_state())
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Generate the goldens**

Run: `python tools/parity/gen_board_golden.py`
Expected: five lines `... bytes ... rows`; `market.json` has 30 rows, `market_all.json` 30, `delta_mirror.json` status `unchanged` (the mirror was just stored and nothing changed), `delta_negative.json` status `full` reason `no-cache`.

- [ ] **Step 5: Write the SQL extractor**

`tools/parity/extract_board_sql.py` — copies the four SQL constants from `api/market.py` into Go raw strings, byte-exact, so the Go query can never drift from Python:

```python
#!/usr/bin/env python
"""چهار متنِ SQL را از api/market.py بیرون می‌کشد و به Go می‌ریزد (بایت‌به‌بایت)."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "api", "market.py")
OUT = os.path.join(ROOT, "backend-go", "internal", "store", "sql_text.go")
NAMES = ["_BOARD_SQL", "_HIST_V_SQL", "_HIST_FV_SQL", "_HIST_FV_SLOT_SQL"]
GO = {"_BOARD_SQL": "BoardSQLBase", "_HIST_V_SQL": "HistVSQL",
      "_HIST_FV_SQL": "HistFvSQL", "_HIST_FV_SLOT_SQL": "HistFvSlotSQL"}


def main() -> int:
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in NAMES and isinstance(node.value, ast.Constant):
                found[t.id] = node.value.value
    missing = [n for n in NAMES if n not in found]
    if missing:
        sys.exit("missing SQL constants: %s" % missing)
    parts = ["// Code generated by tools/parity/extract_board_sql.py; DO NOT EDIT.",
             "// Source: api/market.py (verbatim SQL texts; Python is the reference).",
             "", "package store", ""]
    for name in NAMES:
        body = found[name]
        if "`" in body:
            sys.exit("%s contains a backtick; adjust the extractor" % name)
        parts.append("const %s = `%s`" % (GO[name], body))
        parts.append("")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))
    print("wrote", OUT, "->", {GO[n]: len(found[n]) for n in NAMES})
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the extractor and verify byte-equality**

Run: `python tools/parity/extract_board_sql.py`
Expected: `wrote .../sql_text.go -> {...}`

Run: `cd backend-go && gofmt -w internal/store/sql_text.go && gofmt -l internal/store && go build ./...`
Expected: gofmt prints nothing; build exits 0.

The byte-equality proof is check 2 of the guard in Step 7 (extract to a temp path, compare with the committed file); do not hand-verify it with a one-liner.

- [ ] **Step 7: Write the guard**

`dev/test_board_fixture_v1120.py` — same style as other guards (`check`, PASS/FAIL, final `N passed / M failed`), with these checks:
1. `python tools/parity/make_board_fixture.py` is deterministic: build into a temp copy twice (call the module's functions with `OUT` monkeypatched) and compare `market.db` sha256.
2. `sql_text.go` is current: re-run the extractor into a temp path and compare with the committed file byte-for-byte.
3. Goldens are current: re-run `gen_board_golden.py` in a temp dir (monkeypatch `OUT`) and compare each golden's parsed JSON to the committed one — equal after `json.loads`, so key order/indentation cannot hide drift.
4. The fixture contains exactly 30 `market_watch` rows and one `instruments` row absent from `market_watch`.

Register it in `dev/run_all_tests.py` SUITES next to `dev/test_bors_data_dir_seam.py`:
`('dev/test_board_fixture_v1120.py', 'B1 board fixture + goldens + SQL text are current')`.

- [ ] **Step 8: Commit**

```bash
git add tools/parity/make_board_fixture.py tools/parity/gen_board_golden.py tools/parity/extract_board_sql.py dev/test_board_fixture_v1120.py dev/run_all_tests.py backend-go/internal/store/sql_text.go backend-go/internal/board/testdata
git commit -m "$(cat <<'EOF'
test(go): فیکسچرِ ۳۰نمادی و اوراکلِ طلاییِ تابلو برایِ B1

هر ردیفِ فیکسچر یک قاعدهٔ لبه‌ای را قفل می‌کند؛ بدنۀ طلایی از خودِ پایتون رویِ
همان فیکسچر گرفته می‌شود و متنِ SQLِ تابلو بایت‌به‌بایت از api/market.py برداشته
می‌شود تا Go هرگز نسخهٔ خودیِ کوئری نسازد.
EOF
)"
```

---

### Task 2: `internal/store` — the board frame

**Files:**
- Create: `backend-go/internal/store/board.go`
- Create: `backend-go/internal/store/board_test.go`
- Uses: `backend-go/internal/store/sql_text.go` (Task 1), `backend-go/internal/db`

**Interfaces:**
- Produces: `store.Frame{Codes []string; Cols map[string][]any}`, `store.LoadBoard(db *sql.DB) (*Frame, error)`, `store.BoardSQLForTest(db *sql.DB) (string, error)`.

- [ ] **Step 1: Write the failing test**

```go
package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
)

func openFixture(t *testing.T) *db.Handles {
	t.Helper()
	src, err := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
	if err != nil {
		t.Fatal(err)
	}
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		b, err := os.ReadFile(filepath.Join(src, name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	h, err := db.Open(dst, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h
}

func TestLoadBoardFixture(t *testing.T) {
	h := openFixture(t)
	fr, err := LoadBoard(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if fr.N() != 30 {
		t.Fatalf("rows = %d, want 30", fr.N())
	}
	for _, col := range []string{"symbol", "name", "sector_name", "p_closing", "p_last", "q_tot_tran", "d_even", "mcap"} {
		if _, ok := fr.Cols[col]; !ok {
			t.Fatalf("missing column %q", col)
		}
	}
	for _, c := range fr.Codes {
		if c == "INS-غایب" {
			t.Fatal("instrument without a market_watch row leaked into the board")
		}
	}
}

func TestBoardSQLFallsBackWithoutWindowTables(t *testing.T) {
	h := openFixture(t)
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(text, "SELECT * FROM board_hist_v") {
		t.Fatal("missing-window fallback did not inline the history CTE")
	}
	if !strings.Contains(text, "WITH iso AS") {
		t.Fatal("fallback does not embed _HIST_V_SQL")
	}
	if !strings.Contains(text, "allowed_max <= ") {
		t.Fatal("mcap dead-band gate missing")
	}
}

func TestBoardSQLUsesWindowTablesWhenPresent(t *testing.T) {
	h := openFixture(t)
	for _, q := range []string{
		"CREATE TABLE board_hist_v(x INTEGER)",
		"CREATE TABLE board_hist_fv(x INTEGER)",
	} {
		if _, err := h.Market.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "SELECT * FROM board_hist_v") {
		t.Fatal("window tables present but the query did not use them")
	}
}

func TestBoardSQLPrefersSlotWindow(t *testing.T) {
	h := openFixture(t)
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "tape_ih_slot") {
		t.Fatal("fixture has tape_ih_slot rows; the slot window must be used")
	}
	if strings.Contains(text, "ROW_NUMBER() OVER (PARTITION BY ins_code ORDER BY d_even DESC) AS srn") {
		t.Fatal("row-based [ih] window used although slots are available")
	}
}
```

- [ ] **Step 2: Run and see it fail**

Run: `cd backend-go && go test ./internal/store -v`
Expected: FAIL — `undefined: LoadBoard`.

- [ ] **Step 3: Implement `board.go`**

```go
package store

import (
	"database/sql"
	"fmt"
	"strings"
)

// Frame قابِ ستون‌محور است: هر ستون یک []any به ترتیبِ ردیف‌هایِ تابلو.
type Frame struct {
	Codes []string
	Cols  map[string][]any
}

func (f *Frame) N() int { return len(f.Codes) }

// LoadBoard همان کوئریِ پایتون را رویِ market.dbِ فقط‌خواندنی اجرا می‌کند.
func LoadBoard(db *sql.DB) (*Frame, error) {
	text, err := boardSQL(db)
	if err != nil {
		return nil, err
	}
	rows, err := db.Query(text)
	if err != nil {
		return nil, fmt.Errorf("board query: %w", err)
	}
	defer rows.Close()
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	idx := -1
	for i, c := range cols {
		if c == "ins_code" {
			idx = i
		}
	}
	if idx < 0 {
		return nil, fmt.Errorf("board query returned no ins_code column")
	}
	vals := make([]any, len(cols))
	ptrs := make([]any, len(cols))
	for i := range vals {
		ptrs[i] = &vals[i]
	}
	fr := &Frame{Cols: make(map[string][]any, len(cols))}
	seen := make(map[string]bool, 6000)
	for rows.Next() {
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		code, _ := vals[idx].(string)
		if code == "" || seen[code] { // drop_duplicates(ins_code, keep="first")
			continue
		}
		seen[code] = true
		fr.Codes = append(fr.Codes, code)
		for i, c := range cols {
			fr.Cols[c] = append(fr.Cols[c], vals[i])
		}
	}
	return fr, rows.Err()
}

// BoardSQLForTest فقط برایِ تست: متنِ نهاییِ کوئری را برمی‌گرداند.
func BoardSQLForTest(db *sql.DB) (string, error) { return boardSQL(db) }

func boardSQL(db *sql.DB) (string, error) {
	mcap := "CAST(NULL AS REAL)"
	src := "CAST(NULL AS REAL)"
	if hasColumn(db, "market_watch", "market_cap") {
		gate := "(1=0)"
		if hasColumn(db, "market_watch", "allowed_min") && hasColumn(db, "market_watch", "allowed_max") {
			gate = mcapDeadBand("m")
		}
		mcap = mcapBulkExpr(db, "i", "m")
		src = "CASE WHEN NOT " + gate + " THEN m.market_cap_src END"
	}
	text := BoardSQLBase
	if !tableExists(db, "board_hist_v") || !tableExists(db, "board_hist_fv") {
		fv := HistFvSQL
		if tapeSlotsAvailable(db) {
			fv = HistFvSlotSQL
		}
		text = strings.Replace(text, "SELECT * FROM board_hist_v", "("+HistVSQL+")", 1)
		text = strings.Replace(text, "SELECT * FROM board_hist_fv", "("+fv+")", 1)
	}
	text = strings.Replace(text, "CAST(NULL AS REAL) AS mcap,", mcap+" AS mcap,", 1)
	text = strings.Replace(text, "CAST(NULL AS REAL) AS mcap_src", src+" AS mcap_src", 1)
	return text, nil
}

func tableExists(db *sql.DB, name string) bool {
	var n int
	err := db.QueryRow("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", name).Scan(&n)
	return err == nil && n > 0
}

func hasColumn(db *sql.DB, table, col string) bool {
	rows, err := db.Query("PRAGMA table_info(" + table + ")")
	if err != nil {
		return false
	}
	defer rows.Close()
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err != nil {
			return false
		}
		if name == col {
			return true
		}
	}
	return false
}

func tapeSlotsAvailable(db *sql.DB) bool {
	var n int
	err := db.QueryRow("SELECT COUNT(*) FROM tape_ih_slot").Scan(&n)
	return err == nil && n > 0
}

// mcapDeadBand عینِ fts_engine.mcap_dead_band_sql — بانِ مرده = بی‌اعتبار.
func mcapDeadBand(board string) string {
	return fmt.Sprintf(
		"(COALESCE(%[1]s.allowed_min, 0) > 0 AND COALESCE(%[1]s.allowed_max, 0) > 0"+
			" AND %[1]s.allowed_max <= %[1]s.allowed_min)", board)
}

// mcapBulkExpr عینِ fts_engine.mcap_bulk_expr: ستونِ رسمی، وگرنه آخرین
// daily_prices.market_capِ معتبر، پشتِ همان دروازهٔ بانِ مرده.
func mcapBulkExpr(db *sql.DB, alias, board string) string {
	if !hasColumn(db, "market_watch", "market_cap") {
		return "NULL"
	}
	expr := fmt.Sprintf("CASE WHEN %[1]s.market_cap > 0 THEN %[1]s.market_cap END", board)
	if hasColumn(db, "daily_prices", "market_cap") {
		expr = fmt.Sprintf("COALESCE(%s, (SELECT d.market_cap FROM daily_prices d"+
			" WHERE d.ins_code = %s.ins_code AND d.market_cap > 0"+
			" ORDER BY d.d_even DESC LIMIT 1))", expr, alias)
	}
	if hasColumn(db, "market_watch", "allowed_max") && hasColumn(db, "market_watch", "allowed_min") {
		expr = fmt.Sprintf("CASE WHEN NOT %s THEN %s END", mcapDeadBand(board), expr)
	}
	return expr
}
```

- [ ] **Step 4: Run and see it pass**

Run: `cd backend-go && go test ./internal/store -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend-go/internal/store/board.go backend-go/internal/store/board_test.go
git commit -m "$(cat <<'EOF'
feat(go): قابِ تابلو از همان SQLِ پایتون

متنِ کوئری بایت‌به‌بایت از api/market.py می‌آید؛ پنجره‌هایِ board_hist_* اگر
باشند خوانده و اگر نباشند همان CTE درجا اجرا می‌شود تا بانکِ فقط‌خواندنی چیزی
نسازد. دروازهٔ بانِ مرده هم همان تک‌تعریفِ fts_engine است.
EOF
)"
```

---

### Task 3: `internal/board` — derivations and client split

**Files:**
- Create: `backend-go/internal/board/derive.go`
- Create: `backend-go/internal/board/derive_test.go`
- Create: `backend-go/internal/clientsplit/clientsplit.go`
- Create: `backend-go/internal/clientsplit/clientsplit_test.go`

**Interfaces:**
- Consumes: `store.Frame`
- Produces: `board.Derive(fr *store.Frame) *board.Derived`; exported slices `Tvol`, `MonthAvgVol`, `PrevDayVol`, `PercentChange`, `PercentLast`, `PlpRaw`, `BuyerPower`, `BuyPowerI`, `SellPowerI`, `VolDod`, `VolTrend []string`, `RetailBuyPct`, `LegalBuyPct`, `RetailSellPct`, `LegalSellPct`, `PctBasis []string`, `IsLive []bool`, `DistMin30Pct`, `Mcap`, `McapSrc`. `NaN` means "no value". `clientsplit.Shares(buyI, buyN, sellI, sellN any) Shares{RetailBuy, LegalBuy, RetailSell, LegalSell *float64; Basis *string}`.

- [ ] **Step 1: Write the failing tests**

```go
package board

import (
	"math"
	"testing"

	"borsterminal/backend/internal/store"
)

func testFrame() *store.Frame {
	cols := map[string][]any{
		"symbol":          {"a", "b", "c", "d"},
		"p_closing":       {1100.0, 100.0, 100.0, 1000.0},
		"p_last":          {1100.0, 100.0, 125.0, 1000.0},
		"price_yesterday": {1000.0, 1.0, 100.0, 100.0},
		"price_change":    {100.0, 99.0, 25.0, 900.0},
		"q_tot_tran":      {10.0, 10.0, 10.0, 10.0},
		"month_avg_vol":   {5.0, 5.0, 5.0, 5.0},
		"prev_day_vol":    {4.0, 4.0, 4.0, 4.0},
		"buy_i_vol":       {10.0, 10.0, 10.0, 10.0},
		"sell_i_vol":      {10.0, 10.0, 10.0, 10.0},
		"buy_count_i":     {2.0, 0.0, 2.0, 2.0},
		"sell_count_i":    {2.0, 0.0, 2.0, 2.0},
		"ctv_buy_i_val":   {nil, nil, nil, nil},
		"ctv_buy_n_val":   {nil, nil, nil, nil},
		"ctv_sell_i_val":  {nil, nil, nil, nil},
		"ctv_sell_n_val":  {nil, nil, nil, nil},
		"d_even":          {int64(20261014), int64(20261014), int64(20261014), int64(20261013)},
		"min30_low":       {900.0, 90.0, 90.0, 900.0},
		"mcap":            {1.0, 1.0, 1.0, 1.0},
		"mcap_src":        {"mw", "mw", "mw", "mw"},
	}
	fr := &store.Frame{Cols: cols}
	for i := range cols["symbol"] {
		fr.Codes = append(fr.Codes, "c"+string(rune('0'+i)))
	}
	return fr
}

func TestPercentChangeGuards(t *testing.T) {
	d := Derive(testFrame())
	if got := d.PercentChange[1]; !math.IsNaN(got) {
		t.Fatalf("price_yesterday=1 is a guard value: percent must be null, got %v", got)
	}
	if got := d.PercentChange[0]; math.Abs(got-10.0) > 1e-9 {
		t.Fatalf("percent_change = %v, want 10", got)
	}
	if got := d.PercentChange[3]; !math.IsNaN(got) {
		t.Fatalf("|pct|>100 must be hidden, got %v", got)
	}
	if got := d.PercentLast[2]; math.Abs(got-25.0) > 1e-9 {
		t.Fatalf("percent_last = %v, want 25", got)
	}
	if got := d.PlpRaw[1]; math.Abs(got-9900.0) > 1e-9 {
		t.Fatalf("plp_raw must use py>0 only, got %v", got)
	}
	if !math.IsNaN(d.BuyerPower[1]) {
		t.Fatal("zero buy count must yield null buyer_power, not 1.0")
	}
	if d.VolTrend[0] != "up" {
		t.Fatalf("vol_dod 2.5 => up, got %q", d.VolTrend[0])
	}
	if d.IsLive[3] {
		t.Fatal("older d_even must not be live")
	}
	if got := d.DistMin30Pct[0]; math.Abs(got-18.18) > 1e-9 {
		t.Fatalf("dist_min30_pct = %v, want 18.18", got)
	}
}

func TestRoundHalfEven(t *testing.T) {
	for in, want := range map[float64]float64{
		2.675: 2.67, 2.665: 2.66, 1.005: 1.0, 1.015: 1.01, 0.125: 0.12, 0.135: 0.14,
	} {
		if got := Round2(in); got != want {
			t.Fatalf("Round2(%v) = %v, want %v", in, got, want)
		}
	}
}
```

```go
package clientsplit

import (
	"math"
	"testing"
)

func TestShares(t *testing.T) {
	got := Shares(10e6, 5e6, 8e6, 6e6)
	if got.RetailBuy == nil || math.Abs(*got.RetailBuy-66.7) > 1e-9 {
		t.Fatalf("retail buy = %v, want 66.7", got.RetailBuy)
	}
	if got.LegalBuy == nil || math.Abs(*got.LegalBuy-33.3) > 1e-9 {
		t.Fatalf("legal buy = %v, want 33.3", got.LegalBuy)
	}
	if got.Basis == nil || *got.Basis != "value" {
		t.Fatalf("basis = %v", got.Basis)
	}
	if got := Shares(nil, 5e6, 8e6, 6e6); got.RetailBuy != nil || got.Basis != nil {
		t.Fatal("missing source value must be unknown, not zero")
	}
	if got := Shares(-1.0, 5e6, 8e6, 6e6); got.RetailBuy != nil {
		t.Fatal("negative value must be unknown")
	}
	if got := Shares(0.0, 0.0, 8e6, 6e6); got.RetailBuy != nil {
		t.Fatal("zero denominator must be unknown")
	}
}
```

- [ ] **Step 2: Run and see them fail**

Run: `cd backend-go && go test ./internal/board ./internal/clientsplit`
Expected: FAIL — `undefined: Derive` / `undefined: Shares`.

- [ ] **Step 3: Implement `clientsplit.go`**

```go
package clientsplit

import "math"

// Shares همان client_split.shares است: مبنایِ ارزش، دو سمتِ مستقل، نبود = نامشخص.
type Shares struct {
	RetailBuy  *float64
	LegalBuy   *float64
	RetailSell *float64
	LegalSell  *float64
	Basis      *string
}

func money(v any) (float64, bool) {
	var x float64
	switch n := v.(type) {
	case float64:
		x = n
	case int64:
		x = float64(n)
	case int:
		x = float64(n)
	default:
		return 0, false
	}
	if math.IsNaN(x) || math.IsInf(x, 0) || x < 0 {
		return 0, false
	}
	return x, true
}

func share(retail, legal any) *float64 {
	r, ok1 := money(retail)
	l, ok2 := money(legal)
	if !ok1 || !ok2 {
		return nil
	}
	den := r + l
	if den <= 0 {
		return nil
	}
	x := math.RoundToEven(100.0*r/den*10.0) / 10.0
	return &x
}

func complement(s *float64) *float64 {
	if s == nil {
		return nil
	}
	x := math.RoundToEven((100.0-*s)*10.0) / 10.0
	return &x
}

func Shares(buyI, buyN, sellI, sellN any) Shares {
	rb := share(buyI, buyN)
	sb := share(sellI, sellN)
	out := Shares{RetailBuy: rb, LegalBuy: complement(rb),
		RetailSell: sb, LegalSell: complement(sb)}
	if rb != nil || sb != nil {
		basis := "value"
		out.Basis = &basis
	}
	return out
}
```

- [ ] **Step 4: Implement `derive.go`**

```go
package board

import (
	"math"

	"borsterminal/backend/internal/clientsplit"
	"borsterminal/backend/internal/store"
)

type Derived struct {
	Tvol, MonthAvgVol, PrevDayVol                   []float64
	PercentChange, PercentLast, PlpRaw              []float64
	BuyerPower, BuyPowerI, SellPowerI               []float64
	VolDod                                          []float64
	VolTrend                                        []string // up|down|flat|"" (=null)
	RetailBuyPct, LegalBuyPct, RetailSellPct, LegalSellPct []float64
	PctBasis                                        []string
	IsLive                                          []bool
	DistMin30Pct, Mcap                              []float64
	McapSrc                                         []string
}

// Round2 مثلِ numpy.round(2): نیم‌به‌زوج، نه نیم‌به‌بالا.
func Round2(x float64) float64 { return math.RoundToEven(x*100.0) / 100.0 }
func Round1(x float64) float64 { return math.RoundToEven(x*10.0) / 10.0 }
func Round0(x float64) float64 { return math.RoundToEven(x) }

// Num هر مقدارِ SQL را عدد می‌کند؛ null/رشته/NaN ⇒ NaN.
func Num(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int64:
		return float64(n)
	case int:
		return float64(n)
	default:
		return math.NaN()
	}
}

func col(fr *store.Frame, name string) []any { return fr.Cols[name] }

func nums(fr *store.Frame, name string) []float64 {
	raw := col(fr, name)
	out := make([]float64, len(raw))
	for i, v := range raw {
		out[i] = Num(v)
	}
	return out
}

func pick(v []any, i int) any {
	if v == nil || i >= len(v) {
		return nil
	}
	return v[i]
}

func Derive(fr *store.Frame) *Derived {
	n := fr.N()
	d := &Derived{}
	d.Tvol = nums(fr, "q_tot_tran")
	for i := range d.Tvol {
		if math.IsNaN(d.Tvol[i]) {
			d.Tvol[i] = 0
		}
	}
	d.MonthAvgVol = nums(fr, "month_avg_vol")
	d.PrevDayVol = nums(fr, "prev_day_vol")
	pc := nums(fr, "p_closing")
	pl := nums(fr, "p_last")
	py := nums(fr, "price_yesterday")
	chg := nums(fr, "price_change")
	pyOK := make([]float64, n)
	for i := range py {
		pyOK[i] = math.NaN()
		if py[i] > 1.0 {
			pyOK[i] = py[i]
		}
	}
	d.PercentChange = make([]float64, n)
	d.PercentLast = make([]float64, n)
	d.PlpRaw = make([]float64, n)
	for i := 0; i < n; i++ {
		fromClose := Round2((pc[i] - pyOK[i]) / pyOK[i] * 100)
		fromChange := Round2(chg[i] / pyOK[i] * 100)
		x := fromClose
		if math.IsNaN(x) {
			x = fromChange
		}
		if math.IsNaN(x) || math.Abs(x) > 100 {
			x = math.NaN()
		}
		d.PercentChange[i] = x
		y := Round2((pl[i] - pyOK[i]) / pyOK[i] * 100)
		if math.IsNaN(y) || math.Abs(y) > 100 {
			y = math.NaN()
		}
		d.PercentLast[i] = y
		r := math.NaN()
		if py[i] > 0 {
			r = Round2((pl[i] - py[i]) / py[i] * 100)
		}
		d.PlpRaw[i] = r
	}
	bi, si := nums(fr, "buy_i_vol"), nums(fr, "sell_i_vol")
	bc, sc := nums(fr, "buy_count_i"), nums(fr, "sell_count_i")
	buyPer := make([]float64, n)
	sellPer := make([]float64, n)
	d.BuyerPower = make([]float64, n)
	d.BuyPowerI = make([]float64, n)
	d.SellPowerI = make([]float64, n)
	for i := 0; i < n; i++ {
		buyPer[i], sellPer[i] = math.NaN(), math.NaN()
		if bc[i] > 0 {
			buyPer[i] = bi[i] / bc[i]
		}
		if sc[i] > 0 {
			sellPer[i] = si[i] / sc[i]
		}
		bp := Round2(buyPer[i] / sellPer[i])
		if bp > 10.0 {
			bp = 10.0
		}
		d.BuyerPower[i] = bp
		d.BuyPowerI[i] = Round0(buyPer[i])
		d.SellPowerI[i] = Round0(sellPer[i])
	}
	// درصدِ حقیقی/حقوقی — تنها ورودی چهار ارزشِ مبدأ است.
	d.RetailBuyPct = make([]float64, n)
	d.LegalBuyPct = make([]float64, n)
	d.RetailSellPct = make([]float64, n)
	d.LegalSellPct = make([]float64, n)
	d.PctBasis = make([]string, n)
	biV, bnV := col(fr, "ctv_buy_i_val"), col(fr, "ctv_buy_n_val")
	siV, snV := col(fr, "ctv_sell_i_val"), col(fr, "ctv_sell_n_val")
	put := func(dst []float64, i int, p *float64) {
		if p == nil {
			dst[i] = math.NaN()
			return
		}
		dst[i] = *p
	}
	for i := 0; i < n; i++ {
		s := clientsplit.Shares(pick(biV, i), pick(bnV, i), pick(siV, i), pick(snV, i))
		put(d.RetailBuyPct, i, s.RetailBuy)
		put(d.LegalBuyPct, i, s.LegalBuy)
		put(d.RetailSellPct, i, s.RetailSell)
		put(d.LegalSellPct, i, s.LegalSell)
		if s.Basis != nil {
			d.PctBasis[i] = *s.Basis
		}
	}
	// روندِ حجم: tvol نسبت به آخرین روزِ معامله‌شده.
	d.VolDod = make([]float64, n)
	d.VolTrend = make([]string, n)
	for i := 0; i < n; i++ {
		pdv := math.NaN()
		if d.PrevDayVol[i] > 0 {
			pdv = d.PrevDayVol[i]
		}
		d.VolDod[i] = Round2(d.Tvol[i] / pdv)
		switch {
		case math.IsNaN(d.VolDod[i]):
			d.VolTrend[i] = ""
		case d.VolDod[i] >= 1.10:
			d.VolTrend[i] = "up"
		case d.VolDod[i] <= 0.90:
			d.VolTrend[i] = "down"
		default:
			d.VolTrend[i] = "flat"
		}
	}
	// زنده = تازۀترین d_evenِ همین قاب.
	de := nums(fr, "d_even")
	maxDe := math.Inf(-1)
	for _, v := range de {
		if !math.IsNaN(v) && v > maxDe {
			maxDe = v
		}
	}
	d.IsLive = make([]bool, n)
	for i := range de {
		d.IsLive[i] = !math.IsNaN(de[i]) && de[i] == maxDe
	}
	min30 := nums(fr, "min30_low")
	d.DistMin30Pct = make([]float64, n)
	for i := 0; i < n; i++ {
		d.DistMin30Pct[i] = Round2((pc[i] - min30[i]) / pc[i] * 100)
	}
	d.Mcap = nums(fr, "mcap")
	d.McapSrc = make([]string, n)
	for i, v := range col(fr, "mcap_src") {
		if s, ok := v.(string); ok {
			d.McapSrc[i] = s
		}
	}
	return d
}
```

- [ ] **Step 5: Run the tests**

Run: `cd backend-go && go test ./internal/board ./internal/clientsplit -v`
Expected: PASS. `TestRoundHalfEven` pins banker's rounding; if `2.665` differs, check the multiplication order (Python: `round(2.665, 2)` is `2.66`).

- [ ] **Step 6: Commit**

```bash
git add backend-go/internal/board/derive.go backend-go/internal/board/derive_test.go backend-go/internal/clientsplit/clientsplit.go backend-go/internal/clientsplit/clientsplit_test.go
git commit -m "$(cat <<'EOF'
feat(go): مشتقاتِ تابلو و درصدِ حقیقی/حقوقی

نگهبان‌هایِ درصد (py=1، سقفِ ۱۰۰٪)، سرانهٔ خرید/فروش، روند حجم، زندهٔ نشست و
درصدِ ارزش‌محور با همان ریاضیِ client_split؛ گردکردن نیم‌به‌زوج مثلِ numpy.
EOF
)"
```

---

### Task 4: `internal/tapeflags` — the seven filters

**Files:**
- Create: `backend-go/internal/tapeflags/tapeflags.go`
- Create: `backend-go/internal/tapeflags/tapeflags_test.go`

**Interfaces:**
- Consumes: `store.Frame`, `board.Derived`
- Produces: `tapeflags.Flags{VolRatio, VolRatioFile, BuyerPowerRaw, Resistance59 []float64; Clock, Susp, Jet, Roobi, Noqteh, Smart, Legal []bool}` and `tapeflags.Apply(fr *store.Frame, d *board.Derived) *Flags`. `NaN` = unmeasured; every flag is already ANDed with `is_live`.

- [ ] **Step 1: Write the failing test**

```go
package tapeflags

import (
	"math"
	"testing"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/store"
)

func frame(rows int) *store.Frame {
	fr := &store.Frame{Cols: map[string][]any{}}
	put := func(name string, vals ...any) { fr.Cols[name] = vals }
	zeros := func(n int) []any {
		out := make([]any, n)
		for i := range out {
			out[i] = 0.0
		}
		return out
	}
	put("symbol", "a", "b", "c")
	put("p_closing", 100.0, 100.0, 100.0)
	put("p_last", 102.0, 100.0, 100.0)
	put("z_tot_tran", 40.0, 5.0, 40.0)
	put("q_tot_tran", 110.0, 10.0, 10.0)
	put("month_avg_vol", 10.0, 10.0, 10.0)
	put("prev_day_vol", 10.0, 10.0, 10.0)
	put("hist_sessions", int64(60), int64(10), int64(60))
	put("prior30_vol", 300.0, 300.0, 300.0)
	put("min_low_29", 98.0, 98.0, 98.0)
	put("is6", 60.0, 60.0, 60.0)
	put("tmin", 100.0, 0.0, 0.0)
	put("buy_q1_cnt", 2.0, 0.0, 0.0)
	put("buy_q1_vol", 500.0, 0.0, 0.0)
	put("buy_i_vol", 60.0, 60.0, 60.0)
	put("sell_i_vol", 40.0, 40.0, 40.0)
	put("sell_n_vol", 60.0, 60.0, 60.0)
	put("buy_count_i", 2.0, 2.0, 2.0)
	put("sell_count_i", 2.0, 2.0, 2.0)
	put("p_closing_raw", zeros(rows)...)
	put("buyer_power_hint", zeros(rows)...)
	for _, k := range []string{"h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max", "h49_max", "h59_max"} {
		put(k, 90.0, 90.0, 90.0)
	}
	put("ctv_buy_i_val", nil, nil, nil)
	put("ctv_buy_n_val", nil, nil, nil)
	put("ctv_sell_i_val", nil, nil, nil)
	put("ctv_sell_n_val", nil, nil, nil)
	put("d_even", int64(20261014), int64(20261014), int64(20261013))
	put("min30_low", 90.0, 90.0, 90.0)
	put("mcap", 1.0, 1.0, 1.0)
	put("mcap_src", "mw", "mw", "mw")
	for i := range rows {
		fr.Codes = append(fr.Codes, "c"+string(rune('0'+i)))
	}
	return fr
}

func TestFlags(t *testing.T) {
	fr := frame(3)
	d := board.Derive(fr)
	f := Apply(fr, d)
	if !f.Clock[0] {
		t.Fatalf("row0 should be clock: vol_ratio=%v ztt=%v", f.VolRatio[0], f.VolRatioFile[0])
	}
	if f.Clock[1] || f.Susp[1] || f.Jet[1] || f.Smart[1] {
		t.Fatal("row1 has no measurable history; every volume filter must be false")
	}
	if f.Clock[2] {
		t.Fatal("row2 is not the live session; flags must be masked by is_live")
	}
	if got := f.VolRatioFile[0]; math.Abs(got-11.0) > 1e-9 {
		t.Fatalf("formula ratio = %v, want 11", got)
	}
	if !math.IsNaN(f.Resistance59[1]) {
		t.Fatal("short history must make the ladder unmeasured")
	}
}
```

- [ ] **Step 2: Run and see it fail**

Run: `cd backend-go && go test ./internal/tapeflags`
Expected: FAIL — `undefined: Apply`.

- [ ] **Step 3: Implement `tapeflags.go`**

```go
package tapeflags

import (
	"math"
	"strconv"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/store"
)

const (
	volBaseSessions = 30
	histMinSessions = 30
	lowBaseSessions = 29
	jetVolMult      = 3.0
	suspVolMult     = 3.0
	jetBuyerPower   = 1.5
	clockDelta      = 0.02
	noqtehMaxDist   = 3.0
	roobiMaxChange  = -1.0
	roobiZd1Min     = 1.0
	roobiQd1Min     = 100.0
	clockTrades     = 30.0
	suspTrades      = 50.0
	noqtehTrades    = 5.0
	jetTrades       = 1.0
	jetMinTrades    = 100.0
	smartVolMult    = 1.5
	smartBPGe       = 1.0
	legalShareTvol  = 0.5
)

var jetLadder = []int{2, 5, 9, 19, 29, 39, 49, 59}

type Flags struct {
	VolRatio, VolRatioFile, BuyerPowerRaw, Resistance59 []float64
	Clock, Susp, Jet, Roobi, Noqteh, Smart, Legal     []bool
}

func col(fr *store.Frame, name string) []any { return fr.Cols[name] }

func numAt(v []any, i int) float64 {
	if v == nil || i >= len(v) {
		return math.NaN()
	}
	return board.Num(v[i])
}

// volumeBase: میانگینِ نمایشیِ ماه؛ صفرِ جعلی نمی‌سازد.
func volumeBase(fr *store.Frame) []float64 {
	out := make([]float64, fr.N())
	for i := 0; i < fr.N(); i++ {
		v := numAt(col(fr, "month_avg_vol"), i)
		if v > 0 {
			out[i] = v
		} else {
			out[i] = math.NaN()
		}
	}
	return out
}

// formulaVolumeBase: Σ[ih][0..29] ÷ ۳۰، فقط با سی نشستِ کامل.
func formulaVolumeBase(fr *store.Frame) []float64 {
	n := fr.N()
	out := make([]float64, n)
	prior := col(fr, "prior30_vol")
	hist := col(fr, "hist_sessions")
	for i := 0; i < n; i++ {
		base := numAt(prior, i) / volBaseSessions
		h := numAt(hist, i)
		if base > 0 && !math.IsNaN(h) && h >= volBaseSessions {
			out[i] = base
		} else {
			out[i] = math.NaN()
		}
	}
	return out
}

func ratio(fr *store.Frame, d *board.Derived, base []float64) []float64 {
	out := make([]float64, fr.N())
	for i := range out {
		out[i] = d.Tvol[i] / base[i]
	}
	return out
}

// resistanceLadder: بیشترینِ سقفِ [ih][2..59]، فقط با شصت نشستِ کامل.
func resistanceLadder(fr *store.Frame) []float64 {
	n := fr.N()
	out := make([]float64, n)
	hist := col(fr, "hist_sessions")
	for i := 0; i < n; i++ {
		best := 0.0
		for _, k := range jetLadder {
			name := "h" + strconv.Itoa(k) + "_max"
			v := numAt(col(fr, name), i)
			// NaN عینِ fillna(0) است: نشستِ بی‌معامله سقف را بالا نمی‌برد.
			if !math.IsNaN(v) && v > best {
				best = v
			}
		}
		h := numAt(hist, i)
		if !math.IsNaN(h) && h >= 60 {
			out[i] = best
		} else {
			out[i] = math.NaN()
		}
	}
	return out
}

func Apply(fr *store.Frame, d *board.Derived) *Flags {
	n := fr.N()
	f := &Flags{
		VolRatio:     make([]float64, n),
		VolRatioFile: make([]float64, n),
		BuyerPowerRaw: make([]float64, n),
		Resistance59: resistanceLadder(fr),
		Clock:        make([]bool, n),
		Susp:         make([]bool, n),
		Jet:          make([]bool, n),
		Roobi:        make([]bool, n),
		Noqteh:       make([]bool, n),
		Smart:        make([]bool, n),
		Legal:        make([]bool, n),
	}
	vr := ratio(fr, d, volumeBase(fr))
	vrf := ratio(fr, d, formulaVolumeBase(fr))
	for i := 0; i < n; i++ {
		f.VolRatio[i] = board.Round2(vr[i])
		f.VolRatioFile[i] = board.Round2(vrf[i])
		f.BuyerPowerRaw[i] = bpRaw(fr, i)
	}
	pc := nums(fr, "p_closing")
	pl := nums(fr, "p_last")
	ztt := nums(fr, "z_tot_tran")
	tmin := nums(fr, "tmin")
	q1c := nums(fr, "buy_q1_cnt")
	q1v := nums(fr, "buy_q1_vol")
	is6 := nums(fr, "is6")
	bi := nums(fr, "buy_i_vol")
	sn := nums(fr, "sell_n_vol")
	hist := nums(fr, "hist_sessions")
	prior := nums(fr, "prior30_vol")
	minLow := nums(fr, "min_low_29")
	for i := 0; i < n; i++ {
		alive := d.IsLive[i]
		plp := d.PlpRaw[i]
		bp := f.BuyerPowerRaw[i]
		// A) الگوی ساعت
		f.Clock[i] = alive && pc[i] > 0 && pl[i] >= pc[i]*(1.0+clockDelta) &&
			vrf[i] > 1.0 && ztt[i] > clockTrades
		// B) حجم مشکوک
		f.Susp[i] = alive && vrf[i] > suspVolMult && ztt[i] > suspTrades
		// C) جت
		f.Jet[i] = alive && vrf[i] > jetVolMult && bp >= jetBuyerPower &&
			pc[i] > 0 && pl[i] >= pc[i] && plp > 0 &&
			ztt[i] > jetTrades && ztt[i] > jetMinTrades &&
			pl[i] > f.Resistance59[i]
		// D) کف‌روبی
		f.Roobi[i] = alive && pl[i] > 0 && tmin[i] > 0 && pl[i] == tmin[i] &&
			q1c[i] > roobiZd1Min && plp < roobiMaxChange && q1v[i] > roobiQd1Min
		// E) نقطه‌زنی
		low := minLow[i]
		if low == 0 || math.IsNaN(hist[i]) || hist[i] < lowBaseSessions {
			low = math.NaN()
		}
		dist := board.Round2((pc[i] - low) / pc[i] * 100)
		f.Noqteh[i] = alive && pc[i] > 0 && dist < noqtehMaxDist &&
			vrf[i] > 1.0 && ztt[i] > noqtehTrades
		// F) ورودِ پولِ هوشمند — خطِ اول دروازه است
		line1 := hist[i] >= volBaseSessions && !math.IsNaN(prior[i])
		f.Smart[i] = alive && line1 && d.Tvol[i] > smartVolMult*is6[i] &&
			bp >= smartBPGe && pc[i] > 0 && pl[i] >= pc[i] && plp > 0
		// G) کد به کدِ حقوقی به حقیقی
		f.Legal[i] = f.Smart[i] && bi[i] > legalShareTvol*d.Tvol[i] &&
			sn[i] > legalShareTvol*d.Tvol[i]
	}
	return f
}

func bpRaw(fr *store.Frame, i int) float64 {
	bc := numAt(col(fr, "buy_count_i"), i)
	sc := numAt(col(fr, "sell_count_i"), i)
	if !(bc > 0) || !(sc > 0) {
		return math.NaN()
	}
	buy := numAt(col(fr, "buy_i_vol"), i) / bc
	sell := numAt(col(fr, "sell_i_vol"), i) / sc
	return buy / sell
}

func nums(fr *store.Frame, name string) []float64 {
	raw := col(fr, name)
	out := make([]float64, len(raw))
	for i, v := range raw {
		out[i] = board.Num(v)
	}
	return out
}
```

- [ ] **Step 4: Run the test**

Run: `cd backend-go && go test ./internal/tapeflags -v`
Expected: PASS. If `Clock[0]` is false, print `vrf[0]` — the fixture row uses `hist_sessions=60`, `prior30_vol=300` ⇒ base 10, `tvol=110` ⇒ 11.

- [ ] **Step 5: Commit**

```bash
git add backend-go/internal/tapeflags
git commit -m "$(cat <<'EOF'
feat(go): هفت فیلترِ تابلو با همان آستانه‌هایِ فایل

هر پرچم عیناً از tape_flags.py پورت شد: پنجرۀ سی‌نشستی برایِ نسبتِ حجم،
پلکانِ هشت‌نقطه‌ایِ مقاومت، دروازه‌هایِ کم‌سابقگی و ماسکِ is_live.
EOF
)"
```

---

### Task 5: `internal/screening` — the per-row eligibility verdict

**Files:**
- Create: `backend-go/internal/screening/screening.go`
- Create: `backend-go/internal/screening/screening_test.go`

**Interfaces:**
- Produces: `screening.Eligibility(row map[string]any, sessionDay int64) (bool, string, string)` — exact port of `funnel_engine.screening_eligibility` including the Persian reason strings and `_state_reason` timing label.

- [ ] **Step 1: Write the failing test**

```go
package screening

import "testing"

func row(m map[string]any) map[string]any { return m }

func TestEligibility(t *testing.T) {
	cases := []struct {
		name   string
		row    map[string]any
		ok     bool
		code   string
		reason string
	}{
		{"stale", row(map[string]any{"is_live": false, "st_title": "مجاز"}), false, "NOT_LIVE_SESSION", "درِ تازۀترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)"},
		{"stopped", row(map[string]any{"is_live": true, "stop_state": "متوقف"}), false, "STOPPED", "متوقف: متوقف"},
		{"forbidden", row(map[string]any{"is_live": true, "st_title": "ممنوع", "st_d": int64(20261014), "st_h": int64(93000)}), false, "FORBIDDEN_STATE", "ممنوع (طی معاملات — ساعت ۰۹:۳۰)"},
		{"stopped-title", row(map[string]any{"is_live": true, "st_title": "مجاز-متوقف", "st_d": int64(20261013)}), false, "STOPPED", "مجاز-متوقف — از نشستِ ۱۴۰۵/۰۷/۲۱"},
		{"permitted", row(map[string]any{"is_live": true, "st_title": "مجاز"}), true, "PERMITTED_STATE", "وضعیتِ ثبت‌شدۀ نماد: مجاز"},
		{"other-title", row(map[string]any{"is_live": true, "st_title": "محفوظ"}), true, "NO_BLOCKING_STATE", "وتوی معتبری ثبت نشده (وضعیت: محفوظ)"},
		{"none", row(map[string]any{"is_live": true}), true, "NO_BLOCKING_STATE", "وضعیتی برایِ این نماد ثبت نشده — وتویی نیست"},
	}
	for _, c := range cases {
		ok, code, reason := Eligibility(c.row, 20261014)
		if ok != c.ok || code != c.code || reason != c.reason {
			t.Fatalf("%s: got (%v,%q,%q) want (%v,%q,%q)", c.name, ok, code, reason, c.ok, c.code, c.reason)
		}
	}
}
```

- [ ] **Step 2: Run and see it fail**

Run: `cd backend-go && go test ./internal/screening`
Expected: FAIL — `undefined: Eligibility`.

- [ ] **Step 3: Implement `screening.go`**

```go
package screening

import (
	"fmt"
	"strconv"
	"strings"
)

const (
	forbiddenTitle = "ممنوع"
	permittedTitle = "مجاز"
	stoppedMark    = "متوقف"
)

func faDigits(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(rune(0x06F0 + int(r-'0')))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func num(v any) (float64, bool) {
	switch n := v.(type) {
	case int64:
		return float64(n), true
	case int:
		return float64(n), true
	case float64:
		return n, true
	case string:
		f, err := strconv.ParseFloat(n, 64)
		return f, err == nil
	default:
		return 0, false
	}
}

func stateReason(row map[string]any, title string, sessionDay int64) string {
	stD, hasD := num(row["st_d"])
	d := float64(sessionDay)
	if d == 0 {
		if v, ok := num(row["d_even"]); ok {
			d = v
		}
	}
	hhmm := ""
	if h, ok := num(row["st_h"]); ok && h != 0 {
		s := fmt.Sprintf("%06d", int(h))
		hhmm = s[:2] + ":" + s[2:4]
	}
	same := hasD && stD != 0 && d != 0 && stD == d
	if same {
		out := title + " (طی معاملات"
		if hhmm != "" {
			out += " — ساعت " + faDigits(hhmm)
		}
		return out + ")"
	}
	if hasD && stD != 0 {
		return title + " — از نشستِ " + faDigits(strconv.FormatInt(int64(stD), 10))
	}
	return "وضعیتِ ثبت‌شدۀ نماد: " + title
}

func Eligibility(row map[string]any, sessionDay int64) (bool, string, string) {
	title := strings.TrimSpace(strOf(row["st_title"]))
	code := strings.TrimSpace(strOf(row["st_code"]))
	if live, ok := row["is_live"].(bool); ok && !live {
		return false, "NOT_LIVE_SESSION", "درِ تازۀترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)"
	}
	if stop := strOf(row["stop_state"]); stop != "" {
		return false, "STOPPED", "متوقف: " + stop
	}
	if strings.HasPrefix(title, forbiddenTitle) {
		return false, "FORBIDDEN_STATE", stateReason(row, title, sessionDay)
	}
	if strings.Contains(title, stoppedMark) {
		return false, "STOPPED", stateReason(row, title, sessionDay)
	}
	if strings.HasPrefix(title, permittedTitle) {
		return true, "PERMITTED_STATE", "وضعیتِ ثبت‌شدۀ نماد: " + title
	}
	if title != "" || code != "" {
		return true, "NO_BLOCKING_STATE", "وتوی معتبری ثبت نشده (وضعیت: " + titleOr(title, code) + ")"
	}
	return true, "NO_BLOCKING_STATE", "وضعیتی برایِ این نماد ثبت نشده — وتویی نیست"
}

func strOf(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func titleOr(title, code string) string {
	if title != "" {
		return title
	}
	return code
}
```

- [ ] **Step 4: Run the test**

Run: `cd backend-go && go test ./internal/screening -v`
Expected: PASS. The forbidden case pins the Persian-digit time label; if it differs, the bug is in `stateReason`, not in the test.

- [ ] **Step 5: Commit**

```bash
git add backend-go/internal/screening
git commit -m "$(cat <<'EOF'
feat(go): وتویِ غربالگریِ هر ردیف با همان واژگانِ پایتون

ترتیبِ وتوها (نشستِ کهنه، توقف، ممنوع، متوقف، مجاز) و برچسبِ زمان‌مندِ وضعیت
عیناً از funnel_engine.screening_eligibility پورت شد.
EOF
)"
```

---

### Task 6: `internal/market` — assembly, cache, ETag, delta, sync-state, routes

**Files:**
- Create: `backend-go/internal/market/assemble.go`
- Create: `backend-go/internal/market/service.go`
- Create: `backend-go/internal/market/proc_windows.go`
- Create: `backend-go/internal/market/proc_other.go`
- Create: `backend-go/internal/market/service_test.go`
- Modify: `backend-go/internal/httpapi/server.go` (register the three routes)
- Modify: `backend-go/cmd/borsd/main.go` (construct the service)
- Modify: `backend-go/internal/httpapi/server_test.go` (new `New` signature; move the static-501 case)

**Interfaces:**
- Consumes: `store`, `board`, `tapeflags`, `screening`, `parity` (tests)
- Produces: `market.New(h *db.Handles, dataDir string) *Service`; `(*Service).Board/Delta/SyncState(http.ResponseWriter, *http.Request)`; `httpapi.New(cfg, handles, marketHandler)`; `market.assemble(fr, d, fl, dropUnused) []map[string]any`.

- [ ] **Step 1: Write `assemble.go` — the exact slim-record rules**

```go
package market

import (
	"math"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/tapeflags"
)

// عینِ _DROP_FIELDS در api/market.py — فقط برایِ بدنۀ پیش‌فرض.
var dropFields = map[string]bool{
	"eps": true, "price_max": true, "price_min": true,
	"buy_n_vol": true, "sell_n_vol": true,
	"buy_q_vol": true, "buy_q_val": true, "buy_q_cnt": true,
	"sell_q_vol": true, "sell_q_val": true, "sell_q_cnt": true,
	"prev_day_vol": true, "d1_vol": true, "max30_high": true,
	"plp_raw": true, "tmax": true, "vol_trend": true, "suspicious_vol": true,
	"d_even": true, "resistance_59": true, "dist_min30_pct": true,
	"ctv_buy_i_val": true, "ctv_buy_n_val": true,
	"ctv_sell_i_val": true, "ctv_sell_n_val": true,
}

// عینِ _KEEP_NULL — NaN در اینجا یعنی «کلید نیامد»، نه صفر.
var keepNull = map[string]bool{
	"vol_ratio": true, "vol_dod": true, "vol_trend": true, "dist_min30_pct": true,
	"p_max": true, "p_min": true, "p_first": true,
	"month_avg_vol": true, "prev_day_vol": true, "d1_vol": true,
	"prior30_vol": true, "min_low_29": true, "percent_last": true, "percent_change": true,
	"plp_raw": true, "vol_ratio_file": true, "hist_sessions": true, "tmin": true, "tmax": true,
	"buy_q1_cnt": true, "mcap": true, "mcap_src": true,
	"buyer_power": true, "buy_power_i": true, "sell_power_i": true,
	"buyer_power_raw": true, "resistance_59": true,
	"retail_buy_pct": true, "legal_buy_pct": true, "retail_sell_pct": true, "legal_sell_pct": true,
	"pct_basis": true, "ctv_d": true, "pct_is_current": true,
	"h2_max": true, "h5_max": true, "h9_max": true, "h19_max": true,
	"h29_max": true, "h39_max": true, "h49_max": true, "h59_max": true,
	"min30_low": true, "max30_high": true, "is5": true, "is6": true,
	"st_code": true, "st_title": true, "st_d": true, "st_h": true,
	"sup_flag": true, "sup_title": true, "sup_reason_count": true, "sup_reasons": true,
	"stop_state": true, "stop_since": true, "stop_reasons": true,
}

func put(rec map[string]any, name string, v any) {
	switch x := v.(type) {
	case nil:
		return
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			if keepNull[name] {
				return
			}
			rec[name] = 0.0
			return
		}
		rec[name] = x
	case int64, bool:
		rec[name] = x
	case string:
		if x == "" && (name == "vol_trend" || name == "pct_basis" || name == "mcap_src") {
			return
		}
		rec[name] = x
	}
}

func assemble(fr *store.Frame, d *board.Derived, fl *tapeflags.Flags, dropUnused bool) []map[string]any {
	n := fr.N()
	out := make([]map[string]any, n)
	for i := 0; i < n; i++ {
		rec := map[string]any{"ins_code": fr.Codes[i]}
		for name, vals := range fr.Cols {
			if name == "ins_code" {
				continue
			}
			if dropUnused && dropFields[name] {
				continue
			}
			if i < len(vals) {
				put(rec, name, vals[i])
			}
		}
		// ستون‌هایِ محاسبه‌شده — همان نام‌هایی که رابط می‌خواند.
		put(rec, "tvol", d.Tvol[i])
		put(rec, "percent_change", d.PercentChange[i])
		put(rec, "percent_last", d.PercentLast[i])
		put(rec, "plp_raw", d.PlpRaw[i])
		put(rec, "buyer_power", d.BuyerPower[i])
		put(rec, "buy_power_i", d.BuyPowerI[i])
		put(rec, "sell_power_i", d.SellPowerI[i])
		put(rec, "retail_buy_pct", d.RetailBuyPct[i])
		put(rec, "legal_buy_pct", d.LegalBuyPct[i])
		put(rec, "retail_sell_pct", d.RetailSellPct[i])
		put(rec, "legal_sell_pct", d.LegalSellPct[i])
		put(rec, "pct_basis", d.PctBasis[i])
		put(rec, "vol_dod", d.VolDod[i])
		put(rec, "vol_trend", d.VolTrend[i])
		put(rec, "vol_ratio", board.Round1(fl.VolRatio[i]))
		put(rec, "vol_ratio_file", board.Round2(fl.VolRatioFile[i]))
		put(rec, "buyer_power_raw", fl.BuyerPowerRaw[i])
		put(rec, "resistance_59", fl.Resistance59[i])
		put(rec, "dist_min30_pct", d.DistMin30Pct[i])
		put(rec, "mcap", d.Mcap[i])
		if d.McapSrc[i] != "" {
			rec["mcap_src"] = d.McapSrc[i]
		}
		rec["is_live"] = d.IsLive[i]
		rec["f_clock"] = fl.Clock[i]
		rec["f_susp"] = fl.Susp[i]
		rec["f_jet"] = fl.Jet[i]
		rec["f_roobi"] = fl.Roobi[i]
		rec["f_noqteh"] = fl.Noqteh[i]
		rec["f_smart"] = fl.Smart[i]
		rec["f_legal"] = fl.Legal[i]
		rec["suspicious_vol"] = fl.Susp[i]
		out[i] = rec
	}
	return out
}
```

- [ ] **Step 2: Write `service.go`**

```go
package market

import (
	"context"
	"crypto/md5"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/screening"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/tapeflags"
)

const (
	ttl          = 60 * time.Second
	staleCeiling = 300 * time.Second
	journalMax   = 240
	// عینِ api/_core._PROC_TTL_S — نفسِ اندازه‌گیری‌شده، نه یک عددِ خودی.
	procCacheTTL = 10 * time.Second
	procTimeout  = 15 * time.Second
)

type journalEntry struct {
	rev   int64
	codes []string
}

type Service struct {
	market  *sql.DB
	user    *sql.DB
	dataDir string

	mu       sync.Mutex
	body     []byte
	etag     string
	builtAt  time.Time
	ready    bool
	building bool

	rev     int64
	byCode  map[string]map[string]any
	meta    map[string]any
	counts  map[string]any
	journal []journalEntry

	procMu    sync.Mutex
	procAt    time.Time
	procValue bool
}

func New(h *db.Handles, dataDir string) *Service {
	return &Service{market: h.Market, user: h.User, dataDir: dataDir}
}

func (s *Service) Board(w http.ResponseWriter, r *http.Request) {
	if r.URL.Query().Get("fields") == "all" {
		body, etag, err := s.build(false, false)
		if err != nil {
			httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
			return
		}
		if inm := r.Header.Get("If-None-Match"); inm != "" && inm == etag {
			w.Header().Set("ETag", etag)
			w.WriteHeader(http.StatusNotModified)
			return
		}
		writeBody(w, body, etag, "MISS")
		return
	}
	body, etag, xcache, err := s.cached()
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	if inm := r.Header.Get("If-None-Match"); inm != "" && inm == etag {
		w.Header().Set("ETag", etag)
		w.WriteHeader(http.StatusNotModified)
		return
	}
	writeBody(w, body, etag, xcache)
}

func writeBody(w http.ResponseWriter, body []byte, etag, xcache string) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "max-age=15")
	w.Header().Set("X-Cache", xcache)
	w.Header().Set("ETag", etag)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}

func (s *Service) cached() ([]byte, string, string, error) {
	s.mu.Lock()
	body, etag, builtAt, ready := s.body, s.etag, s.builtAt, s.ready
	s.mu.Unlock()
	if !ready {
		b, e, err := s.build(true, true)
		if err != nil {
			return nil, "", "", err
		}
		return b, e, "MISS", nil
	}
	age := time.Since(builtAt)
	if age < ttl {
		return body, etag, "HIT", nil
	}
	if age > staleCeiling {
		b, e, err := s.build(true, true)
		if err != nil {
			return nil, "", "", err
		}
		return b, e, "MISS", nil
	}
	s.rebuildAsync()
	return body, etag, "STALE", nil
}

func (s *Service) rebuildAsync() {
	s.mu.Lock()
	if s.building {
		s.mu.Unlock()
		return
	}
	s.building = true
	s.mu.Unlock()
	go func() {
		defer func() {
			s.mu.Lock()
			s.building = false
			s.mu.Unlock()
		}()
		_, _, _ = s.build(true, true)
	}()
}

func (s *Service) build(dropUnused, storeCache bool) ([]byte, string, error) {
	fr, err := store.LoadBoard(s.market)
	if err != nil {
		return nil, "", err
	}
	d := board.Derive(fr)
	fl := tapeflags.Apply(fr, d)
	recs := assemble(fr, d, fl, dropUnused)
	meta, err := boardMeta(s.market)
	if err != nil {
		return nil, "", err
	}
	sessionDay := int64(0)
	if v, ok := meta["d_even"].(int64); ok {
		sessionDay = v
	}
	for _, rec := range recs {
		ok, code, reason := screening.Eligibility(rec, sessionDay)
		rec["screening_eligible"] = ok
		if !ok {
			rec["screening_exclusion_code"] = code
			rec["screening_exclusion_reason"] = reason
		}
	}
	live := 0
	for _, rec := range recs {
		if v, _ := rec["is_live"].(bool); v {
			live++
		}
	}
	counts := map[string]any{"count": len(recs), "live_count": live, "fossil_count": len(recs) - live}

	s.mu.Lock()
	rev := s.rev
	var changed []string
	if storeCache && s.byCode != nil {
		changed = diffCodes(s.byCode, recs)
		if len(changed) > 0 {
			rev++
			s.journal = append(s.journal, journalEntry{rev: rev, codes: changed})
			if len(s.journal) > journalMax {
				s.journal = s.journal[len(s.journal)-journalMax:]
			}
		}
	}
	s.mu.Unlock()

	payload := map[string]any{
		"status": "success", "rev": rev, "data": recs, "meta": meta,
		"count": len(recs), "live_count": live, "fossil_count": len(recs) - live,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, "", err
	}
	sum := md5.Sum(body)
	etag := `"` + hex.EncodeToString(sum[:])[:16] + `"`

	if storeCache {
		s.mu.Lock()
		s.body, s.etag, s.builtAt, s.ready = body, etag, time.Now(), true
		s.byCode = indexByCode(recs)
		s.meta, s.counts, s.rev = meta, counts, rev
		s.mu.Unlock()
	}
	return body, etag, nil
}

func indexByCode(recs []map[string]any) map[string]map[string]any {
	out := make(map[string]map[string]any, len(recs))
	for _, r := range recs {
		if code, ok := r["ins_code"].(string); ok {
			out[code] = r
		}
	}
	return out
}

func diffCodes(old map[string]map[string]any, recs []map[string]any) []string {
	var out []string
	for _, r := range recs {
		code, _ := r["ins_code"].(string)
		prev, ok := old[code]
		if !ok || !sameRecord(prev, r) {
			out = append(out, code)
		}
	}
	for code := range old {
		found := false
		for _, r := range recs {
			if r["ins_code"] == code {
				found = true
				break
			}
		}
		if !found {
			out = append(out, code)
		}
	}
	return out
}

func sameRecord(a, b map[string]any) bool {
	x, err1 := json.Marshal(a)
	y, err2 := json.Marshal(b)
	return err1 == nil && err2 == nil && string(x) == string(y)
}

func boardMeta(db *sql.DB) (map[string]any, error) {
	var dEven, hEven sql.NullInt64
	var lastSync sql.NullString
	err := db.QueryRow("SELECT d_even, MAX(h_even), MAX(fetched_at) FROM market_watch" +
		" WHERE d_even = (SELECT MAX(d_even) FROM market_watch)").Scan(&dEven, &hEven, &lastSync)
	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}
	meta := map[string]any{"d_even": nil, "h_even": nil, "last_sync": nil}
	if dEven.Valid {
		meta["d_even"] = dEven.Int64
	}
	if hEven.Valid {
		meta["h_even"] = hEven.Int64
	}
	if lastSync.Valid {
		meta["last_sync"] = lastSync.String
	}
	return meta, nil
}

func (s *Service) Delta(w http.ResponseWriter, r *http.Request) {
	since, _ := strconv.ParseInt(r.URL.Query().Get("since"), 10, 64)
	if r.URL.Query().Get("since") == "" {
		since = -1
	}
	payload := s.delta(since)
	httpapi.WriteJSON(w, http.StatusOK, payload)
}

func (s *Service) delta(since int64) map[string]any {
	s.mu.Lock()
	ready, mirrorRev, meta, counts, byCode, journal := s.ready, s.rev, s.meta, s.counts, s.byCode, s.journal
	s.mu.Unlock()
	if !ready {
		s.rebuildAsync()
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "no-cache"}
	}
	if since == mirrorRev {
		return withCounts(map[string]any{"status": "unchanged", "rev": mirrorRev, "meta": meta}, counts)
	}
	if since < 0 {
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "no-cache"}
	}
	if since > mirrorRev {
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "stale-client"}
	}
	if len(journal) == 0 || journal[0].rev-1 > since {
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "journal-gap"}
	}
	codes := map[string]bool{}
	for _, e := range journal {
		if since < e.rev && e.rev <= mirrorRev {
			for _, c := range e.codes {
				codes[c] = true
			}
		}
	}
	rows := make([]map[string]any, 0, len(codes))
	for c := range codes {
		row, ok := byCode[c]
		if !ok {
			return map[string]any{"status": "full", "rev": mirrorRev, "reason": "missing-rows"}
		}
		rows = append(rows, row)
	}
	return withCounts(map[string]any{"status": "delta", "rev": mirrorRev, "rows": rows, "meta": meta}, counts)
}

func withCounts(m, counts map[string]any) map[string]any {
	for k, v := range counts {
		m[k] = v
	}
	return m
}

func (s *Service) SyncState(w http.ResponseWriter, r *http.Request) {
	last := map[string]any{}
	if raw, err := os.ReadFile(filepath.Join(s.dataDir, "market_sync.json")); err == nil {
		_ = json.Unmarshal(raw, &last)
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "success", "running": s.marketRunning(), "last": last,
	})
}

// marketRunning عینِ _count_procs("test_tsetmc") با کشِ ۶۰ثانیه‌ای.
func (s *Service) marketRunning() bool {
	s.procMu.Lock()
	defer s.procMu.Unlock()
	if time.Since(s.procAt) < procCacheTTL {
		return s.procValue
	}
	s.procAt = time.Now()
	s.procValue = false
	ctx, cancel := context.WithTimeout(context.Background(), procTimeout)
	defer cancel()
	ps := exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-Command",
		"(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'test_tsetmc' }).Count")
	hideWindow(ps)
	out, err := ps.Output()
	if err == nil {
		n, _ := strconv.Atoi(strings.TrimSpace(string(out)))
		s.procValue = n > 0
	}
	return s.procValue
}
```

- [ ] **Step 2b: Hide the console window of the process probe**

`api/_core.py` runs PowerShell with `CREATE_NO_WINDOW`. Without the same flag the desktop app would flash a console window every ten seconds that the UI polls `sync-state`. Two tiny build-tagged files keep `service.go` portable:

Create `backend-go/internal/market/proc_windows.go`:

```go
//go:build windows

package market

import (
	"os/exec"
	"syscall"
)

// hideWindow عینِ CREATE_NO_WINDOWِ api/_core.py؛ بی‌آن هر پولینگِ sync-state
// یک پنجرۀ کنسول رویِ میزِ کاربر پدیدار می‌کند.
func hideWindow(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
}
```

Create `backend-go/internal/market/proc_other.go`:

```go
//go:build !windows

package market

import "os/exec"

func hideWindow(cmd *exec.Cmd) {}
```

- [ ] **Step 3: Wire the routes**

In `httpapi/server.go`:

```go
// Market سه مسیرِ پورت‌شدهٔ تابلو را می‌گیرد؛ nil یعنی هیچ مسیری پورت نشده.
type Market interface {
	Board(http.ResponseWriter, *http.Request)
	Delta(http.ResponseWriter, *http.Request)
	SyncState(http.ResponseWriter, *http.Request)
}

func New(cfg config.Config, h *db.Handles, m Market) http.Handler {
	s := &Server{
		cfg:      cfg,
		db:       h,
		started:  time.Now(),
		rssMB:    rssMB,
		patterns: compileRoutes(Routes()),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.healthz)
	if m != nil {
		mux.HandleFunc("GET /api/market", m.Board)
		mux.HandleFunc("GET /api/market/delta", m.Delta)
		mux.HandleFunc("GET /api/market/sync-state", m.SyncState)
	}
	mux.HandleFunc("/", s.apiGate)
	return mux
}
```

In `cmd/borsd/main.go`, add the import `"borsterminal/backend/internal/market"` and change the last lines to:

```go
	defer handles.Close()

	mkt := market.New(handles, cfg.DataDir)
	srv := &http.Server{Addr: cfg.Addr, Handler: httpapi.New(cfg, handles, mkt)}
```

In `server_test.go`: every `New(cfg, h)` becomes `New(cfg, h, nil)`; the static-501 test switches its path to `/api/fts/config` (any route that stays unported in B1). Add `TestMarketRoutesAreNotPortedWhenServiceMissing`: with a nil market, `GET /api/market` still answers 501 — that keeps the old contract covered.

- [ ] **Step 4: Write `service_test.go` against the Python goldens**

```go
package market

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/parity"
)

func fixtureService(t *testing.T) *Service {
	t.Helper()
	src, _ := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		b, err := os.ReadFile(filepath.Join(src, name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	h, err := db.Open(dst, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return New(h, dst)
}

func golden(t *testing.T, name string) any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "board", "testdata", "golden", name))
	if err != nil {
		t.Fatal(err)
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func getJSON(t *testing.T, s *Service, target string, hdr map[string]string) (int, any, []byte, string) {
	t.Helper()
	req := httptest.NewRequest("GET", target, nil)
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	switch {
	case strings.HasPrefix(target, "/api/market/delta"):
		s.Delta(rec, req)
	case strings.HasPrefix(target, "/api/market/sync-state"):
		s.SyncState(rec, req)
	default:
		s.Board(rec, req)
	}
	var v any
	if rec.Body.Len() > 0 {
		if err := json.Unmarshal(rec.Body.Bytes(), &v); err != nil {
			t.Fatalf("%s: %v", target, err)
		}
	}
	return rec.Code, v, rec.Body.Bytes(), rec.Header().Get("ETag")
}

func TestBoardMatchesPythonGolden(t *testing.T) {
	s := fixtureService(t)
	_, got, _, _ := getJSON(t, s, "/api/market", nil)
	res := parity.Compare(golden(t, "market.json"), got, parity.Options{})
	if !res.Pass {
		t.Fatalf("default board differs: %v", res.Diffs[:min(5, len(res.Diffs))])
	}
	_, gotAll, _, _ := getJSON(t, s, "/api/market?fields=all", nil)
	if res := parity.Compare(golden(t, "market_all.json"), gotAll, parity.Options{}); !res.Pass {
		t.Fatalf("fields=all differs: %v", res.Diffs[:min(5, len(res.Diffs))])
	}
	_, sync, _, _ := getJSON(t, s, "/api/market/sync-state", nil)
	// `running` از شمارشِ زندۀ پروسۀ سینکر می‌آید، نه از داده؛ رویِ ماشینی که
	// سینکرِ پایتون زنده است true می‌شود. شکلش اینجا سنجیده می‌شود، مقدارش را
	// گیتِ دو‌سروری (Task 8) هم‌زمان رویِ هر دو طرف می‌سنجد.
	if res := parity.Compare(golden(t, "sync_state.json"), sync, parity.Options{Exclude: []string{"running"}}); !res.Pass {
		t.Fatalf("sync-state differs: %v", res.Diffs)
	}
}

func TestDeltaContract(t *testing.T) {
	s := fixtureService(t)
	_, full, _, _ := getJSON(t, s, "/api/market/delta?since=-1", nil)
	if res := parity.Compare(golden(t, "delta_negative.json"), full, parity.Options{}); !res.Pass {
		t.Fatalf("delta(-1) differs: %v", res.Diffs)
	}
	if _, _, _, etag := getJSON(t, s, "/api/market", nil); etag == "" {
		t.Fatal("board response has no ETag")
	}
	// پس از یک ساختِ کش‌شده، «همان ویرایش» یعنی unchanged — نه یک بدنهٔ تازه.
	_, same, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	if res := parity.Compare(golden(t, "delta_mirror.json"), same, parity.Options{}); !res.Pass {
		t.Fatalf("delta(0) differs: %v", res.Diffs)
	}
}

func TestETag304(t *testing.T) {
	s := fixtureService(t)
	_, _, _, etag := getJSON(t, s, "/api/market", nil)
	code, _, body, _ := getJSON(t, s, "/api/market", map[string]string{"If-None-Match": etag})
	if code != 304 || len(body) != 0 {
		t.Fatalf("304 expected, got %d (%d bytes)", code, len(body))
	}
}
```

- [ ] **Step 5: Run the tests; expect the first golden comparison to fail on real rules**

Run: `cd backend-go && go test ./internal/market -v`
Expected: FAIL at the first mismatching path. **Do not adjust the golden.** Work down the diffs: the most common causes are a column Python rounds twice (`vol_ratio`), a `_KEEP_NULL` key emitted as 0, or `d_even` leaking into the default body. Repeat until `TestBoardMatchesPythonGolden` passes for both bodies.

- [ ] **Step 6: Full suite + commit**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test -count=1 ./...`
Expected: all green, including `httpapi` with the new signature.

```bash
git add backend-go/internal/market backend-go/internal/httpapi/server.go backend-go/internal/httpapi/server_test.go backend-go/cmd/borsd/main.go
git commit -m "$(cat <<'EOF'
feat(go): سه مسیرِ تابلو با همان بدنۀ پایتون

مونتاژِ ردیف‌ها با قاعدهٔ حذف/تهیِ خودِ پایتون، کشِ ۶۰ثانیه‌ای با همان هدرها و
ETag، دلتایِ آینه‌ای و sync-state از همان market_sync.json.
EOF
)"
```

---
### Task 7: `internal/tapehistory` — the durable daily observation write

**Files:**
- Create: `backend-go/internal/tapehistory/history.go`
- Create: `backend-go/internal/tapehistory/history_test.go`
- Modify: `backend-go/internal/market/assemble.go` (assemble full rows; add `dropUnusedFields`)
- Modify: `backend-go/internal/market/service.go` (record before slimming)

**Interfaces:**
- Consumes: `*sql.DB` (the `user.db` handle from `db.Handles.User`), the assembled records of the current frame.
- Produces: `tapehistory.NewRecorder() *Recorder`; `(*Recorder).Record(db *sql.DB, recs []map[string]any, day int64, token string, now time.Time) (int, error)`; `(*Recorder).LastErr() string`; `market.dropUnusedFields(recs []map[string]any)`.

Why this task exists: `api/market.py` writes the seven filters into `user.db` on every rebuild (`tape_flag_history.record_observations`, api/market.py:1335-1349). That write is a side effect of `GET /api/market`, it is fed by the same frame, and `/api/tape-history` (a later port) reads it back. Skipping it here would make the Go board silently stop recording history the moment it replaces the Python board.

**Token in phase A:** Python passes `market_state.sync_count()` — an in-process counter that only rises when a live sync commits new rows. The Go phase-A service does not run a sync loop, so it derives the same "is this data new" signal from `market_sync.json`'s `(mtime_ns, size)` pair, which the external syncer rewrites on every successful sync. Step 4 below adds `syncToken(dataDir)` to `service.go`. Same file, unchanged token ⇒ no new batch, exactly like an unchanged `sync_count`.

- [ ] **Step 1: Write the failing tests**

```go
package tapehistory

import (
	"database/sql"
	"math"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func openDB(t *testing.T) *sql.DB {
	t.Helper()
	conn, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "user.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

func rec(code string, live bool, on map[string]bool, ev map[string]any) map[string]any {
	m := map[string]any{"ins_code": code, "symbol": code + "-sym", "is_live": live}
	for _, f := range Flags {
		m[f] = on[f]
	}
	for k, v := range ev {
		m[k] = v
	}
	return m
}

func baseRecs() []map[string]any {
	return []map[string]any{
		rec("A", true, map[string]bool{"f_susp": true, "f_jet": true},
			map[string]any{"tvol": 1000.0, "p_closing": 500.5, "z_tot_tran": int64(42)}),
		rec("B", true, map[string]bool{"f_jet": true},
			map[string]any{"tvol": 2000.0, "p_closing": 100.0, "is6": 1.0}),
		rec("C", false, map[string]bool{"f_susp": true}, nil),
	}
}

func count(t *testing.T, conn *sql.DB, q string, args ...any) int {
	t.Helper()
	var n int
	if err := conn.QueryRow(q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestRecordWritesDailyRowsAndMeta(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	now := time.Date(2026, 10, 14, 10, 30, 0, 0, time.Local)

	if n, err := r.Record(conn, baseRecs(), 20261014, "tok-1", now); err != nil || n != 3 {
		t.Fatalf("n=%d err=%v, want 3 rows", n, err)
	}
	if got := count(t, conn, "SELECT COUNT(*) FROM tape_flag_day"); got != 3 {
		t.Fatalf("tape_flag_day rows=%d, want 3", got)
	}
	var first, last, ev, src string
	var passes int
	err := conn.QueryRow("SELECT first_seen_at, last_seen_at, passes, evidence, source"+
		" FROM tape_flag_day WHERE ins_code='A' AND flag='f_jet'").Scan(&first, &last, &passes, &ev, &src)
	if err != nil {
		t.Fatal(err)
	}
	if first != "2026-10-14 10:30:00" || last != first || passes != 1 || src != "board" {
		t.Fatalf("first=%q last=%q passes=%d src=%q", first, last, passes, src)
	}
	wantEv := `{"tvol": 1000.0, "p_closing": 500.5, "z_tot_tran": 42}`
	if ev != wantEv {
		t.Fatalf("evidence=%s, want %s", ev, wantEv)
	}
	var sym string
	if err := conn.QueryRow("SELECT symbol FROM tape_flag_day WHERE ins_code='B' AND flag='f_jet'").Scan(&sym); err != nil {
		t.Fatal(err)
	}
	if sym != "B-sym" {
		t.Fatalf("symbol=%q", sym)
	}
	var metaPasses, symbols int
	if err := conn.QueryRow("SELECT passes, symbols FROM tape_flag_day_meta WHERE d_even=20261014").
		Scan(&metaPasses, &symbols); err != nil {
		t.Fatal(err)
	}
	if metaPasses != 1 || symbols != 2 {
		t.Fatalf("meta passes=%d symbols=%d, want 1 and 2", metaPasses, symbols)
	}
	// ردیف‌های بی‌پرچم و بی‌جان هیچ ردیفی نمی‌سازند.
	if got := count(t, conn, "SELECT COUNT(*) FROM tape_flag_day WHERE ins_code='C'"); got != 0 {
		t.Fatalf("fossil row C was written (%d rows)", got)
	}
}

func TestTokenBlocksRepeatAndKeepsFirstSight(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 10, 30, 0, 0, time.Local)
	if _, err := r.Record(conn, baseRecs(), 20261014, "tok-1", t0); err != nil {
		t.Fatal(err)
	}
	// همان نشانه، حتی بعد از پنجرهٔ چهار دقیقه‌ای: نوبتِ تازه‌ای نیست.
	if n, _ := r.Record(conn, baseRecs(), 20261014, "tok-1", t0.Add(30*time.Minute)); n != 0 {
		t.Fatalf("same token wrote %d rows", n)
	}
	// نشانهٔ تازه پس از پنجره: passes جلو می‌رود، ولی شاهد و اولین‌دید عوض نمی‌شوند.
	changed := baseRecs()
	changed[0]["p_closing"] = 999.9
	if n, err := r.Record(conn, changed, 20261014, "tok-2", t0.Add(5*time.Minute)); err != nil || n != 3 {
		t.Fatalf("n=%d err=%v, want 3", n, err)
	}
	var first, ev string
	var passes int
	if err := conn.QueryRow("SELECT first_seen_at, passes, evidence FROM tape_flag_day"+
		" WHERE ins_code='A' AND flag='f_susp'").Scan(&first, &passes, &ev); err != nil {
		t.Fatal(err)
	}
	if first != "2026-10-14 10:30:00" || passes != 2 {
		t.Fatalf("first=%q passes=%d", first, passes)
	}
	if ev != `{"tvol": 1000.0, "p_closing": 500.5, "z_tot_tran": 42}` {
		t.Fatalf("evidence was rewritten: %s", ev)
	}
	if got := count(t, conn, "SELECT passes FROM tape_flag_day_meta WHERE d_even=20261014"); got != 2 {
		t.Fatalf("meta passes=%d, want 2", got)
	}
}

func TestFlushFloor(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	if _, err := r.Record(conn, baseRecs(), 20261014, "t1", t0); err != nil {
		t.Fatal(err)
	}
	if n, _ := r.Record(conn, baseRecs(), 20261014, "t2", t0.Add(10*time.Second)); n != 0 {
		t.Fatalf("flush floor leaked: %d rows", n)
	}
	if n, err := r.Record(conn, baseRecs(), 20261014, "t2", t0.Add(241*time.Second)); err != nil || n != 3 {
		t.Fatalf("after the floor n=%d err=%v, want 3", n, err)
	}
}

func TestNoLiveRowsConsumesTheWindow(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	fossil := []map[string]any{rec("C", false, map[string]bool{"f_susp": true}, nil)}
	if n, _ := r.Record(conn, fossil, 20261014, "x", t0); n != 0 {
		t.Fatalf("fossil-only frame wrote %d rows", n)
	}
	if got := count(t, conn, "SELECT COUNT(*) FROM tape_flag_day_meta"); got != 0 {
		t.Fatalf("meta row written without observations (%d)", got)
	}
	// عینِ پایتون: نشانه پیش از ساختنِ ردیف‌ها ثبت می‌شود، پس نوبتِ بعدی با همان
	// نشانه — حتی اگر ردیفِ زنده داشته باشد — تا پنجرهٔ بعدی ثبت نمی‌شود.
	if n, _ := r.Record(conn, baseRecs(), 20261014, "x", t0.Add(time.Minute)); n != 0 {
		t.Fatalf("token was not consumed by the empty batch (%d rows)", n)
	}
}

func TestEvidenceDropsMissingNaNAndInf(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	recs := []map[string]any{rec("A", true, map[string]bool{"f_jet": true}, map[string]any{
		"tvol": 1.0, "p_closing": math.NaN(), "p_last": math.Inf(1),
		"percent_last": nil, "z_tot_tran": int64(7),
	})}
	if _, err := r.Record(conn, recs, 20261014, "t", t0); err != nil {
		t.Fatal(err)
	}
	var ev string
	if err := conn.QueryRow("SELECT evidence FROM tape_flag_day WHERE ins_code='A'").Scan(&ev); err != nil {
		t.Fatal(err)
	}
	want := `{"tvol": 1.0, "z_tot_tran": 7}`
	if ev != want {
		t.Fatalf("evidence=%s, want %s", ev, want)
	}
}

func TestFailureIsSwallowedAndReported(t *testing.T) {
	conn := openDB(t)
	conn.Close()
	r := NewRecorder()
	now := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	if n, err := r.Record(conn, baseRecs(), 20261014, "t", now); n != 0 || err == nil {
		t.Fatalf("closed db: n=%d err=%v", n, err)
	}
	if r.LastErr() == "" {
		t.Fatal("LastErr is empty after a failed write")
	}
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend-go && go test ./internal/tapehistory -v`
Expected: FAIL — `package borsterminal/backend/internal/tapehistory is not in std` (the directory does not exist yet).

- [ ] **Step 3: Write `history.go`**

```go
package tapehistory

import (
	"database/sql"
	"math"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ترتیبِ FLAGS و EVIDENCE_COLS عینِ tape_flag_history.py است؛ همان ترتیب در
// متنِ ردیف‌ها و در JSONِ شواهد می‌نشیند.
var Flags = []string{"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal"}

var EvidenceCols = []string{"tvol", "p_closing", "p_last", "percent_last",
	"z_tot_tran", "vol_ratio_file", "buyer_power_raw", "resistance_59", "is6"}

// flushS کفِ فاصلهٔ دو نوبتِ ثبت درِ یک روز است — نه کلید.
const flushS = 240 * time.Second

const source = "board"

var ddl = []string{
	`CREATE TABLE IF NOT EXISTS tape_flag_day (
    ins_code TEXT NOT NULL,
    flag TEXT NOT NULL,
    d_even INTEGER NOT NULL,
    symbol TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    passes INTEGER NOT NULL DEFAULT 1,
    evidence TEXT,
    source TEXT,
    PRIMARY KEY (ins_code, flag, d_even))`,
	`CREATE TABLE IF NOT EXISTS tape_flag_day_meta (
    d_even INTEGER PRIMARY KEY,
    first_at TEXT, last_at TEXT,
    passes INTEGER NOT NULL DEFAULT 1,
    symbols INTEGER,
    active_rows INTEGER)`,
}

const (
	upsertRow = "INSERT INTO tape_flag_day(ins_code, flag, d_even, symbol, first_seen_at," +
		"                          last_seen_at, evidence, source)" +
		" VALUES(?,?,?,?,?,?,?,?)" +
		" ON CONFLICT(ins_code, flag, d_even) DO UPDATE SET" +
		"   last_seen_at = excluded.last_seen_at," +
		"   passes = tape_flag_day.passes + 1"
	upsertMeta = "INSERT INTO tape_flag_day_meta(d_even, first_at, last_at, passes, symbols)" +
		" VALUES(?,?,?,1,?)" +
		" ON CONFLICT(d_even) DO UPDATE SET" +
		"   last_at = excluded.last_at," +
		"   passes = tape_flag_day_meta.passes + 1," +
		"   symbols = excluded.symbols"
)

// Recorder وضعیتِ درون‌پروسه‌ایِ ثبت را نگه می‌دارد (پنجرهٔ روز، نشانهٔ آخرین
// نوبت، خطای آخر). مقدارِ صفر آمادهٔ استفاده است.
type Recorder struct {
	mu        sync.Mutex
	ensured   bool
	lastFlush map[int64]time.Time
	lastToken map[int64]string
	lastErr   string
}

func NewRecorder() *Recorder { return &Recorder{} }

func (r *Recorder) LastErr() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.lastErr
}

// Record همان قراردادِ record_observations: پرچم‌هایِ ردیف‌هایِ زنده را برایِ
// `day` می‌نویسد. صفر یعنی «نوبتِ تکراری، پنجرهٔ بسته، یا پرچمی روشن نبود» —
// و خطا هرگز به درخواستِ تابلو نمی‌رسد؛ فقط در LastErr می‌ماند.
func (r *Recorder) Record(db *sql.DB, recs []map[string]any, day int64, token string, now time.Time) (int, error) {
	if db == nil || len(recs) == 0 || day == 0 {
		return 0, nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.lastFlush == nil {
		r.lastFlush = map[int64]time.Time{}
		r.lastToken = map[int64]string{}
	}
	if token != "" && r.lastToken[day] == token {
		return 0, nil
	}
	if t, ok := r.lastFlush[day]; ok && now.Sub(t) < flushS {
		return 0, nil
	}
	// نشانه و پنجره پیش از نوشتن مصرف می‌شوند — عینِ پایتون: نوبتِ ناموفق یا
	// خالی هم پنجرهٔ چهار دقیقه‌ای را می‌سوزاند.
	r.lastFlush[day] = now
	r.lastToken[day] = token
	n, err := r.write(db, recs, day, now)
	if err != nil {
		r.lastErr = err.Error()
		return 0, err
	}
	return n, nil
}

type obsRow struct {
	code, flag, symbol, evidence string
}

func (r *Recorder) write(db *sql.DB, recs []map[string]any, day int64, now time.Time) (int, error) {
	if !r.ensured {
		for _, q := range ddl {
			if _, err := db.Exec(q); err != nil {
				return 0, err
			}
		}
		r.ensured = true
	}
	stamp := now.Format("2006-01-02 15:04:05")
	rows := make([]obsRow, 0, len(recs))
	codes := map[string]bool{}
	for _, rec := range recs {
		if live, _ := rec["is_live"].(bool); !live {
			continue
		}
		code, _ := rec["ins_code"].(string)
		if code == "" {
			continue
		}
		symbol, _ := rec["symbol"].(string)
		ev := evidenceJSON(rec)
		for _, f := range Flags {
			if on, _ := rec[f].(bool); on {
				rows = append(rows, obsRow{code: code, flag: f, symbol: symbol, evidence: ev})
				codes[code] = true
			}
		}
	}
	if len(rows) == 0 {
		return 0, nil
	}
	tx, err := db.Begin()
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback() }()
	for _, row := range rows {
		if _, err := tx.Exec(upsertRow, row.code, row.flag, day, row.symbol,
			stamp, stamp, row.evidence, source); err != nil {
			return 0, err
		}
	}
	if _, err := tx.Exec(upsertMeta, day, stamp, stamp, len(codes)); err != nil {
		return 0, err
	}
	if err := tx.Commit(); err != nil {
		return 0, err
	}
	return len(rows), nil
}

// evidenceJSON شاهدِ اولین دیدار را با همان قالبِ json.dumps پایتون می‌سازد:
// ترتیبِ EVIDENCE_COLS، جداکنندهٔ «, » و «: »، بی‌NaN.
// اختلافِ متنیِ شناخته‌شده: پایتون برایِ اعدادِ بزرگ‌تر از ۱e16 یا کوچک‌تر از
// ۱e-4 نمادِ توان می‌نویسد و Go هم — ولی مرزها کمی فرق دارند؛ مقدارِ خوانده‌شده
// یکی است و مصرف‌کنندهٔ این JSON عدد را می‌خواند، نه متن را.
func evidenceJSON(rec map[string]any) string {
	var b strings.Builder
	b.WriteByte('{')
	first := true
	for _, name := range EvidenceCols {
		lit, ok := jsonLiteral(rec[name])
		if !ok {
			continue
		}
		if !first {
			b.WriteString(", ")
		}
		first = false
		b.WriteString(strconv.Quote(name))
		b.WriteString(": ")
		b.WriteString(lit)
	}
	b.WriteByte('}')
	return b.String()
}

func jsonLiteral(v any) (string, bool) {
	switch x := v.(type) {
	case int64:
		return strconv.FormatInt(x, 10), true
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return "", false
		}
		return pyFloat(x), true
	case bool:
		if x {
			return "true", true
		}
		return "false", true
	case string:
		return strconv.Quote(x), true
	}
	return "", false
}

// pyFloat مثلِ repr پایتون: 100.0 نه 100 (قالبِ پیش‌فرضِ Go).
func pyFloat(f float64) string {
	s := strconv.FormatFloat(f, 'g', -1, 64)
	if strings.ContainsAny(s, ".eE") {
		return s
	}
	return s + ".0"
}
```

- [ ] **Step 4: Record before slimming (modify the market service)**

In `service.go`, add the import `"borsterminal/backend/internal/tapehistory"`, add the field `recorder *tapehistory.Recorder` after `journal`, and construct it in `New`:

```go
func New(h *db.Handles, dataDir string) *Service {
	return &Service{market: h.Market, user: h.User, dataDir: dataDir, recorder: tapehistory.NewRecorder()}
}
```

Add the token helper right after `SyncState`'s handler (phase A's stand-in for `market_state.sync_count()`; an unchanged file means "no new data", exactly like an unchanged counter — `filepath`, `os` and `strconv` are already imported):

```go
// syncToken «این داده نو است» را از خودِ فایلِ سینکر می‌گیرد: هر سینکِ موفق
// market_sync.json را بازنویسی می‌کند، پس (mtime_ns, size) همان نقشی را دارد
// که sync_count در پروسۀ پایتون داشت.
func syncToken(dataDir string) string {
	p := filepath.Join(dataDir, "market_sync.json")
	st, err := os.Stat(p)
	if err != nil {
		return ""
	}
	return strconv.FormatInt(st.ModTime().UnixNano(), 10) + ":" + strconv.FormatInt(st.Size(), 10)
}
```

In `assemble.go`, change the signature and move the drop into its own function:

```go
func assemble(fr *store.Frame, d *board.Derived, fl *tapeflags.Flags) []map[string]any {
```

and inside the column loop replace

```go
			if dropUnused && dropFields[name] {
				continue
			}
```

with nothing (the loop keeps every column). Then add:

```go
// dropUnusedFields همان _DROP_FIELDS را از ردیف‌هایِ ساخته‌شده حذف می‌کند. بعد
// از ثبتِ سابقه صدا زده می‌شود، چون پایتون شاهد را از قابِ کامل می‌نویسد و
// resistance_59 هم شاهد است و هم در بدنۀ پیش‌فرض حذف می‌شود.
func dropUnusedFields(recs []map[string]any) {
	for _, rec := range recs {
		for name := range dropFields {
			delete(rec, name)
		}
	}
}
```

In `service.go`'s `build`, replace

```go
	recs := assemble(fr, d, fl, dropUnused)
```

with

```go
	recs := assemble(fr, d, fl)
```

and immediately after the `meta`/`sessionDay` resolution — that is, **before** the screening loop, because Python screens the slimmed records — insert:

```go
	// ثبتِ سابقۀ پرچم‌ها — همان side effectِ پایتون، پیش از حذفِ ستون‌ها.
	if len(recs) > 0 && sessionDay != 0 {
		_, _ = s.recorder.Record(s.user, recs, sessionDay, syncToken(s.dataDir), time.Now())
	}
	if dropUnused {
		dropUnusedFields(recs)
	}
```

Two orderings are load-bearing here and both come from api/market.py: the write happens **before** `_slim_records` (so `resistance_59` is still in the evidence), and screening happens **after** it (`screening_eligibility` receives the serialised records, api/market.py:1351-1366). Recording is not tied to cache storage — a `?fields=all` build records too.

- [ ] **Step 5: Run the package tests, then the whole module**

Run: `cd backend-go && go test ./internal/tapehistory -v`
Expected: PASS, six tests.

Run: `cd backend-go && gofmt -l . && go vet ./... && go test -count=1 ./...`
Expected: everything green. `internal/market` still passes its goldens — the history write must not change the payload.

- [ ] **Step 6: Commit**

```bash
git add backend-go/internal/tapehistory backend-go/internal/market/assemble.go backend-go/internal/market/service.go
git commit -m "$(cat <<'EOF'
feat(go): ثبتِ روزانۀ هفت فیلتر در user.db

همان قراردادِ tape_flag_history: پنجرهٔ چهار دقیقه‌ای، نشانهٔ بازارِ تازه،
شاهدِ اولین دیدار و upsertِ passes — پیش از حذفِ ستون‌هایِ بدنۀ پیش‌فرض.
EOF
)"
```

---
### Task 8: `tools/parity/gate_b1.py` — the acceptance gate and its evidence

**Files:**
- Create: `tools/parity/serve_market_copy.py`
- Create: `tools/parity/cases_b1.json`
- Create: `tools/parity/cases_b1_perf.json`
- Create: `tools/parity/gate_b1.py`
- Create: `_audit/parity/B1.json` (generated by the gate)

**Interfaces:**
- Consumes: `backend-go/bin/borsd.exe`, `backend-go/bin/parity.exe`, `tools/parity/cases_b1*.json`, the repo's `market.db` / `user.db` (copied, never opened).
- Produces: `_audit/parity/B1.json` (evidence) and exit code 0/1/2 with the same meaning as `gate_b0.py`.

The two acceptance numbers of spec §8 live here: same rows in the same order (structural comparison, arrays are order-sensitive in `parity.Compare`), payload ≤ Python, and p95 ≤ 0.5× Python on a full rebuild. The gate also proves the three side effects that a naive port drops: the `304`, the `X-Cache` sequence, and the `tape_flag_day` rows written into `user.db`.

- [ ] **Step 1: Write the Python side-server launcher**

`codal_fetcher.DB_PATH` is a module-level constant (`os.path.join(dirname(__file__), "market.db")`) that does **not** follow `BORS_DATA_DIR`, and `app.py`'s startup hook runs `create_schema`/`migrate_schema` on it. Starting the plain app for a parity run would therefore open the operational `market.db` — a write path beside the frozen copy the gate is built on. The launcher closes that door before `app` is imported.

```python
#!/usr/bin/env python
"""سرورِ پاریتی: app را رویِ کپیِ BORS_DATA_DIR بالا می‌آورد، بی‌شبکه.

`codal_fetcher.DB_PATH` ثابتِ ماژول است و به BORS_DATA_DIR گوش نمی‌دهد؛ هوکِ
استارتِ app همان را migrate می‌کند. برایِ سنجشِ پاریتی این یعنی بالقوه نوشتن رویِ
بانکِ عملیاتی، پس پیش از importِ app اشاره‌گر را به کپیِ موقت می‌بندیم. هیچ
حذف/بازنویسی‌ای این‌جا نیست — فقط مسیر عوض می‌شود.

اجرا: BORS_DATA_DIR=<copy> BORS_NO_FETCH_LOOPS=1 BORS_CODAL_OFFLINE=1 \
      BORS_CODAL_AUTO=0 python tools/parity/serve_market_copy.py
"""
import os
import sys

DATA_DIR = (os.environ.get("BORS_DATA_DIR") or "").strip()
if not DATA_DIR:
    raise SystemExit("BORS_DATA_DIR is required")
PORT = int(os.environ.get("BORS_PARITY_PORT", "8299"))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import codal_fetcher  # noqa: E402  (باید پیش از app بیاید)

codal_fetcher.DB_PATH = os.path.join(DATA_DIR, "market.db")

import uvicorn  # noqa: E402
from app import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
```

- [ ] **Step 2: Write the two case files**

`tools/parity/cases_b1.json` — the contract batch. Order matters: the default body first (it populates the delta mirror), then `fields=all`, then the two delta shapes, then sync-state.

```json
{
 "db_sha256": "",
 "cases": [
  {"name": "market-default", "method": "GET", "path": "/api/market", "exclude": []},
  {"name": "market-all", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "delta-cold", "method": "GET", "path": "/api/market/delta?since=-1", "exclude": []},
  {"name": "delta-same-rev", "method": "GET", "path": "/api/market/delta?since=0", "exclude": []},
  {"name": "sync-state", "method": "GET", "path": "/api/market/sync-state", "exclude": []}
 ]
}
```

`tools/parity/cases_b1_perf.json` — 20 uncached full rebuilds per side. `?fields=all` is the only path that skips the 60-second cache on **both** implementations (`store_cache=False` in Python, `storeCache=false` in Go), so it is the honest rebuild benchmark.

```json
{
 "db_sha256": "",
 "cases": [
  {"name": "rebuild-01", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-02", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-03", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-04", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-05", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-06", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-07", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-08", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-09", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-10", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-11", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-12", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-13", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-14", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-15", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-16", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-17", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-18", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-19", "method": "GET", "path": "/api/market?fields=all", "exclude": []},
  {"name": "rebuild-20", "method": "GET", "path": "/api/market?fields=all", "exclude": []}
 ]
}
```

- [ ] **Step 3: Write the gate**

```python
#!/usr/bin/env python
"""گیتِ B1: تطبیقِ سه مسیرِ تابلو با پایتون روی دو کپیِ یخ‌زده، و کارایی.

قواعدِ سخت (همان‌هایِ B0، به‌علاوهٔ یکی):
* بانکِ عملیاتی هرگز با SQLite باز نمی‌شود؛ فقط کپیِ فایل. هر کپی با
  quick_check خوانده می‌شود و کپیِ خراب با exit 2 رد می‌شود.
* گاردِ کناربانک: (اندازه، mtime_ns) هر -wal/-shmِ کنارِ market.db/user.db در
  ریشه پیش و پس از اجرا مقایسه می‌شود. سرورِ پایتون با
  tools/parity/serve_market_copy.py بالا می‌آید تا مسیرِ migrateِ کدال هم به
  کپی بسته باشد، نه به بانکِ عملیاتی.
* فقط PIDهایی کشته می‌شوند که همین اسکریپت بالا آورده.
* پایتون در طولِ دسته پنجره‌های board_hist_v/board_hist_fv را در **کپیِ خودش**
  بازسازی می‌کند (نوشتنِ مشروع و مشتق). پس تغییرِ کپیِ پایتون شکست نیست؛ تغییرِ
  کپیِ Go شکست است (فازِ A فقط می‌خواند) و برابریِ شروع دو کپی الزامی است.
"""
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO = os.path.join(ROOT, "backend-go")
BORSD = os.path.join(GO, "bin", "borsd.exe")
PARITY = os.path.join(GO, "bin", "parity.exe")
SERVE = os.path.join(ROOT, "tools", "parity", "serve_market_copy.py")
CASES = os.path.join(ROOT, "tools", "parity", "cases_b1.json")
PERF_CASES = os.path.join(ROOT, "tools", "parity", "cases_b1_perf.json")
OUT = os.path.join(ROOT, "_audit", "parity", "B1.json")
CONTRACT = os.path.join(ROOT, "_audit", "parity", "B1-contract.json")
PERF = os.path.join(ROOT, "_audit", "parity", "B1-perf.json")
GO_PORT, PY_PORT = 8298, 8299
DB_NAMES = ("market.db", "user.db")
SIDECAR_SUFFIXES = ("-wal", "-shm")
HASH_CHUNK = 1 << 20
PERF_SAMPLES = 20


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sidecar_state():
    state = {}
    for name in DB_NAMES:
        for suffix in SIDECAR_SUFFIXES:
            path = os.path.join(ROOT, name + suffix)
            if os.path.exists(path):
                st = os.stat(path)
                state[name + suffix] = (st.st_size, st.st_mtime_ns)
            else:
                state[name + suffix] = None
    return state


def describe(entry):
    return "absent" if entry is None else "%dB@%dns" % entry


def sidecar_problem(before, after):
    for key in before:
        old, new = before[key], after[key]
        if old is None and new is not None:
            return "%s appeared (%s)" % (key, describe(new))
        if old is not None and new is None:
            return "%s disappeared (was %s)" % (key, describe(old))
        if old != new:
            return "%s changed (%s -> %s)" % (key, describe(old), describe(new))
    return None


def snapshot_db(src, dst):
    shutil.copy2(src, dst)
    src_wal = src + "-wal"
    if os.path.exists(src_wal) and os.path.getsize(src_wal) > 0:
        shutil.copy2(src_wal, dst + "-wal")
    con = sqlite3.connect("file:%s?mode=ro" % dst.replace("\\", "/"), uri=True)
    try:
        return [row[0] for row in con.execute("PRAGMA quick_check").fetchall()]
    finally:
        con.close()


def run(cmd, cwd=None, env=None):
    p = subprocess.run(cmd, cwd=cwd or ROOT, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_json(url, deadline_s, accept):
    start = time.perf_counter()
    last = None
    while time.perf_counter() - start < deadline_s:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                body = json.loads(r.read())
                last = body
                if r.status == 200 and accept(body):
                    return True
        except Exception:
            pass
        time.sleep(0.05)
    print("readiness failed for %s (last=%s)" % (url, last))
    return False


def http_get(url, headers=None):
    """(status, headers, body). هدرها عینِ HTTPMessage می‌مانند تا get بی‌حساس به حرف بزرگ/کوچک باشد؛
    304 هم از مسیرِ HTTPError برمی‌گردد."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def probe(base):
    """MISS، HIT، ۳۰۴ و اندازه‌ها را از یک سرور می‌گیرد."""
    status, headers, body = http_get(base + "/api/market")
    out = {
        "status": status,
        "content_type": (headers.get("Content-Type") or "").split(";")[0].strip().lower(),
        "cache_control": (headers.get("Cache-Control") or "").strip(),
        "xcache_first": (headers.get("X-Cache") or "").strip(),
        "etag": (headers.get("ETag") or "").strip(),
        "bytes": len(body),
    }
    try:
        out["rows"] = len(json.loads(body).get("data") or [])
    except ValueError:
        out["rows"] = -1
    status2, headers2, _ = http_get(base + "/api/market")
    out["xcache_second"] = (headers2.get("X-Cache") or "").strip()
    status3, _, body3 = http_get(base + "/api/market", {"If-None-Match": out["etag"]})
    out["not_modified"] = status3 == 304 and len(body3) == 0
    _, _, all_body = http_get(base + "/api/market?fields=all")
    out["bytes_all"] = len(all_body)
    return out


def flag_rows(path):
    """ردیف‌هایِ tape_flag_day یک کپی؛ ارزش‌ها ساختاری، نه متنی."""
    if not os.path.exists(path):
        return None
    con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    try:
        raw = con.execute("SELECT ins_code, flag, d_even, symbol, evidence, source"
                          " FROM tape_flag_day").fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    out = {}
    for code, flag, day, symbol, evidence, source in raw:
        try:
            ev = json.loads(evidence) if evidence else {}
        except ValueError:
            ev = {"!!unparsed": evidence}
        out[(str(code), str(flag), int(day))] = (symbol or "", ev, source or "")
    return out


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for target, out in (("./cmd/borsd", BORSD), ("./cmd/parity", PARITY)):
        rc, log = run(["go", "build", "-o", out, target], cwd=GO)
        if rc != 0:
            print(log)
            return 2
    rc, tests = run(["go", "test", "-count=1", "./..."], cwd=GO)
    if rc != 0:
        print(tests)
        return 2
    for port in (GO_PORT, PY_PORT):
        if not port_free(port):
            print("port %d is busy" % port)
            return 2
    commit = run(["git", "rev-parse", "--short", "HEAD"])[1].strip()
    go_version = run(["go", "version"])[1].strip()

    before_sidecars = sidecar_state()
    tmp = tempfile.mkdtemp(prefix="bors-b1-")
    go_dir = os.path.join(tmp, "go")
    py_dir = os.path.join(tmp, "py")
    os.makedirs(go_dir)
    os.makedirs(py_dir)
    procs = []
    result = 2
    try:
        for name in DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = snapshot_db(src, os.path.join(dst_dir, name))
                except (sqlite3.Error, OSError) as err:
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2
        go_db = os.path.join(go_dir, "market.db")
        py_db = os.path.join(py_dir, "market.db")
        db_hash = sha256_file(go_db)
        frozen_ok = db_hash == sha256_file(py_db)
        if not frozen_ok:
            print("the two copies are not identical")
            return 2

        py_env = dict(os.environ, BORS_DATA_DIR=py_dir, BORS_NO_FETCH_LOOPS="1",
                      BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
                      BORS_PARITY_PORT=str(PY_PORT), PYTHONIOENCODING="utf-8")
        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not wait_json("http://127.0.0.1:%d/openapi.json" % PY_PORT, 60.0, lambda b: True):
            return 2
        go_proc = subprocess.Popen(
            [BORSD, "--port", str(GO_PORT), "--read-only", "--no-loops", "--db-dir", go_dir],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append((go_proc, None))
        if not wait_json("http://127.0.0.1:%d/healthz" % GO_PORT, 15.0,
                         lambda b: b.get("status") == "ok"):
            return 2
        _, _, health_body = http_get("http://127.0.0.1:%d/healthz" % GO_PORT)
        health = json.loads(health_body)
        if os.path.normcase(os.path.normpath(health.get("data_dir", ""))) != \
                os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % PY_PORT
        go_url = "http://127.0.0.1:%d" % GO_PORT
        p_py = probe(py_url)
        p_go = probe(go_url)

        rc, log = run([PARITY, "--py", py_url, "--go", go_url, "--cases", CASES,
                       "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc != 0:
            print("contract batch failed")
            return 2
        rc, log = run([PARITY, "--py", py_url, "--go", go_url, "--cases", PERF_CASES,
                       "--out", PERF, "--commit", commit])
        print(log.strip())
        if rc != 0:
            print("perf batch failed")
            return 2
        contract = json.load(open(CONTRACT, encoding="utf-8"))
        perf = json.load(open(PERF, encoding="utf-8"))
        with open(CASES, encoding="utf-8") as f:
            case_count = len(json.load(f)["cases"])

        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count
        size_ok = p_go["bytes"] <= p_py["bytes"] and p_go["bytes_all"] <= p_py["bytes_all"]
        rows_ok = p_py["rows"] == p_go["rows"] and p_py["rows"] > 0
        headers_ok = (p_py["content_type"] == p_go["content_type"] == "application/json"
                      and p_py["cache_control"] == p_go["cache_control"] == "max-age=15")
        cache_ok = (p_py["xcache_first"] == p_go["xcache_first"] == "MISS"
                    and p_py["xcache_second"] == p_go["xcache_second"] == "HIT")
        etag_ok = p_py["not_modified"] and p_go["not_modified"]
        ratio = perf["p95_go"] / perf["p95_py"] if perf["p95_py"] else 0.0
        perf_ok = perf["p95_py"] > 0 and perf["p95_go"] <= 0.5 * perf["p95_py"]

        # پس از خاموشی: کپی‌ها دیگر باز نیستند، پس خواندنِ آن‌ها آزاد است.
        go_rows = flag_rows(os.path.join(go_dir, "user.db"))
        py_rows = flag_rows(os.path.join(py_dir, "user.db"))
        history_ok = go_rows is not None and py_rows is not None and go_rows == py_rows
        go_db_unchanged = sha256_file(go_db) == db_hash
        py_db_changed = sha256_file(py_db) != db_hash

        payload = {
            "commit": commit,
            "go_version": go_version,
            "python": sys.version.split()[0],
            "db": {"sha256": db_hash, "frozen_ok": frozen_ok,
                   "go_copy_unchanged": go_db_unchanged,
                   "py_copy_changed": py_db_changed},
            "rows": {"py": p_py["rows"], "go": p_go["rows"], "ok": rows_ok},
            "bytes": {"default_py": p_py["bytes"], "default_go": p_go["bytes"],
                      "all_py": p_py["bytes_all"], "all_go": p_go["bytes_all"],
                      "ok": size_ok},
            "perf": {"samples": PERF_SAMPLES, "p50_py": perf["p50_py"],
                     "p95_py": perf["p95_py"], "p50_go": perf["p50_go"],
                     "p95_go": perf["p95_go"], "ratio": round(ratio, 4), "ok": perf_ok},
            "headers": {"py": p_py, "go": p_go, "ok": headers_ok,
                        "cache_ok": cache_ok, "etag_ok": etag_ok},
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok},
            "history": {"py_rows": 0 if py_rows is None else len(py_rows),
                        "go_rows": 0 if go_rows is None else len(go_rows),
                        "ok": history_ok},
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        checks = {"contract": contract_ok, "rows": rows_ok, "size": size_ok,
                  "perf": perf_ok, "headers": headers_ok, "cache": cache_ok,
                  "etag": etag_ok, "history": history_ok,
                  "go_read_only": go_db_unchanged}
        print("checks: " + " ".join("%s=%s" % (k, v) for k, v in checks.items()))
        print("p50 py=%.1fms go=%.1fms | p95 py=%.1fms go=%.1fms (ratio %.3f)"
              % (perf["p50_py"], perf["p50_go"], perf["p95_py"], perf["p95_go"], ratio))
        print("bytes default %d -> %d | all %d -> %d"
              % (p_py["bytes"], p_go["bytes"], p_py["bytes_all"], p_go["bytes_all"]))
        result = 0 if all(checks.values()) else 1
    finally:
        for proc, log in reversed(procs):
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            if log is not None:
                log.close()
        after_sidecars = sidecar_state()
        problem = sidecar_problem(before_sidecars, after_sidecars)
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
        shutil.rmtree(tmp, ignore_errors=True)
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the gate**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal && python tools/parity/gate_b1.py; echo "exit=$?"`
Expected: `checks: contract=True rows=True size=True perf=True headers=True cache=True etag=True history=True go_read_only=True`, then `exit=0`.

If `contract=False`, open `_audit/parity/B1-contract.json` and read `cases[].diffs` — the first sixty diffs are the port's to-do list, in path order. If `history=False`, the diff is in the two `user.db` copies which the gate deletes; rerun with the debug line `shutil.rmtree` commented out, or reproduce with the fixture test in Task 7. If `perf=False`, look at `B1-perf.json`: a Go p95 above half of Python's means the Go build is doing per-row work Python does vectorized (usually `sameRecord`'s JSON marshal on every row in `diffCodes` — index by `ins_code` instead).

- [ ] **Step 5: Commit**

```bash
git add tools/parity/serve_market_copy.py tools/parity/cases_b1.json tools/parity/cases_b1_perf.json tools/parity/gate_b1.py
git commit -m "$(cat <<'EOF'
test(go): گیتِ پذیرشِ B1 با دو سرور رویِ یک کپیِ یخ‌زده

بدنۀ سه مسیر ساختاری مقایسه می‌شود (ترتیبِ ردیف‌ها هم)، اندازه و p95 سنجیده
می‌شود، و ۳۰۴/کش/سابقۀ user.db جدا اثبات می‌شوند. سرورِ پایتون با
serve_market_copy بالا می‌آید تا migrateِ کدال به کپی بسته بماند.
EOF
)"
```

---
