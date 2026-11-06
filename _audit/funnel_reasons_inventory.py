# -*- coding: utf-8 -*-
"""_audit/funnel_reasons_inventory.py — شمارشِ «دلیل»ها درِ تبِّ غربالگری

برایِ بندِ ۱۰ رأیِ مالک: چه چیزی درِ این تب بی‌دخانہ یا با «داده در دسترس
نیست» می‌آید و متنِ «دلیل» امروز چه می‌گوید. هیچ عددی نمی‌سازد؛ فقط
پاسخِ خودِ موتور را می‌شمارد.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from api.funnel import _run  # noqa: E402

P = _run("trend", [], "standard", {}, {}, full=True)
if P.get("status") != "success":
    print("no success:", P.get("message") or P.get("status"))
    sys.exit(1)

print("universe:", json.dumps(P.get("universe"), ensure_ascii=False))
print("coverage:", json.dumps(P.get("coverage"), ensure_ascii=False)[:900])

for stage in ("tape", "technical", "fundamental", "handover"):
    rows = (P.get("entries") or {}).get(stage) or []
    st = Counter()
    why = Counter()
    for r in rows:
        cell = ((P.get("status_matrix") or {}).get(r.get("symbol") or {}) or {}).get(stage) or {}
        st[cell.get("status") or "?"] += 1
        why[str(r.get("why") or {})] += 0  # placeholder, filled below
    print()
    print(f"== {stage}: {len(rows)} ردیفِ جدول ==")
    print("   statuses:", dict(st))

# «دلیل» همان human_reason درِ trace/coverage است؛ از matrix هم خوانده می‌شود
print()
print("== عللِ خروج (Z) ==")
print(json.dumps((P.get("universe") or {}).get("exclusion_counts"), ensure_ascii=False),
      json.dumps((P.get("universe") or {}).get("exclusion_labels"), ensure_ascii=False))

print()
print("== نمونه‌هایِ دلیلِ هر گام از خودِ entries ==")
for stage in ("tape", "technical", "fundamental", "handover"):
    rows = (P.get("entries") or {}).get(stage) or []
    seen = Counter()
    for r in rows:
        w = r.get("why") or {}
        txt = w.get(stage) if isinstance(w, dict) else None
        seen[str(txt)] += 1
    print(f"-- {stage}")
    for txt, n in seen.most_common(14):
        print(f"   {n:5d}  {txt}")
