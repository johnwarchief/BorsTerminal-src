# -*- coding: utf-8 -*-
"""Official fund distributions + single-session backfill, with no network.

Covers:
  * a typed cash_dividend event is not downgraded to source_ratio;
  * official fund rows enter the canonical factor chain;
  * an official row replaces a same-date detected gap (no double count);
  * a missing official session is merged, a zero-volume admin row is not a candle;
  * a backfilled row is visible to the base-gap detector through all_rows.
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

tmp = tempfile.mkdtemp(prefix="fund_backfill_")
DB = os.path.join(tmp, "t.db")
con = sqlite3.connect(DB)
import tsetmc_p0_schema as P0
P0.create_all(con)
con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT, "
            "paper_type INTEGER, sector_name TEXT, updated_at TEXT)")
con.execute("INSERT INTO instruments VALUES ('F1','پارند','صندوق س. پارند پايدار سپهر',8,'صندوق','2026-01-01')")
con.execute("INSERT INTO fund_profit_events VALUES "
            "('F1',20200107,'پارند','1398/10/15',171.0,10176.0,?, 'fund-portal:test','1:1398/10/15','2026-10-20')",
            ((10176.0 - 171.0) / 10176.0,))
con.execute("INSERT INTO fund_profit_events VALUES "
            "('F1',20200205,'پارند','1398/11/15',167.0,10167.0,?, 'fund-portal:test','1:1398/11/15','2026-10-20')",
            ((10167.0 - 167.0) / 10167.0,))
con.execute("INSERT INTO session_backfill VALUES "
            "('F1',20230327,'پارند',10100.0,10200.0,10050.0,10150.0,10160.0,10080.0,12345.0,"
            "'tsetmc:GetClosingPriceDaily','test','2026-10-20')")
con.commit()
con.close()

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

print("[1] typed cash_dividend survives _engine_events")
applied, rejected, chain = CH._engine_events([
    {"date": "2020-01-07", "kind": "cash_dividend", "reference_price": 10176.0,
     "dividend_per_share": 171.0, "source": "fund-portal:test"}])
ck("one applied, none rejected", len(applied) == 1 and rejected == [], (applied, rejected))
ck("kind stays cash_dividend", chain[0]["kind"] == "cash_dividend", chain)
ck("engine computed (P-D)/P",
   abs(CH.AE.event_factor(chain[0])[0] - (10176.0 - 171.0) / 10176.0) < 1e-12,
   CH.AE.event_factor(chain[0]))

print("[2] official rows enter the canonical chain")
times = ["2020-01-04", "2020-01-06", "2020-01-07", "2020-01-08",
         "2020-02-04", "2020-02-05", "2020-02-06"]
ap, rj, fac, chain2, cov = CH._canonical_adjustment("پارند", times, [])
f = dict(zip(times, fac))
r1 = (10176.0 - 171.0) / 10176.0
r2 = (10167.0 - 167.0) / 10167.0
ck("two official events applied", len(ap) == 2 and len(rj) == 0, (ap, rj))
ck("before both events factor = r1*r2", abs(f["2020-01-06"] - r1 * r2) < 1e-9, f)
ck("on/after first event factor = r2", abs(f["2020-01-07"] - r2) < 1e-9, f)
ck("on/after second event factor = 1", abs(f["2020-02-05"] - 1.0) < 1e-12, f)
ck("coverage counts both fund rows", cov["rows_total"] == 2 and cov["rows_valid"] == 2, cov)

print("[3] official row replaces a same-date detected gap")
merged = CH._merge_official_fund_events(
    [{"date": "2020-01-07", "ratio": 0.5, "source": "base-price-discontinuity"}],
    [{"date": "2020-01-07", "kind": "cash_dividend", "reference_price": 10176.0,
      "dividend_per_share": 171.0, "ratio": r1, "source": "fund-portal:test"}])
ck("exactly one event at the date", len(merged) == 1, merged)
ck("official is the survivor", str(merged[0].get("source")).startswith("fund-portal"), merged)
merged2 = CH._merge_official_fund_events(
    [{"date": "2020-01-07", "kind": "stock_split", "ratio": 0.5}],
    [{"date": "2020-01-07", "kind": "cash_dividend", "reference_price": 10176.0,
      "dividend_per_share": 171.0, "ratio": r1}])
ck("a typed split on the same date is preserved", len(merged2) == 2, merged2)

print("[4] session backfill: traded row becomes a candle, admin row does not")
candles = [{"time": "2023-03-28", "open": 1, "high": 1, "low": 1, "close": 1, "last": 1},
           {"time": "2023-03-25", "open": 1, "high": 1, "low": 1, "close": 1, "last": 1}]
vols = [{"time": c["time"], "value": 0} for c in candles]
rows = [{"time": "2023-03-27", "open": 10100, "high": 10200, "low": 10050,
         "close": 10150, "last": 10160, "base": 10080, "volume": 12345}]
c2, v2, ar2 = CH._merge_session_backfill(candles, vols, [], rows, descending=True)
ck("three candles after merge", len(c2) == 3, c2)
ck("order stays descending", [c["time"] for c in c2] == ["2023-03-28", "2023-03-27", "2023-03-25"], c2)
ck("backfilled row is in all_rows", len(ar2) == 1 and ar2[0]["time"] == "2023-03-27", ar2)
admin = dict(rows[0], high=0, low=0, volume=0)
c3, _v3, ar3 = CH._merge_session_backfill(
    [{"time": "2023-03-28", "open": 1, "high": 1, "low": 1, "close": 1, "last": 1},
     {"time": "2023-03-25", "open": 1, "high": 1, "low": 1, "close": 1, "last": 1}],
    [], [], [admin], descending=True)
ck("zero-volume admin row is not a candle", len(c3) == 2, c3)
ck("admin row still reaches all_rows", len(ar3) == 1, ar3)

print("[5] a proven session-wide base gap is rejected, a typed event is not")
_scon = sqlite3.connect(DB)
_scon.execute("INSERT OR REPLACE INTO session_anomalies VALUES "
              "(20200526,73,0,57,0.0084,'MARKET_WIDE_SESSION_DIFFERENCE','test','2026-10-20')")
_scon.commit(); _scon.close()
kept, rej = CH._filter_unproven_base_events("پارند", [
    {"date": "2020-05-26", "ratio": 0.99, "source": "base-price-discontinuity"},
    {"date": "2020-05-26", "ratio": 0.99, "source": "fund-portal:test"}])
ck("base gap rejected with its reason",
   len(kept) == 1 and kept[0]["source"].startswith("fund-portal")
   and rej and rej[0]["factor_status"] == "session-wide-base-gap", (kept, rej))

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(0 if fails == 0 else 1)
