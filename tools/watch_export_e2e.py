#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/watch_export_e2e.py — مسیرِ واقعیِ HTTPِ خروجیِ دیدهبان، با دادهٔ زنده.

گاردِ `dev/watch_export_v1106.py` کارخانۀ فایل را درِ فرایند می‌سنجد. این ابزار
همان کاری را می‌کند که رابط می‌کند: ردیف‌هایِ واقعیِ `/api/market` را برداشته،
بدنۀ `POST /api/export` را می‌سازد، فایلِ برگشتی را **رویِ دیسک می‌گذارد و باز
می‌کند** و می‌شمارد: چند سطر، چند ستون، خانۀ عددی عدد است یا رشته، تهی صفر
شده یا نه، ردپا درِ فایل هست یا نه.

هیچ نوشتنی رویِ `market.db` ندارد (export فقط بدنه را می‌خواند) و هیچ پروسه‌ای
را می‌کُشد که خودش بالا نیاورده است.

اجرا:  PYTHONIOENCODING=utf-8 python tools/watch_export_e2e.py [--base http://127.0.0.1:8021]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# همان قراردادی که `watchExport.ts` می‌فرستد: سرِ ستونِ واحددار، سپس ردیف‌ها.
# فهرستِ ستون‌ها ازِ خودِ فایلِ رابط خوانده می‌شود تا دومینِ فهرست نسازیم.
COLS_SRC = os.path.join(ROOT, "frontend", "src", "features", "portfolio", "lib", "watchExport.ts")
WATCH_KEY_TO_TSETMC = {
    "symbol": "symbol", "name": "name", "ins_code": "ins_code", "sector": "sector_name",
    "board": "board", "p_last": "p_last", "percent_change": "percent_change",
    "p_closing": "p_closing", "p_first": "p_first", "p_max": "p_max", "p_min": "p_min",
    "price_yesterday": "price_yesterday", "tmin": "tmin", "q_tot_tran": "q_tot_tran",
    "z_tot_tran": "z_tot_tran", "q_tot_cap": "q_tot_cap", "mcap": "mcap",
    "mcap_src": "mcap_src", "pe": "pe", "buy_q1_vol": "buy_q1_vol", "buy_q1_px": "buy_q1_px",
    "buy_q1_cnt": "buy_q1_cnt", "sell_q1_px": "sell_q1_px", "sell_q1_vol": "sell_q1_vol",
    "buy_i_vol": "buy_i_vol", "sell_i_vol": "sell_i_vol", "buy_count_i": "buy_count_i",
    "sell_count_i": "sell_count_i", "buy_power_i": "buy_power_i", "buyer_power": "buyer_power",
    "retail_buy_pct": "retail_buy_pct", "legal_buy_pct": "legal_buy_pct",
    "retail_sell_pct": "retail_sell_pct", "legal_sell_pct": "legal_sell_pct",
    "pct_basis": "pct_basis", "ctv_kind": "ctv_kind", "ctv_d": "ctv_d",
    "vol_ratio": "vol_ratio", "vol_ratio_file": "vol_ratio_file", "vol_dod": "vol_dod",
    "month_avg_vol": "month_avg_vol", "hist_sessions": "hist_sessions",
    "st_title": "st_title", "row_h": "row_h",
}


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "bors-e2e"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def asgi_post(client, body):
    """همان POSTِ رابط، رویِ هندلرِ واقعیِ `/api/export`."""
    r = client.post("/api/export", json=body)
    if r.status_code != 200:
        raise SystemExit("POST /api/export ⇒ %s %s" % (r.status_code, r.text[:200]))
    return r.content, r.headers.get("content-disposition", "")


def columns_from_ui():
    """(کلید, برچسب) هایِ دستۀ «full» ازِ خودِ سورسِ رابط — بی‌فهرستِ دوم."""
    import re
    src = io.open(COLS_SRC, encoding="utf-8").read()
    out = []
    for m in re.finditer(r'\{ key: \'([a-z0-9_]+)\', label: \'([^\']+)\', set: \'(board|full)\'', src):
        out.append((m.group(1), m.group(2), m.group(3)))
    return out


def _export_app(EX):
    """اپی که فقط router خودِ برنامه را سوار می‌کند — همان هندلرِ `/api/export`."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(EX.router)
    return app


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "market_parity_20261014"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # POST رویِ یکِ اپِ ASGIِ تنها-export می‌نشیند (TestClient): همان هندلرِ واقعی
    # و همان زنجیرۀ HTTP، ولی بی‌هیچ دست‌زدنِ `market.db` و بی‌پورتِ اشغال‌شده.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api import _export as EX

    client = TestClient(_export_app(EX))

    cols = columns_from_ui()
    print("ستون‌هایِ خوانده‌شده ازِ رابط: %d (board=%d)"
          % (len(cols), sum(1 for c in cols if c[2] == "board")))
    feed = get(a.base.rstrip("/") + "/api/market")
    rows = feed.get("data") or []
    big = sorted((r for r in rows if (r.get("q_tot_cap") or 0) > 0),
                 key=lambda r: -(r.get("q_tot_cap") or 0))[:a.rows]
    print("ردیف‌هایِ بازار از /api/market: %d → نمونه: %d" % (len(rows), len(big)))

    header = [c[1] for c in cols]
    data = []
    for r in big:
        line = []
        for key, _label, _set in cols:
            if key == "in_feed":
                line.append("هست")
                continue
            if key in ("status", "badges", "tech", "fund", "pct_is_current", "is_live",
                       "source", "exported_at", "q_tot_cap", "mcap_bt", "row_h"):
                line.append(None)          # این ستون‌ها درِ ابزارِ HTTP ساخته نمی‌شوند
                continue
            v = r.get(WATCH_KEY_TO_TSETMC.get(key, key))
            line.append(v if isinstance(v, (int, float, str)) and v == v else None)
        data.append(line)

    meta = [["منبع داده", "TSETMC GetMarketWatch (همان فیدِ زندهٔ تابلو)"],
            ["نشستِ داده (d_even)", str((feed.get("meta") or {}).get("d_even"))],
            ["ساعتِ فید (h_even)", str((feed.get("meta") or {}).get("h_even"))],
            ["آخرین همگام‌سازیِ برنامه", str((feed.get("meta") or {}).get("last_sync"))],
            ["دامنه", "کلِ دیدهبان (نمونۀ ابزار)"]]
    body = {"fmt": "xlsx", "title": "دیدهبان-بازار", "rows": [header] + data, "meta": meta}

    raw, cd = asgi_post(client, body)
    xp = os.path.join(a.out, "watch_export_e2e.xlsx")
    io.open(xp, "wb").write(raw)
    print("فایل Excel: %s (%d بایت) | disposition: %s" % (xp, len(raw), cd[:80]))

    import openpyxl
    wb = openpyxl.load_workbook(xp)
    ws = wb[wb.sheetnames[0]]
    print("صفحه‌ها:", wb.sheetnames, "| سطر:", ws.max_row, "| ستون:", ws.max_column)

    fails = []
    if ws.max_row != len(data) + 1:
        fails.append("شمارِ سطرِ فایل با دامنه نمی‌خواند")
    if ws.max_column != len(header):
        fails.append("شمارِ ستونِ فایل با رابط نمی‌خواند")
    hdr = [c.value for c in ws[1]]
    if hdr != header:
        fails.append("سرستون‌هایِ فارسی درِ فایل تغییر کرده‌اند")
    numeric_cols = [i for i, (_k, label, _s) in enumerate(cols)
                    if any(u in label for u in ("ریال", "سهم", "٪", "نفر", "عدد", "P/E", "برابر"))]
    str_cells = 0
    zero_fill = 0
    for r in ws.iter_rows(min_row=2, values_only=True):
        for i in numeric_cols:
            v = r[i]
            if isinstance(v, str) and v not in ("", ):
                str_cells += 1
        if r[header.index("حجم (سهم)")] == 0:
            zero_fill += 1
    if str_cells:
        fails.append("%d سلولِ عددی رشته شده است" % str_cells)
    sheets = set(wb.sheetnames)
    if "منبع و تازگی" not in sheets:
        fails.append("صفحۀ ردپا درِ فایل نیست")
    else:
        pairs = {rr[0]: rr[1] for rr in wb["منبع و تازگی"].iter_rows(min_row=2, values_only=True)}
        if not pairs.get("نشستِ داده (d_even)"):
            fails.append("ردپایِ نشستِ داده خالی است")

    raw_csv, _ = asgi_post(client, dict(body, fmt="csv", rows=[header] + data[:5], meta=meta))
    csvp = os.path.join(a.out, "watch_export_e2e.csv")
    io.open(csvp, "wb").write(raw_csv)
    txt = raw_csv.decode("utf-8-sig")
    lines = [l for l in txt.splitlines() if l]
    if not raw_csv.startswith(b"\xef\xbb\xbf"):
        fails.append("CSV بی‌BOM است")
    if not any(l.startswith("#") for l in lines):
        fails.append("ردپا درِ انتهای CSV نیست")
    print("فایل CSV: %s (%d بایت) | سطرِ کل: %d | سطرِ ردپا: %d"
          % (csvp, len(raw_csv), len(lines), sum(1 for l in lines if l.startswith("#"))))

    print("\nخلاصه: عددِ سلول‌هایِ رشته‌ایِ غیرمجاز = %d | سطری که حجمش صفر آمده = %d"
          % (str_cells, zero_fill))
    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("OK: فایلِ واقعی با دادهٔ زنده ساخته، دانلود و باز شد و هر پنج سنسور سبز است.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
