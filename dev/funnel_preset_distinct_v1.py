# -*- coding: utf-8 -*-
"""dev/funnel_preset_distinct_v1.py — هر Preset predicateهایِ خودش را اعمال می‌کند.

اثباتِ قطعی (بدونِ اتکا بهِ دادهٔ روز): زنجیرۀِ فیلتر و دروازۀِ تکنیکالِ هر
Preset باید با دیگری فرق کند؛ وِگرنه «تغییرِ Preset» فقط عنوان است.
اجرا: PYTHONIOENCODING=utf-8 python dev/funnel_preset_distinct_v1.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import funnel_registry as REG  # noqa: E402

PASSED, FAILED = 0, []


def ck(label, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED.append(label)
        print(f"  FAIL {label}  {detail}")


swing = REG.preset_chain("swing")
trend = REG.preset_chain("trend")
hour = REG.preset_chain("hourglass")
ck("swing و trend زنجیرۀِ تابلوییِ متفاوت دارند", swing != trend, (swing, trend))
ck("swing با فیلترِ f_clock شروع می‌شود", swing and swing[0] == "f_clock", swing)
ck("trend با فیلترِ f_roobi شروع می‌شود", trend and trend[0] == "f_roobi", trend)
ck("hourglass زنجیرۀِ تابلویی ندارد (تفاوتِ predicate)", hour == (), hour)

# دروازۀِ تکنیکال هم باید فرق کند (hourglass ≠ trend)
g_swing = REG.PRESET_BY_ID["swing"].technical_gate
g_trend = REG.PRESET_BY_ID["trend"].technical_gate
g_hour = REG.PRESET_BY_ID["hourglass"].technical_gate
ck("hourglass دروازۀِ تکنیکالِ متفاوتی با trend دارد", g_hour != g_trend, (g_hour, g_trend))

# امضایِ قواعدِ هر preset یکتا باشد (نه سه کپیِ یکسان)
sigs = {pid: REG.preset_signature(pid) if hasattr(REG, "preset_signature") else None
        for pid in ("swing", "trend", "hourglass")}
if all(sigs.values()):
    ck("امضایِ سه preset متمایز است", len(set(sigs.values())) == 3, sigs)
else:
    ck("ترکیبِ chain+gate به‌تنهایی سه preset را متمایز می‌کند",
       len({(REG.preset_chain(p), REG.PRESET_BY_ID[p].technical_gate)
            for p in ("swing", "trend", "hourglass")}) == 3)

print(f"\nfunnel_preset_distinct_v1: {PASSED} passed / {len(FAILED)} failed")
sys.exit(1 if FAILED else 0)
