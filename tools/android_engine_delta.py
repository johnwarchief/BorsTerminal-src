#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اندازۀ فاصلۀ **موتور** بین بستۀ منتشرشده و بک‌اندِ امروز، رویِ یک بانکِ واحد.

چرا این سنجش: بستۀ `mobile-latest-v2` درِ ۲۰۲۶-۱۰-۱۶T۰۰:۳۲ از همان `market.db`
اینجا و با موتورِ شاخۀ کهنه (1.1.0 = 323 کامیت پایین‌تر ازِ main) پخته شده. پس
تفاوتِ `screenerِ` آن بسته با `screenerِ` همین بانک درِ موتورِ امروز فقط تفاوتِ
**داوری** است، نه تفاوتِ داده. این همان عددی است که باید قبل/بعد گفته شود، نه
لیستِ نمادها.

احتیاطِ ثبت‌شدہ: سطرهایِ وابسته به نشستِ زنده (`as_of`، شمارش‌هایِ تابلو)
مقایسه نمی‌شوند؛ فقط حکمِ هر نماد. بی‌این، هر اجرا «تغییر» نشان می‌داد.
اجرا:
    BORS_CODAL_OFFLINE=1 BORS_NO_FETCH_LOOPS=1 python tools/android_engine_delta.py \
        --old _audit/tmp/pubgz/mobile_snapshot.db
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")

# فیلدهایی که رأیِ موتورند و درِ هر دو پاسخ هم معنا دارند.
VERDICT_FIELDS = ("score", "verdict", "assembly_veto", "excluded", "pricing_mode",
                  "rev_growth", "eps_last", "gross_margin", "sales_to_mcap",
                  "annual_sales_bt", "tech_trend_w", "tech_trend_d", "tech_status")


def rows_by_symbol(payload: dict) -> dict:
    out = {}
    for r in (payload.get("data") or []):
        s = str(r.get("symbol") or "")
        if s.strip():
            out[s] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="بستۀ پختۀ منتشرشده (mobile_snapshot.db)")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "android_engine_delta.json"))
    a = ap.parse_args()

    con = sqlite3.connect("file:%s?mode=ro" % a.old.replace("\\", "/"), uri=True)
    old_raw = con.execute("SELECT json FROM baked WHERE key='screener'").fetchone()
    if not old_raw:
        raise SystemExit("BLOCKED: کلید screener درِ بستهٔ قدیم نیست")
    old = json.loads(old_raw[0])
    old_rows = rows_by_symbol(old)
    old_meta = {k: v for k, v in con.execute("SELECT key,value FROM meta")}
    con.close()

    from fastapi.testclient import TestClient
    import app as appmod
    with TestClient(appmod.app, base_url="http://127.0.0.1:8001") as c:
        r = c.get("/api/screener")
        if r.status_code != 200:
            raise SystemExit("BLOCKED: /api/screener امروز %s داد" % r.status_code)
        new = r.json()
    new_rows = rows_by_symbol(new)

    common = sorted(set(old_rows) & set(new_rows))
    per_field = {f: 0 for f in VERDICT_FIELDS}
    symbols_moved = 0
    examples = []
    for s in common:
        o, n = old_rows[s], new_rows[s]
        moved = [f for f in VERDICT_FIELDS if json.dumps(o.get(f), sort_keys=True)
                 != json.dumps(n.get(f), sort_keys=True)]
        if moved:
            symbols_moved += 1
            for f in moved:
                per_field[f] += 1
            if len(examples) < 6:
                examples.append({"symbol": s,
                                 "fields": {f: {"old": o.get(f), "new": n.get(f)} for f in moved}})

    res = {
        "old_package": {"app_version": old_meta.get("app_version"), "built_at": old_meta.get("built_at"),
                        "package_id": old_meta.get("package_id"), "rows": len(old_rows),
                        "count_field": old.get("count")},
        "today_backend": {"app_version": __import__("bors_config").APP_VERSION,
                          "rows": len(new_rows), "count_field": new.get("count")},
        "universe": {"old_only": len(set(old_rows) - set(new_rows)),
                     "new_only": len(set(new_rows) - set(old_rows)),
                     "common": len(common)},
        "verdict_diff": {"symbols_with_any_change": symbols_moved,
                         "by_field": per_field,
                         "share_of_common": (round(100.0 * symbols_moved / len(common), 2)
                                             if common else 0)},
        "score_histogram": {
            "old": _hist(old_rows), "new": _hist(new_rows)},
        "examples": examples,
        "caveat": ("فقط فیلدهایِ داوری مقایسه شده؛ as_of/شمارش/تابلو سنجیده نمی‌شوند. "
                   "هر دو پاسخ از یک market.db خوانده می‌شوند، پس اختلاف = موتور."),
    }
    json.dump(res, io.open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("old_package", "today_backend", "universe",
                                          "verdict_diff", "score_histogram")},
                     ensure_ascii=False, indent=1))
    print("wrote %s" % a.out)
    return 0


def _hist(rows: dict) -> dict:
    h = {}
    for r in rows.values():
        h[str(r.get("score"))] = h.get(str(r.get("score")), 0) + 1
    return dict(sorted(h.items(), key=lambda kv: (kv[0] == "None", kv[0])))


if __name__ == "__main__":
    sys.exit(main())
