#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v11.2.1 — گاردِ «یکِ شاخص، یکِ قاعده»: پهنایِ بازار و شمارشِ صف.

چرا این گارد متولد شد: درِ مأموریتِ تطبیقِ ۲۰۲۶-۱۰-۱۷ رویِ همان لحظه سنجیده شد
که «مثبت/منفی» رویِ یکِ صفحه دو عدد داشت — کارتِ دماسنج ۲۵۴/۷۴۹ و سریِ
تایم‌لاینِ ساخته‌شده از `snapshot_agg` ۳۴۳/۱۰۷۷. علت درِ قاعده بود نه درِ داده:
`thermometer` فقطِ نمادهایِ معامله‌شدهٔ داخلِ جامعۀ `in_category(group)` را
می‌شمرد، ولی `snapshot_agg` رویِ **همۀ** ردیف‌هایِ تابلو (بی‌فیلترِ حجم،
بی‌جامعه) می‌چرخید و صف‌ها را هم بی‌فیلترِ جامعه می‌شمرد. پس هر دو عدد «درست»
بودند و به دو چیزِ مختلف می‌گفتند، در حالی که رابط یکِ شاخصِ واحد نشان می‌دهد.

این گارد سه چیز را قفل می‌کند:
  ۱) کارت و نقطۀ تایم‌لاین از **همان** قاعده می‌آیند (تغییرِ قاعده ⇒ تغییرِ هر دو)
  ۲) قاعدۀ هر نقطه درِ خودِ نقطه ثبت می‌شود و `timeline` نقطه‌هایِ قاعدۀِ دیگر
     را درِ همان شاخص می‌پوشاند (نه اینکه دو قاعده را رویِ یکِ خط بگذارد)
  ۳) سنسورها کور نیستند: باِ کنترلِ منفی ثابت می‌شود که پوشاندن واقعاً باِ
     برچسبِ قاعده کار می‌کند، نه باِ تصادف.

داده: بانکِ درون‌حافظه‌ای باِ ردیف‌هایِ دست‌چین — هر انتظارِ عددیِ اینجا
حسابِ دستی است و درِ کنارِ همان سنجه نوشته شده.
اجرا:  python dev/mstat_breadth_basis_v1121.py
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import mstat_engine as ME            # noqa: E402
import test_tsetmc as TS             # noqa: E402

PASS = 0
FAIL = 0


