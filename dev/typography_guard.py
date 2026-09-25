#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/typography_guard.py — هیچ کلاسِ اندازهٔ مرده‌ای در فرانت نماند.

چرا: `text-3xs` در ~۸۰ جا به‌کار رفته بود ولی هیچ‌وقت تعریف نشد. Tailwind 4 یک
utilite را فقط وقتی می‌سازد که `--text-<پله>` در `@theme` باشد؛ نبودش یعنی کلاس
**بی‌صدا** هیچ CSS‌ی تولید نمی‌کند و متن اندازهٔ والد را می‌گیرد — نه خطا، نه
تغییرِ قابل‌توجه در تست. نتیجه: «ریزکردن» عملاً اتفاق نمی‌افتاد و همین سکوت،
اندازه‌ها را از قصدِ طراح دور می‌کرد.

این گارد سه چیز را می‌بندد:
  ۱) هر `text-<پله>` که در tsx/ts استفاده شده یا پیش‌فرضِ Tailwind است یا در
     `index.css` تعریف شده؛
  ۲) نردبانِ واکنشی: هر بلوکی که `--fs-2xs` را عوض می‌کند باید `--fs-3xs` را هم
     عوض کند (وگرنه روی ۲K/۴K دو پله از هم فاصله می‌گیرند یا وارونه می‌شوند)؛
  ۳) ترتیبِ اندازه‌ها: 3xs < 2xs، و 3xs از ۱۰px ریزتر نشود.

خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
اجرا:  python dev/typography_guard.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE = os.path.join(ROOT, "frontend", "src")
INDEX_CSS = os.path.join("frontend", "src", "index.css")
TOKENS_CSS = os.path.join("frontend", "src", "shared", "styles", "tokens.css")

# پیش‌فرض‌های Tailwind v4 برای font-size — این‌ها بدون تعریف هم کار می‌کنند.
TAILWIND_DEFAULTS = {"xs", "sm", "base", "lg", "xl"} | {"%dxl" % n for n in range(2, 10)}

# تنها کلاس‌های اندازه (نه رنگ): «پایهٔ عددی + واحد» یا نام‌های معروف
SIZE_RE = re.compile(r"(?<![\w-])text-(\d*xs|\d*sm|\d*base|\d*lg|\d*xl)(?![\w-])")
DECL_RE = re.compile(r"--text-([a-z0-9]+)\s*:")

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _px(value):
    """'0.6875rem' -> 11.0 (پایهٔ ریشه ۱۶px؛ همان چیزی که مرورگر می‌سازد)."""
    v = value.strip()
    m = re.fullmatch(r"([0-9.]+)(rem|px)", v)
    if not m:
        return None
    n = float(m.group(1))
    return n * 16.0 if m.group(2) == "rem" else n


def used_sizes():
    found = {}
    for dirpath, dirs, files in os.walk(FE):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist")]
        for fn in files:
            if not fn.endswith((".tsx", ".ts")):
                continue
            path = os.path.join(dirpath, fn)
            src = _read(os.path.relpath(path, ROOT))
            for m in SIZE_RE.finditer(src):
                found.setdefault(m.group(1), set()).add(os.path.relpath(path, FE))
    return found


def main():
    index = _read(INDEX_CSS)
    tokens = _read(TOKENS_CSS)
    declared = set(DECL_RE.findall(index))
    ck("3xs" in declared and "2xs" in declared, "index.css declares the small steps",
       sorted(declared))

    used = used_sizes()
    undef = {s: v for s, v in used.items()
             if s not in TAILWIND_DEFAULTS and s not in declared}
    ck(not undef, "every text-<size> in use resolves to a real utility",
       {k: sorted(v)[:2] for k, v in undef.items()})

    # ۲) نردبانِ واکنشی: هر media که 2xs را جابه‌جا می‌کند باید 3xs را هم برد
    blocks = re.findall(r"@media[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", tokens, re.S)
    for b in blocks:
        head = b.split("{", 1)[0].strip()
        has2, has3 = "--fs-2xs" in b, "--fs-3xs" in b
        ck(has2 == has3, "responsive block moves both small steps together", head)
    ck(any("--fs-3xs" in b for b in blocks),
       "the micro step scales up on large displays too")

    # ۳) ترتیب و کفِ مطلق
    base3 = re.search(r"--fs-3xs:\s*([^;]+);", tokens)
    base2 = re.search(r"--fs-2xs:\s*([^;]+);", tokens)
    p3, p2 = _px(base3.group(1)) if base3 else None, _px(base2.group(1)) if base2 else None
    ck(p3 is not None and p2 is not None and p3 < p2, "3xs stays smaller than 2xs",
       (p3, p2))
    ck(p3 is not None and p3 >= 10.5, "3xs is not smaller than ~11px", p3)
    for b in blocks:
        m3 = re.search(r"--fs-3xs:\s*([^;]+);", b)
        m2 = re.search(r"--fs-2xs:\s*([^;]+);", b)
        if m3 and m2:
            ck(_px(m3.group(1)) < _px(m2.group(1)),
               "ladder holds inside every breakpoint",
               b.split("{", 1)[0].strip())
        if m3:
            ck(_px(m3.group(1)) >= 10.5, "no breakpoint drops under the micro floor",
               m3.group(1).strip())

    print("typography: %d pass / %d fail  (size steps in use: %s)"
          % (PASS, FAIL, ", ".join(sorted(used))))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
