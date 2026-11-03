# -*- coding: utf-8 -*-
# dev/tape_threshold_boundaries_v1.py — تستِ مرزیِ «زیر / رویِ / بالایِ» آستانه
#
# چرا: ماتریسِ پوشش (`docs/research/STRATEGY-FTS-SIGNAL-COVERAGE-MATRIX-2026-10-18.md` §۶)
# نشان داد پاریتیِ فرمول و فазِّ خوب سنجیده می‌شوند، ولی پنج ثابت هیچ آزمونِ
# مرزیِ یک‌واحدی ندارند: CLOCK_TRADES، SUSP_TRADES، NOQTEH_MAX_DIST،
# LEGAL_SHARE_OF_TVOL، ROOBI_QD1_MIN. رأیِ مالک (2026-10-18، پاسخ ۶): تستِ سه‌حالته
# اضافه شود و **هیچ ثابت، فرمول یا منطقِ اجرایی در این مرحله تغییر نکند**.
#
# روش: برای هر ثابت، یک ردیفِ سازنده که همهٔ قیدهایِ دیگرِ همان فیلتر را
# برآورده می‌کند، و تنها ستونِ سمتِ آستانه را رویِ سه مقدارِ زیر/رویِ/بالایِ
# عددِ فعلی می‌گذاریم. انتظار از **خودِ عملگرِ موجود** خوانده می‌شود (هر پنج
# قید `>` یا `<` بازهستند، پس «رویِ آستانه» مردود است) — عددِ انتظار از
# tape_flags کپی نمی‌شود، عملگرِ همان سطر خوانده می‌شود.
#
# ضدِ عبورِ صوری: درِ هر مجموعه دو شاهدِ اضافه هست — (الف) همان ردیف با ستونِ
# غایب (NaN) باید False بماند، (ب) ردیفِ «بالایِ آستانه» باید True شود؛ اگر
# fixture نتواند True بسازد، سبزشدنِ سه‌حالته بی‌معناست.

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import tape_flags as TF  # noqa: E402

FAILED: list[str] = []
PASSED = 0


def ck(cond: bool, msg: str) -> None:
    global PASSED
    print(("  ok   " if cond else "  FAIL ") + msg)
    if cond:
        PASSED += 1
    else:
        FAILED.append(msg)


def one(**cols) -> pd.DataFrame:
    """یک ردیف؛ هر ستونِ نگفته = غایب (نه صفرِ جعلی)."""
    return pd.DataFrame([{k: v for k, v in cols.items()}])


def flag(fn, cols: dict) -> bool:
    return bool(fn(one(**cols)).iloc[0])


def flag_raises(fn, cols: dict, drop: str) -> bool:
    """ستونی که فیلتر آن را **مستقیم** می‌خواند (`df["…"]`) اختیاری نیست:
    نبودش KeyError می‌دهد، نه False. این رفتارِ امروز است و اینجا ثبت می‌شود،
    چون کوئریِ تابلو آن ستون‌ها را همیشه می‌فرستد و `_col` فقط برایِ ستونِ
    اختیاری است."""
    row = dict(cols)
    row.pop(drop, None)
    try:
        fn(one(**row))
    except KeyError:
        return True
    return False


# ── ۱) CLOCK_TRADES — `z_tot_tran > CLOCK_TRADES` (باز) ───────────────────
# الگوی ساعت علاوه بر تعدادِ معامله: pc>0، pl>=pc*1.02، و نسبتِ حجمِ فایل > 1.
clock_base = dict(
    symbol="TEST1", p_closing=1000.0, p_last=1030.0,      # 3% بالا ⇒ >= 1.02 برمی‌خورد
    tvol=2000.0, prior30_vol=30000.0, hist_sessions=60,   # مبناء 1000 ⇒ نسبت 2.0 > 1
    z_tot_tran=float(TF.CLOCK_TRADES) - 1,
)
n = TF.CLOCK_TRADES
ck(flag(TF.clock_flag, {**clock_base, "z_tot_tran": n - 1}) is False, f"clock: tno={n-1:g} زیرِ آستانه ⇒ False")
ck(flag(TF.clock_flag, {**clock_base, "z_tot_tran": n}) is False, f"clock: tno={n:g} رویِ آستانه ⇒ False (عملگر بازهست)")
ck(flag(TF.clock_flag, {**clock_base, "z_tot_tran": n + 1}) is True, f"clock: tno={n+1:g} بالایِ آستانه ⇒ True")
ck(flag_raises(TF.clock_flag, clock_base, "z_tot_tran"),
   "clock: نبودِ ستونِ z_tot_tran ⇒ KeyError (ستونِ لازمِ کوئری است، نه اختیاری)")