def ck(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL", msg)
    return cond


DAY = 14040601
HR = 110000

# (کد، نماد، نام، paper_type، صنعت) — paper_type 6 = اختیارِ معاملات (بیرونِ
# جامعۀ `all`)، 4 = حق تقدم، 8 = صندوق (نوع از رویِ نام/صنعت خوانده می‌شود)
INS = [
    ("i_st1", "خا1", "سهام یکم", 1, "فلزات اساسي"),
    ("i_st2", "خا2", "سهام دوم", 1, "فلزات اساسي"),
    ("i_st3", "خا3", "سهام سوم", 1, "فلزات اساسي"),
    ("i_st6", "خا6", "سهام ششم", 1, "فلزات اساسي"),
    ("i_rt1", "حقا", "حق تقدم یک", 4, "سرمایه گذاريها"),
    ("i_fx1", "دينا", "صندوق س.درآمد ثابت دينا-د", 8, "صندوق سرمايه گذاري قابل معامله"),
    ("i_op1", "ضهرم1", "اختيارخ اهرم-1", 6, "صندوق سرمايه گذاري قابل معامله"),
]

# سطرهایِ تابلو: همه باِ قیمتِ دیروزِ ۱۰۰۰ و باندِ ۹۰۰/۱۱۰۰ تا `pct` قابلِ
# حسابِ دستی باشد. `buy_q_val=None` یعنی «عمقِ این نماد درِ بانک نیست».
ROWS = {
    # مثبتِ معامله‌شده + صف خریدِ یک‌طرفه (قفل در سقف)
    "i_st1": dict(p_closing=1100.0, p_last=1100.0, q_tot_tran=1e9,
                  allowed_max=1100.0, buy_q_vol=2e6, buy_q_val=2e9,
                  sell_q_vol=0.0, sell_q_val=0.0),
    # منفیِ معامله‌شده + صف فروشِ یک‌طرفه
    "i_st2": dict(p_closing=900.0, p_last=910.0, q_tot_tran=1e9,
                  buy_q_vol=0.0, buy_q_val=0.0, sell_q_vol=1e6, sell_q_val=1e9),
    # مثبت ولی **بی‌معامله** (حجم صفر) ⇒ درِ پهنایِ بازار نمی‌نشیند، درِ صف می‌نشیند
    "i_st3": dict(p_closing=1100.0, p_last=1100.0, q_tot_tran=0.0,
                  buy_q_vol=1e6, buy_q_val=5e8, sell_q_vol=0.0, sell_q_val=0.0),
    # مثبتِ معامله‌شده بی‌عمق ⇒ درِ پهنایِ بازار هست، درِ صف نه
    "i_st6": dict(p_closing=1050.0, p_last=1050.0, q_tot_tran=1e8,
                  buy_q_vol=None, buy_q_val=None, sell_q_vol=None, sell_q_val=None),
    # منفیِ معامله‌شده باِ دفترِ دوطرفه ⇒ هیچ صفی نیست
    "i_rt1": dict(p_closing=950.0, p_last=950.0, q_tot_tran=1e8,
                  buy_q_vol=1e5, buy_q_val=1e8, sell_q_vol=1e5, sell_q_val=1e8),
    # صفرِ واقعیِ صندوقِ درآمد ثابت + صف فروش ⇒ داخلِ جامعۀ `all`
    "i_fx1": dict(p_closing=1000.0, p_last=1000.0, q_tot_tran=1e8,
                  buy_q_vol=0.0, buy_q_val=0.0, sell_q_vol=1e6, sell_q_val=4e8),
    # اختیارِ معامله‌شدهٔ مثبت باِ صف خرید ⇒ بیرونِ جامعۀ `all` (هر دو شمارش)
    "i_op1": dict(p_closing=1100.0, p_last=1100.0, q_tot_tran=1e8,
                  buy_q_vol=1e6, buy_q_val=1e9, sell_q_vol=0.0, sell_q_val=0.0),
}


def new_db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    TS.create_schema(c)
    for ic, sym, nm, pt, sec in INS:
        c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code,"
                  " sector_name, total_shares, eps, pe, base_vol, updated_at, paper_type)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (ic, sym, nm, "68" if pt == 8 else "01", sec, 1e9, 100.0, 5.0,
                   1.0, "now", pt))
    for ic, over in ROWS.items():
        vals = {k: 0.0 for k in TS.MW_COLS}
        vals.update(dict(ins_code=ic, d_even=DAY, h_even=HR, price_min=900.0,
                         price_max=1100.0, allowed_min=900.0, allowed_max=1100.0,
                         price_yesterday=1000.0, price_first=1000.0, z_tot_tran=0.0,
                         price_change=0.0, total_shares=1e9, sector_code="01",
                         fetched_at="f"))
        vals.update(over)
        c.execute("INSERT INTO market_watch (%s) VALUES (%s)"
                  % (",".join(TS.MW_COLS), ",".join("?" * len(TS.MW_COLS))),
                  tuple(vals[k] for k in TS.MW_COLS))
    c.commit()
    return c


DB = new_db()

# ── ۱) حسابِ دستیِ جامعۀ درست، و حسابِ دستیِ قاعدۀ قدیم (کنترلِ واگرایی) ─────
rows_all = DB.execute("SELECT ins_code FROM market_watch WHERE d_even=?", (DAY,)).fetchall()
in_all = {r["ins_code"]: r for r in rows_all}
# پهنایِ درست: i_st1(+), i_st2(−), i_st6(+), i_rt1(−), i_fx1(0) — یعنی ۲/۲/۱
# قاعدۀ قدیم (همهٔ ردیف‌ها، بی‌فیلترِ حجم و جامعه): i_st3 و i_op1 هم مثبت
# شمرده می‌شدند ⇒ ۴/۲/۱. تفاوتِ ۲/۲/۱ با ۴/۲/۱ همانِ «۲۵۴/۷۴۹ در برابر ۳۴۳/۱۰۷۷» است.
ck(len(in_all) == 7, "فیکسچر هفت ردیف دارد (%s)" % len(in_all))

# ── ۲) کارت و نقطۀ تایم‌لاین رویِ ورودیِ یکسان یکی‌اند ──────────────────────
th = ME.thermometer(DB, "all")
ag = ME.snapshot_agg(DB)
dp = ME.depth(DB, "all")
ck((ag["pos"], ag["neg"], ag["zero"]) == (th["positive"], th["negative"], th["zero"]),
   "پهنایِ بازارِ تایم‌لاین == کارتِ دماسنج (%s/%s/%s در برابر %s/%s/%s)"
   % (ag["pos"], ag["neg"], ag["zero"], th["positive"], th["negative"], th["zero"]))
ck((ag["pos"], ag["neg"], ag["zero"]) == (2, 2, 1),
   "پهنایِ بازارِ دستِ‌انسانِ ۲/۲/۱ است (بی‌معامله و اختیار شمرده نشده)")
