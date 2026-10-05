# dev/tape_smartmoney_v1074.py — گاردِ دو فیلترِ تازه: پول هوشمند و کد به کد
#
# منبع، دو فایلِ جزوه درِ `docs/`اند:
#   ورود پول هوشمند.txt:
#     tvol > 1.5*Σ[ih][0..29]/30 && Buy_I/BuyCountI >= Sell_I/SellCountI
#     && pl >= pc && plp > 0            (هیچ قیدِ tno ندارد)
#   ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt: همان چهار قید
#     && Buy_I_Volume > 0.5*tvol && Sell_N_Volume > 0.5*tvol
#
# پاریتیِ تمام‌ست با متنِ فایل درِ `tools/tape_formula_parity.py` سنجیده می‌شود؛
# این سوئیت ماتریسِ حدی/بی‌داده/استثنایی را رویِ ردیفِ ساختگی می‌زند و
# سیم‌کشیِ رابط (schema/چیپ/قیف) را — تا نامِ ستون، همان زخمِ `f_roobi` را
# تکرار نکند.

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tape_flags import (LEGAL_SHARE_OF_TVOL, SMART_VOL_MULT, apply_tape_flags)  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAGS_PY = os.path.join(ROOT, "tape_flags.py")
MARKET_PY = os.path.join(ROOT, "api", "market.py")
ROW_TS = os.path.join(ROOT, "frontend", "src", "shared", "types", "marketRow.ts")
STORE_TS = os.path.join(ROOT, "frontend", "src", "features", "market", "stores", "tapeStore.ts")
FUNNEL_TS = os.path.join(ROOT, "frontend", "src", "features", "master", "lib", "ftsFunnel.ts")

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


def row(**over):
    """ردیفی که هر دو فیلتر را با هم می‌قبولد؛ بعد یک‌به‌یک می‌شکنیمش.

    مبناء: Σ[ih][0..29] = ۳۰M روی ۳۰ نشست = ۱M؛ tvol=۴M ⇒ ۴٫۰×.
    حقوقی: ۲٫۴M خرید روی ۱۰۰ سفارش در برابر ۱M فروش روی ۱۰۰ سفارش ⇒ سرانه ۲۴k ≥ ۱۰k
    و سهم ۲٫۴M > ۰٫۵×۴M (قیدِ کد به کد `>` است، نه `>=`).
    """
    base = {
        "symbol": "آزمون", "p_closing": 1000.0, "p_last": 1025.0,
        "percent_last": 4.6, "percent_change": 2.5, "price_yesterday": 980.0,
        "q_tot_tran": 4_000_000.0, "tvol": 4_000_000.0, "z_tot_tran": 120.0,
        "month_avg_vol": 1_000_000.0, "prev_day_vol": 2_000_000.0,
        "prior30_vol": 30_000_000.0, "hist_sessions": 60.0, "min_low_29": 995.0,
        "buy_i_vol": 2_400_000.0, "buy_count_i": 100.0,
        "sell_i_vol": 1_000_000.0, "sell_count_i": 100.0,
        "buy_n_vol": 2_000_000.0, "sell_n_vol": 3_000_000.0,
        "min30_low": 995.0, "tmin": 900.0, "tmax": 1100.0,
        "buy_q1_cnt": 8.0, "buy_q1_vol": 250_000.0,
    }
    for k in (2, 5, 9, 19, 29, 39, 49, 59):
        base[f"h{k}_max"] = 900.0
    base.update(over)
    return pd.DataFrame([base])


def flags(**over):
    return apply_tape_flags(row(**over)).iloc[0]


def sm(**over):
    return bool(flags(**over)["f_smart"])


def lg(**over):
    return bool(flags(**over)["f_legal"])


