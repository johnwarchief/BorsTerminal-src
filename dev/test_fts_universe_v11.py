# dev/test_fts_universe_v11.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fts_engine import classify_identity

CASES = [
    ("فولاد", "فلزات اساسي", "فولاد مباركه", True, "company", True),
    ("آگاه بازار", "", "", False, "non_company", False),
    ("آبين", "", "كشت و صنعت آبشيرين", True, "company", True),
    ("خیریه نمونه", "", "موسسه خیریه", True, "non_company", False),
    ("شپنا", "فراورده هاي نفتي", "پالايش نفت اصفهان", True, "company", True),
    # بیمه شرکت است، نه صندوق/غیرشرکت — با اینکه نامِ صنعتش «صندوق» دارد.
    ("آسیا", "بيمه وصندوق بازنشستگي به جزتامين اجتماعي", "بيمه آسيا",
     True, "company", True),
    # صندوقِ واقعی (صندوقِ سرمایه‌گذاری قابل معامله) → FTS ندارد.
    ("دارا یکم", "صندوق سرمايه گذاري قابل معامله", "دارا یکم",
     True, "fund", False),
]
failed = 0
for sym, sec, name, inst, kind, applicable in CASES:
    got = classify_identity(sym, sec, name, inst)
    ok = got["kind"] == kind and got["applicable"] is applicable and "reason" in got
    print(("OK  " if ok else "FAIL"), sym, got)
    failed += 0 if ok else 1
print("FAILURES", failed)
raise SystemExit(1 if failed else 0)