ck((ag["bq_n"], ag["sq_n"]) == (dp["buy_queue_count"], dp["sell_queue_count"]),
   "شمارِ صفِ تایم‌لاین == کارتِ عمق (خرید %s فروش %s در برابر %s/%s)"
   % (ag["bq_n"], ag["sq_n"], dp["buy_queue_count"], dp["sell_queue_count"]))
ck(abs(ag["bq_bt"] - dp["buy_queue_b_toman"]) < 0.05
   and abs(ag["sq_bt"] - dp["sell_queue_b_toman"]) < 0.05,
   "ارزشِ صفِ تایم‌لاین == کارتِ عمق (%s/%s میلیارد)" % (ag["bq_bt"], ag["sq_bt"]))
ck((ag["bq_n"], ag["sq_n"]) == (2, 2),
   "شمارِ صفِ دستِ‌انسان ۲/۲ است (i_op1 بیرونِ جامعه، i_st6 بی‌عمق)")
# جمعِ دستِ‌انسان: خرید = i_st1(2e9) + i_st3(5e8) + i_rt1(1e8، دوطرفه ولی دارایِ عمق)
# · فروش = i_st2(1e9) + i_fx1(4e8) + i_rt1(1e8). i_op1 بیرونِ جامعه است و i_st6 عمق ندارد.
Q_buy = 2e9 + 5e8 + 1e8
Q_sell = 1e9 + 4e8 + 1e8
ck(abs(ag["bq_bt"] - round(Q_buy / ME.B_TUMAN_FROM_RIAL, 1)) < 1e-9
   and abs(ag["sq_bt"] - round(Q_sell / ME.B_TUMAN_FROM_RIAL, 1)) < 1e-9,
   "ارزشِ صفِ تایم‌لاین = جمعِ دقیقِ ردیف‌هایِ جامعۀ `all` (خرید %s / فروش %s)"
   % (ag["bq_bt"], ag["sq_bt"]))
ck(round((Q_buy + 1e9) / ME.B_TUMAN_FROM_RIAL, 1) != ag["bq_bt"],
   "اگر i_op1 (اختیار) شمرده می‌شد عدد فرق می‌کرد — پس جامعۀ `all` واقعاً اعمال شده")

# ── ۳) کنترلِ واگرایی: فیکسچر واقعاً دو قاعده را از هم جدا می‌کند ────────────
# اگر این سنجه سبز نباشد، سنجه‌هایِ بالا هیچی نمی‌گویند: فیکسچر باید حالتی
# را بسازد که قاعدۀ قدیم **واضح** عددِ دیگری می‌داد (نه همان عدد را).
_rows, _meta = ME.enrich(DB)
loose_pos = loose_neg = loose_zero = 0
loose_bq = loose_sq = 0
for r in _rows:
    pct = r.get("pct")
    if pct is not None and pct > 0:
        loose_pos += 1
    elif pct is not None and pct < 0:
        loose_neg += 1
    elif pct == 0:
        loose_zero += 1
    q = r["_m"]["qstate"]
    if q == ME.ST_BUYQ:
        loose_bq += 1
    elif q == ME.ST_SELLQ:
        loose_sq += 1
ck((loose_pos, loose_neg, loose_zero) == (4, 2, 1),
   "قاعدۀ قدیم رویِ همین ورودی ۴/۲/۱ می‌داد (بی‌معامله و اختیار شمرده می‌شدند): %s/%s/%s"
   % (loose_pos, loose_neg, loose_zero))
ck((loose_pos, loose_neg) != (ag["pos"], ag["neg"]),
   "فیکسچر واگرایی را واقعاً می‌سازد، نه اینکه دو قاعده تصادفًا یکی شوند")
ck((loose_bq, loose_sq) == (3, 2) and loose_bq != ag["bq_n"],
   "قاعدۀ قدیمِ صف هم بیرونِ جامعه را می‌شمرد: %s/%s در برابر %s/%s"
   % (loose_bq, loose_sq, ag["bq_n"], ag["sq_n"]))

# ── ۴) برچسبِ قاعده درِ خودِ نقطه ثبت می‌شود ─────────────────────────────────
ck(ag.get("breadth_basis") == ME.BREADTH_BASIS == "cat_all_traded",
   "نقطه برچسبِ قاعدۀ پهنایِ بازار دارد (%s)" % ag.get("breadth_basis"))
ck(ag.get("queue_basis") == ME.QUEUE_BASIS == "cat_all_depth",
   "نقطه برچسبِ قاعدۀ صف دارد (%s)" % ag.get("queue_basis"))
for g in ("all", "eq_all", "stock_right"):
    ck(ME.thermometer(DB, g)["breadth_basis"] == "cat_%s_traded" % g
       and ME.depth(DB, g)["queue_basis"] == "cat_%s_depth" % g,
       "کارتِ همۀ تب‌ها قاعدۀ خودش را صریح اعلام می‌کند (%s)" % g)

