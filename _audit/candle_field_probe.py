# -*- coding: utf-8 -*-
"""Which price does each source put in the candle?

Our closes disagree with نهایات‌نگار on 26-40% of sessions by more than 1%,
peaking around 6-8%, and no date offset fixes it. That signature is not noise:
it is what a *field* difference looks like. TSETMC publishes several prices for
one session — «قیمت پایانی» (the closing/call auction price) and «آخرین
قیمت» (last traded) — and they differ most on days with a closing auction or a
thin session.

This probe takes the ten worst mismatched days for a symbol and prints, from
the local tables, every candidate field beside our candle value and theirs, so
the answer is read rather than guessed.
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

DB = os.environ.get(
    "BORS_DB",
    r"C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate\market.db")
SYM = (_argv[1:] or ["فولاد"])[0]


def main():
    import datetime as _dt
    frm = int(_dt.datetime(2015, 1, 1, tzinfo=_dt.timezone.utc).timestamp())
    to = int(time.time())
    sid = H.resolve(SYM)
    if not sid:
        print("isin not found for", SYM)
        return 1
    closes, ev, cnt = H.our_chart(SYM)
    theirs = H.nn_series(sid, 0, frm, to)
    shared = {d for d in closes if d in theirs and theirs[d] > 0}
    gaps = sorted(((abs(closes[d] / theirs[d] - 1), d) for d in shared), reverse=True)[:10]
    print("symbol=%s rows=%d  worst mismatches (ours vs theirs, same day):" % (SYM, len(shared)))
    for g, d in gaps:
        print("   %s  ours=%-9.0f theirs=%-9.0f  %+5.1f%%" % (d, closes[d], theirs[d], 100 * (closes[d] / theirs[d] - 1)))

    con = sqlite3.connect("file:%s?mode=ro" % DB.replace(os.sep, "/"), uri=True)
    row = con.execute("select ins_code from instruments where trim(l_val18)=?", (SYM,)).fetchone()
    print("\nlocal board rows for those days (ins_code=%s)" % (row[0] if row else "?"))
    print("   %s  %-9s %-9s %-9s %-9s" % ("date", "p_closing", "price_first", "p_last", "watch_close"))
    for g, d in gaps:
        de = int(d.replace("-", ""))
        dp = con.execute("select p_closing, price_first from daily_prices "
                         "where ins_code=? and d_even=?", (row[0], de)).fetchone() if row else None
        mw = con.execute("select p_closing, p_last from market_watch "
                         "where ins_code=?", (row[0],)).fetchone() if row else None
        print("   %s  %-9s %-9s %-9s %-9s" % (
            d, dp[0] if dp else "-", dp[1] if dp else "-",
            mw[1] if mw else "-", mw[0] if mw else "-"))
    con.close()
    print("\nnote: daily_prices is a short rolling window, so older days may show '-'.")
    print("      market_watch holds only the latest session per symbol.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
