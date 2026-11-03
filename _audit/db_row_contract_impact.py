#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/db_row_contract_impact.py — پیش ازِ وصل‌کردنِ `get_chart_db` به
`candle_contract.from_db_row`، باید دانست دقیقاً سرِ چه تعدادِ ردیف چه می‌آید.

سه پرسشِ عددی که مالک خواسته (بندِ «شمار ورودی و خروجی و علت هر اختلاف»):
  ۱) چند ردیف درِ بانک است و چندتا درِ هرِ نوشتارِ قدیم/جدید کندل می‌شوند؟
  ۲) هر ردیفِ حذف‌شده به کدامِ قاعدۀِ قرارداد می‌خورد (حجمِ صفر = روزِ بی‌معامله،
     پایانیِ صفر/نامعتبر، بی‌تاریخ) و آیا همان قاعده درِ مسیرِ CDN هم اجرا می‌شود؟
  ۳) درِ ردیف‌هایِ حفظ‌شده، کدامِ فیلد جابه‌جا می‌شود و چرا (سایه گِشاد می‌شود،
     openِ صفر از پایانیِ منتشرشده ساخته می‌شود) — و اینکه هیچ عددِ منتشرشده کُنده
     نمی‌شود.

این فایل فقط اندازه می‌گیرد؛ چیزی را عوض نمی‌کند.
"""
import collections
import io
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import candle_contract as CC   # noqa: E402


def main():
    con = sqlite3.connect(os.path.join(ROOT, "market.db"))
    con.row_factory = sqlite3.Row
    total = con.execute("select count(*) n from price_history").fetchone()["n"]
    symbols = con.execute("select count(distinct symbol) n from price_history").fetchone()["n"]

    rows = con.execute(
        "select symbol, date, open, high, low, close, volume, last, value, src "
        "from price_history order by symbol, date").fetchall()

    kinds = collections.Counter()
    moved = collections.Counter()
    examples = {}
    kept = 0
    for r in rows:
        raw = tuple(r[k] for k in CC.DB_COLUMNS)
        # نوشتارِ قدیم (سازندۀِ دستیِ get_chart_db): بدونِ هیچ فیلتری
        old = {"time": raw[1], "open": float(raw[2] or 0), "high": float(raw[3] or 0),
               "low": float(raw[4] or 0), "close": float(raw[5] or 0),
               "last": float(raw[7]) if raw[7] is not None else None,
               "value": float(raw[8]) if raw[8] is not None else None,
               "volume": float(raw[6] or 0)}
        new = CC.from_db_row(raw)
        if new is None:
            c = float(raw[5] or 0)
            v = float(raw[6] or 0)
            o = float(raw[2] or 0)
            if v <= 0:
                kinds["dropped:zero_volume(no-trade)"] += 1
                examples.setdefault("dropped:zero_volume(no-trade)", raw)
            elif c <= 0:
                kinds["dropped:non-positive_close"] += 1
                examples.setdefault("dropped:non-positive_close", raw)
            elif o <= 0:
                kinds["dropped:non-positive_open_and_close"] += 1
            elif not raw[1]:
                kinds["dropped:no_date"] += 1
            else:
                kinds["dropped:other"] += 1
                examples.setdefault("dropped:other", raw)
            continue
        kept += 1
        # چرا قدیم یکِ کندلِ ناممکن می‌ساخت و جدید نمی‌سازد
        bad_old = not (old["low"] <= min(old["open"], old["close"]) + 1e-9
                       and old["high"] >= max(old["open"], old["close"]) - 1e-9
                       and old["low"] <= old["high"] and old["high"] > 0
                       and old["low"] > 0 and old["open"] > 0)
        if bad_old:
            kinds["kept:old_geometry_impossible→repaired"] += 1
            examples.setdefault("kept:old_geometry_impossible→repaired", (raw, old, new))
        for f in ("open", "high", "low", "close", "volume", "last"):
            ov, nv = old.get(f), new.get(f)
            if ov is None or nv is None:
                if ov != nv:
                    moved[f + ":none-vs-value"] += 1
                continue
            if abs(float(ov) - float(nv)) > 1e-9:
                moved[f] += 1
                if f + "_ex" not in examples:
                    examples[f + "_ex"] = (raw, old, new)
        # کاهشِ قیمتِ منتشرشده؟ (ممنوع درِ قرارداد)
        for f in ("close", "high", "low"):
            if float(new[f]) < float(old[f]) - 1e-9:
                kinds["LOWERED:" + f] += 1

    print("rows total        : %s" % f"{total:,}")
    print("symbols           : %s" % f"{symbols:,}")
    print("kept as candles   : %s" % f"{kept:,}")
    print("\nclassification:")
    for k, n in kinds.most_common():
        print("  %-46s %s" % (k, f"{n:,}"))
    print("\nfields moved by the contract:")
    for k, n in moved.most_common():
        print("  %-24s %s" % (k, f"{n:,}"))
    print("\nنمونۀِ ردیف‌هایِ کلیدی:")
    for k in ("kept:old_geometry_impossible→repaired", "dropped:zero_volume(no-trade)",
              "open_ex", "high_ex", "low_ex"):
        ex = examples.get(k)
        if not ex:
            continue
        print("  ## " + k)
        if isinstance(ex, tuple) and len(ex) == 3:
            raw, old, new = ex
            print("     db row     :", raw)
            print("     old builder:", {f: old[f] for f in ("time", "open", "high", "low", "close", "volume", "last")})
            print("     contract   :", {f: new[f] for f in ("time", "open", "high", "low", "close", "volume", "last")})
        else:
            print("     db row     :", ex)

    # چند نماد متأثر است
    aff = set()
    for r in rows:
        raw = tuple(r[k] for k in CC.DB_COLUMNS)
        new = CC.from_db_row(raw)
        old_ok = (float(raw[3] or 0) > 0 and float(raw[4] or 0) > 0 and float(raw[2] or 0) > 0
                  and float(raw[6] or 0) > 0)
        if (new is None) != (not old_ok):
            aff.add(raw[0])
    print("\nsymbols whose served series changes: %s" % f"{len(aff):,}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
