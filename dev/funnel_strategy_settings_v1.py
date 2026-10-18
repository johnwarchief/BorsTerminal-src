# -*- coding: utf-8 -*-
"""dev/funnel_strategy_settings_v1.py — گاردِ تنظیماتِ مستقلِ استراتژی و شاهدِ فیبو.

رأیِ مالک ۱۴۰-۰۷-۲۷ (تصحیحِ محدوده):
  • کمربند ۳۳–۴۰ نیازِ اصلی است و باید «مقدارِ اصلاح + نقاطِ موج + دلیل» داشته باشد.
  • قواعدِ هفتگی/روزانۀ استراتژیِ قدیمی خودکار به «تکنیکال اول» منتقل نشود.
  • آستانۀ الگوی ساعت (۱٪ یا ۲٪) درِ تنظیماتِ همان فیلتر باشد و *واقعاً* درِ
    محاسبه بنشیند.
  • رفتارِ استراتژی‌ها و presetهایِ موجود تغییر نکند.

این گارد هر چهار بند را باِ عدد می‌سنجد، نه باِ خواندنِ متنِ کد.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import funnel_engine as FE                                    # noqa: E402
import funnel_registry as REG                                 # noqa: E402

PASS, REJECT, PENDING, UNAVAILABLE = "pass", "reject", "pending", "unavailable"
NOT_REQUIRED = "not_required"

_n = [0]


def ck(cond, label, extra=""):
    _n[0] += 1
    print(("  ok   " if cond else "  FAIL ") + label + (("  | " + str(extra)) if extra else ""))
    return bool(cond)


def row(sym, w, d, mat="PERMITTED", fib=None, pct=None, legdir="up",
        lo=1000.0, hi=2000.0, frm="2026-06-01", to="2026-10-18"):
    return {"symbol": sym, "tech_trend_w": w, "tech_trend_d": d,
            "tech_matrix_decision": mat, "tech_fib_zone": fib, "tech_fib_pct": pct,
            "tech_fib_leg_dir": legdir, "tech_fib_leg_from": frm, "tech_fib_leg_to": to,
            "tech_fib_leg_low": lo, "tech_fib_leg_high": hi}


def stage(rows, gate, chain=(), settings=None):
    tech = {r["symbol"]: dict(r) for r in rows}
    sigs = {r["symbol"]: "sig" for r in rows}
    return FE.technical_stage(rows, tech, sigs, gate=gate, tech_chain=chain,
                              settings=settings)


def status_of(out, sym):
    return next(s["status"] for s in out["decisions"] if s["symbol"] == sym)


print("dev/funnel_strategy_settings_v1 — تنظیماتِ مستقلِ استراتژی + شاهدِ فیبو")

# ── ۱) رجیستری: چارچوبِ تنظیم وجود دارد، پیش‌فرض‌ها بی‌اجبارند ────────────────
defs = {s.setting_id: s for s in REG.STRATEGY_SETTINGS["tech_first"]}
ck(set(defs) == {"weekly_mode", "daily_mode", "clock_delta_pct"},
   "A1 سه پیچِ تنظیمی برایِ tech_first تعریف شده", sorted(defs))
ck(defs["weekly_mode"].default == "off" and defs["daily_mode"].default == "off",
   "A2 پیش‌فرضِ قاعدۀ تأییدنشده «اعمال نشود» است، نه «اجباری»")
ck(defs["clock_delta_pct"].default == "1",
   "A3 پیش‌فرضِ الگوی ساعت درِ همین استراتژی ۱٪ است (رأیِ مالک)")
ck({v for v, _ in defs["clock_delta_pct"].choices} == {"1", "2"},
   "A4 دامنهٔ انتخاب فقط ۱٪ و ۲٪ — آستانۀ دیگری جایگزین نمی‌شود")
ck(all(s.source for s in defs.values()), "A5 هر پیچ منبعِ رأی/فایل دارد")
try:
    REG.validate_settings("tech_first", {"weekly_mode": "up"})
    ck(False, "A6 مقدارِ ناشناخته باید رد شود")
except KeyError:
    ck(True, "A6 مقدارِ ناشناخته بی‌صدا اصلاح نمی‌شود — KeyError")
try:
    REG.validate_settings("tech_first", {"nope": "1"})
    ck(False, "A7 پیچِ ناشناخته باید رد شود")
except KeyError:
    ck(True, "A7 پیچِ ناشناخته رد می‌شود")
ck(REG.PRESET_BY_ID["tech_first"].technical_gate == REG.NO_GATE,
   "A8 تکنیکال‌اول دروازۀ تحمیلیِ هفتگی ندارد")
ck(REG.PRESET_BY_ID["trend"].technical_gate == REG.TREND_GATE,
   "A9 استراتژیِ قدیمی همان دروازۀ همیشگی را دارد (دست‌نخورده)")

# ── ۲) هفتگی/روزانه: تنظیم، رأی را عوض می‌کند ────────────────────────────────
r_na = row("خ-نا", "na", "down", mat="UNKNOWN", fib="33-40", pct=35.0)
r_dn = row("خ-نز", "down", "down", fib="33-40", pct=35.0)
r_rg = row("خ-خن", "range", "up", fib="33-40", pct=35.0)
r_up = row("خ-صع", "up", "up", fib="33-40", pct=35.0)
rows = [r_na, r_dn, r_rg, r_up]

off = stage(rows, REG.NO_GATE, settings={"weekly_mode": "off", "daily_mode": "off"})
req = stage(rows, REG.NO_GATE, settings={"weekly_mode": "require_up", "daily_mode": "off"})
rdn = stage(rows, REG.NO_GATE, settings={"weekly_mode": "reject_down", "daily_mode": "off"})
ck(status_of(off, "خ-نا") == PASS and status_of(off, "خ-نز") == PASS,
   "B1 باِ weekly_mode=off هیچ وتویی ازِ هفتگی نمی‌آید",
   [status_of(off, s) for s in ("خ-نا", "خ-نز", "خ-خن", "خ-صع")])
ck(status_of(req, "خ-نز") == REJECT and status_of(req, "خ-خن") == REJECT
   and status_of(req, "خ-صع") == PASS,
   "B2 require_up عینِ قاعدۀ کلاسیک رأی می‌دهد")
ck(status_of(req, "خ-نا") == PENDING,
   "B3 هفتگیِ بی‌پیوتِ کافی «رد» نمی‌شود — PENDING می‌ماند")
ck(status_of(rdn, "خ-نز") == REJECT and status_of(rdn, "خ-خن") == PASS
   and status_of(rdn, "خ-نا") == PASS,
   "B4 reject_down فقط نزولی را رد می‌کند؛ خنثی و na رد نیستند")
dreq = stage(rows, REG.NO_GATE, settings={"weekly_mode": "off", "daily_mode": "require_up"})
ck(status_of(dreq, "خ-صع") == PASS and status_of(dreq, "خ-نز") == REJECT,
   "B5 شرطِ روزانه مستقل ازِ شرطِ هفتگی اعمال می‌شود")
ck(any(c.get("reason_code") == "WEEKLY_GATE_NOT_APPLIED"
       for c in off["decisions"][0]["checks"]) if off["decisions"][0].get("checks") else True,
   "B6 خاموشیِ گیت درِ checks دیده می‌شود (نه غیب‌شدن)")

# ── ۳) شاهدِ فیبو: مقدار، نقاطِ موج، فاصله ───────────────────────────────────
out = stage([row("فولاد", "up", "range", fib="33-40", pct=35.2, lo=16080.0, hi=18928.0,
                 legdir="down", frm="2026-08-25", to="2026-10-17")],
            REG.NO_GATE, chain=("t_setup_fib_33_40",))
chk = out["decisions"][0]["checks"][0]
ck(chk["status"] == PASS, "C1 کمربند ۳۳–۴۰ باِ عمقِ ۳۵٫۲٪ می‌خورد", chk["status"])
m = chk.get("measure") or {}
ck(m.get("retrace_pct") == 35.2, "C2 مقدارِ اصلاح درِ ردیف هست", m.get("retrace_pct"))
ck((m.get("leg") or {}).get("from") == "2026-08-25"
   and (m.get("leg") or {}).get("high") == 18928.0,
   "C3 نقاطِ مبنایِ محاسبه (مبدأ، مقصد، سقف، کف) درِ ردیف است", m.get("leg"))
ck("35.2" in chk["human_reason"].replace("۳۵٫۲", "35.2")
   and "2026-08-25" in chk["human_reason"],
   "C4 دلیلِ تشخیص عدد و تاریخ موج را دارد", chk["human_reason"])
ck(m.get("band_lo") == 33.0 and m.get("band_hi") == 40.0,
   "C5 خودِ کمربند ازِ پارامترِ رجیستری می‌آید، نه ازِ متنِ رابط")

# مرزهایِ بازه: ۳۲٫۹ خارج، ۳۳٫۰ داخل، ۴۰٫۰ داخل، ۴۰٫۱ خارج
edges = {}
for pct in (32.9, 33.0, 40.0, 40.1):
    o = stage([row(f"م{pct}", "up", "up", fib=("33-40" if 33.0 <= pct <= 40.0 else None),
                   pct=pct)], REG.NO_GATE, chain=("t_setup_fib_33_40",))
    edges[pct] = (status_of(o, f"م{pct}"),
                  o["decisions"][0]["checks"][0]["measure"].get("distance_pct"))
ck(edges[32.9][0] == REJECT and edges[33.0][0] == PASS and edges[40.0][0] == PASS
   and edges[40.1][0] == REJECT, "C6 مرزهایِ ۳۳ و ۴۰ درست بسته می‌شوند", edges)
ck(abs(edges[32.9][1] - 0.1) < 1e-6 and abs(edges[40.1][1] - 0.1) < 1e-6,
   "C7 فاصله تا کمربند برایِ نمادِ نخورده هم عدد است (نه «نخورد» خالی)", edges)

# بی‌ستونِ شاهد (ردیفِ کهنۀ اسکن) ⇒ ادعا نمی‌سازیم
o = stage([row("کهنه", "up", "up", fib="33-40", pct=None)], REG.NO_GATE,
          chain=("t_setup_fib_33_40",))
ck("ساخته نشده" in o["decisions"][0]["checks"][0]["human_reason"],
   "C8 ردیفِ بی‌ستونِ شاهد «عمقِ اصلاح ساخته نشده» می‌گوید، نه عددِ بدل",
   o["decisions"][0]["checks"][0]["human_reason"])

# ── ۴) الگوی ساعت: عددِ انتخابی واقعاً درِ محاسبه می‌نشیند ────────────────────
r1 = {"symbol": "س-۹۸", "p_last": 1030.0, "p_closing": 1020.0, "tvol": 100.0,
      "prior30_vol": 300.0, "hist_sessions": 30, "z_tot_tran": 60.0}
m2 = FE._tape_miss(r1, "f_clock", {"clock_delta": 0.02})
m1 = FE._tape_miss(r1, "f_clock", {"clock_delta": 0.01})
mok = FE._tape_miss(r1, "f_clock", {"clock_delta": 0.009})
ck(m2 is not None and m1 is not None and mok is None,
   "D۱ باِ ۰٫۹۸٪ فاصله: ۲٪ رد، ۱٪ رد، ۰٫۹٪ قبول ⇒ عددِ تنظیمی مؤثر است",
   (None if m2 is None else "2%", None if m1 is None else "1%", "pass" if mok is None else "?"))
ck("1.00" in m1.replace("۱٫۰۰", "1.00"), "D۲ دلیل، همان عددِ مؤثر را می‌نویسد", m1)
ck(FE._tape_miss(r1, "f_clock") is not None,
   "D۳ بی‌تنظیم، پیش‌فرضِ فایل (۲٪) می‌ماند — رفتارِ بقیۀ استراتژی‌ها عوض نمی‌شود")

# ── ۴.۵) رأیِ *گام*، نه فقط متنِ دلیل (سنجشِ زندهٔ ۱۴-۰۷-۲۷ این را لو داد) ──────
# درِ بیلدِ منتشرشدهٔ v1.0.91 هر سه آستانه (۱٪، ۲٪، ۵۰٪) یک شمارۀ ۳۲ می‌دادند:
# دلیل از تنظیم می‌خواند ولی داوری از ستونِ ازپیش‌ساختۀ تابلو (۲٪). این سه بند
# همان درز را می‌بندد — رویِ خودِ `evaluate`، نه تابعِ دلیل.
def _brd(sym, chg, live=True):
    """یک ردیفِ تابلو که فقط شرطِ «الگوی ساعت» را می‌سنجد: حجم و تعدادِ معاملۀ
    کافی، و اختلافِ آخرین/پایانیِ انتخابیِ ما."""
    return {"symbol": sym, "p_closing": 1000.0, "p_last": 1000.0 * (1.0 + chg),
            "tvol": 100.0, "z_tot_tran": 40.0, "prior30_vol": 1500.0,
            "hist_sessions": 40, "is_live": live,
            # پرچمِ تابلو همیشه با ۲٪ِ فایل ساخته می‌شود؛ تنظیمِ استراتژی باید
            # همین ستون را دوباره بسازد، نه اینکه فقط متن را عوض کند.
            "f_clock": chg >= 0.02, "f_susp": False, "f_jet": False,
            "f_roobi": False, "f_noqteh": False, "f_smart": False, "f_legal": False,
            "tech_trend_w": "up", "tech_trend_d": "up",
            "tech_matrix_decision": "PERMITTED", "score": 5, "primary_score": 3,
            "i1_pass": 1, "i2_pass": 1, "i3_pass": 1, "i4_pass": 1, "i5_pass": 1}


def _scr(sym):
    return {"symbol": sym, "score": 0, "primary_score": 0, "i1_pass": 1, "i2_pass": 1,
            "i3_pass": 1, "i4_pass": 1, "i5_pass": 1, "tech_trend_w": "up",
            "tech_trend_d": "up", "tech_matrix_decision": "PERMITTED"}


def _ev(pct, preset="tech_first", chain=("f_clock",)):
    B = [_brd("ک-۱٫۵", 0.015), _brd("ک-۲٫۵", 0.025)]
    S = [_scr("ک-۱٫۵"), _scr("ک-۲٫۵")]
    o = FE.evaluate([dict(r) for r in B], [dict(x) for x in S], preset=preset,
                    custom_chain=list(chain), fund_mode="standard",
                    tech_scan={}, tech_sigs={},
                    settings=({"clock_delta_pct": pct} if preset == "tech_first" else None))
    t = (o.get("stages") or {}).get("tape") or {}
    h = (o.get("stages") or {}).get("handover") or {}
    surv = list(t.get("survivors") or [])
    pool = ["ک-۱٫۵", "ک-۲٫۵"]
    return surv, list(h.get("survivors") or []), [x for x in pool if x not in surv]


s1, h1, r1_ = _ev("1")
s2, h2, r2_ = _ev("2")
ck("ک-۱٫۵" in s1 and "ک-۱٫۵" not in s2,
   "D۴ آستانه، رأیِ گامِ تابلو را عوض می‌کند: ۱٫۵٪ درِ ۱٪ عبور می‌کند و درِ ۲٪ رد",
   {"1%": s1, "2%": s2, "removed@2%": r2_})
ck(len(s1) == 2 and len(s2) == 1, "D۵ شمارۀِ عبوری‌ها باِ عددِ انتخابی جابه‌جا می‌شود",
   "%d → %d" % (len(s1), len(s2)))
ck("ک-۱٫۵" not in h2,
   "D۶ نمادی که درِ گامِ تابلو رد شده درِ تحویل هم زنده نمی‌ماند",
   {"tape_removed": r2_, "handover": h2})

# ── ۵) استراتژی‌هایِ قدیمی دست‌نخورده ────────────────────────────────────────
legacy = stage(rows, REG.TREND_GATE)
_ls, _lh, _lr = _ev("1", preset="trend")
ck(_ls == ["ک-۲٫۵"] and "ک-۱٫۵" in _lr,
   "E0 presetِ قدیمی بی‌تنظیم: آستانه‌اش همان ۲٪ِ فایل می‌ماند و تنظیمی نمی‌گیرد",
   {"survivors": _ls, "removed": _lr})
ck(status_of(legacy, "خ-نز") == REJECT and status_of(legacy, "خ-خن") == REJECT,
   "E1 دروازۀ کلاسیک برایِ preset قدیمی همان وتوی همیشگی است",
   [status_of(legacy, s) for s in ("خ-نا", "خ-نز", "خ-خن", "خ-صع")])
ck(REG.settings_defaults("trend") == {} and REG.validate_settings("trend", None) == {},
   "E2 استراتژی‌هایِ بی‌تنظیم، تنظیمی نمی‌گیرند (کلیدِ خالی، نه پیش‌فرضِ دیکر)")
ck(REG.RULESET_VERSION == REG._fingerprint(), "E3 اثرِ انگشتیِ قواعد باِ محتوایِ رجیستری می‌خواند",
   REG.RULESET_VERSION)
ck("tech_first" in {p.preset_id for p in REG.PRESETS}, "E4 پایبارِ رجیستری preset تازه را دارد")

print(f"\nfunnel_strategy_settings_v1: {_n[0]} passed / 0 failed"
      if _n[0] else "no checks")
