# -*- coding: utf-8 -*-
"""functional_available / coverage status contract (2026-10-20).

The engine may return True, but only with an explicit, reproducible status:
  AVAILABLE, AVAILABLE_NO_EVENTS, PARTIAL, SOURCE_GAP, STALE, UNVERIFIED, FAILED,
  UNMEASURED.
No threshold is relaxed here; the tests are synthetic and assert the logic itself.
"""
import io, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

tmp = tempfile.mkdtemp(prefix="availability_")
DB = os.path.join(tmp, "t.db")
con = sqlite3.connect(DB)
con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT, "
            "paper_type INTEGER, sector_name TEXT, updated_at TEXT)")
con.execute("CREATE TABLE boards (ins_code TEXT, board INTEGER)")
con.executemany("INSERT INTO instruments VALUES (?,?,?,?,?,?)", [
    ("1", "فولاد", "فولاد مبارکه", 1, "فلزات اساسي", "2026-01-01"),
    ("2", "ضموج637", "اختيارخ فملي-26000-1405/10/09", 8, "صندوق", "2026-01-01"),
    ("3", "اراد201", "مرابحه عام دولت201-ش.خ", 2, "اوراق", "2026-01-01"),
    ("4", "وتوسمح", "ح . سرمايه گذاري توسعه ملي", 4, "سرمايه گذاريها", "2026-01-01"),
    ("5", "آسان", "صندوق س.درآمدثابت گنجينه مهر-د", 8, "صندوق سرمايه گذاري قابل معامله", "2026-01-01"),
    ("6", "آتي‌فولاد", "قرارداد آتی فولاد فروش سه ماهه", None, "فلزات اساسي", "2026-01-01"),
])
con.commit(); con.close()
import bors_config
bors_config.DB_PATH = DB
import api.chart as CH
CH.DB_PATH = DB

checks, fails = 0, 0
def ck(name, cond, detail=""):
    global checks, fails
    checks += 1
    if cond:
        print(f"  OK   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}  {detail}")

CHAIN = {"provenance": [], "incomplete": [], "complete": True, "anchored_last": True}
COV = {"available": True, "ins_code": "1", "error": None, "rows_total": 2,
       "rows_valid": 2, "rows_rejected": 0, "rows_unmatched": 0,
       "coverage_start": "2019-01-01", "coverage_end": "2026-01-01",
       "pre_coverage_candles": 0, "typed_events": 2, "unresolved_events": 0,
       "needs_offer_price_events": 0, "truncated_flow": False, "flow_cap": 500}
TIMES = ["2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01",
         "2024-01-01", "2025-01-01", "2026-01-01"]

print("[1] instrument kind from validated name rules")
for sym, want in (("فولاد", "stock"), ("ضموج637", "option"), ("اراد201", "bond"),
                  ("وتوسمح", "right"), ("آسان", "fund"), ("آتي‌فولاد", "future")):
    got = CH._instrument_kind(sym)
    ck(f"{sym} -> {want}", got == want, got)

print("[2] complete stock -> AVAILABLE")
av, bl, st, info = CH._functional_state(CHAIN, dict(COV), kind="stock", times=TIMES)
ck("available=True / no blockers", av is True and bl == [], (av, bl))
ck("status=AVAILABLE, window_available=True",
   st == "AVAILABLE" and info["window_available"] is True, (st, info))
ck("all points valid", info["valid_points"] == 7 and info["incomplete_points"] == 0, info)

print("[3] pre-coverage stock -> PARTIAL, but recent window usable")
c = dict(COV, coverage_start="2022-01-01", pre_coverage_candles=2)
av, bl, st, info = CH._functional_state(CHAIN, c, kind="stock", times=TIMES)
ck("functional_available=False", av is False)
ck("status=PARTIAL", st == "PARTIAL", st)
ck("window starts at coverage_start and is available",
   info["window_start"] == "2022-01-01" and info["window_available"] is True, info)
ck("5 valid / 2 incomplete", info["valid_points"] == 5 and info["incomplete_points"] == 2, info)

print("[4] no-event classes -> AVAILABLE_NO_EVENTS")
for kind in ("option", "bond", "future", "right"):
    c = dict(COV, rows_total=0, rows_valid=0, typed_events=0)
    av, bl, st, info = CH._functional_state(CHAIN, c, kind=kind, times=TIMES)
    ck(f"{kind}: available True + AVAILABLE_NO_EVENTS",
       av is True and st == "AVAILABLE_NO_EVENTS" and info["window_available"] is True,
       (av, st, bl))

print("[5] stock/fund without official rows -> SOURCE_GAP")
for kind in ("stock", "fund"):
    c = dict(COV, rows_total=0, rows_valid=0, typed_events=0)
    av, bl, st, info = CH._functional_state(CHAIN, c, kind=kind, times=TIMES)
    ck(f"{kind}: unavailable + SOURCE_GAP",
       av is False and st == "SOURCE_GAP" and any(x.startswith("no-official-rows") for x in bl),
       (av, st, bl))

print("[6] stale / unmeasured / unresolved")
av, bl, st, info = CH._functional_state(CHAIN, dict(COV), kind="stock", times=TIMES, stale=True)
ck("stale -> STALE, window unavailable", av is False and st == "STALE" and info["window_available"] is False, (st, info))
av, bl, st, info = CH._functional_state(None, None, kind="stock", times=TIMES)
ck("unmeasured -> UNMEASURED", av is False and st == "UNMEASURED", (st, bl))
c = dict(COV, unresolved_events=1)
av, bl, st, info = CH._functional_state(CHAIN, c, kind="stock", times=TIMES)
ck("unresolved event -> not available (UNVERIFIED)",
   av is False and st == "UNVERIFIED" and any(x.startswith("event-type-unresolved") for x in bl),
   (st, bl))

print("[7] capability carries status + availability")
cap = CH._adjust_capability([], "no-adjustment-event", chain=CHAIN, coverage=dict(COV),
                            symbol=None, times=TIMES)
ck("functional_status/availability present",
   cap.get("functional_status") == "AVAILABLE" and cap.get("availability", {}).get("status") == "AVAILABLE",
   cap.get("functional_status"))
ck("functional_available is derived, not hard-coded", cap.get("functional_available") is True)

print("[8] descending candle order is normalized at the boundary")
av_d, bl_d, st_d, info_d = CH._functional_state(
    CHAIN, dict(COV), kind="stock", times=list(reversed(TIMES)))
ck("descending times keep AVAILABLE and the same window",
   st_d == "AVAILABLE" and info_d["requested_start"] == TIMES[0]
   and info_d["requested_end"] == TIMES[-1], info_d)
ck("valid points do not depend on input order",
   info_d["valid_points"] == info["valid_points"], (info_d, info))
import datetime as _dt
_today = _dt.date.today().isoformat()
_old = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
ck("staleness reads the newest candle, not the last array item",
   CH._candles_stale([{"time": _today}, {"time": _old}]) is False)
ck("old series still reports stale",
   CH._candles_stale([{"time": _old}, {"time": "2019-01-01"}]) is True)

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(0 if fails == 0 else 1)
