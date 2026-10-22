"""SCREENER-SYMBOL-SCOPE v1 — گاردِ پاسخِ یک‌نمادیِ اسکرینر (P2-R1).

سایدبار برایِ یک ردیف، کلِ `/api/screener` را می‌کشید. اکنون
`/api/screener?symbols=<X>` همان ردیف را می‌دهد. این گارد ثابت می‌کند:
  ۱) پاسخِ یک‌نمادی دقیقاً یک ردیف دارد؛
  ۲) همان ردیف با ردیفِ پاسخِ کاملِ همان نماد یکی است (هیچ محاسبهٔ دوم)؛
  ۳) نمادِ ناشناخته یک ردیفِ خالی می‌دهد، نه ردیفِ نمادِ دیگر.

خواندنی؛ بدونِ market.db ⇒ SKIP.

usage: python dev/screener_symbol_scope_v1.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def main():
    if not os.path.exists("market.db"):
        print("SKIP: market.db نیست")
        return 0
    import api.screener as SC

    full = SC.get_screener()
    rows = full.get("data") or []
    if not rows:
        print("SKIP: screener فعلاً ردیفی ندارد (fts_results/محاسبه در دسترس نیست)")
        return 0
    sample = rows[0]
    sym = str(sample.get("symbol") or "").strip()
    if not sym:
        print("SKIP: ردیفِ نمونه نماد ندارد")
        return 0

    scoped = SC.get_screener(symbols=sym)
    srows = scoped.get("data") or []
    ck("پاسخِ یک‌نمادی دقیقاً یک ردیف دارد", len(srows) == 1 and scoped.get("requested_symbols") == 1,
       "rows=%d requested=%s" % (len(srows), scoped.get("requested_symbols")))
    ck("ردیفِ یک‌نمادی با ردیفِ پاسخِ کامل یکی است",
       bool(srows) and srows[0] == sample,
       "symbol=%s" % sym)
    ck("count با تعدادِ ردیف‌ها می‌خواند", scoped.get("count") == len(srows),
       "count=%s" % scoped.get("count"))

    unknown = SC.get_screener(symbols="__نمادِ‌ناموجود__")
    ck("نمادِ ناشناخته ردیفِ خالی می‌دهد", (unknown.get("data") or []) == [],
       "rows=%d" % len(unknown.get("data") or []))

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("SCREENER-SYMBOL-SCOPE: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
