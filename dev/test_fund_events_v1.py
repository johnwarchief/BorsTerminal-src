# -*- coding: utf-8 -*-
"""Round 8: official fund distribution rows drive the production factor chain.

The fund row is keyed by ins_code and carries (reference_price, unit_profit,
ratio) from the official manager portal importer.  The chart path must:
  * read the rows without touching the network,
  * apply factor(t) = product(ratio) for event dates > t,
  * replace a same-date discovered/base event instead of double counting.
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
os.environ.setdefault("BORS_GATE_ISOLATED", "1")

import api.chart as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=None):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT,"
                    " l_val30 TEXT, board INTEGER, updated_at TEXT)")
        con.execute("INSERT INTO instruments VALUES ('1','آزمون','آزمون',1,'2026-10-21')")
        con.execute("CREATE TABLE fund_profit_events (ins_code TEXT, d_even INTEGER,"
                    " symbol TEXT, profit_date TEXT, unit_profit REAL,"
                    " reference_price REAL, ratio REAL, source TEXT, source_id TEXT,"
                    " fetched_at TEXT)")
        con.execute("INSERT INTO fund_profit_events VALUES"
                    " ('1',20260105,'آزمون','1404/10/15',100,1000,0.9,"
                    " 'fund-portal:test','1:1404/10/15','2026-10-21')")
        con.execute("INSERT INTO fund_profit_events VALUES"
                    " ('1',20260205,'آزمون','1404/11/15',50,1010,0.950495,"
                    " 'fund-portal:test','1:1404/11/15','2026-10-21')")
        con.commit()
        con.close()

        old = C.DB_PATH
        C.DB_PATH = path
        try:
            ev = C._fund_profit_events("آزمون")
            ck(len(ev) == 2, "two official fund rows are read", ev)
            ck(ev[0]["date"] == "2026-01-05" and ev[0]["dividend_per_share"] == 100.0,
               "first fund row keeps date and per-unit amount", ev[0])
            ck(ev[0]["kind"] == C.AE.KIND_CASH_DIVIDEND,
               "fund row is a cash-dividend event", ev[0].get("kind"))

            # A discovered base gap on the same date is replaced, not doubled.
            events = [{"date": "2026-01-05", "ratio": 0.90,
                       "source": "base-price-discontinuity"},
                      {"date": "2026-01-05", "ratio": 0.5,
                       "kind": C.AE.KIND_SPLIT, "source": "shareChange"}]
            merged = C._merge_official_fund_events(events, ev)
            dates = sorted((e["date"], e.get("kind") or e.get("source")) for e in merged)
            ck(sum(1 for d, _ in dates if d == "2026-01-05") == 2,
               "same-date base gap replaced while typed event survives", merged)
            ck(any(k == C.AE.KIND_CASH_DIVIDEND for _, k in dates)
               and any(k == C.AE.KIND_SPLIT for _, k in dates),
               "official fund event and distinct typed event both present", dates)

            times = ["2026-01-04", "2026-01-05", "2026-02-04", "2026-02-05"]
            applied, rejected, factors, chain, cov = C._canonical_adjustment(
                "آزمون", times, [])
            ck(len(applied) == 2 and not rejected,
               "canonical path applies the two fund rows", (applied, rejected))
            by_t = dict(zip(times, factors))
            want = 0.9 * 0.950495
            ck(abs(by_t["2026-01-04"] - want) < 1e-6,
               "factor before both events is the product", (by_t, want))
            ck(abs(by_t["2026-01-05"] - 0.950495) < 1e-6,
               "first event drops out on its own date", by_t)
            ck(abs(by_t["2026-02-04"] - 0.950495) < 1e-6,
               "factor holds until the next event", by_t)
            ck(by_t["2026-02-05"] == 1.0,
               "factor is 1 on the last event date", by_t)
        finally:
            C.DB_PATH = old
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    sys.exit(0 if F == 0 else 1)


if __name__ == "__main__":
    main()
