# dev/test_fts_basis_anchor_v1.py — RC1 (مرحلۀِ ۲): تغییرِ مبنایِ نمایش، لنگرِ تعدیل را جابه‌جا نمی‌کند
# read-only/در‌حافظه؛ هیچ فایلی و بانکِ عملیاتی عوض نمی‌شود. سه شرط:
#   ۱) مبنایِ نمایش (last↔closing) فقط ستونِ `close` را عوض می‌کند، نه `closing`(لنگر)
#      و نه فاکتورهایِ زنجیره.
#   ۲) نبودِ `last` هرگز با `close` پر نمی‌شود؛ apply_basis به لنگرِ closing برمی‌گردد
#      و با `basis_reason` اعلام می‌کند (جعلِ مقدار ممنوع — قراردادِ price-honesty).
#   ۳) فاکتورِ تعدیل از `all_rows` (گسستِ پایه در برابرِ پایانی) می‌آید و به
#      `price_basis.current()` وابسته نیست.
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from api import chart as C        # noqa: E402
import price_basis as PB          # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


def with_basis(value, fn):
    old = PB.current
    PB.current = lambda: value
    try:
        return fn()
    finally:
        PB.current = old


# ── دادهٔ مصنوعی: یک رویدادِ تعدیل (پایهٔ روزِ دوم ≠ پایانیِ روزِ اول)، last≠closing
all_rows = [
    {"time": "2024-01-01", "base": 1000.0, "close": 1000.0, "vol": 500.0},
    {"time": "2024-01-02", "base": 500.0, "close": 520.0, "vol": 600.0},   # ratio 0.5
    {"time": "2024-01-03", "base": 520.0, "close": 540.0, "vol": 700.0},
]
ev, _ = C._adjust_events_from_rows(all_rows)
factors = [{"time": t, "factor": f} for t, f in
           zip([r["time"] for r in all_rows], C._factors_from_events([r["time"] for r in all_rows], ev))]

# candles با lastِ متفاوت از closing (شرطِ واقعیِ TSETMC)
candles = [
    {"time": "2024-01-01", "open": 1000.0, "high": 1010.0, "low": 990.0, "closing": 1000.0, "last": 995.0},
    {"time": "2024-01-02", "open": 500.0, "high": 530.0, "low": 495.0, "closing": 520.0, "last": 525.0},
    {"time": "2024-01-03", "open": 520.0, "high": 545.0, "low": 515.0, "closing": 540.0, "last": 538.0},
]
vols = []

scale_last = with_basis(PB.LAST, lambda: C._fts_scaled([dict(c) for c in candles], factors, vols))
scale_close = with_basis(PB.CLOSING, lambda: C._fts_scaled([dict(c) for c in candles], factors, vols))


def col(rows_, k):
    return [r.get(k) for r in rows_]


# ۱) لنگرِ closing و lastِ خام درِ هر دو مبنایِ نمایش یکسان‌اند؛ فقط `close` فرق می‌کند
check("لنگرِ closing درِ هر دو مبنایِ نمایش بیتغییر", col(scale_last, "closing"), col(scale_close, "closing"))
check("ستونِ last درِ هر دو مبنایِ نمایش بیتغییر", col(scale_last, "last"), col(scale_close, "last"))
check("close درِ مبنایِ last == lastِ تعدیل‌شده", col(scale_last, "close"), col(scale_last, "last"))
check("close درِ مبنایِ closing == لنگرِ تعدیل‌شده", col(scale_close, "close"), col(scale_close, "closing"))
# لنگرِ تعدیلِ روزِ اول باید = closing×k (۱۰۰۰×۰٫۵=۵۰۰)، نه last×k
check("لنگرِ تعدیل از closing ساخته می‌شود نه last", scale_last[0]["closing"], 500.0)

# ۳) فاکتورِ زنجیره به مبنایِ نمایش وابسته نیست (فقط از all_rows می‌آید)
f_last = with_basis(PB.LAST, lambda: C._factors_from_events([r["time"] for r in all_rows], ev))
f_close = with_basis(PB.CLOSING, lambda: C._factors_from_events([r["time"] for r in all_rows], ev))
check("فاکتورهایِ تعدیل درِ هر دو مبنا یکسان", f_last, f_close)

# ۲) نبودِ `last` جعل نمی‌شود: سطرِ بی‌last ⇒ last=None، و close درِ مبنایِ last به closing
#    برمی‌گردد با اعلامِ reason (نه ساختنِ عدد)
candles_nolast = [dict(c) for c in candles]
candles_nolast[1]["last"] = None
scale_nolast = with_basis(PB.LAST, lambda: C._fts_scaled(candles_nolast, factors, vols))
check("lastِ غایب جعل نشد (None ماند)", scale_nolast[1]["last"], None)
# چون یک last غایب است، apply_basis کلِ سری را به closing برمی‌گرداند (قاعدۀِ no-fabrication)
meta = with_basis(PB.LAST, lambda: PB.apply_basis([{"time": c["time"], "open": c["open"],
                                                     "high": c["high"], "low": c["low"],
                                                     "close": c["closing"], "closing": c["closing"],
                                                     "last": (None if c["time"] == "2024-01-02" else c["closing"])}
                                                    for c in candles], copy=True))
check("مبنایِ درخواستیِ last ولی بی‌lastِ کامل ⇒ applied=closing", meta["basis_applied"], PB.CLOSING)
check("دلیلِ بازگشت اعلام شد (بی‌جعل)", str(meta["basis_reason"]).startswith("last_missing:"), True)

print("\n" + "=" * 60)
print(f"نتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
