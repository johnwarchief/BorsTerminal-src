#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/fts_refresh_plan.py — برنامه‌ریزِ افزایشیِ تازه‌سازی ۵ شاخص FTS.

چه‌کاری می‌کند (بدون شبکه؛ فقط دیتابیس):
  برای هر نمادِ تابلوی بازار تصمیم می‌گیرد «آیا باید داده‌اش تازه شود؟» و با چه مودی:

    NEW            نماد در هیچ‌کدام از جداول FTS نیست ⇒ full  (سالانه + ماهانه)
    NEED_ANNUAL    ماهانه دارد ولی صورتِ سالانه ندارد     ⇒ full
    STALE_MONTHLY  آخرین گزارش ماهانه‌اش عقب‌تر از آخرین ماهِ بازار است ⇒ monthly
    STALE_ANNUAL   آخرین صورتِ سالانه‌اش قدیمی‌تر از سالِ جاریِ مالی است ⇒ full
    OK             تازه است ⇒ هیچ

خروجی: یک «برنامه» (JSON + خلاصهٔ انسانی) با فهرستِ نمادها، دلیل، و مودِ پیشنهادی؛
همراه با فرمانِ آمادهٔ اجرای `dev/codal_fts_updater.py` (که خودش `--adb-rotate` و
تأییدِ «IP عوض شد» و resume را دارد).

چرا لازم است: به‌جای واکشیِ کلِ بازار (که کدال را زود 429/بن می‌کند)، فقط
«دِلتا» (نماد جدید + کهنه‌ها) واکشی می‌شود؛ این هم سریع‌تر است و هم نرخِ درخواست را
پایین نگه می‌دارد.

اجرا:
  python dev/fts_refresh_plan.py                 # روی market.db
  python dev/fts_refresh_plan.py --out plan.json # ذخیرهٔ برنامه
  python dev/fts_refresh_plan.py --selftest      # تست آفلاینِ in-memory
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _norm(s: str) -> str:
    return str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()


def build_plan(conn: sqlite3.Connection) -> dict:
    """برنامهٔ افزایشی را از دیتابیس می‌سازد (بدون شبکه)."""
    # آخرین ماهِ گزارش‌شده در کل بازار (تقریبِ «ماه جاری»)
    row = conn.execute(
        "SELECT MAX(year * 12 + month) FROM monthly_sales WHERE ytd_revenue > 0").fetchone()
    latest_month = int(row[0] or 0)
    # آخرین سالِ مالیِ موجود
    row = conn.execute(
        "SELECT MAX(substr(period_end,1,4)) FROM financial_statements "
        "WHERE period_months >= 12").fetchone()
    latest_fy = int(row[0] or 0)

    fs_syms, ann_year = set(), {}
    for sym, pe in conn.execute(
            "SELECT symbol, period_end FROM financial_statements WHERE period_months >= 12"):
        k = _norm(sym)
        fs_syms.add(k)
        y = int(str(pe or "")[:4] or 0)
        if y > ann_year.get(k, 0):
            ann_year[k] = y

    ms_month = {}
    for sym, y, mo in conn.execute(
            "SELECT symbol, year, month FROM monthly_sales WHERE ytd_revenue > 0"):
        k = _norm(sym)
        v = int(y or 0) * 12 + int(mo or 0)
        if v > ms_month.get(k, 0):
            ms_month[k] = v

    items = []
    for (l18,) in conn.execute(
            "SELECT l_val18 FROM instruments WHERE l_val18 IS NOT NULL AND l_val18 <> ''"):
        k = _norm(l18)
        if not k:
            continue
        has_fs = k in fs_syms
        lm = ms_month.get(k, 0)
        if not has_fs and lm == 0:
            items.append({"symbol": l18, "action": "NEW", "mode": "full"})
        elif not has_fs:
            items.append({"symbol": l18, "action": "NEED_ANNUAL", "mode": "full"})
        elif lm < latest_month:
            items.append({"symbol": l18, "action": "STALE_MONTHLY", "mode": "monthly",
                          "last_month": lm, "market_month": latest_month})
        elif ann_year.get(k, 0) < latest_fy:
            items.append({"symbol": l18, "action": "STALE_ANNUAL", "mode": "full",
                          "last_fy": ann_year.get(k, 0), "market_fy": latest_fy})

    by_action = {}
    for it in items:
        by_action[it["action"]] = by_action.get(it["action"], 0) + 1
    by_mode = {}
    for it in items:
        by_mode[it["mode"]] = by_mode.get(it["mode"], 0) + 1

    monthly = [it["symbol"] for it in items if it["mode"] == "monthly"]
    full = [it["symbol"] for it in items if it["mode"] == "full"]
    return {
        "latest_month": latest_month,
        "latest_fy": latest_fy,
        "counts": {"total_todo": len(items), "by_action": by_action, "by_mode": by_mode},
        "monthly_symbols": monthly,
        "full_symbols": full,
        "items": items,
        "commands": {
            "monthly": ("python dev/codal_fts_updater.py --mode monthly --adb-rotate "
                        + ("--symbols " + ",".join(monthly[:200]) if monthly else "")),
            "full": ("python dev/codal_fts_updater.py --mode full --adb-rotate "
                     + ("--symbols " + ",".join(full[:200]) if full else "")),
        },
    }


