# -*- coding: utf-8 -*-
"""Do our three modes line up with نهایات‌نگار, symbol by symbol?

The parity tool answers the *shape* of our adjustment factor. This answers the
other two questions a trader actually asks:

  none  — are our raw closes the same numbers as their «بدون تعدیل»?
  combined — for a fixed set of dates, does our adjusted close equal their
             «افزایش+سود با آورده» close?  (both are rial, so this is a real
             number-to-number check, not just a shape)
  performance — is our index exactly combined/first*100, i.e. self-consistent?

Compared on the same dates, at one instant, from both sources.
"""
import datetime as dt
import json
import statistics
import sys
import time
import urllib.parse
import urllib.request

OUR = "http://127.0.0.1:8001"
NN = "https://www.nahayatnegar.com/tv/chart/history"
HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nahayatnegar.com/tv/"}
SYMS = sys.argv[1:] or ["فولاد", "فملی", "شپنا", "سبهان", "خگستر",
                        "شبندر", "وبهمن", "وغدير", "خودرو", "پارس"]


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def resolve(query):
    """Same resolver the parity tool uses (exact, normalised name match)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "tools"))
    import nn_adjust_parity as p
    return p.nn_resolve(query)


def nn_series(sid, adj, frm, to):
    j = get(f"{NN}?symbol={sid}{adj}&resolution=1D&from={frm}&to={to}"
            f"&type=stock&adjustmentType={adj}&countback=4000")
    return {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): float(c)
            for t, c in zip(j.get("t") or [], j.get("c") or [])}


def our_chart(sym):
    j = get("%s/api/chart/%s" % (OUR, urllib.parse.quote(sym)), timeout=240)
    closes = {c["time"]: float(c["close"]) for c in (j.get("candles") or [])}
    ev = [(e["date"], float(e["ratio"])) for e in (j.get("adjustEvents") or [])
          if e.get("date") and 0.02 < float(e.get("ratio") or 0) < 50]
    return closes, ev, j.get("count")


def combined(closes, ev, date):
    """Exactly frontend applyAdjustmentToCandles(..., 'combined')."""
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    ts = d.timestamp() * 1000
    f = 1.0
    for e_date, ratio in ev:
        e_ts = dt.datetime.strptime(e_date, "%Y-%m-%d").replace(
            tzinfo=dt.timezone.utc).timestamp() * 1000
        if ts < e_ts:
            f *= min(max(ratio, 0.0001), 50.0)
    return round(closes[date] * f)


def pct_within(a, b, tol):
    """درصدِ ردیف‌هایی که |a/b-1| زیرِ tol‌اند (b صفر را می‌اندازد)."""
    out = []
    for d in sorted(set(a) & set(b)):
        if b[d] > 0:
            out.append(abs(a[d] / b[d] - 1))
    if not out:
        return None, None, 0
    return (100.0 * sum(1 for x in out if x <= tol) / len(out)), max(out) * 100, len(out)


def main():
    frm = int(dt.datetime(2010, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    to = int(time.time())
    print("%-8s %-14s %6s  %8s %8s  %8s %8s" %
          ("symbol", "their_isin", "rows", "raw±1%", "rawMax%", "adj±1%", "adjMax%"))
    for sym in SYMS:
        sid = resolve(sym)
        if not sid:
            print("%-8s isin not found" % sym)
            continue
        try:
            closes, ev, cnt = our_chart(sym)
            raw0 = nn_series(sid, 0, frm, to)
            s3 = nn_series(sid, 3, frm, to)
        except Exception as e:
            print("%-8s %s ERR %s" % (sym, sid, type(e).__name__))
            continue
        mine_raw = {d: v for d, v in closes.items() if d in raw0}
        theirs_raw = {d: raw0[d] for d in mine_raw}
        w1, mx1, n = pct_within(mine_raw, theirs_raw, 0.01)
        mine_adj = {d: combined(closes, ev, d) for d in mine_raw}
        theirs_adj = {d: s3[d] for d in mine_raw if d in s3}
        w2, mx2, _ = pct_within(mine_adj, theirs_adj, 0.01)
        print("%-8s %-14s %6d  %8s %8s  %8s %8s" %
              (sym, sid, n,
               "%.1f" % w1 if w1 is not None else "-",
               "%.1f" % mx1 if mx1 is not None else "-",
               "%.1f" % w2 if w2 is not None else "-",
               "%.1f" % mx2 if mx2 is not None else "-"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
