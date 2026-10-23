# -*- coding: utf-8 -*-
"""Cross-sectional session-anomaly detector: positive, negative and synthetic controls."""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

from tools import session_anomaly_scan as S  # noqa: E402

checks, fails = 0, 0
def ck(name, cond, detail=""):
    global checks, fails
    checks += 1
    print(("  OK   " if cond else "  FAIL ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        fails += 1

print("[1] qualification rule")
ck("2020-05-26 measured row qualifies", S.qualifies(0, 57, 0.0084))
ck("a real event cluster with official rows does not qualify", S.qualifies(4, 57, 0.0084) is False)
ck("too few product-only steps does not qualify", S.qualifies(0, 9, 0.0084) is False)
ck("high median deviation does not qualify", S.qualifies(0, 57, 0.03) is False)
ck("exactly 10 steps / 2% is the inclusive boundary", S.qualifies(0, 10, 0.02))
ck("malformed numbers do not qualify", S.qualifies(None, "x", "y") is False)

print("[2] synthetic anomaly is not tied to a date")
# The detector is date-free: any row meeting the rule qualifies.
ck("synthetic 1999 date qualifies", S.qualifies(0, 40, 0.01))
ck("synthetic 2030 date qualifies", S.qualifies(0, 12, 0.005))

print("[3] the chart filter only drops base gaps, never typed officials")
sys.path.insert(0, ROOT)
import tempfile, sqlite3
tmp = tempfile.mkdtemp(prefix="anomaly_")
DB = os.path.join(tmp, "t.db")
con = sqlite3.connect(DB)
import tsetmc_p0_schema as P0
P0.create_all(con)
con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT, "
            "paper_type INTEGER, sector_name TEXT, updated_at TEXT)")
con.execute("INSERT INTO instruments VALUES ('A1','تست','شرکت تست',1,'ساخت','2026-01-01')")
con.execute("INSERT INTO session_anomalies VALUES (19990101,50,0,30,0.005,"
            "'MARKET_WIDE_SESSION_DIFFERENCE','synthetic','2026-10-20')")
con.commit(); con.close()
import bors_config
bors_config.DB_PATH = DB
import api.chart as CH
CH.DB_PATH = DB
kept, rej = CH._filter_unproven_base_events("تست", [
    {"date": "1999-01-01", "ratio": 0.99, "source": "base-price-discontinuity"},
    {"date": "1999-01-01", "ratio": 0.99, "source": "priceAdjust"},
    # The next-day gap is deliberately >1.5%: Round 22 rejects only isolated
    # small unproven gaps; this assertion is about the anomaly filter not
    # bleeding into the next session, not about that separate rule.
    {"date": "1999-01-02", "ratio": 0.95, "source": "base-price-discontinuity"}])
ck("base gap on the synthetic anomaly is rejected",
   len(rej) == 1 and rej[0]["factor_status"] == "session-wide-base-gap", rej)
ck("typed official event survives", any(e["source"] == "priceAdjust" for e in kept), kept)
ck("next day is untouched", any(e["date"] == "1999-01-02" for e in kept), kept)

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(0 if fails == 0 else 1)
