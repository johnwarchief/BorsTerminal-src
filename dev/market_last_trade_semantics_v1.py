# -*- coding: utf-8 -*-
"""dev/market_last_trade_semantics_v1.py — p_last فقط از LASTِ خام، نه استنتاج.

باگِ بازتولیدشده در ممیزیِ 2026-10-20: ردیفِ بی‌معاملهٔ بستهٔ بازار، LASTِ
معتبرِ `pdv` را با p_lastِ کهنهٔ بانک بازنویسی می‌کرد؛ ردیفِ بی‌LAST هم از
`py + pc` یک «آخرین» جعلی می‌ساخت. نتیجه: در 228 ردیف از 3,302 ردیفِ joined،
p_last با TSETMC فرق داشت و در چند نمونهٔ same-tick (مثلاً آسيا3، آپ3) اختلاف
از خودِ منبع نبود.

این گارد خالص است و به network/DB عملیاتی دست نمی‌زند.
اجرا: python dev/market_last_trade_semantics_v1.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import test_tsetmc as T  # noqa: E402

CHECKS = []
FAILS = []


def ck(label, cond, detail=""):
    CHECKS.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + label + (("  <- " + str(detail)) if not cond and detail else ""))
    if not cond:
        FAILS.append(label)


def row(**kw):
    base = {
        "insCode": "IRO1TEST0001", "lva": "آزمون", "lvc": "شرکت آزمون",
        "csv": "01", "dEven": 20261020, "hEven": 123001, "pcl": 100.0,
        "pdv": 95.0, "py": 98.0, "pf": 99.0, "pmn": 94.0, "pmx": 102.0,
        "pMin": 90.0, "pMax": 110.0, "qtj": 1000.0, "qtc": 100000.0,
        "ztt": 10.0, "pc": 2.0, "eps": 5.0, "pe": 10.0, "ztd": 1000.0,
        "bv": 50.0, "blDs": [],
    }
    base.update(kw)
    return base


def main():
    # ۱) LASTِ معتبرِ منبع بر مقدارِ کهنهٔ بانک مقدم است — حتی بسته/بی‌معامله.
    old = {"p_last": 4650.0}
    ck("source LAST wins over stale stored LAST",
       T._last_trade_price(row(pdv=4750.0, pcl=4750.0, qtj=0, qtc=0, ztt=0),
                           prev=old, closed=True, vol=0, val=0, trd=0, pcl=4750.0) == 4750.0)
    # ۲) صفرِ منبع + بسته/بی‌معامله: فقط آخرین LASTِ نشستِ پیشین، در بازهٔ معقول.
    ck("source zero + closed/no-trade preserves prior LAST",
       T._last_trade_price(row(pdv=0.0, pcl=4750.0, qtj=0, qtc=0, ztt=0),
                           prev=old, closed=True, vol=0, val=0, trd=0, pcl=4750.0) == 4650.0)
    # ۳) منبع غایب بیرونِ بازار بسته: هیچ عددی ساخته نمی‌شود.
    ck("source zero outside closed/no-trade -> null",
       T._last_trade_price(row(pdv=0.0, pcl=100.0), closed=False, pcl=100.0) is None)
    # ۴) ردیفِ بی‌معاملهٔ باز یا دارای حجم: LASTِ کهنه جایگزین نمی‌شود.
    ck("no source LAST with traded volume -> null",
       T._last_trade_price(row(pdv=0.0, pcl=100.0, qtj=10.0),
                           prev=old, closed=True, vol=10.0, val=1000.0, trd=1.0,
                           pcl=100.0) is None)
    # ۵) _mw_row باید همان قاعده را در tupleِ نوشتن اعمال کند.
    _i, w_zero, d_zero = T._mw_row(row(pdv=0.0, pcl=100.0, q_tot_cap=0.0), 0, 20261020,
                                   "2026-10-20 15:00:00")
    _i, w_last, d_last = T._mw_row(row(pdv=95.0), 0, 20261020, "2026-10-20 15:00:00")
    idx = T.MW_COLS.index("p_last")
    ck("_mw_row: zero source LAST is null (not pcl/py+pc)", w_zero[idx] is None, w_zero[idx])
    ck("_mw_row: valid source LAST is preserved", w_last[idx] == 95.0, w_last[idx])
    ck("_mw_row: daily_prices p_last follows the same rule",
       d_zero[14] is None and d_last[14] == 95.0, (d_zero[14], d_last[14]))
    # ۶) صفرِ معتبرِ منبع نباید با حجم/ارزش/شمارش/تغییرِ دیروز عوض شود.
    prev = {"q_tot_tran": 5000.0, "q_tot_cap": 50750000.0,
            "z_tot_tran": 1.0, "price_change": 170.0}
    ck("closed: source zero volume/value/trades/change stay zero",
       T._closed_values(0, 0, 0, 0, prev) == (0, 0, 0, 0))
    ck("closed: only a genuinely missing tuple is filled from prior session",
       T._closed_values(None, None, None, None, prev) == (5000.0, 50750000.0, 1.0, 170.0))
    ck("closed: a present but zero source value is not replaced",
       T._closed_values(0, 0, 0, -11910.0, prev) == (0, 0, 0, -11910.0))
    # ۷) هیچ مسیرِ تولیدی نباید دوباره فرمولِ استنتاجی را بسازد.
    import io
    src = io.open(os.path.join(ROOT, "test_tsetmc.py"), encoding="utf-8").read()
    ck("no py+pc derived LAST remains in production source", "py + chg" not in src)

    print("\n%d/%d passed" % (len(CHECKS) - len(FAILS), len(CHECKS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
