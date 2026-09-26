"""چرا بعضی ردیف‌ها با شیتِ ثبت‌شده در کدال تطبیق نمی‌شوند؟ (CARDS-10)

dev/fund_live_audit.py نشان داد ۶ بررسی در ۵ نماد، عددِ ذخیره‌شده را در هیچ
سلولی از «صورت سود و زیان»ِ همان نشانی پیدا نمی‌کند — و همه روی ردیف‌های
«تلفیقی» هستند. این اسکریپت همان عدد را در **همهٔ شیت‌های همان اطلاعیه** و
در **اطلاعیهٔ غیرتلفیقیِ همان دوره** می‌جوید تا معلوم شود مقصر «نشانی» است
یا «عدد».

فقط خواندنی: هیچ نوشتن روی دیتابیس و هیچ ADB ندارد.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time

import requests

sys.path.insert(0, ".")
from dev.fund_live_audit import (abs_url, cells_of, find_row, get,  # noqa: E402
                                 sheet_ids)

SYMS = sys.argv[1:] or ["تیپیکو", "پکرمان", "مبین", "دعبید", "وسدید"]


def main():
    con = sqlite3.connect("market.db")
    for sym in SYMS:
        rows = con.execute(
            "select period_end, url, revenue, net_profit, title, is_consolidated, "
            "has_operating_sales, unit_norm "
            "from financial_statements where symbol=? "
            "order by period_end desc limit 4", (sym,)).fetchall()
        print(f"\n===== {sym}")
        for period_end, url, revenue, net_profit, title, cons, has_sales, unit_norm in rows:
            if not url:
                print(f"  {period_end}: بی‌نشانی")
                continue
            try:
                page = get(abs_url(url))
            except Exception as exc:
                print(f"  {period_end}: منبع خوانده نشد {type(exc).__name__}")
                continue
            sheets = sheet_ids(page)
            hits_any = []
            for sid, label in sheets:
                try:
                    grid, _u = cells_of(get(abs_url(url) + "&sheetId=" + str(sid)))
                except Exception:
                    continue
                for tag, val in (("فروش", revenue), ("خالص", net_profit)):
                    if val:
                        h = find_row(grid, float(val))
                        if h:
                            hits_any.append((tag, label, h[0][2]))
                time.sleep(0.4)
            print(f"  {period_end} cons={cons} «{(title or '')[:34]}» "
                  f"→ شیت‌ها={len(sheets)} "
                  + ("یافت شد در: " + "; ".join(f"{t}←{l}({k})" for t, l, k in hits_any[:4])
                     if hits_any else "در هیچ شیتی از این اطلاعیه نیست"))
            time.sleep(1.2)
    con.close()


if __name__ == "__main__":
    main()