# ── ۵) تک‌منبعِ قاعده: اگر `breadth_counts` عوض شود، **هر دو** سطح عوض می‌شود ─
_orig_counts = ME.breadth_counts
ME.breadth_counts = lambda sel: (99, 98, 97)
try:
    th_m = ME.thermometer(DB, "all")
    ag_m = ME.snapshot_agg(DB)
    ck(th_m["positive"] == 99 and ag_m["pos"] == 99,
       "هر دو سطح از یکِ تابع می‌شمارند (کارت=%s نقطه=%s)"
       % (th_m["positive"], ag_m["pos"]))
finally:
    ME.breadth_counts = _orig_counts
th_after = ME.thermometer(DB, "all")
ck(th_after["positive"] == 2, "بازگرداندنِ تابع، کارت را هم به ۲ برمی‌گرداند (%s)"
   % th_after["positive"])

# ── ۶) `timeline` نقطه‌هایِ قاعدۀ دیگر را درِ همان شاخص می‌پوشاند ───────────
TL = new_db()
legacy = dict(ag, h_even=105000)
legacy.pop("breadth_basis", None)
legacy.pop("queue_basis", None)
legacy["pos"], legacy["neg"] = 4, 2          # قاعدۀ قدیمِ بی‌فیلتر
TL.execute("INSERT OR REPLACE INTO mstat_snap (d_even,h_even,ts,agg) VALUES (?,?,?,?)",
           (DAY, 105000, "t", json.dumps(legacy)))
TL.execute("INSERT OR REPLACE INTO mstat_snap (d_even,h_even,ts,agg) VALUES (?,?,?,?)",
           (DAY, 111000, "t", json.dumps(dict(ag, h_even=111000))))
TL.commit()
tl = ME.timeline(TL, "cum")
ser = tl["series"]
ck(ser["pos"][0] is None and ser["pos"][1] == 2,
   "نقطۀ بی‌برچسب درِ سریِ پهنایِ بازار نمی‌نشیند (%s)" % ser["pos"])
ck(ser["bq_n"][0] is None and ser["bq_n"][1] == ag["bq_n"],
   "سریِ صف هم همان خط را می‌گیرد (%s)" % ser["bq_n"])
ck(ser["val_bt"][0] is not None and ser["val_bt"][1] is not None,
   "سری‌هایِ بی‌وابستگی (ارزشِ معامله) دست‌نخورده می‌مانند")
ck(tl["basis_dropped"].get("pos") == 1,
   "پوشاندن شمارش می‌شود و اعلام می‌شود (%s)" % tl["basis_dropped"])
ck(tl["basis"]["pos"] == ME.BREADTH_BASIS, "قاعدۀ جاریِ هر سری اعلام می‌شود")
ck(tl.get("note") and "قاعد" in tl["note"],
   "دلیلِ کم‌شدنِ نقاط به کاربر گفته می‌شود: %s" % tl.get("note"))
tli = ME.timeline(TL, "inst")
ck(tli["series"]["pos"][0] is None and tli["series"]["pos"][1] is None,
   "حالتِ لحظه‌ای از نقطۀ پوشیده‌شده شیبِ جعلی نمی‌سازد (%s)" % tli["series"]["pos"])

# ── ۷) کنترلِ منفی: اگر برچسب بی‌اثر شود، نقطۀ قدیمی نشت می‌کند ─────────────
_saved = dict(ME._SERIES_BASIS)
ME._SERIES_BASIS = {}
try:
    leak = ME.timeline(TL, "cum")["series"]["pos"]
    ck(leak[0] == 4, "کنترلِ منفی: بی‌برچسب‌سنجی، نقطۀ قاعدۀ قدیم نشت می‌کند (%s)" % leak)
finally:
    ME._SERIES_BASIS.clear()
    ME._SERIES_BASIS.update(_saved)
leak_after = ME.timeline(TL, "cum")["series"]["pos"]
ck(leak_after[0] is None, "سنسور پس از بازگردانی دوباره می‌بیند (%s)" % leak_after)

# ── ۸) نقشۀ ردیف‌به‌ردیفِ وضعیت‌ها عمداً کلِ تابلو می‌ماند ───────────────────
st = ME._dec_states(ag["st"])
ck("i_op1" in st, "نقشۀ وضعیتِ نمادها (فازها) جامعۀ `all` نیست و اختیار هم در آن است")

print("\n%d سنجه، %d خطا" % (PASS + FAIL, FAIL))
print("BREADTH BASIS GUARD " + ("OK" if FAIL == 0 else "FAILED"))
sys.exit(1 if FAIL else 0)
