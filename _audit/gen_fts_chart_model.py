# -*- coding: utf-8 -*-
"""_audit/gen_fts_chart_model.py — تولیدِ `ftsChartModel.ts` از جدولِ فعلیِ گراف

چرا مکانیکی: متن/فرمولِ قاعده/آستانه‌های ۴۶ گره باید **بایت‌به‌بایت** به مدلِ تازه
برود. هر بازنویسیِ دستیِ متنِ فارسی، رقم می‌دزدد (قیدِ شکست‌پذیرِ AGENTS.md) و هیچ
تفاوتِ معنایی‌ای هم ندارد. پس این اسکریپت literalهایِ موجود را از
`_audit/strategy_graph_dump.json` برمی‌دارد، میدان‌هایِ مختصاتِ دستیِ `x/y/radius`
و `stage/stageName/category` را (که جایِ خود را به `zone/parent/order` می‌دهند)
حذف می‌کند و `zone + parent + order + origin + refs` را از جدولِ زیر می‌چسباند.

جدولِ parent از سطرهایِ خودِ چهار صفحۀ چاپی است
(`docs/fts-notes/FTS_CHART3_extracted_text.txt`، حسابرسیِ خط‌به‌خط:
`docs/CHART-FOUR-PAGES-PARITY.md`) — هیچ رابطۀ حدسی اضافه نشده. مفهومی که درِ چند
صفحه تکرار شده یکِ گره می‌ماند و با `refs` (خط‌چینِ «هم‌نام») به آن صفحه‌ها وصل
می‌شود، نه با ساختنِ نسخۀ دوم یا رابطۀ ساختاریِ جعلی.

`PRESET_ACTIVE` عینِ فهرستِ `activeNodes` درِ `routes/StrategyTreePage.tsx` است
(تکلیفِ پرست‌ها از برنامه، نه از این اسکریپت) — فقط به یک منبع منتقل شد.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, "_audit", "strategy_graph_dump.json")
OUT = os.path.join(ROOT, "frontend", "src", "features", "master", "lib", "ftsChartModel.ts")

# (zone, parent, order, origin, refs) — order = ترتیبِ سطر درِ خودِ چارت
MAP = {
    # ── صفحۀ ۱ (F): پنج سطرِ شاخصِ کدال + طبقه‌بندیِ امتیاز که درِ جزوه نیست ──
    "crit_sales_growth":    ("F", "f_root", 1, "chart", []),
    "crit_3y_eps":          ("F", "f_root", 2, "chart", []),
    "crit_gross_margin":    ("F", "f_root", 3, "chart", []),
    "crit_ps_ratio":        ("F", "f_root", 4, "chart", []),
    "crit_pricing_regime":  ("F", "f_root", 5, "chart", []),
    "fund_super":           ("F", "f_tiers", 1, "program", []),
    "fund_good":            ("F", "f_tiers", 2, "program", []),
    "fund_medium":          ("F", "f_tiers", 3, "program", []),
    "fund_weak":            ("F", "f_tiers", 4, "program", []),
    # ── صفحۀ ۲ (T): سیگنال خرید ⇒ فروش ⇒ حد ضرر ──
    "tech_weekly_reject":   ("T", "t_buy", 1, "chart", []),
    "tech_weekly_up":       ("T", "t_buy", 2, "chart", []),
    "setup_pullback":       ("T", "t_daily_up", 1, "chart", ["m_strategy"]),
    "setup_jet":            ("T", "t_daily_up", 2, "chart", ["m_strategy"]),
    "setup_fib":            ("T", "t_daily_down", 1, "chart", []),
    "setup_choch":          ("T", "t_daily_down", 2, "chart", []),
    "setup_last_low":       ("T", "t_daily_neutral", 1, "chart", []),
    "setup_double_bottom":  ("T", "t_sell", 1, "chart", []),
    "setup_double_top":     ("T", "t_sell", 2, "chart", []),
    # چارت: «سقفسوم…»، «واگراییمقاومتی» زیرِ سیگنالِ فروشِ صفحۀ ۲ — برچسبِ `page`
    # این دو گره درِ جدولِ پیشین «چارت صفحه ۴» است؛ ابهامِ موجود دست‌نخورده ماند.
    "exit_third_peak":      ("T", "t_sell", 3, "chart", ["m_stop_kind"]),
    "exit_rsi_div":         ("T", "t_sell", 4, "chart", ["m_stop_kind"]),
    # ── صفحۀ ۳ (S): سبک ⇒ نقدینگی ⇒ صنایع ⇒ حجم ⇒ الگوها ⇒ خشک کردن ──
    "tape_market_liquidity": ("S", "s_arena", 1, "chart", []),
    "tape_breadth":          ("S", "s_arena", 2, "chart", []),
    "tape_flow_charts":      ("S", "s_liquidity", 2, "chart", []),
    "tape_smart_money":      ("S", "s_liquidity", 3, "chart", []),
    "tape_industries_picks": ("S", "s_industries", 1, "chart", []),
    "tape_volume":           ("S", "s_volume_swing", 1, "chart", ["m_reverse_tape"]),
    "tape_volume_trend":     ("S", "s_volume_trend", 1, "chart", []),
    "tape_clock":            ("S", "s_patterns_swing", 1, "chart", ["m_reverse_tape"]),
    "tape_breakout":         ("S", "s_patterns_swing", 2, "chart", []),
    "tape_floor_sweep":      ("S", "s_patterns_trend", 1, "chart", ["m_reverse_tape"]),
    "tape_final_filters":    ("S", "s_dry", 1, "chart",
                              ["tape_clock", "setup_jet", "tape_volume", "tape_floor_sweep"]),
    "setup_point_hunt":      ("S", "s_dry", 2, "chart", ["m_strategy"]),
    # ── صفحۀ ۴ (M): مهندسی معکوس ⇒ مدیریت سرمایه ⇒ رصد ⇒ تناسب ⇒ استراتژی ──
    "rule_max_portfolio":    ("M", "m_money", 1, "chart", []),
    "m_weighting":           ("M", "m_money", 2, "chart", []),
    "hedge_options_etf":     ("M", "m_money", 3, "chart", []),
    "stop_swing":            ("M", "m_stop_kind", 1, "chart", ["t_stop"]),
    "stop_trend":            ("M", "m_stop_kind", 2, "chart", ["t_stop"]),
    "m_ladder":              ("M", "m_money", 4, "chart", []),
    "tech_weekly_hourglass": ("M", "m_ladder", 1, "chart", ["m_strategy"]),
    "stop_hourglass":        ("M", "m_ladder", 2, "chart", ["m_strategy"]),
    "exit_half":             ("M", "m_ladder", 3, "program", []),
    "rule_cap":              ("M", "m_money", 5, "program", []),
    "rule_rr":               ("M", "m_money", 6, "program", []),
    "m_review":              ("M", "m_monitor", 1, "chart", []),
    "m_principles":          ("M", "m_fit", 1, "chart", []),
}

# سرِ شاخه‌هایی که خودِ چارت نام دارد و درِ جدولِ ۴۶گانۀ گره نداشت (تروی‌نویسِ
# سطرهایِ جزوه، نه اختراع). فیلدها: id, zone, parent, order, label, fullTitle,
# صفحه, توضیح, قاعدۀ چارت, refs
HEADS = [
    ("f_root", "F", None, 0, "F: بنیادی",
     "صفحۀ ۱ چارت FTS — غربالگری بنیادی پنج‌شاخصه",
     "چارت صفحه ۱",
     "ریشۀ صفحۀ اول: پنج سطرِ شاخصِ کدال. هیچ شاخصی درِ اینجا محاسبه نمی‌شود؛ "
     "داوری از `api/fundamental.py::evaluate_v10` می‌آید.",
     "۵ شاخص ← امتیاز ۱ تا ۵", []),
    ("f_tiers", "F", "f_root", 6, "طبقه‌بندی امتیاز",
     "طبقه‌بندیِ چهارگانهٔ امتیازِ بنیادی",
     "چارت صفحه ۱",
     "درِ جزوه این چهار طبقه سطر ندارد؛ از منطقِ برنامه است (سوپر/مطلوب/متوسط/رد "
     "صلب) و رأی‌اش از موتورِ بنیادی سرور می‌آید.",
     "برنامۀ FTS، نه سطرِ چارت", []),
    ("t_root", "T", None, 0, "T: تکنیکال",
     "صفحۀ ۲ چارت FTS — سیگنال خرید و فروشِ دو زمانه",
     "چارت صفحه ۲",
     "ریشۀ صفحۀ دوم. روند و ستاپ‌ها از موتورِ `api/chart.py` خوانده می‌شوند؛ "
     "این نقشه چیزی را دوباره حساب نمی‌کند.",
     "هفتگی ⇒ روزانه ⇒ ستاپ", []),
    ("t_buy", "T", "t_root", 1, "سیگنال خرید",
     "سرِ شاخۀ سیگنالِ خرید در چارت",
     "چارت صفحه ۲",
     "چارت اول روندِ هفتگی را می‌پرسد: نزولی reject، خنثی reject، صعودی باز می‌شود.",
     "ریجکت هفتگی = وتوی قطعی", []),
    ("t_daily_up", "T", "tech_weekly_up", 1, "تایم روزانه صعودی",
     "شاخۀ روزانۀ صعودیِ زیرِ هفتگیِ صعودی",
     "چارت صفحه ۲",
     "سطرِ «تایم روزانه صعودی» در چارت: استراتژی پولبک و استراتژی جت.",
     "هفتگی صعودی + روزانه صعودی", []),
    ("t_daily_down", "T", "tech_weekly_up", 2, "تایم روزانه نزولی",
     "شاخۀ روزانۀ نزولیِ زیرِ هفتگیِ صعودی",
     "چارت صفحه ۲",
     "سطرِ «تایم روزانه نزولی» در چارت: استراتژی فیبوناتچی و CHOOCH.",
     "هفتگی صعودی + روزانه نزولی", []),
    ("t_daily_neutral", "T", "tech_weekly_up", 3, "تایم روزانه خنثی",
     "شاخۀ روزانۀ خنثیِ زیرِ هفتگیِ صعودی",
     "چارت صفحه ۲",
     "سطرِ «تایم روزانه خنثی» در چارت: ورود در آخرین کفِ روند صعودی یا آخرین سقفِ "
     "روند نزولی.",
     "هفتگی صعودی + روزانه خنثی", []),
    ("t_sell", "T", "t_root", 2, "سیگنال فروش",
     "بخشِ فروشِ صفحۀ دوم چارت",
     "چارت صفحه ۲",
     "سرِ شاخۀ فروش در چارت: کف دوقلو، سقف دوقلو، سر و شانه، سقف سوم و واگراییِ "
     "مقاومتی. هیچ‌کدام درِ فرانت داوری نمی‌شوند؛ رأی از `exit_engine`ِ سرور است.",
     "ساختارِ فروش", []),
    ("t_stop", "T", "t_root", 3, "حد ضرر",
     "بخشِ حد ضررِ صفحۀ دوم چارت",
     "چارت صفحه ۲",
     "سطرهایِ «حد ضرر» در چارت: ۵٪ زیر آخرین کفِ روند صعودی، نوسانگیر MA=14 با یک "
     "کندلِ کامل زیر MA، و روندگیر با خریدِ پله‌ای و ۵٪ زیر نقطۀ ورود. عددها را "
     "همان گره‌هایِ صفحۀ ۴ نگه می‌دارند (خط‌چینِ هم‌نام) — نسخهٔ دوم ساخته نشده.",
     "۵٪ · MA=14 · پله‌ای", ["stop_swing", "stop_trend"]),
    ("s_root", "S", None, 0, "S: SELECTION",
     "صفحۀ ۳ چارت FTS — انتخاب و غربالگری تابلوخوانی",
     "چارت صفحه ۳",
     "ریشۀ صفحۀ سوم: سبکِ معامله، رصدِ جریان نقدینگی، بررسیِ صنایع، حجمِ معاملات، "
     "الگوهایِ تابلوخوانی و خشک کردن.",
     "تابلو قبل از تکنیکال (مهندسی معکوس)", []),
    ("s_style", "S", "s_root", 1, "انتخاب سبک معامله",
     "سرِ شاخۀ سبکِ معامله در چارت",
     "چارت صفحه ۳",
     "چارت دو سبک را می‌شمارد: نوسانگیر و روندگیر. همین دو، همان دو پرستِ "
     "برنامه‌اند؛ شاخه‌ها جابه‌جا نمی‌شوند، فقط روشن می‌شوند.",
     "نوسانگیر / روندگیر", []),
    ("s_style_swing", "S", "s_style", 1, "نوسانگیر",
     "سبکِ نوسان‌گیری (۱ تا ۲ ماه)",
     "چارت صفحه ۳",
     "سرِ شاخۀ نوسانگیر در چند بخشِ صفحۀ سوم؛ پرستِ `swing` همین شاخه‌ها را روشن "
     "می‌کند.",
     "پرست: swing", []),
    ("s_style_trend", "S", "s_style", 2, "روندگیر",
     "سبکِ روندی (بالای ۳ ماه)",
     "چارت صفحه ۳",
     "سرِ شاخۀ روندگیر در چند بخشِ صفحۀ سوم؛ پرستِ `trend` همین شاخه‌ها را روشن "
     "می‌کند.",
     "پرست: trend", []),
    ("s_liquidity", "S", "s_root", 2, "رصد جریان نقدینگی",
     "سرِ شاخۀ نقدینگی در چارت",
     "چارت صفحه ۳",
     "وضعیتِ کل بازار: TRADERS ARENA، نمودارهایِ جریانِ پول و ورود/خروجِ پول.",
     "مساعد / نامساعد", []),
    ("s_arena", "S", "s_liquidity", 1, "وضعیت بازار در TRADERS ARENA",
     "بررسی وضعیت بازار در TRADERS ARENA",
     "چارت صفحه ۳",
     "سطرِ چارت: ارزشِ معاملاتِ بازارِ سهام و شمارِ سهامِ مثبت/منفی. داوریِ عددی "
     "درِ `mstat_engine` و `/api/live-stats` است، نه این نقشه.",
     "ارزش معاملات · سهام مثبت/منفی", []),
    ("s_industries", "S", "s_root", 3, "بررسی صنایع",
     "خلاصه معاملات صنایع و سهام برگزیده",
     "چارت صفحه ۳",
     "سطرِ «بررسی صنایع: خلاصه معاملات صنایع بورس» و «سهام برگزیده» (صدِ آخرین و "
     "ورودِ پول را از بالا به پایین مرتب می‌کنیم).",
     "خلاصه صنایع · سهام برگزیده", []),
    ("s_volume", "S", "s_root", 4, "حجم معاملات",
     "سرِ شاخۀ حجمِ معاملات در چارت",
     "چارت صفحه ۳",
     "چارت برایِ هر دو سبک یک شرطِ حجمی می‌گذارد: نوسانگیر حجمِ مشکوک (سه برابر "
     "میانگینِ ماهانۀ MA=21)، روندگیر حجمِ معاملات و ورود در قیمتِ ارزنده.",
     "حجم مشکوک / حجم روند", []),
    ("s_volume_swing", "S", "s_volume", 1, "نوسانگیر",
     "حجم معاملات — شاخۀ نوسانگیر",
     "چارت صفحه ۳",
     "سطرِ «نوسانگیر: بررسی حجم مشکوک (سه برابر میانگین ماهانه) volume, MA length=21».",
     "سبک: نوسانگیر", []),
    ("s_volume_trend", "S", "s_volume", 2, "روندگیر",
     "حجم معاملات — شاخۀ روندگیر",
     "چارت صفحه ۳",
     "سطرِ «روندگیر: بررسی حجم معاملات و ورود در قیمتِ ارزنده».",
     "سبک: روندگیر", []),
    ("s_patterns", "S", "s_root", 5, "الگوهای تابلوخوانی",
     "سرِ شاخۀ الگوهایِ تابلوخوانی در چارت",
     "چارت صفحه ۳",
     "الگوی ساعت و خروج از باکسِ رنج برایِ نوسانگیر؛ کف‌روبی برایِ روندگیر.",
     "ساعت / باکس رنج / کف‌روبی", []),
    ("s_patterns_swing", "S", "s_patterns", 1, "نوسانگیر",
     "الگوها — شاخۀ نوسانگیر",
     "چارت صفحه ۳",
     "سرِ شاخۀ «نوسانگیر: الگوی ساعت، خروج از باکس رنج» در چارت.",
     "سبک: نوسانگیر", []),
    ("s_patterns_trend", "S", "s_patterns", 2, "روندگیر",
     "الگوها — شاخۀ روندگیر",
     "چارت صفحه ۳",
     "سطرِ «روندگیر: کف روبی — سهم صف فروش است ولی اوردرهایِ قوی در حال خریدِ سهم "
     "هستند».",
     "سبک: روندگیر", []),
    ("s_dry", "S", "s_root", 6, "خشک کردن (فیلتر)",
     "فیلترِ نهاییِ صفحۀ سوم",
     "چارت صفحه ۳",
     "سطرِ «خشک کردن / فیلتر» در چارت: برایِ نوسانگیر ساعت، جت و حجمِ مشکوک؛ برایِ "
     "روندگیر کف‌روبی و نقطه‌زنی. شمارشِ نمادهایِ عبوری درِ `lib/strictGates.ts` است.",
     "خشک کردنِ فهرست", []),
    ("m_root", "M", None, 0, "مهندسی معکوس + مدیریت سرمایه",
     "صفحۀ ۴ چارت FTS — داوری، سرمایه و استراتژی",
     "چارت صفحه ۴",
     "ریشۀ صفحۀ چهارم: ترتیبِ مهندسی معکوس، مدیریتِ سرمایه، رصدِ پورتفو، اصولِ "
     "پورتفوی بهینه و استراتژی‌ها.",
     "۱ تابلو ۲ تکنیکال ۳ بنیادی", []),
    ("m_reverse", "M", "m_root", 1, "مهندسی معکوس",
     "ترتیبِ مهندسی معکوسِ چارت",
     "چارت صفحه ۴",
     "سطرهایِ «۱-تابلو خوانی، ۲-تکنیکال، ۳-بنیادی». همین ترتیب، همان جریانِ "
     "`reverse` است — جهتِ ریل، نه جایِ صفحه‌ها.",
     "تابلو ← تکنیکال ← بنیادی", []),
    ("m_reverse_tape", "M", "m_reverse", 1, "۱- تابلو خوانی",
     "پیلارِ اولِ مهندسی معکوس",
     "چارت صفحه ۴",
     "چارت زیرِ این سطر سه مورد می‌شمارد: فیلتر حجم مشکوک، الگوی ساعت، کف روبی — "
     "همان سه گره درِ صفحۀ ۳؛ پیوندِ خط‌چین به همان‌ها می‌رود، نسخۀ دوم ساخته "
     "نمی‌شود.",
     "حجم مشکوک · ساعت · کف‌روبی", ["tape_volume", "tape_clock", "tape_floor_sweep"]),
    ("m_reverse_tech", "M", "m_reverse", 2, "۲- تکنیکال",
     "پیلارِ دومِ مهندسی معکوس",
     "چارت صفحه ۴",
     "ارجاع به صفحۀ ۲. داوریِ روند از موتورِ FTS است.",
     "→ صفحۀ ۲", ["t_root"]),
    ("m_reverse_fund", "M", "m_reverse", 3, "۳- بنیادی",
     "پیلارِ سومِ مهندسی معکوس",
     "چارت صفحه ۴",
     "ارجاع به صفحۀ ۱. امتیاز از `/api/fundamental` می‌آید.",
     "→ صفحۀ ۱", ["f_root"]),
    ("m_money", "M", "m_root", 2, "مدیریت سرمایه",
     "سرِ شاخۀ مدیریتِ سرمایه در چارت",
     "چارت صفحه ۴",
     "حداکثر ۷۰٪ کل دارایی در بازارِ سرمایه (در شرایطِ جنگی ۲۰±۱۰٪)، وزنِ سبد با "
     "احتسابِ حداکثرِ ضرر، صندوق‌ها و پوششِ ریسک، نوعِ حدِ ضرر و ورود/خروجِ پله‌ای.",
     "سقف · وزن · پوشش · حدضرر", []),
    ("m_stop_kind", "M", "m_money", 4, "نوع حد ضرر (نوسانی و روندی)",
     "توجه به نوع حد ضرر در معاملات نوسانی و روندی",
     "چارت صفحه ۴",
     "سطرِ چارت: نوسانگیر حد ضرر دارد و خریدِ پله‌ای (۱ تا ۲ ماه+)؛ روندگیر بالای "
     "۳ ماه، خریدِ پله‌ای دارد و حد ضررش بنیادی است نه تکنیکالی (حکمِ ۸ مالک).",
     "نوسانگیر: تکنیکالی · روندگیر: بنیادی", ["t_stop"]),
    ("m_monitor", "M", "m_root", 3, "رصد و تحلیل مداوم پورتفوی",
     "سرِ شاخۀ رصدِ مداوم در چارت",
     "چارت صفحه ۴",
     "سطرِ چارت: هر ماه گزارشِ فروش، هر فصل صورتِ مالی، هر سال صورتِ مالی سالانه و "
     "مقایسه با سال قبل. تقویمِ گزارش‌ها از `codal_periods` است.",
     "ماهانه · فصلی · سالانه", []),
    ("m_fit", "M", "m_root", 4, "تناسب دیدگاه با بورس ایران",
     "تناسب دیدگاه سرمایه‌گذاری با بورس ایران",
     "چارت صفحه ۴",
     "سرِ شاخۀ اصولِ پورتفوی بهینه در چارت: سهام دلاری/ریالی، بزرگ و کوچک، تولیدی و "
     "غیرتولیدی، صندوق‌های سرمایه‌گذاری.",
     "دلاری · ریالی · بزرگ/کوچک", []),
    ("m_strategy", "M", "m_root", 5, "استراتژی",
     "سرِ شاخۀ استراتژی‌های صفحۀ چهارم",
     "چارت صفحه ۴",
     "چارت اینجا سه استراتژی را نام می‌برد: ساعت شنی، جت، نقطه‌زنی. هر سه گره‌شان "
     "درِ صفحۀ ۲ و ۳ ساخته شده، پس این سر با خط‌چین به همان‌ها وصل می‌شود.",
     "ساعت شنی · جت · نقطه‌زنی",
     ["stop_hourglass", "setup_jet", "setup_point_hunt"]),
]

# سرِ شاخه‌هایی که سطرِ خودِ جزوه نیستند (طبقۀ امتیازِ بنیادی از منطقِ برنامه است)
PROGRAM_HEADS = {"f_tiers"}

# فهرستِ پرست‌ها — عینِ `activeNodes` درِ `routes/StrategyTreePage.tsx`. هیچ گره‌ای
# اینجا کم یا زیاد نشده تا نقشه، انتخابِ پرست را عوض نکند.
PRESET_ACTIVE_SRC = """
/** پرست ⇒ گره‌هایِ روشن. این جدول عینِ `activeNodes` درِ `StrategyTreePage.tsx` است
 *  و تنها جایِ نگهداری‌اش به مدلِ داده منتقل شده (تکلیفِ پرست از خودِ برنامه).
 *
 *  چارت ۳ (S: SELECTION): روندگیر = کف‌روبی + نقطه‌زنی، و نقطه‌زنی
 *  «ورود در کف سوم یا پنجم» است (چارت ۴). گرهٔ setup_point_hunt درِ
 *  نقشه ساخته شده، پس اینجا هم باید باشد — وگرنه درختِ روندگیر همان
 *  گره‌ای را خاموش نشان می‌دهد که قیف برایش نماد می‌گیرد.
 *
 *  رأیِ مالک (بند ۸): سهامدارِ روندگیر در سهم بنیادی حد ضررِ قیمتی
 *  ندارد و با گزارشِ فصلی کدال خارج می‌شود — هیچ گره «خروج»ی برایش
 *  روشن نمی‌شود، و این خالی‌بودن عمدی است نه فراموشی.
 *
 *  ساعت شنی ستاپِ مستقل ندارد؛ خودِ همان اشباعِ هفتگی (MA=52 + RSI)
 *  در ستونِ هفتگی روشن می‌شود. */