def _selftest() -> int:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE instruments(l_val18 TEXT, ins_code INTEGER PRIMARY KEY, sector_name TEXT,
                                 total_shares REAL, updated_at TEXT);
        CREATE TABLE market_watch(ins_code INTEGER PRIMARY KEY, d_even INTEGER, p_closing REAL);
        CREATE TABLE financial_statements(symbol TEXT, period_end TEXT, period_months INTEGER,
                                 title TEXT, revenue REAL, gross_profit REAL, net_profit REAL,
                                 basic_eps REAL, capital REAL, total_equity REAL, publish_date TEXT);
        CREATE TABLE monthly_sales(symbol TEXT, year INTEGER, month INTEGER, monthly_revenue REAL,
                                 ytd_revenue REAL, ytd_revenue_prev REAL);
    """)
    for i, s in enumerate(["فولاد", "شپنا", "خساپا", "نمادجدید", "قدیمی"], 1):
        conn.execute("INSERT INTO instruments(l_val18,ins_code) VALUES(?,?)", (s, i))
    # فولاد: کامل و تازه (ماه 1403/12=... استفاده از همت؟ از سال/ماه میلادی استفاده می‌کنیم)
    conn.execute("INSERT INTO monthly_sales VALUES('فولاد',2026,8,10,100,90)")
    conn.execute("INSERT INTO financial_statements(symbol,period_end,period_months) VALUES('فولاد','2026-03-20',12)")
    conn.execute("INSERT INTO monthly_sales VALUES('شپنا',2026,7,10,100,90)")            # کهنه‌ماهانه
    conn.execute("INSERT INTO financial_statements(symbol,period_end,period_months) VALUES('شپنا','2026-03-20',12)")
    conn.execute("INSERT INTO monthly_sales VALUES('خساپا',2026,8,10,100,90)")           # بدونِ سالانه
    conn.execute("INSERT INTO monthly_sales VALUES('قدیمی',2026,8,10,100,90)")           # سالانهٔ قدیمی
    conn.execute("INSERT INTO financial_statements(symbol,period_end,period_months) VALUES('قدیمی','2022-03-20',12)")
    plan = build_plan(conn)
    got = {it["symbol"]: it["action"] for it in plan["items"]}
    expect = {"نمادجدید": "NEW", "خساپا": "NEED_ANNUAL", "شپنا": "STALE_MONTHLY", "قدیمی": "STALE_ANNUAL"}
    ok = all(got.get(k) == v for k, v in expect.items()) and "فولاد" not in got
    print("[selftest] classified:", got)
    print("[selftest] %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="FTS incremental refresh planner (offline)")
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if not os.path.isfile(a.db):
        print("[refresh-plan] «بدون داده»: %s نیست." % a.db)
        return 2
    conn = sqlite3.connect(a.db)
    plan = build_plan(conn)
    conn.close()
    print("latest month=%s  latest FY=%s  todo=%d" %
          (plan["latest_month"], plan["latest_fy"], plan["counts"]["total_todo"]))
    print("by action:", plan["counts"]["by_action"])
    for it in plan["items"][:20]:
        print("  -", it["symbol"], it["action"], "->", it["mode"])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print("saved:", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
