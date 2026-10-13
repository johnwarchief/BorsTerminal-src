# dev/test_fts_event_identity_v1.py — تفکیکِ «هویتِ رویداد» از «محاسبۀِ ضریب» (RC3/§B، مرحلۀِ ۳)
# خالصِ read-only و بدونِ شبکه/دیتابیس: `_ledger_events_for` با stub جایگزین می‌شود تا
# خودِ قاعدۀِ پذیرشِ ردیفِ مبدأسنجیده شود. چهار نامهایِ مرحلۀِ ۳ و مرحلۀِ Bِ سناریوهایِ
# ولانا/شبهرن/لخزر/ومعادن را قفل می‌کند:
#   ۱) ضریبِ دقیق از ردیفِ مبدأ می‌نشیند، تاریخِ دیدہ‌شدہ جابه‌جا نمی‌شود (هویت ≠ ضریب).
#   ۲) ردیفِ مبدأِ ناهمخوانِ بزرگ (اختلافِ ۲۵٪ مثلِ آوردهٔ ولانا) هرگز جای عددِ درست را
#      نمی‌گیرد و رویداد با همان عددِ خودی برمی‌گردد.
#   ۳) دو رویدادِ مستقل که یکِ ردیفِ مبدأ را مطالبه کنند، هیچ‌کدام تیز نمی‌شود و هیچ
#      رویدادی حذف نمی‌شود (بی‌طرفی، نه حذفِ عددِ واقعی).
#   ۴) بی‌ردیفِ مبدأ: رویداد صفر یا حدس نمی‌شود، با همان عددِ پیشین برمی‌گردد.
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from api import chart as C  # noqa: E402

P = F = 0
_real_ledger = C._ledger_events_for


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


def with_ledger(rows):
    C._ledger_events_for = lambda symbol: list(rows)


try:
    # ۱) ضریب از مبدأ، تاریخِ دیدہ‌شدہ ثابت
    #    شبهرن‌مانند: CSV رویدادِ ۲۰۲۵-۰۷-۲۲ را با ضریبِ گِردِ ۰٫۸۵۳۹ می‌بیند؛
    #    دفترِ مبدأ ردیفِ ۲۰۲۵-۰۷-۲۱ با عددِ دقیق ۰٫۸۵۳۷ دارد (اختلاف ۰٫۰۲٪ < آستانه).
    with_ledger([{"date": "2025-07-21", "ratio": 0.8537, "kind": "priceAdjust"}])
    ev = [{"date": "2025-07-22", "ratio": 0.8539}]
    out, sharpened, ambiguous = C._sharpen_events_with_ledger("نماد", ev)
    check("۱ ضریبِ دقیق از مبدأ نشست", out[0]["ratio"], 0.8537)
    check("۱ تاریخِ دیدہ‌شدہ جابه‌جا نشد (هویت ≠ ضریب)", out[0]["date"], "2025-07-22")
    check("۱ منبعِ رویداد priceAdjust علامت خورد", out[0].get("source"), "priceAdjust")
    check("۱ شمارِ تیزشده = ۱، مبهم = ۰", (sharpened, ambiguous), (1, 0))

    # ۲) ردیفِ ناهمخوانِ بزرگ پذیرفته نمی‌شود (آوردهٔ ولانا: ۰٫۳۰۰ در برابرِ ۰٫۳۷۵۵)
    with_ledger([{"date": "2026-05-11", "ratio": 0.300, "kind": "shareChange"}])
    ev = [{"date": "2026-05-11", "ratio": 0.3755}]
    out, sharpened, ambiguous = C._sharpen_events_with_ledger("ولانا", ev)
    check("۲ عددِ درستِ خودی حفظ شد (ردیفِ بی‌ربط جای آن را نگرفت)", out[0]["ratio"], 0.3755)
    check("۲ منبعِ خودی base-price-discontinuity ماند", out[0].get("source"), "base-price-discontinuity")
    check("۲ نه تیز شد نه مبهم", (sharpened, ambiguous), (0, 0))

    # ۳) دو رویدادِ هم‌پنجره یکِ ردیفِ مبدأ را مطالبه می‌کنند → هیچ حذف/تیز نمی‌شود
    with_ledger([{"date": "2025-08-26", "ratio": 0.900, "kind": "priceAdjust"}])
    ev = [{"date": "2025-08-25", "ratio": 0.9002},   # هر دو داخلِ ±۱۰ روز و ±۰٫۱٪
          {"date": "2025-08-28", "ratio": 0.8998}]
    out, sharpened, ambiguous = C._sharpen_events_with_ledger("خودرو", ev)
    check("۳ هیچ رویدادی حذف نشد (دو رویدادِ واقعی باقی‌اند)", len(out), 2)
    check("۳ هر دو درِ ambiguous شمرده شدند", ambiguous, 2)
    check("۳ هیچ‌کدام تیز نشد", sharpened, 0)
    check("۳ عددهایِ خودی دست‌نخورده ماندند", sorted(o["ratio"] for o in out), [0.8998, 0.9002])

    # ۴) بی‌ردیفِ مبدأ: نه صفر نه حدس
    with_ledger([])
    ev = [{"date": "2024-03-01", "ratio": 0.5}]
    out, sharpened, ambiguous = C._sharpen_events_with_ledger("طلا", ev)
    check("۴ بی‌دفتر، رویداد با همان عدد برمی‌گردد", out[0]["ratio"], 0.5)
    check("۴ شمارش‌ها صفر (بی‌دفتر ≠ تیزشده)", (sharpened, ambiguous), (0, 0))

    # ۴-ب) بی‌رویداد → سه‌گانهٔ خالی، نه خطا
    check("۴-ب بی‌رویداد، خروجیِ خالی", C._sharpen_events_with_ledger("نامعلوم", []), ([], 0, 0))
finally:
    C._ledger_events_for = _real_ledger

print(f"\nنتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