export const PRESET_ACTIVE: Record<'swing' | 'trend' | 'hourglass', string[]> = {
  swing: ['fund_good', 'fund_medium', 'tech_weekly_up', 'setup_jet', 'setup_fib', 'tape_clock', 'tape_volume', 'stop_swing', 'exit_half'],
  trend: ['fund_super', 'fund_good', 'tech_weekly_up', 'setup_fib', 'setup_choch', 'setup_jet', 'setup_point_hunt', 'tape_floor_sweep', 'stop_trend'],
  hourglass: ['fund_super', 'tech_weekly_hourglass', 'tape_floor_sweep', 'tape_clock', 'stop_hourglass'],
};
"""

HEADER = """// features/master/lib/ftsChartModel.ts -- مدلِ «چهار صفحۀ FTS در یک نقشه»
// این فایل فقط **داده** است: هیچ SVG، هیچ مختصاتِ دستی و هیچ قاعدۀ تشخیصی درِ آن
// نیست. چهار Zone دقیقاً چهار صفحۀ چاپیِ چارت‌اند (F=۱ بنیادی، T=۲ تکنیکال،
// S=۳ انتخاب، M=۴ مهندسی معکوس/مدیریت سرمایه/استراتژی) و parent/child هر Zone
// همان سطرهایِ خودِ چارت است (`docs/fts-notes/FTS_CHART3_extracted_text.txt`،
// حسابرسیِ خط‌به‌خط: `docs/CHART-FOUR-PAGES-PARITY.md`).
//
// سه قیدِ این مدل:
//  ۱) متن/قاعده/آستانۀ گره‌ها از جدولِ پیشینِ `ObsidianStrategyGraph.tsx` عیناً
//     منتقل شده (تولیدِ مکانیکی: `_audit/gen_fts_chart_model.py`) تا ظاهرِ تازه،
//     معنا را عوض نکند.
//  ۲) چیزی که درِ چارت سطر ندارد `origin: 'program'` می‌خورد (طبقه‌هایِ امتیاز،
//     R/R، سقفِ وزنِ صنعت، فروشِ درصدی در اولین سقف) تا نقشه، برنامه را وعدهٔ
//     جزوه نزند.
//  ۳) مفهومی که درِ چند صفحه تکرار شده یکِ گره می‌ماند و با `refs` به آن صفحه‌ها
//     وصل می‌شود — خط‌چینِ «هم‌نام»، نه نسخۀ دوم و نه رابطۀ ساختاریِ جعلی.
//
// Source of Truth منطق همچنان بک‌اند/پایتون است؛ این مدل هیچ داوری‌ای نمی‌کند.
// GENERATED از `_audit/strategy_graph_dump.json` + جدولِ parentِ همان اسکریپت.

