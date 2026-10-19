#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/unresolved_events_probe.py — سه پلۀِ حل‌نشده ازِ نو، با شاهدِ بانکِ محلی

پیش ازِ این وضعشان UNRESOLVED ثبت شده بود (docs/technical-indicators/reviewed/
ENGINE-1-CLOSURE-1405-07-27.md §۳). این فایل چیزی را ثابت یا رد نمی‌کند؛ فقط
همۀِ ردپایِ موجود درِ بانکِ همین دور را برایِ همانِ سه رویداد بیرون می‌ریزد:

  ۱) ردیف‌هایِ price_history اطرافِ تاریخ (چیزیِ که کاشفِ گسستِ پایه می‌بیند)
  ۲) ردیف‌هایِ price_adjust_events / adjust_events / share_change_events همان نماد
  ۳) اطلاعیه‌هایِ کدالِ همان نماد درِ پنجرۀِ تاریخ (عنوان + تاریخِ انتشار)
  ۴) عددِ مرجع ازِ ADJUSTED-FACTOR-STEPS.csv درِ برابرِ ضریبِ انباشتۀِ خودی

هیچ ضریبِ حدسی ساخته یا وارد نمی‌شود. اگر ردیفِ رسمیِ مبدأ وجود ندارد، همان
«نیست» گزارش می‌شود.
اجرا: python _audit/unresolved_events_probe.py
"""
import csv
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

EVENTS = [
    ("فولاژ", "2024-07-27", 1.25035162),
    ("لخزر", "2026-07-27", 1.20979021),
    ("ولراز", "2024-01-30", 18.90578708),
]
STEPS = os.path.join(ROOT, "_audit", "ADJUSTED-FACTOR-STEPS.csv")
OUT = os.path.join(ROOT, "_audit", "UNRESOLVED-EVENTS-PROBE.json")


def win(date, days):
    import datetime as dt
    d = dt.date.fromisoformat(date)
    return ((d - dt.timedelta(days=days)).isoformat(), (d + dt.timedelta(days=days)).isoformat())


def main():
    con = sqlite3.connect(os.path.join(ROOT, "market.db"))
    con.row_factory = sqlite3.Row

    steps = {}
    with io.open(STEPS, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            steps[(r["symbol"].strip(), r["date"].strip())] = r

    out = {"ranAt": "2026-10-19", "events": []}
    for sym, date, ref_ratio in EVENTS:
        lo, hi = win(date, 45)
        e = {"symbol": sym, "date": date, "reference_step_ratio": ref_ratio,
             "steps_csv_row": steps.get((sym, date)),
             "ins_code": None, "price_history_window": [], "price_adjust_events": [],
             "adjust_events": [], "share_change_events": [], "codal_notices": [],
             "codal_extracted": []}
        ins = con.execute("select ins_code, l_val18 from instruments where l_val18 = ? or l_val30 = ?",
                          (sym, sym)).fetchall()
        e["ins_code"] = [dict(r) for r in ins]
        codes = [r["ins_code"] for r in ins]

        e["price_history_window"] = [dict(r) for r in con.execute(
            "select symbol, date, open, high, low, close, volume, last, value, src "
            "from price_history where symbol = ? and date between ? and ? order by date",
            (sym, lo, hi))]
        # همانِ پنجره، اما فقط روزهایِ نزدیکِ رویداد (چیزیِ که قاعدۀِ گسستِ پایه می‌خواند)
        e["price_history_close_to_event"] = [dict(r) for r in con.execute(
            "select symbol, date, open, high, low, close, volume, last, value, src "
            "from price_history where symbol = ? and date between ? and ? order by date",
            (sym, win(date, 7)[0], win(date, 7)[1]))]

        if codes:
            q = ",".join("?" * len(codes))
            e["price_adjust_events"] = [dict(r) for r in con.execute(
                "select ins_code, d_even, symbol, p_closing, p_closing_not_adjusted, "
                "corporate_type_code, ratio, source from price_adjust_events "
                "where ins_code in (%s) order by d_even" % q, codes)]
            e["share_change_events"] = [dict(r) for r in con.execute(
                "select ins_code, d_even, symbol, shares_old, shares_new, ratio, source "
                "from share_change_events where ins_code in (%s) order by d_even" % q, codes)]
        e["adjust_events"] = [dict(r) for r in con.execute(
            "select symbol, date, ratio, source from adjust_events where symbol = ? order by date",
            (sym,))]
        e["codal_notices"] = [dict(r) for r in con.execute(
            "select tracing_no, symbol, company_name, title, letter_code, publish_date, sent_date "
            "from codal_notices where symbol = ? and (publish_date like ? or sent_date like ?) "
            "order by publish_date", (sym, date[:4] + "%", date[:4] + "%"))]
        try:
            e["codal_extracted"] = [dict(r) for r in con.execute(
                "select * from codal_extracted where symbol = ? limit 40", (sym,))]
        except sqlite3.Error as ex:
            e["codal_extracted"] = {"error": str(ex)}

        counts = {k: (len(v) if isinstance(v, list) else v)
                  for k, v in e.items() if k not in ("symbol", "date", "reference_step_ratio",
                                                     "steps_csv_row", "price_history_window",
                                                     "price_history_close_to_event")}
        print("%s %s  ref_ratio=%s" % (sym, date, ref_ratio))
        print("   price_history in 45d window : %d" % len(e["price_history_window"]))
        print("   price_history +/-7d         : %d" % len(e["price_history_close_to_event"]))
        for k in ("price_adjust_events", "adjust_events", "share_change_events",
                  "codal_notices", "codal_extracted"):
            v = e[k]
            print("   %-20s: %s" % (k, len(v) if isinstance(v, list) else v))
        print("   adjust_events rows for this symbol: %s"
              % json.dumps(e["adjust_events"], ensure_ascii=False)[:300])
        print("   steps CSV: %s" % json.dumps(e["steps_csv_row"], ensure_ascii=False))
        print("")
        out["events"].append(e)

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("out: " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
