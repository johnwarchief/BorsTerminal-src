# -*- coding: utf-8 -*-
"""dev/guard_counts_v1110.py — گاردِ «آیا شمارشِ گاردها واقعاً خوانده می‌شود؟»

مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۱-۱۴ و ۷: «گاردهایی که صرفاً exit code گزارش
می‌کنند و تعدادِ واقعی بررسی‌هایشان مشخص نیست». گزارشگرِ `run_all_tests.py`
پیش‌تر سه الگو می‌شناخت و بقیه را با شمردنِ کلمه‌های PASS/FAIL پر می‌کرد؛ نتیجه
این بود که suiteای با خروجیِ «۱۲ سنجه، ۰ خطا» درِ خلاصه «۰ pass / ۰ fail»
می‌آمد — و خواننده نمی‌فهمید آن صفر یعنی «هیچِ بررسی» یا «گزارشگر کور بود».

چه قفلی می‌زند:
  ۱ هر الگویِ شمارشی که گاردها چاپ می‌کنند، در `parse_counts` به شمارشِ درست می‌رسد
  ۲ خروجیِ بی‌شمارش (`ok`) صریح «بی‌شمارش» می‌شود، نه ۰/۰
  ۳ rc=1 با شمارشِ صفرِ خطا ⇒ همان «سرخی» خودِ rc را می‌بَرَد (تعارض پنهان نمی‌ماند)
  ۴ `run_all_tests.py` واقعاً از همین ترجمان import می‌کند (نه پارسرِ inlineِ کهنه)
  ۵ سه گاردِ زنده اجرا می‌شوند و خروجی‌شان *همین حالا* شمارش‌پذیر است
  ۶ کنترلِ منفی: اگر ترجمان را با الگویِ خرابِ قبلی عوض کنم، سنجه‌ها قرمز می‌شوند
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from guard_counts import parse_counts, summarize  # noqa: E402

PASS, FAIL = 0, 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:140]))
    return bool(cond)


def test_known_shapes():
    got = parse_counts("execution_contract_v1: 20 passed / 0 failed\n")
    ck(got and got["pattern"] == "N passed, M failed" and got["passed"] == 20
       and got["total"] == 20, "۱ «20 passed / 0 failed»", got)

    got = parse_counts("watchlist export: 33/33 passed\n")
    ck(got and got["passed"] == 33 and got["total"] == 33, "۱ «33/33 passed»", got)

    got = parse_counts("۴۵ بررسی سبز، ۰ شکست\n")
    ck(got and got["total"] == 45 and got["passed"] == 45,
       "۱ «N بررسی سبز، M شکست»", got)

    got = parse_counts("market_tick: ۱۲ سنجه، ۲ خطا\n")
    ck(got and got["total"] == 12 and got["passed"] == 10 and got["failed"] == 2,
       "۱ «N سنجه، M خطا»", got)

    got = parse_counts("paths parity: ۹ سبز، ۲ قرمز\n")
    ck(got and got["total"] == 9 and got["passed"] == 7 and got["failed"] == 2,
       "۱ «N سبز، M قرمز»", got)

    got = parse_counts("OK — 12/12\n")
    ck(got and got["passed"] == 12 and got["total"] == 12, "۱ «OK — N/M»", got)

    got = parse_counts("۲۹ سرخ\n" + "PASS\n" * 40)
    ck(got and got["failed"] == 29 and got["total"] >= 29, "۱ «N سرخ»", got)


def test_silent_and_rc():
    s = summarize("ok\n", 0)
    ck(s["countable"] is False and s["ok"] is True and "بی\u200cشمارش" in s["detail"],
       "۲ خروجیِ «ok» ⇒ بی‌شمارش، نه ۰/۰", s)
    s = summarize("", 0)
    ck(s["countable"] is False, "۲ خروجیِ خالی هم بی‌شمارش است", s)
    s = summarize("۱۲ سنجه، ۰ خطا\n", 1)
    ck(s["countable"] and s["ok"] is False,
       "۳ rc=1 با صفرِ خطا ⇒ سرخ (تعارض پنهان نمی‌ماند)", s)
    s = summarize("۱۲ سنجه، ۳ خطا\n", 0)
    ck(s["countable"] and s["ok"] is False,
       "۳ شمارشِ خطا با rc=0 ⇒ سرخ (خروجیِ ناقص رد می‌شود)", s)
    s = summarize("PASS\nPASS\nFAIL\n", 0)
    ck(s["countable"] and s["ok"] is False, "۳ tokenهای PASS/FAIL هم شمارش‌اند", s)


def test_harness_wiring():
    src = open(os.path.join(ROOT, "dev", "run_all_tests.py"), encoding="utf-8").read()
    ck("from guard_counts import summarize" in src,
       "۴ گزارشگر از ترجمانِ مشترک import می‌کند")
    ck("uncounted" in src and "suite counted" in src,
       "۴ گزارشگر شمارِ بی‌شمارش‌ها را اعلام می‌کند")
    # پارسرِ inlineِ کهنه نباید هنوز مسیرِ تصمیم باشد
    ck("mf = re.search(" not in src, "۴ پارسرِ inlineِ کهنه حذف شده")


LIVE = ("dev/execution_contract_v1.py", "dev/watch_export_v1106.py",
        "dev/per_capita_sell_v1107.py")


def test_live_outputs_are_countable():
    for rel in LIVE:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            ck(False, "۵ %s وجود ندارد" % rel)
            continue
        r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=ROOT)
        txt = (r.stdout or "") + (r.stderr or "")
        s = summarize(txt, r.returncode)
        ck(s["countable"] and s["ok"], "۵ خروجِ زندهٔ %s شمارش‌پذیر و سبز است" % rel,
           (s, txt.strip().splitlines()[-1:] ))


def test_negative_control():
    """۶ اگر ترجمان همان سه‌الگویِ کهنه باشد، سنجه‌ها باید قرمز شوند."""
    import re as _re
    import guard_counts as GC
    real = GC.PATTERNS
    GC.PATTERNS = (("old", _re.compile(r"(\d+)\s*/\s*(\d+)\s+passed")),)
    try:
        ck(GC.parse_counts("۱۲ سنجه، ۲ خطا\n") is None,
           "۶ با الگوهایِ کهنه، خروجیِ «سنجه/خطا» بی‌شمارش می‌شود (سنسور زنده است)")
    finally:
        GC.PATTERNS = real
    got = GC.parse_counts("۱۲ سنجه، ۲ خطا\n")
    ck(got and got["passed"] == 10, "۶ پسِ بازگردانی، همان خروجی دوباره شمارش می‌شود")


if __name__ == "__main__":
    for fn in (test_known_shapes, test_silent_and_rc, test_harness_wiring,
               test_live_outputs_are_countable, test_negative_control):
        print("── %s" % fn.__name__)
        try:
            fn()
        except Exception as e:
            import traceback
            FAIL += 1
            print("FAIL %s استثنا: %s" % (fn.__name__, e))
            traceback.print_exc()
    print("\n%d passed / %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
