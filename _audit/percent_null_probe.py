# -*- coding: utf-8 -*-
"""scratch: how many board rows carry a *fabricated* percent_change?

Runs the app's own `_build_market_response` against a throwaway copy of a
market.db and counts, per column, how many rows came back as 0 / null. Used to
prove that «تغییر٪ = ۰٫۰۰» on symbols whose TSETMC yesterday-price is the guard
value (price_yesterday <= 1) is invented by the JSON-safety fillna, and that it
disappears once the column is allowed to stay null.

    python _audit/percent_null_probe.py --label before --db "<installed market.db>"
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


class FakeRequest:
    def __init__(self):
        self.headers = {}
        self.query_params = {}


class NoCloseConn(sqlite3.Connection):
    def close(self):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = os.path.abspath(args.db)
    tmp = tempfile.mkdtemp(prefix="bors_pct_null_")
    work = os.path.join(tmp, "copy.db")
    a = sqlite3.connect("file:" + src.replace("\\", "/") + "?mode=ro", uri=True)
    b = sqlite3.connect(work, factory=NoCloseConn)
    a.backup(b, pages=256)
    a.close()

    import api.market as mk

    holder = {"c": b}
    mk.get_db = lambda: holder["c"]
    b.execute("PRAGMA cache_size=-65536")

    t0 = time.perf_counter()
    out = mk._build_market_response(FakeRequest())
    body = out.body if isinstance(out.body, (bytes, str)) else json.dumps(out.body)
    data = json.loads(body)
    rows = data["data"]

    cols = ("percent_change", "percent_last", "vol_ratio", "vol_dod", "month_avg_vol",
            "prev_day_vol", "hist_sessions", "buyer_power", "min_low_29", "last_vs_close")
    nulls = {c: sum(1 for r in rows if r.get(c) is None) for c in cols}
    zeros = {c: sum(1 for r in rows if r.get(c) == 0 and r.get(c) is not None) for c in cols}
    guard_rows = [r for r in rows if (r.get("price_yesterday") or 0) <= 1]
    fabricated = [r for r in guard_rows if r.get("percent_change") == 0]
    sample = [{"symbol": r.get("symbol"), "py": r.get("price_yesterday"),
               "p_closing": r.get("p_closing"), "p_last": r.get("p_last"),
               "percent_change": r.get("percent_change"),
               "percent_last": r.get("percent_last")} for r in fabricated[:5]]
    report = {
        "label": args.label,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "build_seconds": round(time.perf_counter() - t0, 3),
        "rows": len(rows),
        "guard_base_rows": len(guard_rows),
        "fabricated_zero_percent_change": len(fabricated),
        "nulls": nulls,
        "zeros": zeros,
        "sample": sample,
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    sqlite3.Connection.close(b)
    try:
        os.remove(work)
        os.rmdir(tmp)
    except OSError:
        print("left behind:", work)
    return 0


if __name__ == "__main__":
    sys.exit(main())
