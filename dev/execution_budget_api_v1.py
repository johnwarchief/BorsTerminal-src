# -*- coding: utf-8 -*-
# dev/execution_budget_api_v1.py — گاردِ پیش‌نمایشِ بودجه درِ لایۀ API
#
# چرا monkeypatch و نه بانکِ واقعی: `market.db` درِ Git نیست و CI آن را ندارد؛
# گاردی که به نبودش بشکند، گاردِ داده است نه گاردِ منطق. پس تصمیم‌ها باِ ورودیِ
# کنترل‌شده سنجیده می‌شوند و فقط «ثبت‌شدنِ دروازه» ازِ خودِ router خوانده می‌شود.
#
# چهار حکمی که می‌پرسد:
#   بی‌قدرتِ خرید ⇒ plan UNKNOWN باِ دلیلِ روشن، و هیچ عددی ازِ خودِ برنامه.
#   بی‌قیمتِ صریح ⇒ مبنایِ قیمت سقفِ مجازِ *همان* نماد است (برایِ خرید) و این
#     مبنا درِ پاسخ نوشته می‌شود؛ قیمت حدس نمی‌شود.
#   نماد بی‌ردیف ⇒ blocker روشن، بی‌قیمت و بی‌تعداد.
#   پاسخ هیچ‌وقت خودش را «سفارش» یا «پاسخِ کارگزاری» جا نمی‌زند.

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


BAND_OK = {"present": True, "source": "market.db", "ins_code": "7740831252462823",
           "isin": "IRO1DRVN0001", "lot_size": 1.0, "d_even": 20261019,
           "p_last": 10770.0, "p_closing": 10690.0, "allowed_min": 10370.0,
           "allowed_max": 11010.0, "as_of": "2026-10-19 06:25:50"}


def main():
    print("execution_budget_api_v1 — تصمیم‌هایِ پیش‌نمایشِ بودجه")
    import api.execution as EX

    band_real, power_real = EX._instrument_band, EX._buying_power
    try:
        # ── بی‌قدرتِ خرید ──
        EX._instrument_band = lambda s: dict(BAND_OK)
        EX._buying_power = lambda: (None, "آداپتورِ فعلی هیچ خوانشِ حسابی ندارد")
        r = EX.budget_preview("داروند")
        ck(r["plan"]["status"] == "UNKNOWN" and r["plan"]["quantity"] is None,
           "بی‌قدرت خرید ⇒ تعداد هیچ‌جا ساخته نمی‌شود", r["plan"]["status"])
        ck(any("قدرت خرید" in b for b in r["blockers"]), "دلیلِ بلوکه درِ پاسخ است")
        ck(r["price"] == 11010 and r["price_basis"] == "allowed_max",
           "مبنایِ قیمت = سقفِ مجازِ همان نماد", str(r["price"]))
        ck(any("مبنایِ قیمت" in b for b in r["blockers"]), "خودِ مبنا هم نوشته می‌شود")
        ck(r["instrument"]["resolved"] is True and r["instrument"]["isin"] == "IRO1DRVN0001",
           "هویتِ نماد با ISIN ازِ بانکِ محلی تأیید می‌شود")
        ck(r["is_order"] is False and r["from_broker"] is False and r["plan"]["is_order"] is False,
           "پاسخ هیچ‌جا خودش را سفارش یا پاسخِ کارگزاری جا نمی‌زند")

        # ── باِ قدرت خریدِ واقعی ──
        EX._buying_power = lambda: (50_000_000, "broker:account")
        r2 = EX.budget_preview("داروند")
        ck(r2["plan"]["status"] == "OK", "باِ قدرت خرید ⇒ محاسبه انجام می‌شود",
           r2["plan"]["status"])
        # 50_000_000 / 11_010 = 4541.3 -> 4541 سهم (4542 از پول رد می‌شود)
        ck(r2["plan"]["quantity"] == 4541, "تعداد از 50,000,000 / 11,010",
           str(r2["plan"]["quantity"]))
        ck(r2["plan"]["total_rial"] <= 50_000_000, "ازِ قدرت خرید رد نمی‌شود",
           str(r2["plan"]["total_rial"]))
        ck(r2["plan"]["caps_verified"] is False,
           "سقفِ تعدادِ کارگزاری نرسیده ⇒ مجازبودن تأیید‌نشده می‌ماند")

        # ── قیمتِ صریحِ کاربر ──
        r3 = EX.budget_preview("داروند", price="10800")
        ck(r3["price"] == 10800 and r3["price_basis"] == "explicit",
           "قیمتِ صریحِ کاربر بر مبنایِ پیش‌فرض مقدم است")
        r4 = EX.budget_preview("داروند", price="abc")
        ck(r4["price"] is None and any("عدد نیست" in b for b in r4["blockers"]),
           "قیمتِ بی‌اعتبار ⇒ هیچ محاسبه‌ای باِ آن انجام نمی‌شود")

        # ── نماد بی‌ردیف ──
        EX._instrument_band = lambda s: {"present": False, "source": "market.db",
                                         "error": "ردیفی برای این نماد در تابلو نیست"}
        r5 = EX.budget_preview("نیست۰۱")
        ck(r5["price"] is None and r5["instrument"]["resolved"] is False,
           "نماد بی‌ردیف ⇒ بی‌قیمت، بی‌ISIN")
        ck(any("تابلو" in b for b in r5["blockers"]), "علتش درِ پاسخ نوشته می‌شود")

        # ── فروش روی کفِ مجاز ──
        EX._instrument_band = lambda s: dict(BAND_OK)
        r6 = EX.budget_preview("داروند", side="sell")
        ck(r6["price"] == 10370 and r6["price_basis"] == "allowed_min",
           "فروش ⇒ کفِ مجاز، نه سقف", str(r6["price"]))
    finally:
        EX._instrument_band, EX._buying_power = band_real, power_real

    # ── دروازه ثبت شده؟ (ازِ خودِ router، نه ازِ متنِ فایل) ──
    paths = set()
    stack = [EX.router]
    while stack:
        rt = stack.pop()
        for route in getattr(rt, "routes", []):
            p = getattr(route, "path", None)
            if p:
                paths.add(p)
        if getattr(rt, "original_router", None) is not None:
            stack.append(rt.original_router)
    ck("/api/execution/budget" in paths, "دروازۀ /api/execution/budget درِ router هست")

    # ── کنترلِ منفی: اگر UNKNOWNِ قدرت خرید حذف شود، سنجشِ اول قرمز می‌شود ──
    src = open(os.path.join(ROOT, "api", "execution.py"), encoding="utf-8").read()
    ck('blockers.append("قدرت خرید ازِ کارگزاری نرسیده' in src,
       "دلیلِ بلوکه درِ کد نوشته شده (سنسورِ متنِ پاسخ کور نیست)")

    print(f"\nexecution_budget_api_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
