# -*- coding: utf-8 -*-
# dev/persian_glyph_guard.py — گاردِ نویسه‌هایِ جاافتاده درِ متنِ فارسی
#
# سه خانۀِ خطا را می‌گیرد؛ هر سه درِ همین ریپو *واقعاً* دیده شده‌اند:
#
# ۱) نویسهٔ CJK/هنگول/کانا که وسطِ یک واژۀِ فارسی می‌نشیند. نمونه‌هایِ واقعیِ
#    همین ریپو (عمداً با کدپوینت نوشته شده‌اند، تا خودِ این فایل هم زیرِ گارد
#    باشد و به استثنایِ پنهان نیاز نداشته باشد):
#      U+89C2 U+6D4B   درِ یک docstring
#      U+4EA7 U+7269   درِ markdown
#      U+56DE U+5F52   درِ پیامِ commit
#      U+C774 U+C158   درِ «انیمیشن» — رویِ صفحه کاملاً فارسی به نظر می‌رسد و
#                      فقط با مقایسۀِ کدپوینت لو می‌رود
# ۲) رقمِ فارسیِ شمارۀِ بخش که بی‌صدا می‌افتد: سطرِ bannerِ شماره‌دار به شکلِ
#    «── ‎)» درمی‌آید و گیت سبز می‌ماند. پنج مورد از این درِ dev/ پیدا شد.
# ۳) ك/ي عربی (U+0643 و U+064A) درِ فایل‌هایِ سرخطی: درِ آن‌ها هیچ استثنایِ
#    املایی نیست، پس سخت گرفته می‌شود. بیرونِ آن‌ها گیت *نیست* — سنجشِ همین دور
#    ۳۵۰ سطرِ چنین درِ ریپو نشان داد، و اکثراً یا املاىِ خودِ نمادهایِ تابلو
#    («تكنار»، «کايزد»، «اميد») یا بحثِ صریحِ norm_fa دربارهٔ «ك عربی / ي عربی».
#    تا سیاستِ «داده ≠ نص» روشن نشود، گیتِ سراسری ماشینِ مثبتِ کاذب است.
#
# اجرا:  python dev/persian_glyph_guard.py [--selftest]

import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

#: نویسهٔ CJK/هنگول/کانا
CJK = re.compile(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7A3]+")
ARABIC_KEF_YEH = re.compile(r"[\u0643\u064A]")      # ك عربی / ي عربی
PERSIAN_ONLY = re.compile(r"[پچژگ۰-۹]")             # امضایِ «این سطر فارسی است»
#: فقط سطرِ banner (شروعِ سطر با #) — تا خودِ توضیحِ این قانون درِ کامنت یا
#: رشتهٔ تست، مثبتِ کاذب نسازد.
BARE_BANNER = re.compile(r"^\s*#\s*──\s*\)")
CODE_SPAN = re.compile(r"`[^`]*`")
EXTS = (".py", ".md", ".ts", ".tsx", ".css", ".iss", ".ps1")

MABNA = "_audit/mabnaIndicators.wip-1405-07-11.ts"
#: نامِ ژاپنیِ ایچیموکو درِ یادداشتِ شاخص؛ با کدپوینت ساخته شده تا حتی یک
#: نویسهٔ بیگانه درِ source این گارد نماند.
ICHIMOKU_TOKENS = frozenset((chr(0x4E5D) + chr(0x5341) + chr(0x516C)
                             + chr(0x5E73) + chr(0x8868), chr(0x4E94)))

#: استثنایِ CJK: مسیر → مجموعهٔ *دقیقِ* نویسه‌هایِ مجاز، هرکدام با دلیل.
#: استثنایِ تازه باید آگاهانه اینجا بیاید؛ چکِ پایانی تعدادشان را قفل می‌کند.
CJK_ALLOW = {MABNA: set(ICHIMOKU_TOKENS)}
CJK_ALLOW_REASON = {MABNA: "نامِ ژاپنیِ ایچیموکو درِ یادداشتِ شاخص، "
                           "نه نویسهٔ جاافتاده"}

#: فایل‌هایی که ك/ي عربی درِ آنها بی‌استثنا خطاست (متنِ سرخطی، نه دادهٔ تابلو)
STRICT_KEF_YEH_PREFIXES = ("execution_", "dev/execution_", "docs/execution/")

#: سم‌هایِ selftest هم با کدپوینت، نه با نویسهٔ خام
POISON_CJK = chr(0x89C2) + chr(0x6D4B)
POISON_KEF = chr(0x0643)

CHECKS = []


def ck(label, cond, detail=""):
    CHECKS.append((bool(cond), label, detail))


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True)
    return [p.decode("utf-8") for p in out.stdout.split(b"\0") if p]