ck(flag(TF.clock_flag, {**clock_base, "z_tot_tran": np.nan}) is False,
   "clock: z_tot_tranِ NaN ⇒ False (نه تطبیقِ خودکار)")
ck(flag(TF.clock_flag, {**clock_base, "z_tot_tran": n + 1, "p_last": 1005.0}) is False,
   "clock: با plِ زیرِ 1.02 حتی بالایِ آستانه هم True نمی‌شود (fixture تنها-شرطی نیست)")

# ── ۲) SUSP_TRADES — `z_tot_tran > SUSP_TRADES` (باز) ─────────────────────
susp_base = dict(symbol="TEST2", tvol=4000.0, prior30_vol=30000.0, hist_sessions=60)
n = TF.SUSP_TRADES
ck(flag(TF.suspicious_flag, {**susp_base, "z_tot_tran": n - 1}) is False, f"susp: tno={n-1:g} زیرِ آستانه ⇒ False")
ck(flag(TF.suspicious_flag, {**susp_base, "z_tot_tran": n}) is False, f"susp: tno={n:g} رویِ آستانه ⇒ False")
ck(flag(TF.suspicious_flag, {**susp_base, "z_tot_tran": n + 1}) is True, f"susp: tno={n+1:g} بالایِ آستانه ⇒ True")
ck(flag_raises(TF.suspicious_flag, susp_base, "z_tot_tran"),
   "susp: نبودِ ستونِ z_tot_tran ⇒ KeyError (همان قیدِ لازم)")
ck(flag(TF.suspicious_flag, {**susp_base, "z_tot_tran": np.nan}) is False, "susp: z_tot_tranِ NaN ⇒ False")
ck(flag(TF.suspicious_flag, {**susp_base, "z_tot_tran": n + 1, "tvol": 2500.0}) is False,
   "susp: نسبتِ حجمِ 2.5 (زیرِ SUSP_VOL_MULT) با tnoِ کافی True نمی‌شود")

# ── ۳) ROOBI_QD1_MIN — `qd1 > ROOBI_QD1_MIN` (باز) ────────────────────────
roobi_base = dict(
    symbol="TEST3", p_last=900.0, tmin=900.0,             # pl == tmin (آستانۀ مجازِ پایین)
    buy_q1_cnt=2.0,                                       # zd1 > 1
    plp_raw=-3.0,                                         # plp < -1
)
n = TF.ROOBI_QD1_MIN
ck(flag(TF.roobi_flag, {**roobi_base, "buy_q1_vol": n - 1}) is False, f"roobi: qd1={n-1:g} زیرِ آستانه ⇒ False")
ck(flag(TF.roobi_flag, {**roobi_base, "buy_q1_vol": n}) is False, f"roobi: qd1={n:g} رویِ آستانه ⇒ False")
ck(flag(TF.roobi_flag, {**roobi_base, "buy_q1_vol": n + 1}) is True, f"roobi: qd1={n+1:g} بالایِ آستانه ⇒ True")
ck(flag(TF.roobi_flag, {**roobi_base, "buy_q1_vol": np.nan}) is False,
   "roobi: qd1ِ NaN ⇒ False (ستونِ اختیاری؛ نبودش «سنجیده نشد» است نه تطبیق)")
ck(flag_raises(TF.roobi_flag, {**roobi_base, "buy_q1_vol": n + 1}, "p_last"),
   "roobi: نبودِ ستونِ p_last ⇒ KeyError (قیدِ لازمِ خودِ فیلتر)")
ck(flag(TF.roobi_flag, {**roobi_base, "buy_q1_vol": n + 1, "buy_q1_cnt": 1.0}) is False,
   "roobi: zd1=1 (نخوردِ >1) با qd1ِ کافی True نمی‌شود")

# ── ۴) NOQTEH_MAX_DIST — `dist < NOQTEH_MAX_DIST` (باز) ───────────────────
# dist = round((pc − min_low_29)/pc*100, 2)؛ pc=1000 ⇒ کمینه‌ها عددِ فاصله را مستقیم می‌دهند.
noqteh_base = dict(
    symbol="TEST4", p_closing=1000.0, tvol=2000.0, prior30_vol=30000.0,
    hist_sessions=60, z_tot_tran=10.0,                    # tno > NOQTEH_TRADES(5) و نسبتِ حجم > 1
)
n = TF.NOQTEH_MAX_DIST
ck(flag(TF.noqteh_flag, {**noqteh_base, "min_low_29": 1000.0 * (1 - (n - 0.1) / 100)}) is True,
   f"noqteh: فاصلۀ {n-0.1:g}٪ زیرِ آستانه ⇒ True")
