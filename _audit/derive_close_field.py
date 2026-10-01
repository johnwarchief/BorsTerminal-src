# -*- coding: utf-8 -*-
"""Which TSETMC column is each source's candle close? Derived, not assumed.

On days where قیمت پایانی and آخرین قیمت differ, exactly one of the columns can
equal the number a source prints. Testing only the ten worst days would be an
anecdote, so this sweeps every comparable day of several symbols and counts,
per source, which column the value matches to within one price step.

Outputs, for نهایات‌نگار and for our own app:
  - how many disagreeing days each source explained, and by which column
  - the unmatched residue, so a wrong hypothesis cannot hide
"""
import datetime as dt
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_argv = list(sys.argv)
sys.argv = [sys.argv[0]]
import _audit.adjust_three_way as H  # noqa: E402
import test_tsetmc as T              # noqa: E402
import csv as _csv
import io as _io
import requests

DB = os.environ.get("BORS_DB",
                    r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate\market.db")
SYMS = _argv[1:] or ["فولاد", "پارس", "خگستر", "شبندر", "فملی"]


def csv_rows(ins_code, since="20150101"):
    u = f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/{since}"
    r = requests.get(u, headers=T.HEADERS, timeout=150)
    r.raise_for_status()
    rows = list(_csv.reader(_io.StringIO(r.text)))
    head = [h.strip("<>") for h in rows[0]]
    idx = {n: i for i, n in enumerate(head)}
    out = {}
    for f in rows[1:]:
        if len(f) < len(head):
            continue
        d = f[idx["DTYYYYMMDD"]].strip()
        if len(d) != 8 or not d.isdigit():
            continue
        try:
            out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = {
                k: float(f[idx[k]]) for k in
                ("FIRST", "HIGH", "LOW", "CLOSE", "OPEN", "LAST", "VALUE", "VOL")}
        except (ValueError, KeyError, IndexError):
            continue
    return out


def ins_of(con, sym):
    r = con.execute("select ins_code from instruments where trim(l_val18)=?", (sym,)).fetchone()
    return r[0] if r else None


def which(val, day, step=1.0):
    """نامِ ستون‌هایی که عددِ val با ایشان تا یک پله می‌خواند."""
    hits = []
    for k in ("FIRST", "OPEN", "HIGH", "LOW", "CLOSE", "LAST"):
        v = day.get(k)
        if v and abs(val - v) <= max(step, v * 0.0006):
            hits.append(k)
    return hits


def main():
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace(os.sep, "/"), uri=True)
    frm = int(dt.datetime(2015, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    to = int(time.time())
    tally_nn, tally_us = {}, {}
    print("%-9s %-8s %6s %6s %7s" % ("symbol", "ins_code", "days", "differ", "ours/nn"))
    for sym in SYMS:
        code = ins_of(con, sym)
        sid = H.resolve(sym)
        if not code or not sid:
            print("%-9s skipped (ins_code=%s isin=%s)" % (sym, bool(code), sid or "-"))
            continue
        days = csv_rows(code)
        theirs = H.nn_series(sid, 0, frm, to)
        mine = {d: c for d, c in con.execute(
            "select date, close from price_history where symbol=?", (sym,))}
        n_diff = 0
        shown = 0
        for d, day in sorted(days.items()):
            if d not in theirs or d not in mine:
                continue
            close, last = day.get("CLOSE", 0), day.get("LAST", 0)
            if not close or not last or abs(close - last) <= max(1.0, close * 0.0006):
                continue          # روزهایی که دو ستون یکی‌اند چیزی را اثبات نمی‌کنند
            n_diff += 1
            hn = which(theirs[d], day)
            hu = which(mine[d], day)
            key_n = "+".join(hn) or "NONE"
            key_u = "+".join(hu) or "NONE"
            tally_nn[key_n] = tally_nn.get(key_n, 0) + 1
            tally_us[key_u] = tally_us.get(key_u, 0) + 1
            if shown < 2:
                print("     %s پایانی=%-9.0f آخرین=%-9.0f | theirs=%-9.0f -> %-12s | ours=%-9.0f -> %s"
                      % (d, close, last, theirs[d], key_n, mine[d], key_u))
                shown += 1
        print("%-9s %-8s %6d %6d" % (sym, code[-8:], len(days), n_diff))
    con.close()
    print("\nOUR close, over all disagreeing days:")
    for k, v in sorted(tally_us.items(), key=lambda x: -x[1]):
        print("   %-14s %6d" % (k, v))
    print("\nنهایات‌نگار close, over the same days:")
    for k, v in sorted(tally_nn.items(), key=lambda x: -x[1]):
        print("   %-14s %6d" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
