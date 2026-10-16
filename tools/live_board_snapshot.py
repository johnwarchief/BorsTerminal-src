#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""نمونۀ زندۀ یک‌لحظه‌ای از بکاندِ در حال اجرا + شمارشِ تغییرِ داده بینِ دو نمونه.

فقط خواندنی: هیچ POST/PUTی نمیزند و هیچ جدولی را نمی‌نویسد.
خروجی: _audit/live_audit_<stamp>.json (برایِ مقایسۀ دو نمونه در گزارشِ نشست).
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

APP = os.environ.get("BORS_APP", "http://127.0.0.1:8001")
OUT = sys.argv[1] if len(sys.argv) > 1 else "_audit/live_sample.json"

PATHS = [
    "/api/market",
    "/api/live-stats",
    "/api/mstat/summary",
    "/api/mstat/thermometer?group=eq_all",
    "/api/mstat/smart-money",
    "/api/mstat/depth?group=eq_all",
    "/api/mstat/histogram",
    "/api/mstat/clientsplit",
    "/api/mstat/industries",
    "/api/mstat/mainwatch",
    "/api/mstat/timeline",
    "/api/mstat/phase",
    "/api/screener",
]

# نمونه‌هایِ رفتاریِ متفاوت: پرمعامله، کم‌معامله، صف‌دار، بی‌معامله
WATCH = ["فولاد", "خرید", "وشمال", "ثاخت", "نوری", "سپا"]


def get(path, timeout=30):
    t0 = time.time()
    try:
        with urllib.request.urlopen(APP + path, timeout=timeout) as r:
            raw = r.read()
        return {"status": r.status, "ms": round((time.time() - t0) * 1000),
                "bytes": len(raw), "json": json.loads(raw)}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "ms": round((time.time() - t0) * 1000),
                "error": f"{type(e).__name__}: {e}", "json": None}


def main():
    out = {"app": APP, "wall_clock_machine": datetime.now().isoformat(timespec="seconds"),
           "epoch": time.time(), "endpoints": {}}
    for p in PATHS:
        out["endpoints"][p] = get(p)

    mk = out["endpoints"]["/api/market"]["json"] or {}
    rows = mk.get("data") or []
    out["board"] = {
        "meta": mk.get("meta"),
        "rev": mk.get("rev"),
        "count": mk.get("count"),
        "live_count": mk.get("live_count"),
        "fossil_count": mk.get("fossil_count"),
        "rows_returned": len(rows),
        "zero_volume_rows": sum(1 for r in rows if not r.get("q_tot_tran")),
        "null_p_last_rows": sum(1 for r in rows if r.get("p_last") in (None, 0)),
    }
    idx = {r.get("symbol"): r for r in rows}
    out["watch"] = {}
    for s in WATCH:
        r = idx.get(s)
        if not r:
            out["watch"][s] = None
            continue
        out["watch"][s] = {k: r.get(k) for k in (
            "p_last", "p_closing", "price_change", "q_tot_tran", "z_tot_tran", "q_tot_cap",
            "buy_i_vol", "sell_i_vol", "buy_q1_px", "buy_q1_vol", "sell_q1_px", "sell_q1_vol",
            "p_max", "p_min", "p_first", "price_yesterday", "tmin", "is_live" if "is_live" in r else None)}
    # شمارشِ وضعیت‌هایِ بازار (تازگیِ خودِ داده)
    try:
        import sqlite3
        db = os.environ.get("BORS_DB", "")
        if db and os.path.exists(db):
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            c.execute("PRAGMA query_only=ON")
            out["db_ro"] = {
                "max_d_even_market_watch": c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0],
                "max_d_even_daily_prices": c.execute("SELECT MAX(d_even) FROM daily_prices").fetchone()[0],
                "max_d_even_tape_history": c.execute("SELECT MAX(d_even) FROM tape_history").fetchone()[0],
                "rows_market_watch": c.execute("SELECT COUNT(*) FROM market_watch").fetchone()[0],
                "rows_today": c.execute("SELECT COUNT(*) FROM market_watch WHERE d_even=(SELECT MAX(d_even) FROM market_watch)").fetchone()[0],
                "fetched_at_min_max": c.execute("SELECT MIN(fetched_at), MAX(fetched_at) FROM market_watch").fetchone(),
            }
            c.close()
    except Exception as e:  # noqa: BLE001
        out["db_ro_error"] = f"{type(e).__name__}: {e}"

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({"wall": out["wall_clock_machine"], "board": out["board"],
                      "endpoints_ms": {p: (v["status"], v["ms"]) for p, v in out["endpoints"].items()}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
