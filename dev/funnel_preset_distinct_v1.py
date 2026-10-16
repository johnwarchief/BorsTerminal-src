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

# ── اثباتِ *خروجی*، نه فقط رجیستری ─────────────────────────────────────────
# چرا این بخش اضافه شد: متنِ بالا فقط «تعریف‌ها» را می‌خواند. درِ اجرایِ واقعی،
# `technical_gate` درِ هیچ کدی مصرف نمی‌شد (هیچ‌جا به `technical_stage` پاس داده
# نمی‌شد) و زنجیرۀ `hourglass` تهی بود — یعنی hourglass و custom[] عیناً یکِ
# خروجی می‌دادند و این گارد سبز بود. گاردی که شاخۀِ مرده را نبیند، گارد نیست.
# پس اینجا همان fixture کنترل‌شده از `FE.tape_stage`/`FE.technical_stage`ِ واقعی
# عبور می‌کند و خروجیِ هر preset مقابله می‌شود.
import funnel_engine as FE  # noqa: E402

FLAG_KEYS = ("f_clock", "f_jet", "f_susp", "f_roobi", "f_noqteh", "f_smart", "f_legal")


def _row(sym, **kw):
    base = {k: None for k in FLAG_KEYS}
    base.update({"symbol": sym, "tech_trend_w": None, "tech_trend_d": None,
                 "tech_matrix_decision": None, "tech_hourglass_active": None,
                 "tech_hourglass_action": None})
    base.update(kw)
    return base


# سه نماد، سه ترکیبِ عمداً جدا: یکی فقط زنجیرۀِ نوسان‌گیر را رد می‌شود، یکی فقط
# ساعتِ شنی را، یکی هر دو را — تا هیچ دو presetی نتوانند تصادفی هم‌رأی بمانند.
FIXTURE = [
    _row("الف", f_clock=1, f_jet=1, f_susp=1, f_roobi=0, f_noqteh=1,
          tech_trend_w="up", tech_trend_d="up", tech_matrix_decision="ENTRY_LONG",
          tech_hourglass_active=0, tech_hourglass_action="NONE"),
    _row("ب", f_clock=0, f_jet=1, f_susp=1, f_roobi=1, f_noqteh=1,
          tech_trend_w="down", tech_trend_d="up", tech_matrix_decision="REJECT",
          tech_hourglass_active=1, tech_hourglass_action="ACCUMULATE"),
    _row("پ", f_clock=1, f_jet=0, f_susp=1, f_roobi=1, f_noqteh=0,
          tech_trend_w="up", tech_trend_d="range", tech_matrix_decision="ENTRY_LONG",
          tech_hourglass_active=1, tech_hourglass_action="ACCUMULATE"),
]


def preset_output(pid, custom=()):
    """(بازماندگانِ تابلو، رأیِ هر نماد درِ گیتِ تکنیکال) — از خودِ موتور."""
    chain = REG.preset_chain(pid, custom)
    tape = FE.tape_stage([dict(r) for r in FIXTURE], chain)
    gate = REG.PRESET_BY_ID[pid].technical_gate
    tech = FE.technical_stage(list(tape["survivors"]), None, {}, gate=gate)
    return (tuple(sorted(str(r["symbol"]) for r in tape["survivors"])),
            tuple(sorted((d["symbol"], d["status"]) for d in tech["decisions"])))


o_swing = preset_output("swing")
o_trend = preset_output("trend")
o_hour = preset_output("hourglass")
o_custom = preset_output("custom")
o_custom_clock = preset_output("custom", ("f_clock",))

ck("swing و trend رویِ همین fixture خروجِ متفاوت می‌دهند (تابلو)",
   o_swing[0] != o_trend[0], (o_swing[0], o_trend[0]))
ck("hourglass با کپیِ custom[] نیست (تکنیکال)", o_hour != o_custom, (o_hour, o_custom))
ck("hourglass با کپیِ custom[] نیست (تابلو هم)",
   o_hour[0] != o_custom[0] or o_hour[1] != o_custom[1], (o_hour, o_custom))
ck("زنجیرۀِ دستیِ custom هم خروجِ خودش را می‌سازد (رجیستریِ URL نه فقط دکمه)",
   o_custom_clock != o_custom, (o_custom_clock, o_custom))
# ساعتِ شنیِ فعال باید درِ گیتِ خودش PASS شود، هرچند داورِ روند وتوش می‌کند
# (نماد «ب»: هفتگی نزولی + ساعتِ شنی فعال) — وگرنه گیتِ ساعتِ شنی فقط تزئین است.
ck("گیتِ ساعتِ شنی، وتویِ هفتگیِ داورِ روند را بازتولید نمی‌کند",
   ("ب", FE.PASS) in o_hour[1] and ("ب", FE.REJECT) in o_trend[1],
   (o_hour[1], o_trend[1]))
# کنترلِ منفی: اگر گیت دوباره نادیده گرفته شود (همان باگِ این دور)، ساعت‌شنی و
# custom هم‌رأی می‌شوند. این خط ثابت می‌کند سنسور آن را می‌بیند: دو گیت رویِ
# همین fixture رأیِ متفاوت تولید می‌کنند، پس کورِ یکسان‌شدن نیستیم.
_tech_trend = FE.technical_stage([dict(r) for r in FIXTURE], None, {}, gate=REG.TREND_GATE)
_tech_hour = FE.technical_stage([dict(r) for r in FIXTURE], None, {}, gate=REG.HOURGLASS_GATE)
_v = lambda tt: sorted((d["symbol"], d["status"]) for d in tt["decisions"])
ck("کنترلِ منفی: دو گیت رویِ همین fixture رأیِ متفاوت می‌دهند (گارد کور نیست)",
   _v(_tech_trend) != _v(_tech_hour), (_v(_tech_trend), _v(_tech_hour)))

print(f"\nfunnel_preset_distinct_v1: {PASSED} passed / {len(FAILED)} failed")
sys.exit(1 if FAILED else 0)
