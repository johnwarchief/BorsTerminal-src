#!/usr/bin/env python
"""گاردِ طبقهٔ ابزار در سینکِ زنده.

سنجشِ زندهٔ ۲۰۲۶-۱۱-۰۳: پاسخِ paperType=8 سهامِ واقعی (شبندر، فولاد، …) را هم
برگرداند. `fetch_paper_types` با «rank ۸ > ۱» آن‌ها را صندوق ذخیره کرد و
تعداد سهام از ۱٬۳۳۵ به ۳۹۲ افتاد. `mstat_engine.classify` نام/سکتور را اول
می‌بیند و باید مرجعِ همین تصمیم باشد.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from test_tsetmc import fetch_paper_types


def row(ic, sym, name):
    # واقعیتِ پاسخِ TSETMC: lva = نماد (l_val18)، lvc = نام (l_val30).
    return {"insCode": ic, "lva": sym, "lvc": name}


ROWS = {
    1: [
        row("1", "شبندر", "پالايش نفت بندرعباس"),          # سهامِ واقعی
        row("2", "آوند", "صندوق س. آوند مفيد-د"),           # صندوق
        row("3", "ضجوا6000", "اختيارخ جوانه.ك-11000-05/06/25"),  # اختیار
        row("5", "اراد3154", "مرابحه عام دولت315-ش.خ070212"),      # اوراق
        row("6", "پاسارگاد", "صندوق س.درآمد ثابت پاسارگاد-د"),    # صندوق
    ],
    8: [
        row("1", "شبندر", "پالايش نفت بندرعباس"),          # همان سهام زیر pt=8
        row("2", "آوند", "صندوق س. آوند مفيد-د"),
    ],
    4: [
        row("4", "کگلح", "حق تقدم سنگ آهن گل گهر"),
    ],
}


def fake_getter(url):
    m = re.search(r"paperTypes\[0\]=(\d+)", url)
    pt = int(m.group(1)) if m else 0
    return ROWS.get(pt, [])


passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} — {detail}")


m = fetch_paper_types(fake_getter)
check("stock is 1 even when pt=8 also returns it", m.get("1") == 1, f"got {m.get('1')}")
check("fund is 8 even when pt=1 also returns it", m.get("2") == 8, f"got {m.get('2')}")
check("right is 4", m.get("4") == 4, f"got {m.get('4')}")
check("option is not stored as stock", m.get("3") is None, f"got {m.get('3')}")
check("bond is not stored as stock", m.get("5") is None, f"got {m.get('5')}")
check("fund is 8, not stock, when pt=1 also returns it", m.get("6") == 8, f"got {m.get('6')}")

print(f"\npaper_type_classify: {passed} passed / {failed} failed")
sys.exit(1 if failed else 0)