import { toFaDigits } from '@shared/lib/fmt';
import type { StrategyParameters } from '../stores/strategyParamsStore';

export type FtsZone = 'F' | 'T' | 'S' | 'M';
export type FtsPreset = 'swing' | 'trend' | 'hourglass' | 'custom';
/** جهتِ ریل: مهندسی معکوسِ جزوه (S→T→F→M) یا جریانِ کلاسیکِ تحلیلی (F→T→S→M).
 *  فقط ترتیبِ روشن‌شدن و فلشِ ریل را عوض می‌کند — هیچ گره، هیچ parent و هیچ
 *  جایگاهِ Zone را جابه‌جا نمی‌کند (قیدِ مالک: جهت، توپولوژی را نسازد). */
export type FlowDirection = 'reverse' | 'classic';

export interface FtsZoneMeta {
  key: FtsZone;
  page: number;
  /** سربرگِ Zone رویِ نقشه */
  title: string;
  sub: string;
  /** همان «رکن: …» که پنلِ جزئیات نشان می‌داد (متنِ پیشین) */
  stageName: string;
  /** رنگِ تمِ Zone، دو حالتِ روشن/تاریک */
  accentLight: string;
  accentDark: string;
}

export const ZONES: FtsZoneMeta[] = [
  { key: 'F', page: 1, title: '۱ · F بنیادی', sub: 'پنج‌شاخص کدال', stageName: 'بنیادی F', accentLight: '#059669', accentDark: '#10b981' },
  { key: 'T', page: 2, title: '۲ · T تکنیکال', sub: 'سیگنال دو زمانه', stageName: 'تکنیکال T', accentLight: '#0284c7', accentDark: '#38bdf8' },
  { key: 'S', page: 3, title: '۳ · S انتخاب', sub: 'تابلوخوانی', stageName: 'تابلوخوانی S', accentLight: '#d97706', accentDark: '#f59e0b' },
  { key: 'M', page: 4, title: '۴ · M داوری و سرمایه', sub: 'مهندسی معکوس و سرمایه', stageName: 'مدیریت سرمایه M', accentLight: '#dc2626', accentDark: '#ef4444' },
];

