# -*- coding: utf-8 -*-
"""Is the raw-close mismatch real, or are the two series one day apart?

Compares OUR close on day D against THEIR close on the day k positions away
from D in their own calendar. If some nonzero k hits ~100%, the mismatch is a
date-key artefact of the comparison, not a data difference. (A previous version
of this probe shifted a series against itself and so proved nothing; k=0 here is
the honest same-day number.)
"""
import datetime as dt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_argv = list(sys.argv)
sys.argv = [sys.argv[0]]
import _audit.adjust_three_way as H  # noqa: E402

OFFSET = _argv[1:] or ["0", "-1", "1", "-2", "2"]
SAMPLE = ["فولاد", "پارس", "خگستر", "شبندر", "وحکمت"]


def match(ours, theirs_keys, theirs, k):
    """ours[d] vs theirs[theirs_keys[index_of(d)+k]]"""
    pos = {d: i for i, d in enumerate(theirs_keys)}
    dev = []
    for d, v in ours.items():
        i = pos.get(d)
        j = (i + k) if i is not None else None
        if j is None or not (0 <= j < len(theirs_keys)):
            continue
        b = theirs[theirs_keys[j]]
        if b > 0:
            dev.append(abs(v / b - 1))
    if not dev:
        return None, None, 0
    return (100.0 * sum(1 for x in dev if x <= 0.01) / len(dev),
            max(dev) * 100, len(dev))


def main():
    frm = int(dt.datetime(2015, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    to = int(time.time())
    ks = [int(x) for x in OFFSET]
    print("%-9s %s" % ("symbol", "  ".join("k=%+d" % k for k in ks)))
    for sym in SAMPLE:
        sid = H.resolve(sym)
        if not sid:
            print("%-9s not found" % sym)
            continue
        closes, ev, cnt = H.our_chart(sym)
        raw0 = H.nn_series(sid, 0, frm, to)
        keys = sorted(raw0)
        ours = {d: closes[d] for d in closes if d in raw0}
        cells = []
        for k in ks:
            w, mx, n = match(ours, keys, raw0, k)
            cells.append("%s%%" % ("%.1f" % w if w is not None else "-"))
        print("%-9s %s   rows=%d" % (sym, "  ".join("%-8s" % c for c in cells), n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
