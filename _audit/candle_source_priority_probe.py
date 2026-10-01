# -*- coding: utf-8 -*-
"""Step 4 — طبقه‌بندیِ علتِ واگرایی: تابلو در برابرِ CSVِ منتشرشده، نشست‌به‌نشست.

`_audit/candle_builder_divergence.py` رویِ سه نماد شمارد این را داد: از ۱٬۱۹۵ روزِ
مشترکِ «کندلِ RAMِ /api/chart» در برابرِ «کندلِ `/api/chart-db`»، در ۳۰۴ روز `open`،
۷۶ روز `high`، ۱۰۹ روز `low` و ۳ روز `close` فرق دارد. این یعنی دو نویسدۀ
`price_history` (مسیرِ ۱ = CSVِ روزانۀ منتشرشده، مسیرِ ۲ = snapshotِ تابلو) برایِ
**یکِ نشستِ یکسان** دو عددِ مختلف می‌نویسند و آخرینِ نویسنده برنده می‌شود — همان
خطری که inventory §۲-الف با «هیچ تستی مالکیتِ ترتیب را نگه نمی‌دارد» نامید.

این فایل علت را جدا می‌کند:
  ۱) رویِ نشست‌هایی که هر دو منبع دارند، differenceِ هر فیلد + جهتِ difference.
  ۲) آیا difference با «تابلو در لحظه‌ای از میانه/پیشِ بستُُنِ نهایی خوانده شده» توضیح
     داده می‌شود؟ (یعنی board snapshot ≠ published daily list برایِ همان روز)
  ۳) چند روز درِ `price_history` هست که درِ CSVِ منتشرشده **هیچ‌وقت** نبوده
     (کندلِ شبحِ مسیرِ ۲)، و چند روزِ CSV درِ بانک نیست (کندلِ جاافتاده).
خروجی: `_audit/candle_source_priority.json` — بی‌حدس؛ هر دسته با شمار و نمونه.
"""
import json
import os
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_tsetmc as T  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
SYMS = [("فولاد", "46348559193224090"), ("خگستر", "48990026850202503"),
        ("شبندر", "35366681030756042"), ("پارس", "6110133418282108")]
COLS = ("FIRST", "HIGH", "LOW", "CLOSE", "VOL", "LAST", "OPEN", "VALUE")


def csv_map(ins):
    u = f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/19900101"
    txt = urllib.request.urlopen(urllib.request.Request(u, headers=T.HEADERS),
                                 timeout=150).read().decode("utf-8", "replace")
    lines = [l for l in txt.splitlines() if l.strip()]
    head = [h.strip("<>") for h in lines[0].split(",")]
    ix = {k: i for i, k in enumerate(head)}
    out = {}
    for l in lines[1:]:
        p = [x.strip() for x in l.split(",")]
        if len(p) < len(head) or not p[ix["DTYYYYMMDD"]].isdigit():
            continue
        d = p[ix["DTYYYYMMDD"]]
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        try:
            out[iso] = {k: float(p[ix[k]]) for k in COLS if p[ix[k]]}
        except ValueError:
            continue
    return out


def main():
    out = {"symbols": {}, "totals": {}}
    keys = ("board_vs_csv_open", "board_vs_csv_high", "board_vs_csv_low",
            "board_vs_csv_close", "board_vs_csv_vol", "board_vs_csv_last_missing",
            "phantom_days_in_db", "csv_days_missing_from_db", "overlapped_sessions")
    tot = {k: 0 for k in keys}
    for name, ins in SYMS:
        csv = csv_map(ins)
        con = sqlite3.connect(Path(DB).as_uri() + "?mode=ro", uri=True, timeout=30)
        # نشست‌هایی که مسیرِ ۲ از تابلو ساخته است: daily_prices ∩ price_history
        board = {}
        for r in con.execute(
                "SELECT d.d_even, d.price_first, d.price_max, d.price_min, d.p_closing,"
                " d.q_tot_tran, d.p_last, d.q_tot_cap FROM daily_prices d"
                " JOIN instruments i ON i.ins_code = d.ins_code"
                " WHERE i.l_val18 = ? OR i.l_val30 = ?", (name, name)).fetchall():
            iso = T._iso_from_deven(r[0])
            if not iso:
                continue
            board[iso] = dict(zip(("first", "hi", "lo", "close", "vol", "p_last", "cap"), r[1:]))
        db = {r[0]: dict(zip(("o", "h", "l", "c", "v", "last"), r[1:]))
              for r in con.execute(
                  "SELECT date, open, high, low, close, volume, last FROM price_history"
                  " WHERE symbol=?", (name,)).fetchall()}
        con.close()
        both = sorted(set(board) & set(csv))
        s = {k: 0 for k in keys}
        s["overlapped_sessions"] = len(both)
        ex = []
        for d in both:
            b, c = board[d], csv[d]
            if (b["first"] or 0) > 0 and c.get("FIRST") and abs(b["first"] - c["FIRST"]) > 0.5:
                s["board_vs_csv_open"] += 1
                if len(ex) < 3:
                    ex.append({"day": d, "board_first": b["first"], "csv_FIRST": c["FIRST"],
                               "csv_CLOSE": c.get("CLOSE"), "board_close": b["close"],
                               "in_db": db.get(d, {}).get("o")})
            if (b["hi"] or 0) > 0 and c.get("HIGH") and abs(b["hi"] - c["HIGH"]) > 0.5:
                s["board_vs_csv_high"] += 1
            if (b["lo"] or 0) > 0 and c.get("LOW") and abs(b["lo"] - c["LOW"]) > 0.5:
                s["board_vs_csv_low"] += 1
            if (b["close"] or 0) > 0 and c.get("CLOSE") and abs(b["close"] - c["CLOSE"]) > 0.5:
                s["board_vs_csv_close"] += 1
            if (b["vol"] or 0) > 0 and c.get("VOL") and abs(b["vol"] - c["VOL"]) / c["VOL"] > 0.005:
                s["board_vs_csv_vol"] += 1
            if b.get("p_last") in (None, 0) and c.get("LAST"):
                s["board_vs_csv_last_missing"] += 1
        s["phantom_days_in_db"] = len([d for d in db if d not in csv])
        s["csv_days_missing_from_db"] = len([d for d in csv if d not in db])
        out["symbols"][name] = {**s, "examples": ex,
                                "db_rows": len(db), "csv_rows": len(csv),
                                "board_rows": len(board)}
        for k in keys:
            tot[k] += s[k]
        print(f"--- {name}: نشستِ مشترکِ تابلو/CSV = {s['overlapped_sessions']} | "
              f"open واگرایی {s['board_vs_csv_open']} | high {s['board_vs_csv_high']} | "
              f"low {s['board_vs_csv_low']} | close {s['board_vs_csv_close']} | "
              f"vol {s['board_vs_csv_vol']} | شبح‌DB {s['phantom_days_in_db']}")
        for e in ex:
            print("     ", json.dumps(e, ensure_ascii=False)[:170])
    out["totals"] = tot
    print("\nTOTALS:", json.dumps(tot, ensure_ascii=False))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "candle_source_priority.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("نوشته شد:", p)


if __name__ == "__main__":
    main()