export const ZONE_BY_KEY: Record<FtsZone, FtsZoneMeta> = Object.fromEntries(
  ZONES.map((z) => [z.key, z]),
) as Record<FtsZone, FtsZoneMeta>;

export interface FtsChartNode {
  id: string;
  /** صفحۀ اصلیِ گره — همان Zone که درِ آن رسم می‌شود */
  zone: FtsZone;
  /** سرِ شاخۀ واقعی درِ همان صفحه؛ null یعنی ریشۀ همان Zone */
  parent: string | null;
  /** ترتیبِ خواندنِ چارت درِ همان شاخه (۰ = اول) */
  order: number;
  /** 'chart' = سطرِ خودِ جزوه، 'program' = افزونۀ منطقِ برنامه */
  origin: 'chart' | 'program';
  /** 'head' = سرِ شاخه (نقلِ سطرِ چارت)، 'leaf' = گره برچسب‌دار */
  kind: 'head' | 'leaf';
  label: string;
  fullTitle: string;
  /** برچسبِ «چارت صفحۀ …» که درِ پنلِ جزئیات دیده می‌شود — متنِ پیشین */
  page: string;
  description: string;
  ruleFormula: string;
  badge: string;
  color: string;
  /** هم‌نام‌هایِ این مفهوم درِ صفحه‌های دیگر (خط‌چین، نه یالِ ساختاری) */
  refs: string[];
  editableParamKeys?: (keyof StrategyParameters)[];
}

