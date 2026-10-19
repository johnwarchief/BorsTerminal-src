#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/fix_rule_map_lines.py — بازگردانی ارجاع‌های `NAME:LINE`ِ سندِ نقشهٔ قواعد

علتِ نیاز: این مأموریت چند تابعِ `api/chart.py` را جابه‌جا کرد و گارد
`dev/test_rule_map_citations.py` درست همین را قرمز کرد (سطرِ کهنه، خطای ارجاع است
نه نکتهٔ ظاهری — متنِ خودِ گارد).

روش (بدون regexِ حریص روی پیامِ گارد — درسِ دورِ قبل):
  ۱) نامِ توابعی که گارد نامبرده را صریح فهرست می‌کنیم؛
  ۲) سطرِ هر نام **از خودِ فایل** با الگوی `^def NAME(` درمی‌آید؛
 ۳) درِ سند فقط همان `NAME:<digits>` جایِ سطرِ درست می‌نشیند؛
  ۴) جدولِ قبل/بعد چاپ می‌شود و گارد دوباره اجرا می‌شود.

هیچ نامی که در کد پیدا نشود دست نمی‌خورد؛ هیچ سطرِ دیگری بازنویسی نمی‌شود.
اجرا: PYTHONIOENCODING=utf-8 python _audit/fix_rule_map_lines.py --apply
"""
import argparse
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "FTS-RULE-ALGORITHM-MAP.md")
SRC = "api/chart.py"
NAMES = ["_fts_analyze_candles", "_fts_jet_setup", "_fts_analyze_symbol"]


def def_line(text, name):
    pat = re.compile(r"^def %s\(" % re.escape(name))
    for i, ln in enumerate(text.split("\n"), 1):
        if pat.match(ln):
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    src = io.open(os.path.join(ROOT, SRC), encoding="utf-8").read()
    doc = io.open(DOC, encoding="utf-8").read()
    out = doc
    changed = []
    for name in NAMES:
        real = def_line(src, name)
        if real is None:
            print("SKIP %s: تعریفش در %s پیدا نشد" % (name, SRC))
            continue
        cited = [int(m.group(1)) for m in re.finditer(
            re.escape(name) + r":(\d+)", out)]
        if not cited:
            print("SKIP %s: ارجاعی در سند ندارد" % name)
            continue
        if cited == [real] * len(cited):
            print("ok   %s: همان %d (بدون تغییر)" % (name, real))
            continue
        out = re.sub(re.escape(name) + r":\d+", "%s:%d" % (name, real), out)
        changed.append((name, sorted(set(cited)), real))
        print("FIX  %s: سند %s ⇒ سطرِ واقعی %s" % (name, sorted(set(cited)), real))

    if not changed:
        print("بی‌نیاز از اصلاح")
        return 0
    if not a.apply:
        print("(dry-run؛ با --apply بنویس)")
        return 0
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(out)
    print("written: %s (%d row fixed)" % (DOC, len(changed)))
    r = subprocess.run([sys.executable, "dev/test_rule_map_citations.py"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [ln for ln in (r.stdout or "").splitlines() if "FAIL" in ln or "passed" in ln]
    print("guard rc=%d" % r.returncode)
    for ln in tail[-6:]:
        print("   " + ln[:160])
    return r.returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
