"""تستِ واحدِ خوانندهٔ سریِ شاخص و payloadِ snapshot — بدونِ بانکِ عملیاتی.

اجرا:  python dev/test_market_index_series.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import mstat_engine as M  # noqa: E402

fails = []


def say(ok, msg):
    print("  %s %s" % ("PASS" if ok else "FAIL", msg))
    if not ok:
        fails.append(msg)


def make_db(with_totals=True):
    con = sqlite3.connect(":memory:")
    totals = ", z_tot_tran REAL, q_tot_cap REAL, q_tot_tran REAL" if with_totals else ""
    con.execute("CREATE TABLE market_index (d_even INTEGER PRIMARY KEY, idx_last REAL,"
                " idx_change REAL, idx_pct REAL, ew_last REAL, ew_change REAL,"
                " ew_pct REAL%s)" % totals)
    if with_totals:
        con.execute("INSERT INTO market_index VALUES (20261027, 100, 1, 1.0, 90, 1, 1.1,"
                    " 700000, 400000000000000.0, 9000000000.0)")
        con.execute("INSERT INTO market_index VALUES (20261028, 110, 10, 10.0, 95, 5, 5.5,"
                    " 800000, 500000000000000.0, 10000000000.0)")
    else:
        con.execute("INSERT INTO market_index VALUES (20261027, 100, 1, 1.0, 90, 1, 1.1)")
    return con


con = make_db()
series = M.market_index_series(con, 2)
say(len(series) == 2, "series returns 2 rows")
say(series[0]["d_even"] == 20261028, "series is newest-first")
say(series[0]["z_tot_tran"] == 800000, "z_tot_tran is read")
say(series[1]["q_tot_cap"] == 400000000000000.0, "previous q_tot_cap is read")

con2 = make_db(with_totals=False)
legacy = M.market_index_series(con2, 1)
say(len(legacy) == 1, "legacy schema still answers")
say(legacy[0]["z_tot_tran"] is None, "legacy schema gives None, not zero")

M.macro_health = lambda _conn: {"market_value_hemat": 8123.4, "value_hemat": 45.6,
                                "state": "good", "label": "مساعد",
                                "good_min": 20, "bad_max": 10, "excellent_min": 50,
                                "basis": "x", "cause": None}
snap = M.market_snapshot(make_db())
say(snap["status"] == "ok", "snapshot status ok")
say(snap["index"]["last"] == 110, "index is the newest row")
say(snap["prev"]["d_even"] == 20261027, "prev is the previous session")
say(snap["market"]["trades"] == 800000, "market.trades comes from z_tot_tran")
say(snap["market"]["trade_value_hemat"] == 50.0, "trade value converts rial to hemat")
say(snap["retail"]["value_hemat"] == 45.6, "retail comes from macro")
say(snap["retail"]["bad_max"] == 10, "thresholds are passed through")

print("\n%d failed" % len(fails))
sys.exit(1 if fails else 0)