export interface FtsChartModel {
  nodes: FtsChartNode[];
  byId: Map<string, FtsChartNode>;
  childrenOf: Map<string, string[]>;
  roots: Record<FtsZone, string>;
  byZone: Record<FtsZone, FtsChartNode[]>;
}
"""


def head_literal(h) -> str:
    hid, zone, parent, order, label, full_title, page, desc, rule, refs = h
    par = "null" if parent is None else "'%s'" % parent
    refs_js = ", ".join("'%s'" % r for r in refs)
    origin = "program" if hid in PROGRAM_HEADS else "chart"
    badge = "سرِ شاخۀ برنامه" if origin == "program" else "سرِ شاخۀ چارت"
    return ("  {\n    id: '%s',\n    zone: '%s',\n    parent: %s,\n    order: %d,\n"
            "    origin: '%s',\n    kind: 'head',\n    label: '%s',\n    fullTitle: '%s',\n"
            "    page: '%s',\n    description: '%s',\n    ruleFormula: '%s',\n"
            "    badge: '%s',\n    color: '',\n    refs: [%s],\n  }," % (
                hid, zone, par, order, origin, label, full_title, page, desc, rule,
                badge, refs_js))


def leaf_literal(fields) -> str:
    nid = fields["id"].strip("'\"")
    zone, parent, order, origin, refs = MAP[nid]
    out = ["  {", "    id: %s," % fields["id"]]
    out.append("    zone: '%s'," % zone)
    out.append("    parent: '%s'," % parent)
    out.append("    order: %d," % order)
    out.append("    origin: '%s'," % origin)
    out.append("    kind: 'leaf',")
    out.append("    label: %s," % fields["label"])
    out.append("    fullTitle: %s," % fields["fullTitle"])
    out.append("    page: %s," % fields["page"])
    out.append("    description: %s," % fields["description"])
    out.append("    ruleFormula: %s," % fields["ruleFormula"])
    out.append("    badge: %s," % fields["badge"])
    out.append("    color: %s," % fields["color"])
    out.append("    refs: [%s]," % ", ".join("'%s'" % r for r in refs))
    if fields.get("editableParamKeys"):
        out.append("    editableParamKeys: %s," % fields["editableParamKeys"])
    out.append("  },")
    return "\n".join(out)


FOOTER = """
/** سرِ شاخه‌ها و ریشه‌ها — متن‌ها عینِ سطرهایِ خودِ چارت است */
const CHART_HEADS: FtsChartNode[] = [
__HEADS__
];

