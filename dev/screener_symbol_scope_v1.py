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

    # `_funnel_gate` از همان `build_funnel` می‌خواند که ردیف‌هایِ کش‌شده را با
    # `_backend_rank` می‌آراید؛ اولین درخواستِ سرد، ردیف‌ها را بی‌این کلید می‌بیند.
    # یک گرم‌کردن، مقایسۀ «همان ردیف» را قطعی می‌کند (نه یک تفاوتِ محاسبه).
    SC.get_screener()
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

    # P2-R6: پنلِ کنارِ نماد پرچمِ قیف را نمی‌خواند؛ `/api/screener/row` همان
    # ردیفِ اسکنِ کش‌شده را بی‌ساختِ قیف می‌دهد. جدولِ کامل همچنان از
    # `get_screener` با گیت می‌آید و پارامترِ خاموش‌کنندهٔ گیت ندارد.
    gate_fields = {"tape_status", "technical_status", "fundamental_status",
                   "gate_state", "funnel_candidate", "technical_reason"}
    full_row = srows[0] if srows else {}
    skipped = SC.get_screener_row(symbols=sym)
    krows = skipped.get("data") or []
    base = {k: v for k, v in full_row.items() if k not in gate_fields}
    keep = {k: v for k, v in (krows[0] if krows else {}).items() if k not in gate_fields}
    ck("row یک ردیف با همان شاخص‌ها/وتوها می‌دهد",
       len(krows) == 1 and base == keep,
       "rows=%d" % len(krows))
    ck("row وضعیت را skipped اعلام می‌کند و پرچمِ قیف نمی‌سازد",
       (skipped.get("funnel_gate") or {}).get("state") == "skipped"
       and "funnel_candidate" not in (krows[0] if krows else {}),
       "state=%s" % (skipped.get("funnel_gate") or {}).get("state"))
    ck("get_screener (پیش‌فرض) پرچمِ قیف را نگه می‌دارد",
       "funnel_candidate" in full_row and (full.get("funnel_gate") or {}).get("state") != "skipped",
       "state=%s" % (full.get("funnel_gate") or {}).get("state"))

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("SCREENER-SYMBOL-SCOPE: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
