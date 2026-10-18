# -*- coding: utf-8 -*-
"""Header + §۵ item 8: what actually shipped in the evidence folder."""
import io
import os

RUN = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(RUN, "..", "..", "docs", "research",
                      "PERFORMANCE-MARKET-HOURS-2026-10-17.md")


def fa(s):
    t = str(s)
    out = []
    for ch in t.lstrip("-"):
        out.append(chr(0x06F0 + int(ch)) if ch.isdigit() else
                   ("٬" if ch == "," else ("٫" if ch == "." else ch)))
    return ("−" if t.startswith("-") else "") + "".join(out)


p = REPORT
L = io.open(p, encoding="utf-8").read().split("\n")

i = next(k for k, v in enumerate(L) if v.startswith("خروجیِ خام:"))
RUNNAME = os.path.basename(RUN)  # keep paths ASCII, never digit-transliterated
L[i:i + 2] = [
    "خروجیِ خام: `_test_runs/" + RUNNAME + "/`",
    "— بنچِ قبل/بعد، گیتِ برابری (`equal-check.md`)، شنودِ زندهٔ JSONL، پنجره‌هایِ مرورگر",
    "(`browser-perf.json` و `browser-before-paired/`)، اسکریپت‌هایِ سنجش و سه اسکریپتی که این",
    "اعداد را از همان فایل‌ها ساخت (`repair_report_numbers.py`, `finalize_report.py`,",
    "`add_equal_section.py`). `machine.csv` فقط سرِ ستون دارد، چون پالرِ CPU/RAM مُرد (§۵).",
    "اسکرین‌شات‌ها (PNG) رویِ دیسکِ همین ورک‌تری‌اند و commit نشدند تا شاخه سبک بماند.",
]

j = next(k for k, v in enumerate(L) if v.strip().startswith(fa(8) + ". `python dev/run_all_tests.py`"))
L[j:j + 5] = [
    fa(8) + ". `python dev/run_all_tests.py`: گیتِ کاملِ آفلاین (" + fa(105) + " سوئیت) اجرا **نشد** — این",
    "   رانر هیچ فیلترِ انتخابِ سوئیت ندارد (بدونِ `argparse`)، پس یا همه یا هیچ؛ سرورهایِ devِ",
    "   مأموریت‌هایِ دیگر بالاست و خودِ گیت ~" + fa(35) + " دقیقه می‌خواهد. جایش پنج سوئیتِ مرتبطِ آفلاین",
    "   اجرا و سبز شدند + گیتِ برابریِ " + fa(27) + " اندپوینتی (§۴ب) و دو گاردِ هدفمند:",
    "   `dev/persian_glyph_guard.py` (" + fa(4) + "/" + fa(4) + ") و `dev/funnel_body_cache_v1.py` (" + fa(11) + "/" + fa(11) + ").",
]

io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("header -> %d lines | item 8 rewritten at %d" % (len(L), j + 1))
