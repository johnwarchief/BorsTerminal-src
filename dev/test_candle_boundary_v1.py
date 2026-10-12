# dev/test_candle_boundary_v1.py — RC2 (مرحلۀِ ۶): مرزهایِ FIRST/LAST/CLOSE و حجمِ صفر
# سیاستِ مالکِ مرحلۀِ ۱: OHLC خامِ TSETMC حفظ شود، نه تقلیدِ خاموشِ بازۀِ جلسۀِ اصلیِ
# رهاورد. پس high/lowِ مرجعِ تنگ‌تر «اختلافِ تعریف» است نه باگِ دادهٔ خودی. این آزمون
# قاعدۀِ هندسه را تثبیت می‌کند که هیچ پرینتِ FIRST/LAST/CLOSE بی‌صدا جابه‌جا یا حذف نشود
# و روزِ بی‌معامله کندل نسازد. اثباتِ قطعیِ علتِ تنگ‌بودنِ بازۀِ رهاورد (RC2) همچنان
# نیازمندِ پرینتِ لحظه‌ایِ پیش‌گشایش است و بیرونِ این دور UNVERIFIED می‌ماند.
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import candle_contract as CC  # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


# widen هیچ قیمتِ معتبری را خُرد نمی‌کند؛ فقط سایه را باز می‌کند
check("widen سقفِ معیوبِ پایین‌ترِ بدنه را به بدنه ترجیح می‌دهد",
      CC.widen(1200, 1100, 0, 1150), (1200, 1150))
check("widen close را عوض نمی‌کند (سایه باز، بدنه دست‌نخورده)",
      CC.widen(1000, 1200, 900, 1150), (1200, 900))

# روزِ بی‌معامله (v=0) کندل نمی‌شود — ردیفِ «امروزِ» پیش‌ازِ بازگشایی با حجمِ صفر
check("حجمِ صفر ⇒ کندل نیست", CC.candle("خ", "2026-01-01", 100, 100, 100, 100, volume=0), None)
check("حجمِ مثبت ⇒ کندل می‌سازد", bool(CC.candle("خ", "2026-01-01", 100, 110, 90, 105, volume=10)), True)

# lastِ غایب با close جعل نمی‌شود؛ lastِ حاضر دست‌نخورده می‌ماند
c = CC.candle("خ", "2026-01-01", 100, 110, 90, 105, volume=10, last=None)
check("lastِ None با close پر نشد", c["last"], None)
check("closeِ واقعیِ دست‌نخورده", c["close"], 105.0)
c2 = CC.candle("خ", "2026-01-01", 100, 110, 90, 105, volume=10, last=108)
check("lastِ حقیقی جابه‌جا نشد", c2["last"], 108.0)
check("open از FIRST می‌آید نه از close", c2["open"], 100.0)

# هندسۀِ ناممکنِ TSETMC (close بیرونِ [L,H]) با گشادکردنِ سایه حل می‌شود، نه خُردکردنِ close
c3 = CC.candle("خ", "2026-01-01", 100, 100, 100, 105, volume=10, last=105)
check("closeِ بیرونِ سایه ⇒ سایه گِشاد می‌شود (نه جعلِ close)", (c3["high"], c3["close"]), (105.0, 105.0))

print("\n" + "=" * 60)
print(f"نتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