/** گره‌هایِ برچسب‌دارِ نقشه — متن/قاعده/آستانه عیناً از جدولِ پیشین. تابع است چون
 *  برچسبِ چند گره آستانۀ زندۀ `strategyParamsStore` را درِ خودش نشان می‌دهد. */
export function chartLeaves(params: StrategyParameters): FtsChartNode[] {
  return [
__LEAVES__
  ];
}

/** تنها درختِ نقشه: یال‌هایِ parent→child درِ همان Zone. بی‌تأثیر از پرست و جهت. */
export function treeEdges(model: FtsChartNode[]): { id: string; source: string; target: string }[] {
  return model
    .filter((n) => n.parent)
    .map((n) => ({ id: 'tr_' + (n.parent as string) + '_' + n.id, source: n.parent as string, target: n.id }));
}

/** وابستگی‌هایِ بین‌صفحه‌ای که خودِ چارت اعلام می‌کند: ترتیبِ مهندسی معکوسِ صفحۀ ۴
 *  (۱ تابلو ۲ تکنیکال ۳ بنیادی) و داوریِ نهایی که به مدیریتِ سرمایه می‌رسد.
 *  ستون‌ها جایِ ثابت دارند؛ فقط `flow` جهتِ فلشِ همین سه رابطۀ ثابت را می‌خواند. */
