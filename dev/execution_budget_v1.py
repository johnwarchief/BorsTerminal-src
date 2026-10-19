# -*- coding: utf-8 -*-
# dev/execution_budget_v1.py — گاردِ «حداکثرِ قابل‌سفارش» (بی‌تخمینِ پول)
#
# چهار حکمی که نگهبانش است:
#   بی‌قدرتِ خریدِ واقعی ⇒ UNKNOWN، و هیچ تعدادی ساخته نمی‌شود.
#   بی‌سقفِ تعداد ازِ کارگزاری ⇒ LIMITS_UNKNOWN (نه «مجاز» و نه «رد»).
#   هیچ حالتِ OK بیشتر ازِ پولِ داده‌شده نمی‌رود (جاروبِ اعداد).
#   کنترلِ منفی: اگر UNKNOWNِ پول را باِ «پولِ ساختگی» عوض کنیم، سنجه‌ها باید
#   قرمز شوند — ثابت می‌کند سنسور کور نیست.

import os
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_budget as EB  # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


def main():
    print("execution_budget_v1 — حسابتِ قدرت خرید، بی‌حدس")

    # ── بی‌پولِ واقعی هیچ تعدادی ساخته نمی‌شود ──
    r = EB.max_affordable(None, 12340)
    ck(r.status == EB.UNKNOWN and r.quantity == 0, "قدرت خرید نرسیده ⇒ UNKNOWN")
    d = r.as_dict()
    ck(d["quantity"] is None and d["from_broker"] is False and d["is_order"] is False,
       "پاسخِ UNKNOWN نه تعداد می‌دهد نه ادعایِ کارگزاری")
    ck(EB.plan_from_status({}, 12340).status == EB.UNKNOWN,
       "پاسخِ سرویس بی‌account ⇒ همان UNKNOWN")
    ck(EB.plan_from_status(None, 12340).status == EB.UNKNOWN,
       "هیچ پاسخی نیامده ⇒ همان UNKNOWN")

    # ── ورودیِ نامعتبر ──
    ck(EB.max_affordable(10_000_000, None).status == EB.NOT_POSITIVE, "بی‌قیمت ⇒ رد")
    ck(EB.max_affordable(10_000_000, 0).status == EB.NOT_POSITIVE, "قیمت صفر ⇒ رد")
    ck(EB.max_affordable(10_000_000, "-12").status == EB.NOT_POSITIVE, "قیمت منفی ⇒ رد")
    ck(EB.max_affordable(0, 12340, max_qty=10 ** 9).status == EB.NOT_POSITIVE,
       "قدرت خرید صفر ⇒ رد، نه «یک سهم»")
    ck(EB.max_affordable("abc", 12340).status == EB.UNKNOWN, "پولِ غیرعددی ⇒ UNKNOWN")
    ck(EB.max_affordable(10_000_000, 12340, fee_rate=0.9,
                         max_qty=10 ** 9).status == EB.NOT_POSITIVE,
       "کارمزدِ نامعقول ⇒ رد")

    # ── سقف/گامِ ناشناخته ⇒ ادعا نمی‌شود ──
    r2 = EB.max_affordable(10_000_000, 12340, fee_rate=Decimal("0.0012"))
    ck(r2.status == EB.OK and r2.caps_verified is False,
       "بی‌سقفِ تعداد ⇒ تعداد حساب می‌شود ولی مجازبودنش تأیید نشده", r2.status)
    ck(any("سقف" in a for a in r2.assumptions), "فقدانِ سقفِ کارگزاری درِ فرضها نوشته می‌شود")
    ck(r2.as_dict()["caps_verified"] is False, "پرچمِ caps_verified درِ پاسخ هم هست")

    # ── حالتِ کامل: حسابِ درست و هیچ‌گاه بیشتر ازِ پول ──
    # 10_000_000 / (12_340 * 1.0012) = 809.4 -> 809 سهم
    # gross 9_983_060 + fee 11_979 = 9_995_039 -> مانده 4_961
    full = EB.max_affordable(10_000_000, 12340, fee_rate=Decimal("0.0012"),
                             lot_size=1, max_qty=10 ** 9)
    ck(full.status == EB.OK, "حالتِ کامل ⇒ OK", full.status)
    ck(full.quantity == 809, "تعداد ازِ قدرت خرید درست درمی‌آید", str(full.quantity))
    ck(full.gross_rial == 9_983_060, "ناخالص درست", str(full.gross_rial))
    ck(full.fee_rial == 11_979, "کارمزد درست (گرد به پایین)", str(full.fee_rial))
    ck(full.total_rial == 9_995_039, "مبلغِ کل درست", str(full.total_rial))
    ck(full.remaining_rial == 4_961, "مانده درست", str(full.remaining_rial))
    ck(full.total_rial <= 10_000_000, "هرگز بیشتر ازِ قدرت خرید نمی‌رود")
    ck(any("کارمزد" in a for a in EB.max_affordable(
        10_000_000, 12340, lot_size=1, max_qty=10 ** 9).assumptions),
       "بی‌کارمزدِ اعلام‌شده، فرضش درِ پاسخ نوشته می‌شود")

    # ── سقفِ کارگزاری و سهمیه ──
    capped = EB.max_affordable(10_000_000, 12340, fee_rate=Decimal("0.0012"),
                               lot_size=1, max_qty=500)
    ck(capped.status == EB.OK and capped.quantity == 500,
       "سقفِ تعداد جایِ قدرت خرید را می‌گیرد", str(capped.quantity))
    ck(any("سقف" in a for a in capped.assumptions), "علتِ محدودشدن نوشته می‌شود")
    lot = EB.max_affordable(10_000_000, 12340, fee_rate=Decimal("0.0012"),
                            lot_size=10, max_qty=10 ** 9)
    ck(lot.quantity % 10 == 0 and lot.quantity == 800, "سهمیۀ ۱۰ ⇒ مضربِ ۱۰",
       str(lot.quantity))
    tiny = EB.max_affordable(5000, 12340, fee_rate=Decimal("0.0012"), lot_size=1,
                             max_qty=10 ** 9)
    ck(tiny.status == EB.UNKNOWN and tiny.quantity == 0,
       "پولِ کمتر از یک سهم ⇒ UNKNOWN، نه «یک سهم»")

    # ── جاروب: هیچ ترکیبی بیشتر ازِ پول نرود ──
    bad = []
    for money in (10 ** 6, 7_345_678, 10 ** 8, 999_999):
        for price in (100, 1, 4321, 99_999, 123_450):
            for fee in (None, Decimal("0.0012"), Decimal("0.05")):
                p = EB.max_affordable(money, price, fee_rate=fee, lot_size=1,
                                      max_qty=10 ** 9)
                if p.status == EB.OK and p.total_rial > money:
                    bad.append((money, price, str(fee), p.total_rial))
    ck(not bad, "جاروبِ اعداد: هیچ OK بیشتر ازِ پول نمی‌رود", str(bad[:3]))

    # ── کنترلِ منفی: پولِ ساختگی باید UNKNOWN را بشکند ──
    real_dec = EB._dec

    def leaky(v):
        return Decimal("100000000") if v is None else real_dec(v)

    EB._dec = leaky
    try:
        mutated = EB.max_affordable(None, 12340, lot_size=1, max_qty=10 ** 9)
        ck(mutated.status != EB.UNKNOWN,
           "کنترلِ منفی: باِ پولِ ساختگی UNKNOWN نمی‌ماند (سنسور کور نیست)")
    finally:
        EB._dec = real_dec
    ck(EB.max_affordable(None, 12340).status == EB.UNKNOWN,
       "پس ازِ بازگردانی، بی‌پول همان UNKNOWN می‌ماند")

    print(f"\nexecution_budget_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