def read(path):
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def hits_in(path, text, strict_kef_yeh=None):
    """هر سه سنسور رویِ یک متن. خروجی: [(خانۀِ خطا، شمارۀِ خط، نمونه), …]

    `strict_kef_yeh` را selftest تزریق می‌کند تا سم‌ها بی‌نام‌گذاریِ ساختگیِ
    فایل، همان مسیرِ واقعیِ کد را طی کنند.
    """
    if strict_kef_yeh is None:
        strict_kef_yeh = path.startswith(STRICT_KEF_YEH_PREFIXES)
    allowed = CJK_ALLOW.get(path, frozenset())
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        for tok in CJK.findall(line):
            if tok not in allowed:
                out.append(("CJK", n, tok))
        if BARE_BANNER.search(line):
            out.append(("BANNER", n, line.strip()[:48]))
        if strict_kef_yeh:
            stripped = CODE_SPAN.sub(" ", line)
            if PERSIAN_ONLY.search(stripped) and ARABIC_KEF_YEH.search(stripped):
                out.append(("KEF-YEH", n, line.strip()[:48]))
    return out


def scan(files):
    buckets = {"CJK": [], "BANNER": [], "KEF-YEH": []}
    for p in files:
        if not p.endswith(EXTS):
            continue
        for kind, n, sample in hits_in(p, read(p)):
            buckets[kind].append("%s:%d %s" % (p, n, sample))
    return buckets["CJK"], buckets["BANNER"], buckets["KEF-YEH"]


def loose_kef_yeh_count(files):
    """شمارشِ *اطلاعی* ك/ي عربی بیرونِ فایل‌هایِ سرخطی؛ رأی نمی‌دهد."""
    total = 0
    for p in files:
        if not p.endswith(EXTS) or p.startswith(STRICT_KEF_YEH_PREFIXES):
            continue
        for line in read(p).split("\n"):
            stripped = CODE_SPAN.sub(" ", line)
            if PERSIAN_ONLY.search(stripped) and ARABIC_KEF_YEH.search(stripped):
                total += 1
    return total


def selftest():
    """هر سه سنسور باید رویِ سمِ ساخته‌شده واکنش نشان دهند، وگرنه کورند."""
    cases = [
        ("CJK", "x = 1  # این یک واژۀِ " + POISON_CJK + "شده است\n", "CJK"),
        ("رقمِ افتاده", "# ── ) بخشِ بی‌شماره ─────────\n", "BANNER"),
        ("ك عربی", "# ۱ توضیحِ پارسی با " + POISON_KEF + " عربی\n", "KEF-YEH"),
        ("سطرِ سالم", "# ۲) بخشِ سالمِ فارسی\n", None),
        ("bannerِ شماره‌دار", "# ── ۳) بخشِ شماره‌دار\n", None),
        ("توضیحِ قانون درِ متن", '        ck("هیچ بخشِ بی‌شماره", x)\n', None),
        ("استثنایِ ثبت‌شده",
         "Ichimoku " + " ".join(sorted(ICHIMOKU_TOKENS)) + " lines\n", None),
    ]
    for label, body, want in cases:
        path = MABNA if label == "استثنایِ ثبت‌شده" else "sym.py"
        found = hits_in(path, body, strict_kef_yeh=True)
        if want is None:
            ck("selftest: «" + label + "» داوری نمی‌شود", not found,
               str(found))
        else:
            ck("selftest: سنسورِ «" + label + "» سم را می‌بیند",
               any(k == want for k, _n, _s in found), str(found))
    empty = scan([])
    ck("selftest: بی‌فایل هیچ سنسوری رأی نمی‌دهد", not any(empty),
       str(empty))


def main():
    print("persian_glyph_guard — نویسهٔ بیگانه و رقمِ افتاده درِ متنِ فارسی")
    if "--selftest" in sys.argv[1:]:
        selftest()
    else:
        files = tracked()
        c, b, y = scan(files)
        ck("هیچ متنِ فارسیِ آلوده به CJK/هنگول (بیرونِ استثنایِ ثبت‌شده)",
           not c,
           " | ".join(c[:8]) + (" …+%d" % (len(c) - 8) if len(c) > 8 else ""))
        ck("هیچ سطرِ banner بی‌شماره", not b,
           " | ".join(b[:8]) + (" …+%d" % (len(b) - 8) if len(b) > 8 else ""))
        ck("ك/ي عربی درِ فایل‌هایِ سرخطی نیست", not y, " | ".join(y[:8]))
        ck("استثنا فقط همان یک فایلِ ثبت‌شده است",
           set(CJK_ALLOW) == set(CJK_ALLOW_REASON) == {MABNA}
           and CJK_ALLOW[MABNA] == ICHIMOKU_TOKENS, str(sorted(CJK_ALLOW)))
        print("  (اطلاعی: %d سطرِ ك/ي عربی بیرونِ فایل‌هایِ سرخطی — اکثراً "
              "املاىِ نمادهایِ تابلو، پس گیت نیست؛ §۳)"
              % loose_kef_yeh_count(files))
    passed = sum(1 for ok, _, _ in CHECKS if ok)
    for ok, label, detail in CHECKS:
        print(("  ok   " if ok else "FAIL  ") + label
              + ("  | " + detail if detail and not ok else ""))
    print("persian_glyph_guard: %d passed / %d failed"
          % (passed, len(CHECKS) - passed))
    return 1 if passed != len(CHECKS) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