export const ZONE_LINKS: { id: string; from: FtsZone; to: FtsZone }[] = [
  { id: 'zl_s_t', from: 'S', to: 'T' },
  { id: 'zl_t_f', from: 'T', to: 'F' },
  { id: 'zl_f_m', from: 'F', to: 'M' },
];

/** ترتیبِ ریل برایِ جهتِ انتخابی — همان چهار Zone، فقط با اولویتِ خواندن.
 *  توپولوژیِ درخت این عدد را نمی‌شناسد (`ZONE_LINKS` ثابت است). */
export function railOrder(flow: FlowDirection): FtsZone[] {
  return flow === 'reverse' ? ['S', 'T', 'F', 'M'] : ['F', 'T', 'S', 'M'];
}

__PRESET__

/** پرست ⇒ گره‌هایِ روشن + جدّهایِ مسیرشان، تا ریل رویِ نقشه بُرش نداشته باشد. */
export function activeIdsForPreset(
  preset: FtsPreset,
  model: FtsChartModel,
  customIds: string[] = [],
): Set<string> {
  const base = preset === 'custom' ? customIds : PRESET_ACTIVE[preset];
  const set = new Set<string>();
  for (const id of base) {
    if (!model.byId.has(id)) continue;
    for (const a of ancestorsOf(model, id)) set.add(a);
  }
  return set;
}

export function buildFtsChartModel(params: StrategyParameters): FtsChartModel {
  const nodes: FtsChartNode[] = [...CHART_HEADS, ...chartLeaves(params)];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map<string, string[]>();
  for (const n of nodes) {
    if (!n.parent) continue;
    const arr = childrenOf.get(n.parent);
    if (arr) arr.push(n.id);
    else childrenOf.set(n.parent, [n.id]);
  }
  childrenOf.forEach((arr) => arr.sort((a, b) => (byId.get(a)?.order ?? 0) - (byId.get(b)?.order ?? 0)));
  const roots = {} as Record<FtsZone, string>;
  const byZone = {} as Record<FtsZone, FtsChartNode[]>;
  for (const z of ZONES) {
    const root = nodes.find((n) => n.zone === z.key && !n.parent);
    roots[z.key] = root ? root.id : '';
    byZone[z.key] = nodes
      .filter((n) => n.zone === z.key)
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  }
  return { nodes, byId, childrenOf, roots, byZone };
}

/** همهٔ جدّهایِ یک گره، ریشه تا خودِ گره — برایِ «روشن‌شدنِ کل مسیر» درِ جست‌وجو. */
export function ancestorsOf(model: FtsChartModel, id: string): string[] {
  const out: string[] = [];
  let cur: string | null | undefined = id;
  while (cur) {
    out.push(cur);
    cur = model.byId.get(cur)?.parent;
  }
  return out;
}

/** همهٔ فرزندانِ یک گره (بی‌_ordered) — برایِ جمع‌کردنِ شاخه و جست‌وجو. */
export function descendantsOf(model: FtsChartModel, id: string): string[] {
  const out: string[] = [];
  const stack = [id];
  while (stack.length) {
    const k = stack.pop() as string;
    for (const c of model.childrenOf.get(k) ?? []) {
      out.push(c);
      stack.push(c);
    }
  }
  return out;
}

/** سازۀ «هم‌نام»ها: هر رابطۀ بین‌صفحه‌ای که گونۀ دومِ یک مفهوم است، خط‌چین می‌شود
 *  و هیچ‌وقت یالِ ساختاری. جهتِ تعریف رویِ نمایش اثر ندارد؛ نمایش از refs می‌آید. */
export interface FtsRefEdge {
  id: string;
  source: string;
  target: string;
  kind: 'ref';
}

export function refEdges(model: FtsChartModel): FtsRefEdge[] {
  const seen = new Set<string>();
  const out: FtsRefEdge[] = [];
  for (const n of model.nodes) {
    for (const r of n.refs) {
      if (!model.byId.has(r)) continue;
      const key = [n.id, r].sort().join('|');
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ id: 'rf_' + key.replace('|', '_'), source: n.id, target: r, kind: 'ref' });
    }
  }
  return out;
}

/** سازۀ یال‌ها برایِ مصرف‌کننده‌هایِ پیشین (`getGraphLinks` درِ کامپوننت).
 *  توپولوژیِ درخت ثابت است؛ `flow` فقط ترتیبِ ریل را تعیین می‌کند. */
export interface FtsCompatLink {
  id: string;
  source: string;
  target: string;
  presets: ('swing' | 'trend' | 'hourglass')[];
  flow: FlowDirection;
}

