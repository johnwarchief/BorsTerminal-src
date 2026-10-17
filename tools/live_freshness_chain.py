#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/live_freshness_chain.py — زنجیرۀ «منبع ← بانک ← محاسبه ← API ← UI» در لحظه

مأموریت «صحت دادهٔ تابلو + خروجیِ دیده‌بان» می‌گوید تازگیِ داده را از سرعتِ
پاسخ جدا کن و برایِ هر حلقۀ زنجیره زمانِ واقعی ثبت کن. این ابزار هیچ چیزی را
restart نمی‌کند و چیزی نمی‌نویسد: فقط `market.db` را فقط‌خواندنی باز می‌کند و
همان endpointهایی را می‌زند که رابطِ کاربر می‌زند، و در هر دور ثبت می‌کند:

  • ساعتِ محلی (تهران)
  • آخرین `fetched_at` و بالاترین `h_even` درِ `market_watch` (لحظۀ ذخیره)
  • `last`ِ خودِ سینکر (`market_sync.json`) و «آیا سینکر زنده است؟»
  • `activity_h_even` و مرحلۀ رسمیِ بازار از `/api/mstat/phase`
  • تأخیر و حجمِ `/api/market` و شمار ردیف‌هایش
  • فاصلۀ «اکنون − آخرین ذخیره» = تأخیرِ واقعیِ داده، نه تأخیرِ پاسخ

اجرا: PYTHONIOENCODING=utf-8 python tools/live_freshness_chain.py \
        --base http://127.0.0.1:8001 --cycles 6 --interval 20
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zoneinfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEHRAN = zoneinfo.ZoneInfo("Asia/Tehran")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--cycles", type=int, default=6)
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--sync-json", default=os.path.join(ROOT, "market_sync.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "perf_live",
                                                  "freshness_chain.jsonl"))
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    rows_out = []
    for i in range(a.cycles):
        rec = {"i": i}
        tnow = __import__("datetime").datetime.now(TEHRAN)
        rec["tehran"] = tnow.strftime("%H:%M:%S")
        try:
            c = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"),
                                uri=True, timeout=20)
            r = c.execute("SELECT MAX(d_even), MAX(h_even), MAX(fetched_at),"
                          " COUNT(*) FROM market_watch").fetchone()
            rec["db"] = {"d_even": r[0], "max_h_even": r[1], "max_fetched_at": r[2],
                         "rows": r[3]}
            try:
                d = r[0]
                rec["db"]["stale_rows"] = c.execute(
                    "SELECT COUNT(*) FROM market_watch WHERE d_even<>?", (d,)).fetchone()[0]
            except sqlite3.Error:
                pass
            c.close()
        except sqlite3.Error as e:
            rec["db"] = {"error": str(e)[:80]}
        try:
            with open(a.sync_json, encoding="utf-8") as f:
                sj = json.load(f)
            rec["syncer_last"] = {k: sj.get(k) for k in
                                  ("stage", "phase", "detail", "ts", "current", "total")}
        except OSError:
            rec["syncer_last"] = None
        for name, path in (("phase", "/api/mstat/phase"),
                          ("market", "/api/market"),
                          ("sync_state", "/api/market/sync-state")):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(a.base + path, timeout=45) as resp:
                    raw = resp.read()
                ms = round((time.perf_counter() - t0) * 1000.0, 1)
                try:
                    d = json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    d = {}
                if name == "phase":
                    rec["phase"] = {"ms": ms,
                                    "activity_h_even": d.get("activity_h_even"),
                                    "official_state": d.get("official_state"),
                                    "is_live": d.get("is_live"),
                                    "phase": d.get("phase")}
                elif name == "market":
                    rr = d.get("rows") or d.get("data") or []
                    rec["market"] = {"ms": ms, "bytes": len(raw),
                                    "rows": len(rr) if isinstance(rr, list) else None,
                                    "keys": sorted(d.keys())[:8] if isinstance(d, dict) else None}
                else:
                    rec["sync_state"] = {"ms": ms,
                                         "running": d.get("running"),
                                         "last": (d.get("last") or {}).get("ts"),
                                         "stage": (d.get("last") or {}).get("stage")}
            except (urllib.error.URLError, OSError) as e:
                rec[name] = {"ms": round((time.perf_counter() - t0) * 1000.0, 1),
                             "error": "%s" % type(e).__name__}
        # تأخیرِ واقعیِ داده: اکنون − آخرین ذخیرهٔ تابلو
        try:
            fa = (rec.get("db") or {}).get("max_fetched_at")
            if fa:
                dt = __import__("datetime").datetime.strptime(fa, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=TEHRAN)
                rec["data_lag_seconds"] = int((tnow - dt).total_seconds())
        except Exception:
            rec["data_lag_seconds"] = None
        rows_out.append(rec)
        print(json.dumps(rec, ensure_ascii=False))
        if i < a.cycles - 1:
            time.sleep(a.interval)
    with open(a.out, "w", encoding="utf-8") as f:
        for rec in rows_out:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("saved: %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