ck(flag(TF.noqteh_flag, {**noqteh_base, "min_low_29": 1000.0 * (1 - n / 100)}) is False,
   f"noqteh: فاصلۀ {n:g}٪ رویِ آستانه ⇒ False (عملگر بازهست)")
ck(flag(TF.noqteh_flag, {**noqteh_base, "min_low_29": 1000.0 * (1 - (n + 0.1) / 100)}) is False,
   f"noqteh: فاصلۀ {n+0.1:g}٪ بالایِ آستانه ⇒ False")
ck(flag(TF.noqteh_flag, {**noqteh_base, "min_low_29": np.nan}) is False,
   "noqteh: min_low_29ِ NaN ⇒ False (ستونِ اختیاریِ کوئری)")
ck(flag(TF.noqteh_flag, {**noqteh_base, "min_low_29": 0.0}) is False,
   "noqteh: کمینۀ صفر (پنجرۀ ناقصِ کوئری) سنجیده نمی‌شود ⇒ False")
ck(flag(TF.noqteh_flag, {**noqteh_base, "min_low_29": 971.0, "hist_sessions": TF.LOW_BASE_SESSIONS - 1}) is False,
   "noqteh: با یکِ نشستِ کمتر از LOW_BASE_SESSIONS حتی فاصلۀ مناسب هم True نمی‌شود")

# ── ۵) LEGAL_SHARE_OF_TVOL — `buy_i_vol > 0.5*tvol` و `sell_n_vol > 0.5*tvol` ─
legal_base = dict(
    symbol="TEST5", tvol=1000.0, is6=300.0,               # 1.5*is6=450 < tvol ⇒ قیدِ حجمِ فایل
    hist_sessions=60, prior30_vol=30000.0,
    p_closing=1000.0, p_last=1000.0, plp_raw=2.0,          # pl>=pc و plp>0
    buy_count_i=1.0, sell_count_i=1.0, sell_i_vol=100.0,   # buyer_power = buy_i_vol/100 ≥ 1
    sell_n_vol=600.0,                                     # بالایِ نصفِ tvol، ثابت
)
n = TF.LEGAL_SHARE_OF_TVOL
half = n * legal_base["tvol"]
ck(flag(TF.legal_to_retail_flag, {**legal_base, "buy_i_vol": half - 1}) is False,
   f"legal: buy_i_vol={half-1:g} (زیرِ {n:g}×tvol) ⇒ False")
ck(flag(TF.legal_to_retail_flag, {**legal_base, "buy_i_vol": half}) is False,
   f"legal: buy_i_vol={half:g} (رویِ آستانه) ⇒ False")
ck(flag(TF.legal_to_retail_flag, {**legal_base, "buy_i_vol": half + 1}) is True,
   f"legal: buy_i_vol={half+1:g} (بالایِ آستانه) ⇒ True")
ck(flag(TF.legal_to_retail_flag, {**legal_base, "buy_i_vol": half + 1, "sell_n_vol": half}) is False,
   "legal: سمتِ حقوقی رویِ آستانه ⇒ False (هر دو قید لازم‌اند، یکی کافی نیست)")
ck(flag(TF.legal_to_retail_flag, {**legal_base, "buy_i_vol": half + 1, "is6": np.nan}) is False,
   "legal: is6ِ NaN (مبناءِ فایلِ خودِ سایت) سنجش را متوقف می‌کند ⇒ False")

# ── ۶) هیچ ثابتی درِ این گارد تکان نخورده ────────────────────────────────
now = dict(CLOCK_TRADES=TF.CLOCK_TRADES, SUSP_TRADES=TF.SUSP_TRADES,
           NOQTEH_MAX_DIST=TF.NOQTEH_MAX_DIST, LEGAL_SHARE_OF_TVOL=TF.LEGAL_SHARE_OF_TVOL,
           ROOBI_QD1_MIN=TF.ROOBI_QD1_MIN)
src = open(os.path.join(REPO, "tape_flags.py"), encoding="utf-8").read()
for k, v in now.items():
    ck(f"{k} = {v}" in src or f"{k} = {v:g}" in src or f"{k} = {int(v)}" in src,
       f"ثابتِ {k} درِ منبع همان {v:g} است (گارد عددی عوض نکرده)")

print()
if FAILED:
    print(f"tape_threshold_boundaries_v1: {PASSED} passed / {len(FAILED)} failed")
    sys.exit(1)
print(f"tape_threshold_boundaries_v1: {PASSED} passed / 0 failed")