/** یال‌هایِ درختِ ثابتِ نقشه: [parent, child]. متنِ گره‌ها اینجا نمی‌آید تا
 *  سازۀ یال‌ها به `strategyParamsStore` وابسته نشود. */
const TREE_PAIRS: [string, string][] = [
__PAIRS__
];

const CHILD_OF: Map<string, string[]> = (() => {
  const m = new Map<string, string[]>();
  for (const [p, c] of TREE_PAIRS) {
    const arr = m.get(p);
    if (arr) arr.push(c);
    else m.set(p, [c]);
  }
  return m;
})();

/** پرست‌هایِ یک گره: برگ‌ها از `PRESET_ACTIVE` و سرِ شاخه‌ها از uniteِ فرزندان. */
export function presetsOfNode(id: string): ('swing' | 'trend' | 'hourglass')[] {
  const direct = (Object.keys(PRESET_ACTIVE) as ('swing' | 'trend' | 'hourglass')[]).filter(
    (p) => PRESET_ACTIVE[p].includes(id),
  );
  if (direct.length) return direct;
  const kids = CHILD_OF.get(id);
  if (!kids || !kids.length) return [];
  const acc = new Set<string>();
  for (const k of kids) for (const p of presetsOfNode(k)) acc.add(p);
  return [...acc] as ('swing' | 'trend' | 'hourglass')[];
}

export function getGraphLinks(flow: FlowDirection): FtsCompatLink[] {
  const out: FtsCompatLink[] = TREE_PAIRS.map(([p, c]) => ({
    id: 'tr_' + p + '_' + c,
    source: p,
    target: c,
    presets: presetsOfNode(c),
    flow,
  }));
  // سه رابطۀ بین‌صفحه‌ای که خودِ چارت اعلام می‌کند (ترتیبِ مهندسی معکوسِ صفحۀ ۴).
  // سرِ این سه یال ریشۀ Zone است، نه یک گره؛ و جهتِ توپولوژی ثابت می‌ماند —
  // `flow` فقط فلشِ ریل را برعکس می‌کشد.
  const roots = zoneRoots();
  for (const zl of ZONE_LINKS) {
    out.push({
      id: zl.id,
      source: roots[zl.from],
      target: roots[zl.to],
      presets: ['swing', 'trend', 'hourglass'],
      flow,
    });
  }
  return out;
}

/** ریشۀ هر Zone — همان چهار صفحۀ چاپی، جایِ ثابت رویِ نقشه */
export function zoneRoots(): Record<FtsZone, string> {
  return { F: 'f_root', T: 't_root', S: 's_root', M: 'm_root' };
}
"""


def main():
    dump = json.load(io.open(DUMP, encoding="utf-8"))
    nodes = {n["id"].strip("'\""): n for n in dump["nodes"]}
    missing = [k for k in MAP if k not in nodes]
    extra = [k for k in nodes if k not in MAP]
    # `fts_core` تنها گره‌ای است که درِ مدلِ تازه جایِ خود را به چهار ریشۀ Zone
    # می‌دهد (درخواستِ مالک: مانعی که ده‌ها یال از یک هسته بیرون نرود).
    if missing or sorted(extra) != ["fts_core"]:
        print("نقصِ پوشش:", missing, extra)
        return 1
    head_ids = {h[0] for h in HEADS}
    # هر parent باید یا None باشد یا درِ سرِ شاخه‌ها یا درِ گره‌هایِ برگ
    known = head_ids | set(MAP)
    bad = [(h[0], h[2]) for h in HEADS if h[2] and h[2] not in known]
    bad += [(k, v[1]) for k, v in MAP.items() if v[1] not in known]
    if bad:
        print("parentِ ناشناخته:", bad)
        return 1
    for k, v in MAP.items():
        for r in v[4]:
            if r not in known:
                print("refِ ناشناخته در", k, "->", r)
                return 1
    for p, ids in PRESET_ACTIVE_EXPECT.items():
        for i in ids:
            if i not in known:
                print("گره‌ای که درِ پرست", p, "نیست:", i)
                return 1

    ordered_leaves = sorted(MAP, key=lambda k: (MAP[k][0], MAP[k][1], MAP[k][2]))
    pairs = [(h[2], h[0]) for h in HEADS if h[2]] + [(v[1], k) for k, v in MAP.items()]
    pair_src = ",\n".join("  ['%s', '%s']" % (p, c) for p, c in pairs)
    text = (HEADER + FOOTER
            .replace("__HEADS__", "\n".join(head_literal(h) for h in HEADS))
            .replace("__LEAVES__", "\n".join(leaf_literal(nodes[k]) for k in ordered_leaves))
            .replace("__PRESET__", PRESET_ACTIVE_SRC.strip())
            .replace("__PAIRS__", pair_src))
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    print("نوشته شد:", os.path.relpath(OUT, ROOT), "— سرِ شاخه:", len(HEADS), "برگ:", len(MAP))
    return 0


# فهرستِ پرست‌ها آن‌طور که درِ StrategyTreePage هست — فقط برایِ اعتبارسنجیِ همین اسکریپت
PRESET_ACTIVE_EXPECT = {
    "swing": ['fund_good', 'fund_medium', 'tech_weekly_up', 'setup_jet', 'setup_fib',
              'tape_clock', 'tape_volume', 'stop_swing', 'exit_half'],
    "trend": ['fund_super', 'fund_good', 'tech_weekly_up', 'setup_fib', 'setup_choch',
              'setup_jet', 'setup_point_hunt', 'tape_floor_sweep', 'stop_trend'],
    "hourglass": ['fund_super', 'tech_weekly_hourglass', 'tape_floor_sweep', 'tape_clock',
                  'stop_hourglass'],
}

if __name__ == "__main__":
    sys.exit(main())