def main():
    # ── ۱) متنِ فایل == آستانه‌هایِ کد ───────────────────────────────────────
    ck(abs(SMART_VOL_MULT - 1.5) < 1e-12, "ضریبِ حجمِ پول هوشمند ۱٫۵ است (عینِ فایل)", str(SMART_VOL_MULT))
    ck(abs(LEGAL_SHARE_OF_TVOL - 0.5) < 1e-12, "سهمِ کد به کد نصفِ حجمِ نشست است (عینِ فایل)", str(LEGAL_SHARE_OF_TVOL))

    # ── ۲) مثبتِ هر دو ───────────────────────────────────────────────────────
    ck(sm(), "پول هوشمند: ردیفِ تمام‌شرط قبول است")
    ck(lg(), "کد به کد: با دو قیدِ سهم هم قبول است")

    # ── ۳) قیدها یکی‌یکی ─────────────────────────────────────────────────────
    ck(not sm(tvol=1_400_000.0, q_tot_tran=1_400_000.0, buy_i_vol=700_000.0, sell_n_vol=800_000.0),
       "حجمِ ۱٫۴× زیرِ آستانه رد است")
    ck(sm(tvol=1_500_001.0, q_tot_tran=1_500_001.0),
       "۱٫۵۰۰۰۰۱÷۱M درست بالای آستانه است (>)")
    ck(not sm(tvol=1_500_000.0, q_tot_tran=1_500_000.0),
       "دقیقاً ۱٫۵× رد است — فایل `>` می‌خواهد نه `>=`")
    ck(sm(buy_i_vol=2_000_000.0, sell_i_vol=2_000_000.0),
       "برابریِ سرانه (۲۰k >= ۲۰k) قبول است — فایل `>=` نوشته")
    ck(not sm(sell_i_vol=2_400_100.0),
       "سرانۀِ فروشِ یک‌واحد بالاتر از خرید ⇒ رد")
    ck(not sm(p_last=999.0), "pl < pc رد است")
    ck(sm(p_last=1000.0, percent_last=2.04), "pl == pc قبول است (>=)")
    ck(not sm(percent_last=0.0), "plp = 0 رد است (file: plp > 0)")
    # tno هیچ قیدی درِ این دو فایل نیست؛ با معاملاتِ کم هم باید قبول بماند
    ck(sm(z_tot_tran=3.0), "بی‌قیدِ tno: فایل چنین گیتی ندارد و ما اضافه نمی‌کنیم")

    # ── ۴) سهم‌هایِ کد به کد ─────────────────────────────────────────────────
    ck(sm(sell_n_vol=1_000_000.0) and not lg(sell_n_vol=1_000_000.0),
       "Sell_N = دقیقاً نصفِ حجم ⇒ پول هوشمند می‌ماند، کد به کد رد می‌شود (>)")
    ck(not lg(buy_i_vol=2_000_000.0, sell_i_vol=2_000_000.0, sell_n_vol=3_000_000.0),
       "Buy_I = نصفِ حجم ⇒ کد به کد رد")  # سرانه ۲۰k>=۲۰k می‌ماند ولی قیدِ سهم `>` است
    ck(lg() and sm(), "هر کد-به-کدِ قبولی پول هوشمند هم هست (نسخۀِ افزوده)")

    # ── ۵) بی‌داده ⇒ نسنجیده، نه صفرِ جعلی ───────────────────────────────────
    ck(not sm(prior30_vol=None), "مبناءِ غایب ⇒ سنجش نیست")
    ck(not sm(hist_sessions=10.0), "ده نشستِ سابقه ⇒ درِ سایت استثنا؛ اینجا هم نسنجیده")
    ck(not sm(buy_count_i=0.0, sell_count_i=0.0),
       "بی‌معاملۀِ حقوقی (۰/۰ = NaN درِ سایت) ⇒ رد، نه «قدرتِ متعادلِ» جعلی")
    ck(not sm(buy_i_vol=None, sell_i_vol=None), "ستونِ تهی ⇒ رد")

    # ── ۶) ردیفِ بیرونِ تابلو ⇒ هیچ‌وقت قبول ─────────────────────────────────
    ck(not sm(is_live=False), "فسیلِ بیرونِ تابلو درِ پول هوشمند نمی‌نشیند")
    ck(not lg(is_live=False), "فسیل درِ کد به کد هم نمی‌نشیند")

    # ── ۶-ب) plp خام در برابرِ نگهبانِ نمایشی (شاهدِ زنده ۱۳ آبان) ────────────
    # اختیارِ py=1 که به ۳ می‌رسد: سایت plp=+۲۰٪ می‌بیند و ردیف را فیلتر
    # می‌کند؛ `percent_last`ِ نمایشی همان را تهی می‌کند. فیلتر باید plp_raw
    # را بخواند، نه ستونِ سانسور‌شده را.
    from tape_flags import plp_series
    import pandas as _pd
    fr = plp_series(_pd.DataFrame([{"plp_raw": [200.0][0], "percent_last": None}]))
    ck(float(fr.iloc[0]) == 200.0, "plp_series خامِ plp_raw را به ستونِ سانسور‌شده ترجیح می‌دهد", str(fr.iloc[0]))
    fb = plp_series(_pd.DataFrame([{"percent_last": None}]))
    ck(_pd.isna(fb.iloc[0]), "بی‌plp_raw (کوئریِ قدیمی) ⇒ همان percent_lastِ تهی — بی‌ساختگی")
    ck(sm(price_yesterday=1.0, p_last=3.0, p_closing=3.0, percent_last=None, plp_raw=200.0),
       "اختیارِ py=1→+۲۰۰٪: با plp خام قبول است (سایت همین را می‌زند)")
    ck(sm(price_yesterday=4.0, p_last=9.0, p_closing=8.0, percent_last=None, plp_raw=125.0),
       "اختیارِ py=4→+۱۲۵٪: سقفِ ۱۰۰٪ِ نمایشی فیلتر را نمی‌کُشد")
    ck(not sm(price_yesterday=1.0, p_last=3.0, p_closing=3.0, percent_last=None),
       "بی‌plp_raw و percent_lastِ تهی ⇒ نسنجیده، نه صفرِ جعلی (منفیِ همان ردیف)")
    ck(not lg(price_yesterday=4.0, p_last=9.0, p_closing=8.0, percent_last=None,
              plp_raw=125.0, buy_i_vol=1_000_000.0),
       "منفیِ جهت‌دار: پول هوشمندِ درست با خریدِ حقوقیِ زیرِ نصفِ حجم ⇒ کد به کد رد")
    LAD8 = {f"h{k}_max": 8.0 for k in (2, 5, 9, 19, 29, 39, 49, 59)}
    flags_jet = apply_tape_flags(row(price_yesterday=4.0, p_last=9.0, p_closing=8.0,
                                     percent_last=None, plp_raw=125.0,
                                     tvol=12_000_000.0, q_tot_tran=12_000_000.0,
                                     **LAD8)).iloc[0]
    ck(bool(flags_jet["f_jet"]),
       "جت هم plp را خام می‌خواند: +۱۲۵٪ با پلکانِ شکسته قبول است")
    flags_rb = apply_tape_flags(row(p_last=900.0, tmin=900.0, price_yesterday=4000.0,
                                    percent_last=None, percent_change=-3.0,
                                    plp_raw=-77.5)).iloc[0]
    ck(bool(flags_rb["f_roobi"]),
       "کف‌روبی با plp خامِ منفیِ عمیق (اختیارِ ۴۰۰۰→۹۰۰ رویِ آستانه) قبول است")

    # ── ۷) سیم‌کشی — همان اشتباهِ نامِ ستونِ f_roobi تکرار نشود ───────────────
    fl = open(FLAGS_PY, encoding="utf-8").read()
    mk = open(MARKET_PY, encoding="utf-8").read()
    ck('"f_smart": smart_money_flag' in fl.replace(" = ", ": ", 0) or 'out["f_smart"] = smart_money_flag(out)' in fl,
       "پرچمِ پول هوشمند درِ apply_tape_flags ساخته می‌شود")
    ck('out["f_legal"] = legal_to_retail_flag(out)' in fl, "پرچمِ کد به کد درِ apply_tape_flags ساخته می‌شود")
    ck('("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal")' in mk,
       "کوئریِ تابلو هر هفت پرچم را رویِ ردیف می‌گذارد")
    ck('"f_smart", "f_legal"' in mk, "پاک‌سازیِ NaN هم دو تازه را پوشش می‌دهد")
    for name, path, needles in (
        ("marketRow", ROW_TS, ("f_smart: flag", "f_legal: flag")),
        ("tapeStore", STORE_TS, ("'f_smart'", "'f_legal'",
                                 "ورود پول هوشمند", "کد به کد")),
        # پلِ ورودِ قیف عمداً پنج‌گره‌ایِ چارت ۳ مانده — چکِ ضدِ تورمِ پیش‌فرض:
        ("ftsFunnel", FUNNEL_TS, ("const FILE_FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh']",)),
    ):
        src = open(path, encoding="utf-8").read()
        for needle in needles:
            ck(needle in src, f"رابطِ {name} کلیدِ «{needle}» را می‌شناسد (یک داوری، بی‌آینه)")

    print(f"\ntape_smartmoney_v1074: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
