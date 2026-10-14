# -*- coding: utf-8 -*-
"""phase5f_coverage_union.py — سنجشِ قدمِ ۵: «اتحادِ» منبعِ رویداد قبلِ نوشتنِ قاعدۀِ زنجیرۀِ جدید.

چرا این سنجش لازم است: اتصالِ موتورِ تعدیل به مسیرِ چارت یک تصمیمِ عددی دارد —
آیا ردیفِ دفترِ مبدأ که CSV هیچ گسستی درِ آن روز ندیده، هم ضریب می‌شود یا فقط
ردیف‌هایی که کشفِ CSV آن‌ها را دیده؟ «بله» یعنی افزودنِ گام‌هایی که سریِ قیمتِ
منتشرشده آن‌ها را نشان نمی‌دهد؛ «نه» یعنی اگر کاشفِ CSV رویدادی را از دست بدهد،
همان رویداد هرگز تعدیل نمی‌شود. حدس نمی‌زنیم: هر دو عدد را درِ بانکِ واقعی می‌شماریم.

دو مجموعه درِ همین بانکِ عملیاتی (فقط خواندنی) مقایسه می‌شوند:
  • `adjust_events` — رویدادهایِ کشف‌شده از گسستِ CSV، یک‌بارکشف‌شده برایِ همان نماد
  • `corporate_ledger.build_typed_events` — ردیف‌هایِ رسمیِ price/shareChange با
    اعتبارسنجیِ خودِ موتور (`AE.event_factor`)

خروجی: تفکیکِ «ردیفِ مبدأِ همتادار / بی‌همتا / ردشدۀِ موتور» و «رویدادِ CSVِ
بی‌همتا»، به‌علاوهٔ اثرِ ترکیبیِ بی‌همتاها بر فاکتورِ قدیمی‌ترین کندل (عددِ «چقدر
چارت عوض می‌شد»). هیچ داده‌ای نوشته نمی‌شود.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import pathlib
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import adjustment_engine as AE    # noqa: E402
import api.chart as CH            # noqa: E402  (کران‌ها از خودِ مسیرِ تولید، نه کپیِ عدد)
import corporate_ledger as CL     # noqa: E402

TARGETS = os.path.join(ROOT, "_audit", "ra365_phase5f_targets.json")
OUT = os.path.join(ROOT, "_audit", "RA365-PHASE5F-UNION.csv")
DB = os.path.join(ROOT, "market.db")
WINDOW, TOL = CH._LEDGER_WINDOW_DAYS, CH._LEDGER_AGREE_TOL


def _day(s):
    return dt.date(*[int(x) for x in str(s)[:10].split("-")])


def _gap(a, b):
    return abs((_day(a) - _day(b)).days)


def _agree(r_ledger, r_csv):
    return r_csv > 0 and abs(r_ledger / r_csv - 1.0) <= TOL


def main():
    d = json.load(io.open(TARGETS, encoding="utf-8"))
    conn = sqlite3.connect(pathlib.Path(DB).as_uri() + "?mode=ro", uri=True, timeout=30)
    out, tot = [], {}
    K = ("official_total", "official_ok", "official_rejected", "matched", "unmatched",
         "csv_only", "symbols_no_cache", "symbols_no_ledger")
    for k in K:
        tot[k] = 0
    unmatched_prod_worst = (1.0, "")   # حاصل‌ضربِ بی‌همتاها: هرچه از ۱ دورتر، اثرِ بیشتر
    for t in d["symbols"]:
        ins, sym = str(t["ins_code"]), t["symbol"]
        events, _meta = CL.build_typed_events(conn, ins)
        try:
            disc = [(str(r[0])[:10], float(r[1])) for r in conn.execute(
                "SELECT date, ratio FROM adjust_events WHERE symbol=? ORDER BY date", (sym,))]
        except sqlite3.OperationalError:
            disc = []
        ok, rejected, matched, unmatched, unprod = [], 0, 0, [], 1.0
        for ev in events:
            r, status = AE.event_factor(ev)
            if status != AE.OK or r is None:
                rejected += 1
                continue
            hit = [d0 for d0, dr in disc if _gap(d0, ev["date"]) <= WINDOW and _agree(r, dr)]
            ok.append(ev)
            if hit:
                matched += 1
            else:
                unmatched.append((ev["date"], r))
                unprod *= r
        # رویدادهایِ CSV که هیچ ردیفِ مبدأِ معتبرِ همتا ندارند (کشفِ بی‌شاهدِ مبدأ).
        # همان آزمونِ سازۀِ `_sharpen_events_with_ledger` است، فقط برعکسِ جهت.
        csv_only = 0
        for d0, dr in disc:
            if not any(_gap(ev["date"], d0) <= WINDOW and _agree(float(ev["ratio"]), dr)
                       for ev in ok):
                csv_only += 1
        tot["official_total"] += len(events)
        tot["official_ok"] += len(ok)
        tot["official_rejected"] += rejected
        tot["matched"] += matched
        tot["unmatched"] += len(unmatched)
        tot["csv_only"] += csv_only
        if not disc:
            tot["symbols_no_cache"] += 1
        if not events:
            tot["symbols_no_ledger"] += 1
        if unmatched and abs(1.0 - unprod) > abs(1.0 - unmatched_prod_worst[0]):
            unmatched_prod_worst = (unprod, sym)
        out.append({"symbol": sym, "ins_code": ins,
                    "official_rows": len(events), "official_ok": len(ok),
                    "official_rejected": rejected, "matched_to_csv": matched,
                    "unmatched_official": len(unmatched),
                    "unmatched_dates": "|".join(x[0] for x in unmatched)[:120],
                    "unmatched_product": round(unprod, 8),
                    "csv_only_events": csv_only, "csv_events": len(disc)})
    conn.close()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        for r in out:
            w.writerow(r)

    print("نماد:", len(out))
    for k in K:
        print(f"  {k:22s} = {tot[k]}")
    print("بدترینِ اثرِ ترکیبیِ ردیف‌هایِ بی‌همتا: {0:.6f} درِ {1}".format(*unmatched_prod_worst))
    print("کران‌هایِ خوانده‌شده از api.chart: window={0} روز، tol={1}".format(WINDOW, TOL))
    print("CSV:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
