#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fts_engine.py — موتور ۵ شاخص استراتژی FTS — v8.0 (بازنویسی ممیزی‌شده).

منابع داده:
  * monthly_sales        — گزارش فعالیت ماهانه (کدال): monthly_revenue / ytd_revenue
  * financial_statements — صورت‌های مالی (کدال): revenue / gross_profit / basic_eps / title
  * instruments          — TSETMC: sector_name / total_shares
  * market_watch         — TSETMC: p_closing + d_even (آخرین روز معاملاتیِ خودِ نماد)

۵ شاخص (طبق متدولوژی جزوه):
  ۱) رشد فروش           = (فروش تجمیعی YTD ÷ فروش تجمیعی همان دورهٔ سال قبل) × ۱۰۰ − ۱۰۰
                          مخرج هرگز «ماه قبل» نیست. بانک: جمع درآمدهای تسهیلات/سپرده‌گذاری/
                          سرمایه‌گذاری/اوراق/کارمزد (توسط codal_fetcher._bank_fallback تجمیع
                          میشود و همین‌جا در ytd_revenue خوانده میشود)؛
                          تولیدی: جمع فروش داخلی + صادراتی (ردیف «جمع» جدول فروش).
  ۲) روند ۳ ساله EPS    = EPS_y > EPS_y-1 > EPS_y-2، صرفاً از صورت‌های مالی ۱۲ ماههٔ
                          حسابرسی‌شدهٔ «شرکت اصلی» (غیرتلفیقی) و در سال‌های مالی متوالی.
  ۳) حاشیه سود ناخالص   = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰ — نه سود خالص، نه سود عملیاتی.
  ۴) فروش به ارزش بازار = فروش سالانهٔ Annualized از گزارش‌های ماهانه ÷ ارزش بازار روز
                          + «پتانسیل سود ناخالص به ارزش بازار».
  ۵) فیلتر صنعت         = تفکیک تگ‌های صنعت به «قیمت‌گذاری آزاد/بورس کالا» و «قیمت‌گذاری دستوری».

فیلترهای حذف خودکار از خروجی (پیش‌غربالگری): نماد تعلیق + صنعت بیمه.

نکتهٔ ساختاری v8: تمام تطبیق متن‌های فارسی از norm_fa() عبور میکند. در v7.3 کد «تلفيقي»
با ی عربی می‌جست در حالی که ۱۳۳۹ عنوان دیتابیس «تلفیقی» با ی فارسی دارند → فیلتر تلفیقی
هرگز فعال نمیشد. همین کلاس باگ در «بيمه» هم وجود داشت.
"""
from __future__ import annotations
import sqlite3
from typing import Optional

import mstat_engine
# تنها تعریفِ «دورۀ گزارش» (شکل، بی‌دوره، سالِ مالی) — ببین `codal_periods.py`.
import codal_periods as CP
import codal_units as CU                # تنها تعریفِ «واحدِ پول» (mrl/btl/بی‌واحد)
import symbol_identity as SI            # تنها تعریفِ «این ردیف مالکِ کدام ابزار است»


# ============================================================ نرمال‌سازی نوشتار
_YA_AR, _YA_FA = "\u064a", "\u06cc"      # ي  → ی
_KAF_AR, _KAF_FA = "\u0643", "\u06a9"    # ك  → ک
_HAMZA_YA = "\u0649"                     # ى  → ی
_ZWNJ = "\u200c"


def norm_fa(text) -> str:
    """یکسان‌سازی نوشتار عربی/فارسی برای مقایسهٔ بی‌خطر تگ‌ها.

    ي→ی ، ك→ک ، ى→ی و حذف نیم‌فاصله. بدون این، «تلفيقي» هرگز با «تلفیقی»
    مطابقت نمیکند (باگ واقعی v7.3).
    """
    s = str(text if text is not None else "")
    if not s:
        return ""
    s = s.replace(_YA_AR, _YA_FA).replace(_KAF_AR, _KAF_FA).replace(_HAMZA_YA, _YA_FA)
    return s.replace(_ZWNJ, "")


# ================================================== باگ نوشتار مختلط (v9.7.3)
# «norm_fa فقط برای عنوان صورت‌مالی کافی است» فرضی بود که داده‌ها نقضش کردند:
# در market.db ستون symbol خودش دو نوشتار دارد — از ۱۰۱۵ نمادِ
# financial_statements، ۳۴۶ تا (۳۴٪) با ي/ك/ى عربی ثبت شده‌اند و ۲۱ گروه
# «دو-نویشتاری» وجود دارد (ماهیانه ۲۷ گروه). نتیجهٔ عملی:
#   scan_symbol('داریک') → WHERE symbol='داریک' → ۰ ردیف → nodata/امتیاز ۰
#   bulk_scan            → کلید از خودِ دیتابیس (نوشتار عربی) → داده کامل
# یعنی /api/fts/{symbol} و /api/screener دو پاسخ متفاوت به یک نماد می‌دادند.
#
# چرا `WHERE SI.key(symbol)=?` راه‌حل نیست (روی همین market.db اندازه گرفته شد):
#   نماد خام =  ۰٫۰۱ میلی‌ثانیه   (SEARCH USING COVERING INDEX ix_fs_symbol)
#   norm_fa() =  ۵٫۷۴ میلی‌ثانیه   (اسکن کامل ۸۰۰۹ ردیف — ایندکس قابل استفاده نیست)
# هر scan_symbol ~۱۹ کوئری می‌زند و scan_all روی ۸۶۸+ نماد اجرا می‌شود →
# افزودن تابع به WHERE یعنی ~۹۵ ثانیه رگرسیون. پس کلیدِ نرمال باید «در Python»
# ساخته شود و به شکل `symbol IN (?,?...)` به SQL برود: همان ایندکس، ۰٫۰۹ms.
_YA_CLASS = (_YA_FA, _YA_AR, "\u0649")       # ی  ي  ى  → هر سه norm_fa یکسان
_KAF_CLASS = ("\u06a9", _KAF_AR)             # ک  ك
_CHAR_CLASS = {}
for _c in _YA_CLASS:
    _CHAR_CLASS[_c] = _YA_CLASS
for _c in _KAF_CLASS:
    _CHAR_CLASS[_c] = _KAF_CLASS
# «فاصله ↔ نیم‌فاصله» عمداً اینجا اضافه نشده: ضربِ آن با جایگشت‌هایِ ی/ك
# بی‌حد می‌شود (سنجشِ بانکِ کاری: با سقفِ ۹۶ بیشینۀ جایگشت ۲۱۶ و با سقفِ ۲۵۶
# باز ۶۴۸ شد، یعنی سقف فقط نقطۀ برش را جابه‌جا می‌کند). واگراییِ «شهر فرش»
# که از این می‌آید درِ `docs/fts-notes/CODAL-AUDIT-ROUND2-2026-10-12.md` بند
# ۹-پ) با عدد ثبت شده و راهِ درستش مقایسه رویِ کلیدِ نرمال‌شده است، نه
# حدسِ نوشتارها.
del _c


def sym_in(conn, col: str, symbol, domain=None):
    """(شرح SQL, پارامترها) برای «همۀ نوشتارهایِ همین ابزار در همین بانک».

    Stage 1.2: این تابع دیگر هیچ جایگشتِ نویسه‌ای نمی‌سازد؛ نامزدها از خودِ
    بانک خوانده می‌شوند (`symbol_identity`). پیش‌تر کارت با جایگشتِ ي/ك/ى و
    حذفِ نیم‌فاصله، نوشتارِ «شهر »+نیم‌فاصله+«فرش» را هرگز نمی‌ساخت، پس ۶ از ۷
    گزارشِ آن صادرکننده را نمی‌دید (۱۶۷۵ جفتِ نماد×جدول واگرایی، سنجیده‌شده؛
    همیشه در جهت «قیف می‌بیند، کارت نمی‌بیند»).

    `conn` اجباری است: بی‌بانک نمی‌توان دانست کدام نوشتار واقعیت دارد.
    """
    return SI.pred(conn, col, symbol, domain or SI.CODAL)


def symbol_variants(conn, symbol, domain=None):
    """نامزدهای خامِ یک نماد — جانشینِ `symbol_aliases` در مصرف‌کننده‌های متنی."""
    return SI.variants(conn, symbol)


def sym_key(symbol) -> str:
    """کلیدِ هویتِ نماد — تنها چیزی که نقشه‌های کل‌بازاری با آن می‌سازند."""
    return SI.key(symbol)


def symbol_class_siblings(conn, symbol):
    """خطِ کلاسِ یکتای همان نام درِ تابلو — فقط با ردپا، بی‌رقم‌چندنفری."""
    return SI.class_siblings(conn, symbol)


def symbol_pending_siblings(conn, symbol):
    """نامزدِ خطِ کلاس که ادغامش بسته شده — برایِ اعلام درِ کارت، بی‌ادغام."""
    return SI.pending_siblings(conn, symbol)


def symbol_pending_variants(conn, symbol, domain=None):
    """نامزدهایِ الحاقِ بسته‌شدۀ خودِ نماد (پسوندِ رقمی) با شاهد."""
    return SI.pending_variants(conn, symbol, domain or SI.CODAL)


def symbol_evidence(conn, symbol, domain=None) -> str:
    """چطور این نماد به ردیف‌ها رسید: same-key | isin-agree | pending-review |
    isin-clash | unmatched. «بی‌شاهدِ ISIN» دیگر ادغام نمی‌شود (رأیِ مالک)."""
    return SI.evidence(conn, symbol, domain or SI.CODAL)


def register_sql(conn):
    """`sym_key` را به SQLite می‌دهد (کنارِ `norm_fa` برای مصرف‌های نوشتاری).

    چرا لازم است: تا وقتی کوئریِ SQL روی ستونِ نماد تابع می‌نشاند، آن تابع
    **باید** همان کلیدِ پایتون باشد. `api/fundamental._INSTR_SQL` زنجیرۀ
    REPLACE دست‌سازِ خودش را داشت (ي/ك را یکی می‌کرد ولی نیم‌فاصله و فاصله را
    نه) — یعنی چهارمین تعریفِ هویت. حالا آن کوئری `sym_key` را صدا می‌زند.
    هزینه تابع در WHERE عوض نمی‌شود (~۵٫۷ms در برابر ~۰٫۰۱ms برای IN)، پس
    `sym_in` همان `IN` را با نامزدهایِ واقعی می‌دهد.

    توجه: این تابع در مسیرِ «کوئری تک‌نمادی» استفاده **نمی‌شود** — همان‌طور
    که بالاتر اندازه گرفته شد، ۵۷۴ برابر کند از ایندکس است. جای درستش
    build-side است: کوئری‌های کل‌بازاری که از قبل جدول را کامل می‌خوانند
    (m141_map، ساخت نقشه‌ها) و هر فیلتر SQL که در آینده روی نوشتار لازم باشد.
    """
    try:
        conn.create_function("norm_fa", 1, norm_fa, deterministic=True)
        conn.create_function("sym_key", 1, SI.key, deterministic=True)
    except Exception:
        pass                       # اتصال read-only / نسخهٔ بی‌deterministic
    return conn


# ================================================== FTS v2.2: جداولِ مرجعِ F-04/F-05
# دو جدولِ نماد→صنعت و اسنپ‌شاتِ ارزشِ بازار در مهاجرتِ افزودنی ساخته شدند،
# ولی تا پیش از این هیچ نویسنده‌ای نداشتند (داده فقط از instruments /
# market_watchِ «همین الان» خوانده میشد). طبقِ تصمیم: نویسنده در
# dev/codal_fts_updater است و خواننده‌هایِ زیر با fallback شفاف کار میکنند —
# یعنی جدولِ خالی = همان رفتارِ قبلی، و هیچ مسیرِ موجودی نمی‌شکند.
#
# هر دو تابع نمادِ نرمال‌شده (norm_fa) را به‌عنوان کلید می‌خواهند تا با
# کلیدِ سایرِ نقشه‌ها (m141_map و غیره) یکسان بماند.

_SECTOR_CACHE: dict = {}          # (id(conn)) -> {norm_symbol: sector_name}
_MCAP_CACHE: dict = {}            # (id(conn)) -> {norm_symbol: (date, market_cap)}


def _table_exists(conn, name: str) -> bool:
    try:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone())
    except Exception:
        return False


def sector_of(conn, symbol: str, fallback: str = "") -> str:
    """نامِ صنعتِ نماد — اول از جدولِ مرجعِ symbol_sectors، با fallback.

    fallback: جدول خالیست / نماد در آن نیست / جدول وجود ندارد → همان
    `fallback` برمی‌گردد (فراخواننده آن را از instruments.sector_name می‌آورد).
    """
    if not symbol:
        return fallback
    key = id(conn)
    tab = _SECTOR_CACHE.get(key)
    if tab is None:
        tab = {}
        if _table_exists(conn, "symbol_sectors"):
            try:
                for sym, name in conn.execute(
                        "SELECT symbol, sector_name FROM symbol_sectors"):
                    if sym and name:
                        tab[SI.key(sym)] = name
            except Exception:
                tab = {}
        _SECTOR_CACHE[key] = tab
    return tab.get(SI.key(symbol)) or fallback


def market_cap_at(conn, symbol: str, date: str = "",
                  fallback: Optional[float] = None) -> Optional[float]:
    """ارزشِ بازار در `date` (یا نزدیک‌ترین تاریخِ ماقبل آن) — ریال.

    F-04 میخواهد ارزشِ بازار را در **زمانِ گزارش** بسنجد، نه فقط امروز.
    fallback: اسنپ‌شاتی در/قبل از `date` نبود → `fallback` (فراخواننده مقدارِ
    امروز را می‌دهد). هیچ‌وقت ۰ برنمی‌گرداند که نسبت را بی‌نهایت کند
    (None = «قابل محاسبه نبود»).
    """
    if not symbol:
        return fallback
    key = id(conn)
    tab = _MCAP_CACHE.get(key)
    if tab is None:
        tab = {}
        if _table_exists(conn, "market_cap_snapshots"):
            try:
                # هر نماد ممکن است چندین اسنپ‌شات در تاریخ‌های مختلف داشته باشد
                # (هر اجرای updater یک ردیف برای همان روز مینویسد)؛ همه را
                # میخوانیم و به ترتیبِ تاریخ نگه میداریم.
                buckets: dict = {}
                for sym, d, mc in conn.execute(
                        "SELECT symbol, date, market_cap FROM market_cap_snapshots"):
                    if not sym or mc is None:
                        continue
                    buckets.setdefault(SI.key(sym), []).append((d or "", _f(mc)))
                for k, lst in buckets.items():
                    lst.sort(key=lambda t: t[0])
                    tab[k] = lst
            except Exception:
                tab = {}
        _MCAP_CACHE[key] = tab
    lst = tab.get(SI.key(symbol))
    if not lst:
        return fallback
    if not date:
        return lst[-1][1]                    # جدیدترین اسنپ‌شات
    # آخرین اسنپ‌شاتی که تاریخش <= تاریخِ درخواستی است («نزدیک‌ترین ماقبل»).
    # تاریخِ درخواستی قبل از قدیمی‌ترین اسنپ‌شات است → هیچ داده‌ای در آن زمان
    # نداشتیم → fallback، تا مقدارِ آینده به‌عنوانِ گذشته گزارش نشود.
    best = None
    for d, mc in lst:
        if d and d <= date:
            best = (d, mc)
        else:
            break                            # lst سورت‌شده است
    return best[1] if best else fallback


# ═══════════════════════════════════════════════════════════════════════════
# لایهٔ مادی‌سازیِ خروجیِ v10 (تسک ۱۹ — جدول fts_results)
# ═══════════════════════════════════════════════════════════════════════════
# همان الگوی تصمیم ۴ (sector_of / market_cap_at): نویسنده در dev/codal_fts_updater،
# خواننده با fallback اینجا. جدولِ غایب/خالی/ناهم‌خوان با cfg = همان رفتارِ قبلی
# (محاسبهٔ زنده با evaluate_v10)، پس مسیرِ v8 اسکرینر رفتارش عوض نمیشود.
_FTS_RESULTS_CACHE: dict = {}          # id(conn) -> {"cfg_hash": str, "rows": {norm_symbol: tuple}}

# ترتیبِ ستون‌های SELECT در fts_results_of (اندیس‌های ۰-پایه):
#   0 symbol          1 f01_growth_pct   2 f01_pass        3 f02_eps_series(JSON)
#   4 f02_pass        5 f03_margin_pct   6 f03_pass        7 f04_ratio
#   8 f04_pass        9 f05_verdict     10 f05_pass       11 score
#  12 verdict        13 excluded        14 exclusion_reasons
#  15 i1a_pass       16 i1b_pass        17 i4a_pass       18 i4b_pass
#  19 rev_growth     20 gross_margin    21 sales_to_mcap  22 profit_potential_pct
#  23 annual_sales_bt  24 annualize_months  25 cfg_hash
_FTS_RESULTS_COLS = (
    "symbol, f01_growth_pct, f01_pass, f02_eps_series, f02_pass,"
    " f03_margin_pct, f03_pass, f04_ratio, f04_pass, f05_verdict, f05_pass,"
    " score, verdict, excluded, exclusion_reasons,"
    " i1a_pass, i1b_pass, i4a_pass, i4b_pass,"
    " rev_growth, gross_margin, sales_to_mcap, profit_potential_pct,"
    " annual_sales_bt, annualize_months, cfg_hash",
)


def invalidate_fts_results(conn, symbols=None) -> int:
    """حذفِ ردیف‌های مادی‌شده (و کشِ خواننده).

    سینکِ کدال/تابلو هر دو کشِ اسکرینر و این جدول را کثیف می‌کند؛
    invalidate_screener_cache این را صدا میزند. برمی‌گرداند: تعداد ردیفِ حذف‌شده.

    `symbols` (افزودنی، بندِ ۷ مأموریتِ خودکارسازی): فقط ردیفِ همان نمادها
    می‌رود، پس یکِ اطلاعیهٔ تازه کلِ جدولِ مادی‌شده را بی‌دلیل دور نمی‌ریزد.
    کشِ خواننده به‌هرحال پوپ می‌شود: کلیدهایِ آن `norm_symbol` است و حذفِ
    تک‌نمادیِ آن نقشه بی‌مدرک درست نمی‌ماند — یکِ SELECTِ دوباره‌سازی به‌ازایِ
    محاسبۀ مجددِ کلِ بازار خیلی ارزان‌تر است (محاسبۀ محافظه‌کارانهٔ بیشتر،
    نتیجهٔ کهنه نه).
    """
    n = 0
    syms = [str(x) for x in (symbols or []) if str(x or "").strip()]
    try:
        if syms:
            ph = ",".join("?" * len(syms))
            n = int(conn.execute(
                "DELETE FROM fts_results WHERE symbol IN (%s)" % ph, syms).rowcount or 0)
        else:
            n = int(conn.execute("DELETE FROM fts_results").rowcount or 0)
        conn.commit()
    except Exception:
        n = 0
    _FTS_RESULTS_CACHE.pop(id(conn), None)
    return n


def ind4_na(card_ind4) -> bool:
    """آیا کارتِ جزئیات، شاخص ۴ را «کاربرد ندارد» اعلام کرده؟

    رأیِ مالک (۱۴۰۵-۰۷-۰۳): معافیت = نظر نمی‌دهد، نه پاسِ رایگان و نه رد.
    کارت این را در `na`/`exempt` می‌گوید و `passes` را bool نگه می‌دارد
    (امتیاز همان ۰ می‌ماند). هر کسی که حکمِ کارت را به ستونِ جدولِ غربالگری
    کپی می‌کند — اسکرینرِ زنده و نویسندهٔ fts_results — باید همین را بپرسد،
    وگرنه یک نماد با کشِ سرد «مردود» و با کشِ گرم «N/A» می‌شود.
    """
    return bool(card_ind4) and (card_ind4.get("na") is True
                                or card_ind4.get("exempt") is True)


def ind1_na(card_ind1) -> bool:
    """آیا کارت، محور ۱ (رشد فروش/درآمد) را «سنجیده نشده» اعلام کرده؟

    همان رأیِ ۱۶ که برای ۲/۳/۴ جاری است و برایِ محور ۱ جا افتاده بود:
    `api/screener` برایِ سه محورِ دیگر `_na2/_na3/_na4` را می‌پرسد و سپس
    `i{n}_pass` را None می‌کند، ولی محور ۱ را بی‌پرسش از `passes` برمی‌داشت
    که عمداً bool است. سنجشِ زندهٔ ۱۴۰۵-۰۷-۲۳: «شهر فرش» و «شتهران» درِ کارت
    «بی‌داده» و درِ `/api/screener` «مردود» بودند — دو پاسخ برایِ یکِ نماد.
    «بی‌داده» یعنی هیچ درصدی ساخته نشده (مخرج YoY غایب)، نه درصدِ زیرِ کف.
    """
    if not card_ind1:
        return False
    mon = card_ind1.get("monetary") if isinstance(card_ind1.get("monetary"), dict) else card_ind1
    return bool(mon.get("data_gap")) or mon.get("monetary_pct") is None


def ind2_na(card_ind2) -> bool:
    """آیا کارتِ جزئیات، شاخص ۲ (سابقۀ سه‌سالۀ EPS) را «سنجیده نشده» اعلام کرده؟

    همان رأیِ ۱۳/۱۶ که برایِ شاخص ۳ و ۴ جاری است: سابقه‌ای که یک اسلاتش از
    صورتهایِ تلفیقی است (جزوه ص ۴: «تلفیقی مدنظر ما نیست») «رد» نیست. کارت
    `na: True` می‌گوید و `passes` را bool نگه می‌دارد، پس هر کپی‌کاریِ حکم به
    ستونِ جدول باید جدا بپرسد (الگوی `ind3_na`/`ind4_na`) — وگرنه همان نماد در
    فیلترِ «حذفِ مردودها» مردود شمرده می‌شود.
    """
    return bool(card_ind2) and card_ind2.get("na") is True


def ind3_na(card_ind3) -> bool:
    """آیا شاخص ۳ (حاشیهٔ ناخالص) «N/Aِ طبقه» است — نه شکافِ داده؟

    همان رأی ۱۶ در شاخص ۳: «بی‌داده» با «رد» یکی نیست. کارت در حالتِ
    not_applicable فقط `na: True` را می‌گوید و `passes` را عمداً bool نگه
    می‌دارد، پس هر کپی‌کاری که حکمِ کارت را به ستونِ سه‌حالۀ جدول می‌برد باید
    جدا بپرسد. بدونِ این، صندوق و نمادی که سطرِ «سود ناخالص» ندارد سرخِ «رد»
    می‌شوند (شاهد ۲۰۲۶-۰۹-۳۰: ۲۹۷ ردیف از ۸۷۳ با gross_margin تهی در
    اسکرینرِ زنده، و اندوخته داريوش در قیف).

    از Task 10B2a1 (fix round 1) کارت `na_kind` را هم می‌دهد:
    `"class"` = ماهیتِ مالی/بانکی/هلدینگ/صندوق (N/Aِ خاکستری) و
    `"data"` = شکافِ داده (نبودِ صورتِ مالی/سطرِ سود ناخالص). فقط `"class"`
    پرچمِ N/A می‌گیرد؛ شکافِ داده حکمِ None دارد ولی «N/Aِ ماهیت» نیست و
    جدول باید تفاوت را نشان دهد (پیش از این ۱۱۷ ردیفِ شکاف چنین برچسبی
    می‌گرفتند).

    سازگاریِ عقب‌رو: payloadهایِ قدیمی (مسیرِ مادی‌شدهٔ `fts_results` و کارتِ
    کش‌شده) `na_kind` ندارند؛ برایشان همان رفتارِ پیشین حفظ می‌شود
    (`na`/`exempt`/`margin_pct is None` ⇒ N/A).
    """
    if not card_ind3:
        return False
    kind = card_ind3.get("na_kind")
    if kind == "class":
        return True
    if kind == "data":
        return False
    return bool(card_ind3.get("na") is True or card_ind3.get("exempt") is True
                or card_ind3.get("margin_pct") is None)


def _tp(v):
    """ستونِ پاسِ جدول → سه‌حاله (None همان «نظر نمی‌دهد» می‌ماند — رأی ۱۶)."""
    return None if v is None else bool(v)


def _fts_row_to_result(r) -> dict:
    """تبدیلِ یک ردیفِ خامِ fts_results به همان شکلِ خروجیِ evaluate_v10.

    فقط فیلدهایی که اسکرینر/واچ‌لیست می‌خوانند بازسازی میشوند؛ بقیقۀ لایه‌های
    تشخیصی (series/ref/profile) عمداً ذخیره نمیشوند — مسیرِ کارتِ جزئیات همچنان
    evaluate_v10 زنده را صدا میزند و جدول فقط کشِ جدولِ بازار است.
    """
    import json as _json
    eps_series = None
    try:
        if r[3]:
            eps_series = _json.loads(r[3])
    except Exception:
        eps_series = None
    return {
        "score": int(r[11] or 0),
        # مسیرِ مادی‌شده جدول fts_results را می‌خواند و ستونِ primary ندارد؛ از
        # همان سه بیتِ ذخیره‌شده مشتق می‌شود تا پاریتیِ scan_symbol حفظ شود.
        "primary_score": int(bool(r[2])) + int(bool(r[4])) + int(bool(r[6])),
        "verdict": r[12] or "",
        "excluded": bool(r[13]),
        "exclusion_reasons": (r[14].split(" · ") if r[14] else []),
        "pricing_mode": r[9],
        # رأی ۱۶: None در ستونِ پاس یعنی «این شاخص سنجیده نشد» (معافیت/صندوق)؛
        # جدول ستون‌هایش را nullable ساخته، پس باز هم None می‌ماند. بی‌این،
        # اسکرینر با کشِ مادی‌شده همان نماد را «رد» می‌گفت که بی‌کش «نظر
        # نمی‌دهد» می‌گفت.
        "passes": {
            "1_growth": _tp(r[2]),
            "2_eps_trend": _tp(r[4]),
            "3_gross_margin": _tp(r[6]),
            "4_sales_to_mcap": _tp(r[8]),
            "5_industry": _tp(r[10]),
            "1a_monetary_growth": _tp(r[15]),
            "1b_volume_growth": _tp(r[16]),
            "4a_sales_to_mcap": _tp(r[17]),
            "4b_profit_potential": _tp(r[18]),
        },
        "indicators": {
            "1": {"monetary": {"monetary_pct": r[1]}, "volume": {}},
            "2": {"eps_series": eps_series},
            "3": {"margin_pct": r[5], "margin_tier": margin_tier(r[5])},
            "4": {"sales_to_mcap": r[7], "potential_pct": r[22],
                  "annual": {"annual_sales_bt": r[23], "months_used": r[24]}},
            "5": {"verdict": r[9]},
        },
    }


def _fts_results_table(conn, cfg_hash: str = "") -> Optional[dict]:
    """خواندنِ یکبارهٔ کل جدول + بررسیِ اعتبارِ cfg_hash.

    برمی‌گرداند: {"cfg_hash": str, "rows": {norm_symbol: tuple}} یا None اگر جدول
    غایب/خالی باشد یا cfg_hashِ ذخیره‌شده با cfg_hashِ درخواستی ناهم‌خوان باشد
    (یعنی آستانه‌ها تغییر کرده‌اند → محاسبهٔ قدیمی دیگر معتبر نیست).
    """
    if not _table_exists(conn, "fts_results"):
        return None
    try:
        rows = conn.execute("SELECT %s FROM fts_results" % _FTS_RESULTS_COLS[0]).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    # نویسنده همهٔ ردیف‌ها را با یک cfg_hash در یک تراکنش مینویسد؛ اگر با cfgِ
    # درخواستی نمی‌خواند، کل جدول متعلق به پیکربندیِ قدیمی است → بی‌اعتبار.
    stored = rows[0][25]
    if cfg_hash and stored and stored != cfg_hash:
        return None
    tab = {"cfg_hash": cfg_hash or stored or "", "rows": {}}
    for r in rows:
        k = SI.key(r[0])
        if k and k not in tab["rows"]:
            tab["rows"][k] = r
    return tab


def fts_results_of(conn, symbol: str, cfg_hash: str = "") -> Optional[dict]:
    """خروجیِ مادی‌شدهٔ v10 برای یک نماد — یا None (fallback به محاسبهٔ زنده).

    None برمی‌گرداند اگر: جدول نباشد / خالی باشد / cfg_hash ناهم‌خوان باشد /
    نمادی در آن نباشد. فراخواننده در آن حالت دقیقاً مسیرِ evaluate_v10 را
    اجرا می‌کند — یعنی یک DB قدیمی یا خالی رفتارِ امروزی را دارد.
    """
    if not symbol:
        return None
    key = id(conn)
    tab = _FTS_RESULTS_CACHE.get(key)
    if tab is None or tab.get("cfg_hash") != (cfg_hash or ""):
        tab = _fts_results_table(conn, cfg_hash=cfg_hash)
        if tab is None:
            tab = {"cfg_hash": cfg_hash or "", "rows": {}}
        _FTS_RESULTS_CACHE[key] = tab
    r = (tab.get("rows") or {}).get(SI.key(symbol))
    if r is None:
        return None
    return _fts_row_to_result(r)


def fts_results_bulk(conn, cfg_hash: str = "") -> Optional[dict]:
    """تمامِ ردیف‌های مادی‌شده به‌صورتِ norm_symbol -> نتیجه (یک SELECT).

    برای مسیرِ دسته‌ای اسکرینر — به‌جای ~۲۵۰۰ فراخوانیِ evaluate_v10. همان
    قراردادِ fts_results_of: None یعنی «جدول بی‌اعتبار/خالی → fallback زنده».
    """
    key = id(conn)
    tab = _FTS_RESULTS_CACHE.get(key)
    if tab is None or tab.get("cfg_hash") != (cfg_hash or ""):
        tab = _fts_results_table(conn, cfg_hash=cfg_hash)
        if tab is None:
            _FTS_RESULTS_CACHE[key] = {"cfg_hash": cfg_hash or "", "rows": {}}
            return None
        _FTS_RESULTS_CACHE[key] = tab
    rows = tab.get("rows") or {}
    if not rows:
        return None
    return {k: _fts_row_to_result(v) for k, v in rows.items()}


# ================================================== شاخص ۵: دیکشنری قیمت‌گذاری
# همهٔ توکن‌ها به نوشتار نرمال (ی/ک فارسی) ذخیره میشوند و با norm_fa(sector) سنجیده‌اند.
# فهرست با ۵۵ sector_name واقعیِ جدول instruments راستی‌آزمایی شده است.

# قیمت‌گذاری دستوری / کنترل‌شده (حذف از سبد FTS) — حکمِ مالک (Task 8): فقط
# سه صنعتِ الزامیِ جزوه: خودرو/قطعات · نیروگاه (عرضه/تولید/توزیع برق) · لاستیک.
# قند و شکر و شوینده الزامی نیستند؛ «شوینده» هم تگِ مستقل در TSETMC ندارد.
# بیمه هم این‌جا نیست — وتویِ سختِ جداگانه است (`reject_insurance`) و در
# risk_gates/bulk_scan/scan_symbol اعمال می‌شود.
# سند v2.1 + جدولِ ص ۶ جزوه: «دارو» و «غذای عمومی» یک‌جا رد نمی‌شوند (در جزوه
# هر دو ✓‌اند، غذا با برچسب «کنترل قیمت»؛ ✗ فقط خودرو، نیروگاهی و لاستیک‌اند).
MANDATORY_PRICING_TOKENS = (
    "خودرو", "نقلیه موتور", "لاستیک",
    "نیروگاه", "عرضه برق", "تولید برق", "توزیع برق",
)

# قیمت‌گذاری آزاد / بورس کالا (اولویت مثبت):
FREE_PRICING_TOKENS = (
    "سیمان", "آهک", "شیمیایی", "پتروشیمی", "فلزات", "کانه", "کانی", "کاشی", "سرامیک", "شیشه",
    "فرآورده‌های نفتی", "نفت", "زغال سنگ", "معادن", "محصولات فلزی",
    "مس", "فولاد", "سرب و روی", "رایانه", "اطلاعات", "نرم افزار",
)

# صنعت بیمه — حذف قطعی از خروجی (بخش ۲ دستور کار).
INSURANCE_TOKENS = ("بیمه", "بازنشستگی")


def sector_core(sector: str) -> str:
    """برچسبِ صنعت تا پیش از بندِ «به جز …» — نرمال‌شده.

    «محصولات غذايي و آشاميدني **به جز قند و شكر**» اسمِ همان صنعتِ غذایی است که
    در جدولِ ص ۶ جزوه ✓ خورده؛ ولی چون زیررشتهٔ «قند و شكر» *داخلِ استثنایِ نام*
    آمده، تطبیقِ ساده آن را «دستوری» می‌کرد و نماد را از غربالگری حذف. بندِ
    استثنا را که ببریم، هم «قند و شكر» واقعی دستوری می‌ماند و هم غذاییِ «به جز
    قند و شکر» آزاد/خنثی. (نسخۀ بدونِ فاصلهٔ «به جزتامين» هم با همین پیشوند
    گرفته می‌شود.)
    """
    s = norm_fa(sector or "")
    for cut in ("به جز", "به استثنا", "به حذف"):
        i = s.find(cut)
        if i > 0:
            s = s[:i]
    return s.strip()


def pricing_mode(sector: str) -> str:
    """طبقه‌بندی صنعت: 'mandatory' | 'free' | 'neutral' (همیشه نرمال‌سازی‌شده)."""
    s = sector_core(sector)
    if not s:
        return "neutral"
    # دستوری اولویت دارد: اگر صنعتی در هر دو فهرست بیفتد، احتیاطاً مردود است
    if any(norm_fa(t) in s for t in MANDATORY_PRICING_TOKENS):
        return "mandatory"
    if any(norm_fa(t) in s for t in FREE_PRICING_TOKENS):
        return "free"
    return "neutral"


def is_insurance_sector(sector: str) -> bool:
    """آیا صنعت بیمه است؟ (روی sector_name تست میشود، نه روی نماد — رفع باگ v7.3)"""
    s = norm_fa(sector)
    return bool(s) and any(norm_fa(t) in s for t in INSURANCE_TOKENS)


# ==================================================== انتخاب صورت‌مالیِ مرجع
def _is_audited(title: str) -> bool:
    """عنوان شامل «حسابرسی شده» باشد و «نشده» نداشته باشد."""
    t = norm_fa(title)
    return ("حسابرسی شده" in t) and ("نشده" not in t)


def _is_consolidated(title: str) -> bool:
    """عنوان «تلفیقی» دارد و «غیرتلفیقی» ندارد — الگوی `_is_audited`.

    بدونِ بندِ دوم، «صورت مالی ۱۲ماهه حسابرسی‌شدهٔ **غیرتلفیقی**» تلفیقی خوانده
    می‌شود و رأیِ ۱۳ سرِ همان نماد می‌نشیند. در بانکِ امروز چنین عنوانی صفر ردیف
    دارد (سنجش: ۷۵۳ عنوانِ متمایز)، ولی فیکچرهایِ تست و نوشتارِ کدال فردا را
    نباید با زیررشته‌ای باطل کرد.
    """
    t = norm_fa(title or "")
    return "تلفیقی" in t and "غیرتلفیقی" not in t


def _is_amendment(title: str) -> bool:
    return "اصلاحیه" in norm_fa(title)


def row_conflicts(period_end, title, period_months) -> list:
    """تناقض‌هایِ اعلامی یکِ ردیف: دوره/ماه درِ متن با درِ ستون نمی‌خواند.

    بندِ ۱.۲/۱۰ مأموریت: ردیفی که عنوان، شرکت، دوره و نمادش یکی نیستند باید
    درِ انتخابِ مرجع **دیده** شود، نه خاموش رد یا خاموش پذیرفته. اینجا هیچ
    آستانه‌ای وضع نمی‌شود و هیچ ردیفی کنار نمی‌رود (آن رأیِ مالک است، نه
    حدسِ مهندس) — فقط برچسبِ تناقض رویِ ردیف می‌نشیند و درِ همان
    `reference_identity` که ابهامِ هویت را اعلام می‌کند خوانده می‌شود.

    دو تناقضِ سنجیده‌شده رویِ ۸٬۷۲۳ ردیفِ بانکِ کاری (۱۴۰۵-۰۷-۲۲):
      * `title_period`: دورۀ داخلِ عنوان ≠ دورۀ ستون — صفر ردیف؛ یعنی
        زنجیرۀ `codal_periods.derive` امروز می‌خواند و این نگهبانِ روزِ بعد است.
      * `title_months`: «X ماهه» درِ عنوان ≠ `period_months` — ۱ ردیف
        («۶ ماهه» با `period_months=12`، tracing_no 1447293) و ۳۸ ردیفِ
        `period_months` خالی. شاخص ۲ فقط سالانۀ ۱۲ماهه می‌خواهد، پس همین
        یکی هم رأیِ «دو تا سالِ کامل» را می‌تواند بسازد؛ اعلام می‌شود تا
        داوریِ بعدی رویِ عددِ حدسی نشیند.
    """
    out = []
    t = str(title or "")
    tp = CP.from_title(t)
    pe = CP.canonicalize(period_end)
    if tp and pe and tp != pe:
        out.append("title_period")
    tm = CP.months_from_title(t)
    try:
        pm = int(period_months) if period_months is not None and str(period_months).strip() else None
    except (TypeError, ValueError):
        pm = None
    if tm and pm and tm != pm:
        out.append("title_months")
    return out


# پسوندهای پرانتزیِ «مقطعِ نامه»، نه نامِ شرکت — همان سه زیررشته‌ای که
# `_is_audited`/`_is_consolidated`/`_is_amendment` می‌خوانند.
_TITLE_SCOPE_MARKS = ("حسابرس", "تلفیق", "اصلاحی")

# نشانۀ «اسمِ یکِ شخصیتِ حقوقی»: کدال شرکتِ فرعی را درِ پرانتز با نامِ
# خودش و با این پیشوندها می‌نویسد. بی‌این شرط، صفت‌هایِ بی‌نام هم «شرکتِ
# دیگر» خوانده می‌شدند — سنجشِ بانکِ کاری: از ۱۹۱ پسوندِ درِ
# financial_statements دقیقاً ۱۸۹ تا با نشانۀ شخصیت‌اند و ۲ تایِ باقی‌مانده
# صفتِ «شامل مقادیر برآوردی» (بی‌نام) بودند.
_TITLE_ENTITY_MARKS = ("شرکت", "شرکای", "موسسه", "مؤسسه", "گروه",
                        "بانک", "بانك", "صندوق", "بیمه", "بيمه")
# واژه‌هایِ عمومیِ پس از نشانهد: «(شرکت اصلی)» نامِ شرکتِ دیگری نیست.
_TITLE_ENTITY_GENERIC = ("اصلی", "مادر", "خود", "دیگر", "همه", "فرعی")
_TITLE_PAREN_OPEN = "（("
_TITLE_PAREN_CLOSE = "）)"


def _entity_span(span):
    """آیا این پرانتزِ عنوان نامِ یکِ شخصیتِ حقوقی است؟ اگر نه، رشتهٔ خالی."""
    t = str(span or "").strip()
    if len(t) <= 2 or any(m in t for m in _TITLE_SCOPE_MARKS):
        return ""
    if not t.startswith(_TITLE_ENTITY_MARKS):
        return ""
    rest = t.split(" ", 1)[1].strip() if " " in t else ""
    if not rest or rest in _TITLE_ENTITY_GENERIC:
        return ""
    return t


def title_entity_suffix(title: str) -> str:
    """نامِ شرکتِ دیگری که درِ پایانِ عنوانِ نامه آمده، یا ''.

    کدال صورتِ مالیِ شرکت‌هایِ فرعی را زیرِ نمادِ هلدینگ منتشر می‌کند و آن شرکت
    را در پرانتزِ آخرِ عنوان می‌نویسد: «… (حسابرسی شده) (شرکت هلپاک)». چنین
    ردیفی *وضعیتِ مالیِ شرکتِ دیگری* است، نه خودِ نماد — پس نمی‌تواند نمایندۀ
    آن نماد باشد. این تابع فقط «هویتِ filed-by» را می‌خواند؛ هیچ رأیِ مالیِ
    دوم نمی‌سازد و هیچِ توابعِ بالا را تغییر نمی‌دهد. بی‌regex، چون این ماژول
    `re` را وارد نمی‌کند (همان قراردادی که `_is_consolidated` را ساده نگه داشته).

    مصرفِ همین حالا: لایۀ صفرِ `statement_rank` — یعنی کارتِ بنیادی،
    موتورِ قیف (`annual_statements`/`pick_reference`)، نویسندۀ
    `codal_fetcher.period_winners` و سریِ فصلی (`quarter_reference_rows`)
    هر چهار رأیِ «کدامِ ردیف نمایندۀ این نماد است» را از یکِ تابع می‌گیرند.
    هیچ ردیفی به‌خاطرِ این لایه حذف نمی‌شود؛ فقط از دیدِ انتخابِ مرجع کنار
    می‌رود (سیاستِ CA-3: تاریخچه حفظ است).
    """
    s = str(title or "")
    found = ""
    i, n = 0, len(s)
    while i < n:
        if s[i] in _TITLE_PAREN_OPEN:
            j = i + 1
            while j < n and s[j] not in _TITLE_PAREN_CLOSE:
                j += 1
            span = norm_fa(s[i + 1:j]).strip()
            hit = _entity_span(span)
            if hit:
                found = hit
            i = j + 1
        else:
            i += 1
    return found


# ═══════════════════════════════════════════════════════════════════════════
#  تک‌منبعِ «کدامِ ردیف، این دورۀ این نماد را نمایندگی می‌کند»
#  (نویسنده: codal_fetcher.period_winners — خواننده‌ها: annual_statements،
#   reference_annual، کارتِ بنیادی، اسکرینر، dev/db_housekeeping)
# ═══════════════════════════════════════════════════════════════════════════
# هیچ آستانه‌ای اینجا نیست: فقط «چند ستونِ کلیدی عدد دارد» شمرده می‌شود.
FS_NUMBER_KEYS = ("revenue", "gross_profit", "operating_profit", "net_profit", "basic_eps")
MS_NUMBER_KEYS = ("monthly_revenue", "ytd_revenue", "monthly_volume", "ytd_volume")


def row_completeness(keys, row) -> int:
    """شمارِ ستون‌هایِ کلیدیِ پُرشدهٔ یکِ ردیف (None/«» = خالی؛ صفرِ واقعی پُر است)."""
    n = 0
    for k in keys:
        v = row.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        n += 1
    return n


def statement_rank(keys, consolidated, completeness, tracing_no,
                   other_entity=False) -> tuple:
    """کلیدِ ascendingِ «برنده اول»: هویتِ شرکت، مبنایِ جزوه، کامل‌بودن، تازگی.

    ۰) ردیفی که *شرکتِ دیگری* درِ عنوانش ذکر شده (صورتِ مالیِ شرکتِ فرعی که
       کدال زیرِ نمادِ هلدینگ منتشر می‌کند: «… (شرکت هلپاک)») نمایندۀ این نماد
       نیست و همیشه کنار می‌رود. این لایه *همین‌جا* است، نه درِ خواننده‌ها —
       وگرنه کارت/قیف/سریِ فصلی سه رأیِ متفاوت می‌گرفتند (`title_entity_suffix`).
    ۱) غیرتلفیقی (مبنایِ جزوه) برِ تلفیقی — این جابه‌جا نمی‌شود.
    ۲) ردیفی که ستون‌هایِ کلیدیِ پُرتر دارد برنده است. این لایه پیش ازِ این نبود
       و نتیجه‌اش آن بود که پوستۀ بی‌عددِ تازه‌تر (نامه‌ای که پارسر عددش را
       نخوانده) ردیفِ عدددارِ کهنه‌تر را می‌کُشت — سنجیده رویِ بانکِ کاری
       ۱۴۰۵-۰۷-۱۰: ومهرگان ۱۴۰۱/۰۶/۳۱ و ۱۴۰۲/۰۶/۳۱ (۸ ستونِ پُر در برابر ۰).
    ۳) درِ تساوی، newest `tracing_no` (اصلاحیه) — قراردادِ پیشین دست‌نخورده.
    """
    return (1 if other_entity else 0,
            1 if consolidated else 0, -completeness, -int(tracing_no or 0))


def quarter_reference_rows(rows, limit=16) -> list[dict]:
    """ساختِ نمای مرجعِ سری فصلی بدون حذفِ اطلاعیه‌های منبع.

    یک دوره ممکن است اطلاعیه‌های مستقل، تلفیقی یا اصلاحیه‌های مشروع داشته باشد.
    این تابع صرفاً برای نمودار یک مرجع در هر (period_end, period_months, report_kind)
    انتخاب می‌کند. تقدمِ مرجع: دامنۀ شرکت (`title_entity_suffix`، شرکتِ فرعیِ
    زیرِ نمادِ هلدینگ کنار می‌رود) و سپس همان `statement_rank` موجود
    (غیرتلفیقی ← کامل‌بودن ← tracing_no بالاتر). publish_date خام عمداً در
    رتبه‌بندی نیست؛ چون encoding فارسی/ASCII آن در داده یکسان نیست و مقایسهٔ
    لغوی قابل اعتماد نیست.

    limit پس از انتخابِ مرجع اعمال می‌شود تا چند نسخهٔ یک دوره پنجره را پر نکنند.
    """
    best = {}
    stable_fields = (
        "title", "report_kind", "revenue", "gross_profit",
        "operating_profit", "net_profit", "basic_eps",
    )
    for raw in rows or ():
        row = dict(raw)
        period_end = CP.canonicalize(row.get("period_end"))
        if not period_end:
            continue
        row["period_end"] = period_end
        # طولِ دوره از `effective_months` (بندِ ۲.۳): کلیدِ «یکِ دوره» نمی‌تواند
        # درِ سریِ فصلی ۶ باشد و درِ پنجرۀ سالانۀ همان ردیف ۱۲ — یکِ قاعده،
        # سه reader.
        months, months_src = CP.effective_months(period_end, row.get("period_months"),
                                                row.get("title"))
        row["period_months"] = months
        if months_src == "title" or months_src is None:
            row["months_source"] = months_src or "unknown"
        report_kind = str(row.get("report_kind") or "")
        key = (period_end, months, report_kind)
        title = str(row.get("title") or "")
        # لایۀ صفر «دامنۀ شرکت» است: کدال صورتِ مالیِ شرکتِ فرعی را زیرِ نمادِ
        # هلدینگ منتشر می‌کند و آن شرکت را در پرانتزِ عنوان می‌نویسد؛ چنین ردیفی
        # وضعیتِ مالیِ شرکتِ دیگری است و نمی‌تواند نمایندۀ این نماد باشد.
        # پس ازِ آن همان `statement_rank`ِ موتور (غیرتلفیقی ← کامل‌بودن ← newest
        # tracing_no). اگر همهٔ ردیف‌هایِ یکِ دوره فرعی باشند، همان قاعده بینِ
        # آن‌ها می‌گزیند — پاسخی حذف نمی‌شود.
        rank = statement_rank(
            FS_NUMBER_KEYS,
            _is_consolidated(title),
            row_completeness(FS_NUMBER_KEYS, row),
            row.get("tracing_no") or 0,
            bool(title_entity_suffix(title)),
        )
        # tracing_no در DB یکتا است؛ این signature فقط برای ورودی ناسازگارِ موقت
        # که دو ردیف با رتبه یکسان دارد، ترتیب را قطعی می‌کند.
        signature = tuple(
            "" if row.get(name) is None else str(row.get(name))
            for name in stable_fields
        )
        current = best.get(key)
        if current is None or rank < current[0] or (rank == current[0] and signature > current[1]):
            best[key] = (rank, signature, row)

    selected = [entry[2] for entry in best.values()]

    def order_key(row):
        try:
            months = int(row.get("period_months") or 0)
        except (TypeError, ValueError):
            months = 0
        try:
            tracing_no = int(row.get("tracing_no") or 0)
        except (TypeError, ValueError):
            tracing_no = 0
        return (
            str(row.get("period_end") or ""),
            months,
            str(row.get("report_kind") or ""),
            tracing_no,
        )

    selected.sort(key=order_key, reverse=True)
    try:
        bounded_limit = max(1, min(int(limit), 40))
    except (TypeError, ValueError):
        bounded_limit = 16
    return selected[:bounded_limit]


# `unit_norm` از همین دور درِ **هر دو** مسیرِ خواندن هست: مقیاسِ پولِ یک ردیف فقط
# از خودِ ردیف خوانده می‌شود (`codal_units`)، نه از ثابتِ ماژول. تا پیش از این
# ستون درِ بانک پر می‌شد ولی هیچ کوئری‌ای نمی‌خواندش، پس «بی‌واحد» با «میلیون
# ریال» یکی به‌نظر می‌رسید.
FS_COLS = ("period_end, period_months, title, revenue, gross_profit, "
           "operating_profit, net_profit, basic_eps, company_name, unit_norm")


def annual_statements(conn: sqlite3.Connection, symbol: str, require_audit: bool = True,
                      exclude_consolidated: bool = True, limit: int = 12) -> list[dict]:
    """صورت‌های مالی سالانه (۱۲ ماهه) — جدیدترین در ابتدا، یکی به ازای هر سال مالی.

    پیش‌فرض: فقط «حسابرسی‌شده» و فقط «شرکت اصلی» (غیرتلفیقی) — شرط شاخص ۲.
    """
    pred, params = sym_in(conn, "symbol", symbol)
    # پنجرهٔ خواند عمداً بزرگ است و غربال در Python انجام می‌شود:
    # `limit*4` (یعنی ۴ ردیف برای limit=1) باعث می‌شد صورت‌مالیِ ۱۲ماههٔ
    # حسابرسی‌شده‌ای که در ترتیب period_end عقب‌تر از ۴ ردیف اول می‌افتد هرگز
    # دیده نشود؛ آن‌وقت reference_annual به شاخهٔ تنزل (تلفیقی/حسابرسی‌نشده)
    # می‌غلتید و حاشیهٔ سود ناخالصِ همان نماد با bulk_scan فرق می‌کرد.
    # سقف تازه از ایندکس ix_fs_symbol خوانده می‌شود، پس هزینه تقریباً صفر است.
    window = max(int(limit), 1) * 12 + 48
    rows = conn.execute(
        f"SELECT {FS_COLS}, tracing_no FROM financial_statements "
        # پیش‌فیلترِ SQL فقط «حداکثرِ ممکن» را نگه می‌دارد؛ داوریِ «سالانہ بودن»
        # با `CP.effective_months` درِ Python است (ستونِ تهی از عنوان پر می‌شود و
        # دورۀ گذارِ شش‌ماهه با ستونِ ۱۲ رد می‌شود).
        f"WHERE {pred} AND {CP.DATED_SQL} AND (period_months>=12 OR period_months IS NULL) "
        "ORDER BY period_end DESC LIMIT ?",
        (*params, window)).fetchall()
    # یکِ سالِ مالی = یکِ صورتِ مالی. اگر برایِ یکِ دوره چند ردیف باشد (اصلی +
    # اصلاحیه / دو نوشتارِ همان نماد) برنده با `statement_rank` انتخاب می‌شود،
    # نه با ترتیبِ پیشآمدِ SQLite — وگرنه یکِ پوستۀ بی‌عددِ تازه‌تر، ردیفِ
    # عدددار را از دیدِ کلِ لایه‌ها پنهان می‌کرد.
    by_year: dict = {}
    for pe, pm, title, rev, gp, op, np_, eps, cn, un, tn in rows:
        t = title or ""
        # طولِ دوره از `CP.effective_months` خوانده می‌شود، نه از ستونِ خام:
        # یکِ ردیفِ بانک «دورۀ ۶ ماهه» است ولی `period_months=12` دارد، و ۲۴
        # ردیفِ بی‌ستون از عنوان قابل‌تعیین‌اند. بی‌این، دورۀ گذار به‌عنوان
        # «سالِ مالی» درِ پنجرۀ سه‌ساله می‌نشست (بندِ ۲.۳ سیاستِ بنیادی).
        months, months_src = CP.effective_months(pe, pm, t)
        if months is None or months < 12:
            continue
        if exclude_consolidated and _is_consolidated(t):
            continue
        if require_audit and not _is_audited(t):
            continue
        yr = CP.fiscal_year(pe)
        if not yr:
            continue
        cand = {"period_end": pe, "fiscal_year": yr, "period_months": months,
                "months_source": months_src, "title": t,
                "audited": _is_audited(t), "consolidated": _is_consolidated(t),
                "other_entity": bool(title_entity_suffix(t)),
                "conflicts": row_conflicts(pe, t, months),
                # مقیاسِ همین ردیف، از خودِ ردیف. `unit_valid` نقیضِ
                # `codal_units.PRESENT_SQL` است — یکِ تعریف، دوconsumer.
                "unit_norm": un, "unit_valid": CU.is_valid(un),
                "tracing_no": tn, "company_name": str(cn or ""),
                "amended": _is_amendment(t), "revenue": _fn(rev), "gross_profit": _fn(gp),
                "operating_profit": _fn(op), "net_profit": _fn(np_), "basic_eps": _fn(eps)}
        # لایۀ «شرکتِ دیگر» درِ هر دو مسیر فعال است: از دورِ Stage 1.2 کارت و قیف
        # نامزدها را از خودِ بانک می‌خوانند (`symbol_identity`)، پس این پرچم دیگر
        # دو جواب نمی‌سازد. بی‌این لایه، ردیفِ شرکتِ فرعی درِ سبدِ یکِ سالِ مالی
        # برنده می‌شد و صورتِ مالیِ **خودِ نماد** را از پنجره بیرون می‌انداخت —
        # آن‌وقت `pick_reference` که ردیفِ فرعی را رد می‌کند، آن سال را هرگز
        # نمی‌دید («شهر فرش» ۱۴۰۴: ردیفِ «شرکت داتیس نوین ایرانیان» جای
        # صورتِ مالیِ خودِ نماد را می‌گرفت).
        rank = statement_rank(FS_NUMBER_KEYS, _is_consolidated(t),
                              row_completeness(FS_NUMBER_KEYS, cand), tn,
                              cand["other_entity"])
        cur = by_year.get(yr)
        if cur is None or rank < cur[0]:
            by_year[yr] = (rank, cand)
    out = []
    for yr in sorted(by_year, reverse=True):
        out.append(by_year[yr][1])
        if len(out) >= limit:
            break
    return out


_CONFLICT_LABEL = {"title_period": "دورۀ داخلِ عنوان با دورۀ ستون یکی نیست",
                   "title_months": "شمارِ ماه‌هایِ دورۀ عنوان با ستون نمی‌خواند"}


def reference_identity(rows, reference):
    # آیا گزارشِ منتخب واقعاً به همین نماد تعلق دارد؟ بله/نه + دلیل، بی‌رأیِ مالی.

    # کدال شناسۀ مستقلِ شرکت ندارد (خودِ فیدِ زنده فقط Symbol/CompanyName/
    # TracingNo می‌دهد — سنجیده ۱۴۰۵-۰۷-۲)، پس تنها شاهدِ موجود درِ بانک
    # «نامِ شرکتِ غالبِ همین نماد» در برابرِ «نامِ شرکتِ ردیفِ منتخب» است.
    # این دو نخوانند، انتخاب **قطعی نیست** و باید دیده شود: نه رد، نه پاس،
    # نه صفر. سنجشِ بانکِ کاری (فقط‌خواندنی): از ۱۱۹۵ نمادِ دارای صورتِ مالی
    # ۴۴ تا بیش از یک نامِ شرکت دارند و ۱۸ تا ردیفِ منتخبشان با نامِ غالبِ
    # خودشان نمی‌خواند (اکثراً صندوق/سریِ صندوق زیرِ یکِ نماد مثلِ «گوهر» و
    # «ستاره»، و یکِ تغییرِ نامِ واقعی: «غگز»).

    # برگردان: {"checked", "match", "reason", "reference_company",
    #          "dominant_company", "names", "conflicts", "conflict_note"}
    # `checked`/`match` تنها از نامِ شرکت حرف می‌زنند (معنایشان درِ این دور عوض
    # نشد). `conflicts` چیزِ دیگری است: برچسب‌هایِ `row_conflicts` رویِ همان
    # ردیفِ منتخب — تناقضِ متن/ستون، که رأیِ هویت نیست ولی باید درِ ردپا باشد.
    ref = reference or {}
    conflicts = list(ref.get("conflicts") or [])
    note = "؛ ".join(_CONFLICT_LABEL.get(c, c) for c in conflicts)
    rc = norm_fa(str(ref.get("company_name") or ""))
    if not rc:
        return {"checked": False, "match": None, "reason": None,
                "reference_company": "", "dominant_company": "", "names": 0,
                "conflicts": conflicts, "conflict_note": note}
    counts = {}
    for r in rows or []:
        n = norm_fa(str(r.get("company_name") or ""))
        if n:
            counts[n] = counts.get(n, 0) + 1
    if not counts:
        return {"checked": False, "match": None, "reason": None,
                "reference_company": rc, "dominant_company": "", "names": 0,
                "conflicts": conflicts, "conflict_note": note}
    dominant = max(counts, key=lambda k: (counts[k], k))
    if rc == dominant:
        return {"checked": True, "match": True, "reason": None,
                "reference_company": rc, "dominant_company": dominant,
                "names": len(counts), "conflicts": conflicts,
                "conflict_note": note}
    return {"checked": True, "match": False,
            "reason": ("نامِ شرکتِ گزارشِ منتخب («" + rc + "») با نامِ غالبِ این نماد («"
                       + dominant + "») یکی نیست" + (("؛ " + note) if note else "")),
            "reference_company": rc, "dominant_company": dominant,
            "names": len(counts), "conflicts": conflicts, "conflict_note": note}


# آنچه شاخص ۳ برایِ ساختنِ یک عدد لازم دارد: صورتِ سود و زیانی که هم «سود
# ناخالص» در آن خوانده شده و هم درآمدِ عملیاتی. نبودِ هر دو ⇒ «قابل محاسبه
# نبود»، نه صفر.
MARGIN_NEED = ("gross_profit", "revenue")


def row_carries(row, need=MARGIN_NEED) -> bool:
    for k in need or ():
        v = (row or {}).get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if k == "revenue" and _f(v) <= 0:
            return False
    return True


def pick_reference(rows, need=None) -> Optional[dict]:
    """ردیفٔ مرجعٔ شاخص‌های ۳ و ۴ — خالص روی هر فهرست ردیف.

    سلسلۀ‌مراتب همانِ `reference_annual` است: سالانۀ حسابرسی‌شدۀ غیرتلفیقی →
    سالانۀ غیرتلفیقی → سالانۀ اخیر. انتخابِ داخلِ هر سالِ مالی با `statement_rank`
    (دامنۀ شرکت ← مبنا ← کامل‌بودن ← تازگی) است، پس مسیرِ تک‌نمادی (SQL) و مسیرِ
    کل‌بازار (`bulk_scan` که ردیف‌ها را از پیش خوانده) یکِ ردیف را مرجع می‌گیرند،
    نه دو تا.

    آرگومانِ `need` برایِ بندِ P-2 سیاست نوشته شده: جزوه «غیرتلفیقی بودن» را درِ
    بندِ **شاخص ۲** شرط کرده، نه درِ حاشیۀ سود. بی‌آن، نمادی که آخرین سالانۀ
    غیرتلفیقی‌اش عددِ سودِ ناخالص ندارد حاشیه‌اش `None` می‌شد، در حالی که
    سالانۀ تلفیقیِ همان شرکت با هر دو عدد درِ بانک بود (`وكادو` ۱۴۰۴ با
    ۲۹٫۶٪، `سيتا` ۱۴۰۴ با ۴۰٫۲٪). با `need`، اول ردیفی که آن ستون‌ها را دارد
    جست‌وجو می‌شود و اگر نبود، همان ردیفِ پیشین برمی‌گردد (یعنی عددِ شرکتِ
    دیگر هرگز نیاید، ولی نبودِ یک ستون هم باعث نشود سالِ دارایِ عدد دور ریخته
    شود).
    """
    by_year: dict = {}
    for r in rows or []:
        if int(_f(r.get("period_months"))) < 12:
            continue
        yr = str(r.get("fiscal_year") or "")
        if not yr:
            continue
        rank = statement_rank(FS_NUMBER_KEYS, bool(r.get("consolidated")),
                              row_completeness(FS_NUMBER_KEYS, r),
                              r.get("tracing_no") or 0,
                              bool(r.get("other_entity")))
        cur = by_year.get(yr)
        if cur is None or rank < cur[0]:
            by_year[yr] = (rank, r)
    cand = sorted(by_year.values(), key=lambda t: str(t[1].get("fiscal_year") or ""),
                  reverse=True)
    tiers = (lambda a, c, o: a and not c,      # حسابرسی‌شدۀ غیرتلفیقی
             lambda a, c, o: not c,            # غیرتلفیقی
             lambda a, c, o: True)             # هر سالانۀ اخیر
    # دو گذر، نه دو قاعده: اگر `need` داده شد، اول **هر سه پلّه** با شرطِ «این
    # عدد را دارد» جست‌وجو می‌شود و فقط اگر هیچ‌کدام نداشت، همان پلّه‌ها بی‌آن
    # شرط. بی‌این ترتیب، پلۀ اول با یکِ ردیفِ تهی برنده می‌شد و گذرِ دوم هرگز
    # دیده نمی‌شد (همان اشتباهی که `وكادو` را بی‌حاشیه می‌گذاشت).
    for require_numbers in ((True, False) if need else (False,)):
        for want in tiers:
            # قاعدۀ «هرگز» برایِ ردیفِ شرکتِ دیگر: پلِ سوم هم آن را بیرون
            # می‌گذارد، و اگر سالِ مالی تنها ردیفش آن بود، آن سال درِ این
            # پلکان حضور ندارد. دلیل: عددِ آن ردیف صورتِ مالیِ آن شرکت است،
            # نه این نماد — «شهر فرش» دقیقاً همین‌جا دو جواب می‌داد (۲۰٪ از
            # ردیفِ «شرکت داتیس نوین ایرانیان» در برابرِ ۳۷٫۹٪ از تلفیقیِ خودِ نماد).
            for _rank, r in cand:
                if bool(r.get("other_entity")):
                    continue
                if not want(bool(r.get("audited")), bool(r.get("consolidated")), False):
                    continue
                if require_numbers and not row_carries(r, need):
                    continue
                return r
    return None


def reference_annual(conn: sqlite3.Connection, symbol: str,
                     need=None) -> Optional[dict]:
    """آخرین صورت مالی سالانۀ «حسابرسی‌شدۀ غیرتلفیقی»؛ در نبودش سلسلۀ‌مراتب تنزل:
    سالانۀ غیرتلفیقی → سالانۀ اخیر. (منبع قطعی شاخص‌های ۳ و ۴)

    یک پنجرۀ ۱۲ماهه از DB خوانده می‌شود و انتخاب در `pick_reference` است — همان
    تابعی که `bulk_scan` روی ردیف‌های ازپیش‌خواندۀ خودش صدا می‌زند. `need` فقط
    جست‌وجو را برایِ همان شاخص دقیق‌تر می‌کند (بندِ P-2 سیاست) و منبعِ انتخابی را
    عوض نمی‌کند جز در موردِ «این عدد را نداشت».
    """
    return pick_reference(annual_statements(conn, symbol, require_audit=False,
                                           exclude_consolidated=False, limit=12),
                          need=need)




# ============================================================ تبدیل واحد
# مقیاس‌ها از `codal_units` می‌آیند (تنها تعریف). دو ثابتِ این فایل دیگر «عددِ
# ماژول» نیستند، فقط نامِ محلّیِ همان جدول‌اند: اگر روزی مقیاسِ تازه‌ای به
# `CU.SCALES` بیافزایید، اینجا خودبه‌خود درست می‌شود و هیچ consumer دومی برای
# اصلاح باقی نمی‌ماند (`api/fundamental` هم از همین‌جا واگرد می‌کند).
MRL_TO_BTM_FACTOR = CU.SCALES["mrl"] / CU.RIAL_PER_BTM     # = 1e-4 (قاعدۀ جزوه)


def normalize_mrl_to_btom(value_million_rials) -> float:
    """میلیون ریال → میلیارد تومان (حذف ۴ رقم سمت راست — قاعدهٔ جزوه).

    ورودی این تابع **باید** میلیون ریال باشد؛ تبدیلِ خودِ ردیف (که ممکن است
    میلیارد تومانِ خالصِ منبع باشد) از `fs_amount_mrl` می‌گذرد، نه اینجا.
    """
    return _f(value_million_rials) * MRL_TO_BTM_FACTOR


def fs_amount_mrl(row, key: str = "revenue"):
    """پولِ یک ردیفِ صورتِ مالی ← مبناىِ داخلیِ موتور (میلیون ریال).

    مقیاس از خودِ `unit_norm`ِ ردیف می‌آید (`codal_units.to_mrl`). ردیفِ
    بی‌واحد **None** می‌دهد: نه صفر، نه فرضِ «مثلِ بقیه میلیون ریال است». مصرف‌
    کننده باید آن را «قابل محاسبه نبود» اعلام کند، نه رأیِ منفی.
    """
    return CU.to_mrl((row or {}).get(key), (row or {}).get("unit_norm"))


def _f(v) -> float:
    """float امن (None/str/NaN → 0)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if x == x else 0.0          # NaN guard


def _fn(v):
    """float امنِ «قابل‌سکوت»: None واقعی را حفظ میکند.

    برای ستون‌هایی که «درج نشده» بودنشان معنا دارد (سود ناخالص بانک/صندوق) —
    چون _f آن را صفر می‌کرد و شاخص ۳ به‌جای «نامفهوم» مقدار ۰٪ می‌داد.
    """
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _dedupe_ym(rows, ytd_idx: int = 3):
    """یکی‌کردن ردیف‌های تکراریِ (سال, ماه) پس از ادغام نوشتارهای متفاوت.

    با symbol_aliases، گزارش‌های یک شرکت از دو نوشتار (داریک/داريك) با هم
    می‌آیند؛ ۲۷ گروهِ چنین تکراری در monthly_sales وجود دارد. بدون این،
    ردیفِ «همان ماه» دوبار شمرده می‌شد و مخرج رشد YoY می‌توانست صفرِ
    نوشتارِ بی‌داده باشد. قاعده: برای هر (سال,ماه) برداری که ytd_revenue
    بزرگ‌تر دارد نگه داشته می‌شود (رکوردهای کامل‌تر برنده است)؛ در تساوی
    اولین ردیفِ مرتب‌شده می‌ماند → خروجی قطعی است.
    """
    best, order = {}, []
    for r in rows:
        try:
            k = (int(r[0] or 0), int(r[1] or 0))
        except (TypeError, ValueError):
            k = (str(r[0]), str(r[1]))
        if k not in best:
            order.append(k)
            best[k] = r
            continue
        if _f(r[ytd_idx]) > _f(best[k][ytd_idx]):
            best[k] = r
    return [best[k] for k in order]



MRL_TO_RIAL = CU.SCALES["mrl"]        # مبناىِ داخلی = میلیون ریال؛ مقیاسِ هر
#                                       # ردیفِ صورتِ مالی جدا خوانده می‌شود
#                                       # (`fs_amount_mrl`) — این ثابت تنها برایِ
#                                       # مسیری است که خودش میلیون ریال ساخته.


# فالۀبکِ آستانه‌ها وقتی کلید در cfg نباشد، فقط همین‌جا
# نوشته می‌شود: پیش از این scan_symbol برای sales_to_mcap_min
# «۱ٮ۰» و bulk_scan «۰ٮ۳۳» در فالۀبک داشت؛ گاردِ پاریتی
# (confidence_engine_v973) همان واگرایی را می‌گرفت.
DEFAULT_TH = {
    "growth_min": 40.0,                # حکم ۳: کف قبولیِ رشد
    "v10_monetary_growth_min": 60.0,   # حکم ۳: هدفِ پوشش تورم
    "eps_years": 3,
    "margin_min": 20.0,                # حکم ۲: کف حاشیهٔ ناخالص
    "margin_optimal": 30.0,            # حکم ۲: استاندارد
    "sales_to_mcap_min": 0.33,         # حکم ۴: کف فروش سالانه ÷ ارزش بازار
    "profit_potential_min": 40.0,
    "pharma_margin_exempt_min": 0.0,   # **خاموش** (رأیِ مالک ۱۴۰۵-۰۷-۱۱): این عدد
                                       # در جزوه نیست؛ دارو را نه معاف می‌کند نه
                                       # رد — همان کلیدِ `FTS_DEFAULTS`، صفر = خاموش
}


def _th(cfg, key):
    """آستانه از cfg، وگرنه DEFAULT_TH. صفرِ عمدی («بدون گیت») را حفظ می‌کند —
    برخلافِ `or DEFAULT` که صفر را بی‌صدا به آستانهٔ پیش‌فرض برمی‌گرداند."""
    try:
        v = float((cfg or {}).get(key))
    except (TypeError, ValueError):
        return DEFAULT_TH[key]
    return v if v == v else DEFAULT_TH[key]


# =============================================== شاخص ۱: رشد فروش تجمیعی (YoY)
MS_SERIES_COLS = ("year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, "
                  "period_end, title")


def monthly_series(conn: sqlite3.Connection, symbol: str, limit: int = 60) -> list:
    """سریِ گزارش‌هایِ فعالیت ماهانه، تازۀترین اول.

    **تک‌منبعِ** لایۀ ۱ (رشد ریالی/تجمیعی)، لایۀ ۱ب (پهنا) و سالانه‌سازیِ لایۀ ۴
    درِ هر سه مسیر (کارت، `scan_symbol`، `bulk_scan`). پیش از این کارت این کوئری
    را با LIMIT ۶۰ و موتور با LIMIT ۳۰ داشت: برایِ نمادی که بیش از ۳۰ ماهِ
    گزارشِ تجمیعی دارد، ردیفِ «همان دورۀ سالِ قبل» بیرونِ پنجره می‌ماند و موتور
    data_gap می‌داد جایی که کارت عدد می‌داد. سقفِ تازه = همان ۶۰.
    """
    pred, params = sym_in(conn, "symbol", symbol)
    rows = conn.execute(
        "SELECT " + MS_SERIES_COLS + " FROM monthly_sales WHERE " + pred +
        " AND ytd_revenue IS NOT NULL AND ytd_revenue>0 "
        "ORDER BY year DESC, month DESC LIMIT ?",
        (*params, max(int(limit or 60), 1))).fetchall()
    # بندِ ۲.۱ سیاستِ بنیادی: گزارشِ شرکتِ دیگر برای **هیچ** شاخصی قابل‌قبول نیست.
    # همین قاعده درِ `financial_statements` نوشته شده بود و سریِ ماهانه از آن
    # مستثنا بود: سنجشِ بانک — ۱ ردیف از ۱۴٬۹۵۷ ردیفِ `monthly_sales` شرکتِ
    # دیگری را نام می‌برد (tn 1591838، «غنوش» ← «شرکت سرمایه گذاری نوش مازندران»
    # با `ytd_revenue = -62`)؛ امروز شرطِ `ytd_revenue>0` همان ردیف را بیرون
    # می‌انداخت، پس این بند امروز رفتار را عوض نمی‌کند و نگهبانِ فرداست.
    return _dedupe_ym([list(r[:-1]) for r in rows if not title_entity_suffix(r[-1] or "")])


def monthly_has_rows(conn: sqlite3.Connection, symbol: str) -> bool:
    """آیا برایِ این نماد اصلاً ردیفی در `monthly_sales` ثبت شده است؟

    `monthly_series` ردیف‌هایِ `ytd_revenue` نامعتبر/غیرمثبت را دور می‌ریزد،
    پس «سریِ تهی» دو معنی داشت: «هیچ گزارشِ ماهانه‌ای نیست» و «گزارش هست ولی
    تجمیعی‌اش صفر/نامعتبر است» (غنوش/ثنوسا). این helper فقط وجودِ ردیف را
    می‌سنجد (بی‌فیلترِ مقدار) تا سه مسیر — کارت، `scan_symbol`، `bulk_scan` —
    بتوانند BAD_YTD را از NO_SERIES جدا کنند (Task 10B2a1 C1).
    نمادِ نامعتبر همان «بدونِ ردیف» می‌ماند (`sym_in` شرطِ همیشه‌نادرست می‌دهد).
    """
    pred, params = sym_in(conn, "symbol", symbol)
    return conn.execute(
        "SELECT 1 FROM monthly_sales WHERE " + pred + " LIMIT 1",
        params).fetchone() is not None


def ytd_denominator(rows):
    """مخرجِ «همان دورۀ سالِ قبل» — تک‌قاعده، خالص رویِ سریِ ازپیش‌خوانده‌شده.

    (سال, ماه, فروشِ ماه, تجمیعی, تجمیعیِ سالِ قبل[, دورۀ پایان]) — ردیف‌هایِ
    تازه‌ترینِ سالِ مالی اول، یعنی خروجیِ `monthly_series` یا `ms[key]`ِ bulk.

    اولویت‌ها (قاعدهٔ جزوه؛ هرگز «ماه قبل» مخرج نمی‌شود):
      ۱) ستونِ رسمیِ «مقایسه با دورۀ مشابه سال قبل» (`ytd_revenue_prev`)
      ۲) ردیفِ (سال−۱، همان ماه) از خودِ گزارش‌هایِ ماهانه
    نبودِ هر دو ⇒ (`None`, «ناموجود») که فراخواننده data_gap می‌شمارد، نه صفر.
    """
    if not rows:
        return None
    cur = rows[0]
    year, month, ytd_now = int(cur[0] or 0), int(cur[1] or 0), _f(cur[3])
    if ytd_now <= 0 or month <= 0:
        return None
    prev_col = _f(cur[4]) if len(cur) > 4 else 0.0
    if prev_col > 0:
        return {"year": year, "month": month, "ytd_now": ytd_now, "ytd_prev": prev_col,
                "denominator_basis": "ستون «مقایسهٔ دورهٔ مشابه سال قبل» در همان گزارش"}
    prev = next((r for r in rows[1:] if int(r[0] or 0) == year - 1
                 and int(r[1] or 0) == month), None)
    if prev is None or _f(prev[3]) <= 0:
        return {"year": year, "month": month, "ytd_now": ytd_now, "ytd_prev": None,
                "denominator_basis": "ناموجود — ردیف تجمیعی همان دورهٔ سال قبل نیست"}
    return {"year": year, "month": month, "ytd_now": ytd_now, "ytd_prev": _f(prev[3]),
            "denominator_basis": "تجمیعی %02d/%d از گزارش فعالیت ماهانه (نه ماه قبل)"
                                 % (month, year - 1)}


# ═══════════════════════════════════════════════════════════════════════════
#  شاخص ۱ برای مالی/خدماتی/هلدینگ — رشد درآمد از صورتِ مالی غیرتلفیقی
# ═══════════════════════════════════════════════════════════════════════════
# این طبقه‌ها «فروش کالا» ندارند و گزارشِ ماهانه‌شان یا نیست یا مبنای درآمد
# را پوشش نمی‌دهد. پس رشد از خودِ صورتِ مالی سنجیده می‌شود: میاندوره ÷ همان
# دورهٔ سالِ قبل، و در نبودِ آن سالانه ÷ سالانه. مخرج هرگز «دورهٔ قبل» نیست.
FS_GROWTH_KINDS = ("service", "financial", "holding")
FS_GROWTH_NO_ROWS = "هیچ صورت مالی غیرتلفیقی با درآمد ثبت نشده است."
# «دورهٔ مشابه» فقط برایِ جدیدترین دوره معنا دارد: اگر جدیدترین صورتِ مالی
# جفتِ سالِ قبل ندارد، دورهٔ قدیمی‌ترِ دارای جفت جای آن نمی‌نشیند (Task 4) —
# عددِ دورهٔ قدیمی رشدِ «امسال» خوانده می‌شد و همین، N/A را به یک عددِ
# گمراه‌کننده تبدیل می‌کرد.
FS_GROWTH_NO_PRIOR = ("دورهٔ مشابهٔ سال قبل برای جدیدترین صورت مالی موجود نیست؛ "
                      "از دورهٔ قدیمی‌تر استفاده نمی‌شود.")


def _fs_growth_gap(reason: str, revenue_basis: str = "",
                   threshold: float = None) -> dict:
    """نتیجهٔ «قابل محاسبه نبود» — عدد ساخته نمی‌شود، دلیل می‌آید.

    `basis="fs_unavailable"` عمداً از `None` (مسیرِ ماهانهٔ YTD) جدا است تا
    مصرف‌کننده بفهمد شکاف از کدام مسیر آمده؛ پیش از این هر دو حالت `None`
    بودند و N/A ماهانه با N/A صورتِ مالی قابلِ تفکیک نبود (Task 4).
    """
    return {"monetary_pct": None, "basis": "fs_unavailable", "period": "",
            "months": 0, "year": None, "pass": False, "data_gap": True,
            "reason": reason, "revenue_basis": revenue_basis,
            "threshold": threshold}


def _fs_growth_floor(th) -> float:
    """کفِ قبولیِ شاخص ۱ — از dict کارت (`monetary_growth_min`) یا cfg موتور
    (`growth_min`). نبودِ هر دو = پیش‌فرضِ همان کف."""
    if isinstance(th, dict) and th.get("monetary_growth_min") is not None:
        try:
            return float(th["monetary_growth_min"])
        except (TypeError, ValueError):
            pass
    return _th(th, "growth_min")


def fs_growth_from_rows(rows, th=None, revenue_basis: str = "") -> dict:
    """رشد درآمد از ردیف‌هایِ ازپیش‌خوانده‌شدهٔ صورتِ مالی (بدونِ کوئری).

    rows: (period_end, period_months, revenue, title) — تازه‌ترین اول.
    برایِ هر (دورهٔ canonical, ماه) یک مقدار نگه داشته می‌شود (اولی = تازه‌ترین).
    تازه‌ترین میاندوره مقدم است؛ در نبودِ جفتِ میاندوره، تازه‌ترین سالانه.

    **قاعدهٔ صادقانه (Task 4):** فقط جدیدترین دورهٔ هر مبنا داوری می‌شود.
    اگر جدیدترین میاندوره جفتِ همان دورهٔ سالِ قبل را ندارد، میاندورهٔ
    قدیمی‌ترِ دارای جفت جای آن نمی‌نشیند؛ مسیر به سالانه می‌رود و اگر آن هم
    جفت ندارد، نتیجه `data_gap` با دلیل است — نه عددِ یک دورهٔ قدیمی که
    «رشدِ امسال» خوانده شود. شکاف با `basis="fs_unavailable"` از شکافِ
    مسیرِ ماهانه (`basis=None`) جدا می‌شود.

    میاندوره بر همان ماه و **همان روز** تطبیق می‌خورد؛ سالانه بر (سال−۱، همان
    ماه، همان تعدادِ ماه) و روز را نادیده می‌گیرد — پایانِ سالِ مالیِ ایرانی
    بین ۱۲/۲۹ و ۱۲/۳۰ جابه‌جا می‌شود و اختلافِ یک‌روزه نباید جفتِ معتبر را N/A کند.
    """
    floor = _fs_growth_floor(th)
    by_key = {}
    for pe, months, rev, title in rows:
        if _is_consolidated(title or ""):
            continue
        pe_c = CP.canonicalize(pe) or ""
        try:
            m = int(months or 0)
        except (TypeError, ValueError):
            m = 0
        if not pe_c or m <= 0 or _f(rev) <= 0:
            continue
        by_key.setdefault((pe_c, m), _f(rev))
    if not by_key:
        return _fs_growth_gap(FS_GROWTH_NO_ROWS, revenue_basis, floor)
    interims = sorted([(k, v) for k, v in by_key.items() if 0 < k[1] < 12],
                      key=lambda kv: kv[0][0], reverse=True)
    annuals = sorted([(k, v) for k, v in by_key.items() if k[1] >= 12],
                     key=lambda kv: kv[0][0], reverse=True)
    # سالانه روز را نادیده می‌گیرد: ۱۴۰۴/۱۲/۲۹ و ۱۴۰۳/۱۲/۳۰ یک دورهٔ مالی‌اند
    # (سالِ کبیسه پایانِ سال را یک روز جابه‌جا می‌کند). میاندوره دقیق می‌ماند.
    annual_prior = {}
    for (pe, months), val in annuals:
        y, mm, _dd = pe.split("/")[:3]
        annual_prior.setdefault((int(y), mm, months), val)

    # فقط جدیدترین دورهٔ هر مبنا — نه اولین دوره‌ای که اتفاقاً جفت دارد.
    if interims:
        (pe, months), now = interims[0]
        y, mm, dd = pe.split("/")[:3]
        prev_val = by_key.get(("%d/%s/%s" % (int(y) - 1, mm, dd), months))
        if prev_val:
            growth = (now / prev_val - 1.0) * 100.0
            return {"monetary_pct": growth, "basis": "fs_interim", "period": pe,
                    "months": months, "year": int(y),
                    "pass": growth >= floor, "data_gap": False, "reason": "",
                    "revenue_basis": revenue_basis, "threshold": floor}
    if annuals:
        (pe, months), now = annuals[0]
        y, mm, _dd = pe.split("/")[:3]
        prev_val = annual_prior.get((int(y) - 1, mm, months))
        if prev_val:
            growth = (now / prev_val - 1.0) * 100.0
            return {"monetary_pct": growth, "basis": "fs_annual", "period": pe,
                    "months": months, "year": int(y),
                    "pass": growth >= floor, "data_gap": False, "reason": "",
                    "revenue_basis": revenue_basis, "threshold": floor}
    return _fs_growth_gap(FS_GROWTH_NO_PRIOR, revenue_basis, floor)


def _fs_nonconsolidated_sql(conn: sqlite3.Connection) -> str:
    """فیلترِ SQLیِ «غیرتلفیقی» فقط وقتی ستون در DB هست.

    پایگاه‌هایِ قدیمی/نصب‌هایِ پیش از ستونِ is_consolidated این ستون را ندارند؛
    `fs_growth_from_rows` عنوانِ سطر را هم می‌سنجد، پس در آن‌ها فقط قیدِ SQL حذف
    می‌شود و حکم عوض نمی‌شود. (گیتِ `dev/fts_pipeline_v981.py` همین را می‌گیرد.)
    """
    return (" AND is_consolidated=0"
            if has_column(conn, "financial_statements", "is_consolidated") else "")


def fs_growth_map(conn: sqlite3.Connection, th=None) -> dict:
    """نقشهٔ تک‌گذرِ رشدِ صورتِ مالی برایِ کلِ بازار (کلید = norm_fa).

    `bulk_scan` این را یک بار می‌سازد و در حلقه فقط می‌خواند — نه N+1.
    """
    rows_by = {}
    for sym, pe, months, rev, title in conn.execute(
            "SELECT symbol, period_end, period_months, revenue, title "
            "FROM financial_statements "
            "WHERE revenue>0 AND period_months>0" + _fs_nonconsolidated_sql(conn) +
            " ORDER BY symbol, period_end DESC"):
        key = norm_fa(sym)
        if key:
            rows_by.setdefault(key, []).append((pe, months, rev, title))
    return {k: fs_growth_from_rows(v, th=th) for k, v in rows_by.items()}


def revenue_growth_yoy(conn: sqlite3.Connection, symbol: str, min_growth: float = 40.0,
                       growth_target: float = 60.0, sector: str = "",
                       series=None) -> Optional[dict]:
    """رشد فروش/درآمد تجمیعیِ «از ابتدای سال مالی تا ماه آخر» نسبت به همان دورهٔ سال قبل.

    قاعدهٔ جزوه (تأیید ممیزی): مخرج کسر **فروش تجمیعی دورهٔ متناظر سال قبل** است،
    نه فروش ماه قبل و نه فروش تک‌ماهه.

    منبع ستون‌ها (codal_fetcher):
      * تولیدی/خدماتی → ردیف «جمع» جدول فروش = فروش داخلی + صادراتی
      * بانک/مالی     → `_bank_fallback`: جمع ردیف‌های «درآمد محقق‌شده»
                        (تسهیلات اعطایی + سپرده‌گذاری + اوراق بدهی + سرمایه‌گذاری‌ها + کارمزد)
    هر دو در `ytd_revenue` (تجمیعی) و `monthly_revenue` (تک‌ماهه) ذخیره میشوند؛
    این تابع **صرفاً ytd_revenue** را میخواند → مخرج هرگز ماه قبل نمیشود.
    """
    series = series if series is not None else monthly_series(conn, symbol)
    d = ytd_denominator(series)
    if not d:
        return None
    year, month, ytd_now = d["year"], d["month"], d["ytd_now"]
    ytd_prev, basis = d["ytd_prev"], d["denominator_basis"]
    if ytd_prev is None:
        return {"growth_pct": None, "pass": False, "threshold": min_growth,
                "ytd_now_bt": round(normalize_mrl_to_btom(ytd_now), 1),
                "ytd_prev_bt": None, "period": f"{month:02d}/{year}",
                "year": year, "months": month,
                "denominator_basis": basis, "revenue_basis": _revenue_basis(sector),
                "data_gap": True}
    growth = (ytd_now / ytd_prev - 1.0) * 100.0
    return {
        "growth_pct": round(growth, 1),
        "ytd_now_bt": round(normalize_mrl_to_btom(ytd_now), 1),
        "ytd_prev_bt": round(normalize_mrl_to_btom(ytd_prev), 1),
        "period": f"{month:02d}/{year}",
        "year": year, "months": month,
        "denominator_basis": basis,
        "revenue_basis": _revenue_basis(sector),
        "pass": growth >= min_growth,
        "threshold": min_growth,
        # «بیش از تورم» دیگر عددِ ۵۸ دست‌چین نیست: همان هدفِ ۶۰٪ جزوه است
        # (کف ۴۰٪ برای قبولی، ۶۰٪ برای پوشش تورم — حکم ۳ مالک).
        "beats_inflation": growth >= growth_target,
        "growth_target": growth_target,
        "data_gap": False,
    }


def _revenue_basis(sector: str) -> str:
    """برچسبِ مبنایِ درآمد — واگرد به `company_profile` (تک‌منبعِ طبقه).

    توضیحی است، نه محاسباتی؛ ولی یکسان‌سازیِ آن لازم است چون کارت از
    `company_profile(...)^"revenue_basis"` می‌خواند و این نسخهٔ موتور توکن‌های
    خودش را داشت ⇒ یکِ نماد درِ دو مسیر دو برچسبِ مبنا می‌گرفت.
    """
    return company_profile(sector).get("revenue_basis", "")


def eps_trend_reason(series, years=None) -> str:
    """دلیلِ شکستِ روند EPS از خودِ سری ساخته میشود (نه متنِ عمومیِ «دیتا ناقص»).

    خروجی به نقطهٔ واقعیِ شکست اشاره میکند — مثلاً «سقوط سود به زیان در سال آخر» —
    تا کاربر علتِ رد را ببیند، نه یک پیامِ مبهمِ کمبودِ داده. یک منبعِ حقیقتِ
    مشترک برای مسیرِ سختِ v8 و مسیرِ ترکیبیِ v10.
    """
    vals = [_f(v) for v in (series or []) if v is not None]
    yrs = [str(y) for y in (years or [])]
    if not vals:
        return "سابقهٔ EPS محاسبه نشد"
    n = len(vals)

    def _ylab(i):
        return yrs[i] if 0 <= i < len(yrs) else "سال %d" % (i + 1)

    # ۱) زیاندهی — مهمترین دلیلِ رد
    if not all(v > 0 for v in vals):
        if all(v <= 0 for v in vals):
            return "سودسازی منفی در تمام دورهها"
        if vals[-1] <= 0 and (n < 2 or vals[-2] > 0):
            return "سقوط سود به زیان در سال آخر"
        if vals[-1] <= 0:
            return "زیاندهی در سال آخر (%s)" % _ylab(n - 1)
        for i, v in enumerate(vals):
            if v <= 0:
                return "زیاندهی در %s" % _ylab(i)
    # ۲) همه مثبت ولی اکیداً صعودی نیست → نقطهٔ افت/توقف
    for i in range(n - 1):
        if vals[i + 1] <= vals[i]:
            if vals[i + 1] == vals[i]:
                return "توقف رشد سود در %s" % _ylab(i + 1)
            pct = round((vals[i + 1] / vals[i] - 1.0) * 100.0, 1) if vals[i] else None
            tail = (" (افت %.1f٪)" % abs(pct)) if pct is not None else ""
            return "افت سود در %s%s" % (_ylab(i + 1), tail)
    return "روند سودسازی صعودی نیست"

# ============================================ شاخص ۲: روند ۳ سالهٔ EPS (اصلی)
# ==================================== شاخص ۲: نردبانِ شاهدِ EPS (تک‌منبع)
_EPS_QUALITY = {0: "audited_year_end", 1: "unaudited_year_end",
                2: "consolidated_audited", 3: "consolidated_unaudited"}

# برچسبِ شاهدِ EPS (Task 5) — همان پنج مقدارِ قرارداد، کلید = tier داوری.
# «تلفیقی — نمایشی» عمداً واژهٔ «نمایشی» دارد: آن سری دیده می‌شود ولی حکم
# نمی‌گیرد (N/A). کمبودِ کمتر از سه سال همیشه «دادهٔ ناکافی» است، حتی اگر
# بهترین شاهدِ موجود تلفیقی یا میاندوره باشد (قاعدهٔ مالک).
_EVIDENCE_LABEL = {
    "audited_year_end": "سالانهٔ حسابرسی‌شده",
    "year_end_unaudited": "سالانهٔ حسابرسی‌نشده",
    "year_end_plus_interim": "برآورد میان‌دوره",
    "consolidated_year_end": "تلفیقی — نمایشی",
    "insufficient": "دادهٔ ناکافی",
}


def eps_evidence_label(tier: str) -> str:
    """tier داوری → برچسبِ فارسیِ شاهد — تک‌مرجعِ کارت/اسکرینر/دریل‌دان."""
    return _EVIDENCE_LABEL.get(str(tier or ""), _EVIDENCE_LABEL["insufficient"])


def eps_ladder(conn: sqlite3.Connection, symbol: str, years: int = 3) -> dict:
    """سابقهٔ سودسازی با نردبانِ شفافِ شاهد — **تک‌پیاده‌سازیِ هر دو مسیر**.

    قاعدهٔ سختِ v8 (فقط ۱۲ماههٔ حسابرسی‌شدهٔ غیرتلفیقی) رویِ این بانک برایِ
    خیلی از نمادهای بزرگ صفرِ رکورد می‌داد — یا صورتِ سالانه «حسابرسی‌نشده»
    بارگذاری شده (فولاد ۱۴۰۳/۱۴۰۴) یا شرکت اصلاً صورتِ سالانهٔ غیرتلفیقی
    منتشر نمی‌کند. دستورِ کارِ v10 صریحاً «year-end **and** interim» را می‌خواهد،
    پس نبودنِ سالانۀ مستقیم هرگز به‌تنهایی `data_gap` نیست:

      ۱) سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی      (audited_year_end)
      ۲) سال‌پایانِ غیرتلفیقیِ حسابرسی‌نشده     (unaudited_year_end)
      ۳) سال‌پایانِ حسابرسی‌شدهٔ تلفیقی         (consolidated_audited)
      ۴) سال‌پایانِ تلفیقیِ حسابرسی‌نشده        (consolidated_unaudited)
      ۵) بلندترین دورۀ میاندورۀ همان سال ×۱۲÷م  (annualized_interim[_short])

    هر تنزل با `evidence` / `relaxed_evidence` / `low_quality_track` برچسب
    می‌خورد، نه این‌که پنهان شود. سالِ در‌جریان (فقط میاندوره) بیرونِ سابقه
    می‌ماند مگر این‌که سابقهٔ need‌ساله از آبِ تمام‌ها درنیاید و دقیقاً بعدِ
    آخرین سالِ کامل باشد. قاعدهٔ «سطر هرگز حذف نشود»: اگر کمتر از need دوره
    موجود است، `partial=True` با خانه‌هایِ None برمی‌گردد (نه نتیجهٔ تهی).
    """
    pred, params = sym_in(conn, "symbol", symbol)
    # `tracing_no` شاهدِ «کدام گزارش» است (مرتبهٔ `statement_rank`) — رویِ
    # اسکیمای کامل همیشه هست، ولی فیکسچرهایِ حداقلی (آزمون‌هایِ EPS با جدولِ
    # پنج‌ستونیِ مأموریت) آن را ندارند؛ نبودش دلیلِ شکستنِ نردبان نیست.
    _tn_col = (", tracing_no"
               if has_column(conn, "financial_statements", "tracing_no") else "")
    rows = conn.execute(
        "SELECT period_end, period_months, title, basic_eps, net_profit"
        + _tn_col +
        " FROM financial_statements "
        "WHERE %s AND basic_eps IS NOT NULL "
        "AND (period_months > 0 OR period_months IS NULL) "
        "AND %s ORDER BY period_end DESC LIMIT 120" % (pred, CP.DATED_SQL),
        params).fetchall()
    per_year: dict = {}
    for row in rows:
        pe, pm, title, eps, net = row[0], row[1], row[2], row[3], row[4]
        tn = row[5] if len(row) > 5 else None
        # همان قاعدۀ «شرکتِ دیگر» که درِ `statement_rank` و `quarter_reference_rows`
        # می‌نشیند: این نردبان یگانۀ readerِ شاخص ۲ است و بی‌این خط، EPS یکِ
        # شرکتِ فرعی واردِ سابقۀ سودسازی نماد می‌شد. سنجشِ فقط‌خواندنی رویِ
        # همین بانک: از ۷٬۳۰۹ ردیفِ EPS‌دار، ۱۷۹ ردیف عنوانشان شرکتِ دیگری را
        # نام می‌برد (زیرِ ۷۸ نوشتارِ نماد) — «شهر فرش» دقیقاً همین بود: سالِ
        # ۱۴۰۴ با EPS 109 از ردیفِ «شرکت داتیس نوین ایرانیان» خوانده می‌شد، در
        # حالی که خودِ نماد برایِ همان سال EPS 382 (تلفیقیِ حسابرسی‌شده) دارد.
        # قاعدۀ شاخص ۲ «سالانۀ حسابرسی‌شدۀ غیرتلفیقی» است؛ صورتِ مالیِ شرکتِ
        # دیگر هیچ‌کدام از این‌ها نیست — پیش ازِ این، نبودِ برچسبِ «تلفیقی» درِ
        # عنوان کافی بود تا آن ردیف از فیلترِ غیرتلفیقی رد شود.
        if title_entity_suffix(title or ""):
            continue
        # طولِ دوره از `effective_months` (بندِ ۲.۳ سیاست): «دورۀ ۶ ماهه» با
        # ستونِ ۱۲ ⇒ شش‌ماهه حساب می‌شود و از سبدِ «سالِ مالی» بیرون می‌ماند،
        # و ۲۴ ردیفِ بی‌ستون که عنوانشان دورۀ صریح دارد از گم‌شدن نجات
        # می‌یابند. ستونِ تهیِ بی‌عنوانِ دوره‌دار همان‌جا تهی می‌ماند — حدس نیست.
        months, _msrc = CP.effective_months(pe, pm, title)
        try:
            y, ev = int(CP.fiscal_year(pe)), float(eps)
        except (TypeError, ValueError):
            continue
        if y <= 0 or not months:
            continue
        cons = _is_consolidated(title or "")
        bucket = per_year.setdefault(y, {"annual": [], "interim": []})
        (bucket["annual"] if months >= 12 else bucket["interim"]).append(
            (months, _is_audited(title or ""), ev, _fn(net), CP.canonicalize(pe) or "",
             cons, tn))
    if not per_year:
        return {}

    def _rank(r):
        pm, aud, eps, net, pe, cons, _tn = r
        if pm >= 12:
            return ((2 if cons else 0) + (0 if aud else 1), -pm, pe)
        return (4, -pm, pe)

    def _pick(y):
        """بهترین رکوردِ یکِ سال مالی → (eps, period_end, quality, months, cons, net)."""
        b = per_year[y]
        best = sorted(list(b["annual"]) + list(b["interim"]), key=_rank)[0]
        pm, aud, eps, net, pe, cons, tn = best
        if pm >= 12:
            return eps, pe, _EPS_QUALITY[_rank(best)[0]], pm, cons, net, tn
        return (round(eps * 12.0 / pm, 2), pe,
                "annualized_interim_short" if pm < 6 else "annualized_interim",
                pm, cons, None, tn)

    def _has_annual(y):
        return bool(per_year[y]["annual"])

    years_sorted = sorted(per_year, reverse=True)
    complete = [y for y in years_sorted if _has_annual(y)]
    newest = years_sorted[0]
    in_progress = newest if not _has_annual(newest) else None
    need = max(int(years or 3), 2)
    window: list = []
    if complete:
        y = complete[0]
        while len(window) < need and y in per_year:
            window.append(y)
            y -= 1
        if (len(window) < need and in_progress and in_progress == window[0] + 1):
            window.insert(0, in_progress)
            in_progress = None
    out = {"years_required": need, "years_available": len(window),
           "in_progress_year": in_progress,
           "fiscal_years": [str(y) for y in reversed(window)]}
    if len(window) < need:
        if not window:
            out.update({"eps_series": None, "pass": False, "data_gap": True,
                        "available_periods": 0, "periods_missing": need,
                        "partial": False,
                        "reason": "کمتر از %d سال مالیِ متوالی با EPS ثبت‌شده (موجود: 0)" % need})
            return out
        picked_g = {yr: _pick(yr) for yr in window}
        top = max(picked_g)
        slots = list(range(top - need + 1, top + 1))          # قدیمی ← تازه
        have = [str(y) for y in slots if y in picked_g]
        out.update({
            "eps_series": [(round(_f(picked_g[y][0]), 2) if y in picked_g else None)
                           for y in slots],
            "period_slots": [str(y) for y in slots],
            "period_ends": [picked_g[y][1] if y in picked_g else None for y in slots],
            "evidence": [picked_g[y][2] if y in picked_g else "missing" for y in slots],
            "period_months": [picked_g[y][3] if y in picked_g else None for y in slots],
            "net_profit_series": [(picked_g[y][5] if y in picked_g else None) for y in slots],
            "ref_tracing_nos": [(picked_g[y][6] if y in picked_g else None) for y in slots],
            "available_periods": len(have),
            "periods_missing": need - len(have),
            "partial": True,
            "pass": False, "data_gap": True,
            "reason": ("فقط %d دوره از %d موجود است — %s"
                       % (len(have), need,
                          " و ".join("%s: %s" % (y, picked_g[int(y)][0]) for y in have)))
                      if len(have) < need else ""})
        return out
    picked = [_pick(yr) for yr in window]
    series = [p[0] for p in reversed(picked)]
    ev = [p[2] for p in reversed(picked)]
    out.update({
        "eps_series": [round(_f(s), 2) for s in series],
        "period_slots": [str(y) for y in reversed(window)],
        "partial": False, "available_periods": need, "periods_missing": 0,
        "period_ends": [p[1] for p in reversed(picked)],
        "evidence": ev,
        "period_months": [p[3] for p in reversed(picked)],
        "net_profit_series": [p[5] for p in reversed(picked)],
        # ردپایِ بندِ ۵: هر خانه از سری EPS به کدامِ گزارش برمی‌گردد.
        "ref_tracing_nos": [p[6] for p in reversed(picked)],
        "consecutive_years": True,
        "strictly_rising": all(series[i] < series[i + 1] for i in range(len(series) - 1)),
        "all_profitable": all(_f(s) > 0 for s in series),
        "consolidated_used": any(p[4] for p in picked),
        "audited_only": all(e == "audited_year_end" for e in ev),
        "relaxed_evidence": any(e != "audited_year_end" for e in ev),
        "low_quality_track": any(e.startswith("annualized_interim") for e in ev),
        "fiscal_years": [str(y) for y in reversed(window)],
        "data_gap": False,
        "source": "کدال — صورت‌های مالی سالانه + میاندوره"})
    out["pass"] = bool(out["strictly_rising"] and out["all_profitable"])
    out["soft_gap"] = bool(not out["pass"] and ev[-1] == "annualized_interim_short")
    if out["pass"]:
        out["reason"] = ""
    else:
        out["reason"] = eps_trend_reason(series, [str(y) for y in reversed(window)])
        if out["soft_gap"]:
            out["reason"] += " (برآورد میاندوره)"
    return out


def eps_assessment(conn: sqlite3.Connection, symbol: str, years: int = 3,
                   sector: str = "") -> dict:
    """داوریِ نهاییِ شاخص ۲ رویِ یکِ نردبان — کارت و اسکرینر همین را می‌خوانند.

    بیمه پیش‌گیت است (لایه اجرا نمی‌شود — رأیِ ۱). سابقه‌ای که **هر** اسلاتش از
    صورتهایِ تلفیقی باشد «رد» هم نیست و «سبز» هم: `na + data_gap` (حکمِ مالک
    ۱۴۰۵-۰۷؛ جزوه ص ۴: «صورتهای مالی تلفیقی مدنظر ما نیست» — پس یک سالِ
    تلفیقی یعنی آن سالِ غیرتلفیقی هرگز منتشر نشده و سابقهٔ سه‌ساله کامل نیست).
    """
    need = max(int(years or 3), 2)
    if is_insurance_sector(sector):
        return {"eps_series": None, "pass": False, "na": True, "data_gap": False,
                "years_required": need, "years_available": 0,
                "evidence_tier": "insurance", "strict_evidence": False,
                "relaxed_evidence": False, "consolidated_used": False,
                "low_quality_track": False, "soft_gap": False,
                "evidence_label": eps_evidence_label("insurance"),
                "reason": "صنعت بیمه — لایهٔ EPS اجرا نمیشود."}
    track = eps_ladder(conn, symbol, years=need)
    ev = [str(e or "") for e in (track.get("evidence") or [])]
    if not track or track.get("available_periods", 0) == 0:
        return {"eps_series": None, "pass": False, "data_gap": True,
                "years_required": need, "years_available": 0,
                "evidence_tier": "insufficient", "strict_evidence": False,
                "relaxed_evidence": False, "consolidated_used": False,
                "low_quality_track": False, "soft_gap": False,
                "evidence_label": eps_evidence_label("insufficient"),
                "reason": (track or {}).get("reason")
                or "هیچ صورت مالیِ معتبری با EPS ثبت نشده."}
    # سه پرچم از خودِ برچسبِ اسلات‌ها ساخته می‌شوند، نه از شاخۀ خاصِ نردبان:
    # شعبۀ `partial` هرگز `consolidated_used` را نمی‌گذاشت، پس سابقۀ ناقصِ
    # تلفیقی بی‌برچسب داوری می‌شد. ترتیبِ سنجش هم جزءِ قاعده است — «تلفیقی»
    # مبنایِ جزوه نیست (ص ۴) و باید زودتر از تنزلِ میاندوره بیفتد، وگرنه
    # شاخۀ `year_end_plus_interim` آن را می‌بلعد (سنجشِ ۱۴۰۵-۰۷-۱۲: ۲۶۱
    # سابقه بدین‌گونه بدونِ برچسبِ تلفیقی داوری می‌شدند).
    cons_years = [str(y) for y, e in zip(track.get("period_slots") or [], ev)
                  if e.startswith("consolidated_")]
    track["consolidated_used"] = bool(cons_years)
    track["low_quality_track"] = any(e.startswith("annualized_interim") for e in ev)
    track["relaxed_evidence"] = any(e not in ("audited_year_end", "missing")
                                    for e in ev)
    if ev and all(e == "audited_year_end" for e in ev):
        tier = "audited_year_end"
    elif cons_years:
        tier = "consolidated_year_end"
    elif track["low_quality_track"]:
        tier = "year_end_plus_interim"
    elif track["relaxed_evidence"]:
        tier = "year_end_unaudited"
    else:
        tier = "insufficient"
    track["evidence_tier"] = tier
    track["strict_evidence"] = (tier == "audited_year_end")
    # برچسبِ شاهد: کمبودِ کمتر از سه سال بر نوعِ شاهد مقدم است — سابقهٔ ناقص
    # (حتی اگر بهترین شاهدش تلفیقی یا میاندوره باشد) «دادهٔ ناکافی» است، نه
    # برچسبِ کامل. این فقط برچسب را عوض می‌کند؛ `evidence_tier`، حکم و قاعدهٔ
    # تلفیقی دست‌نخورده‌اند.
    _short = bool(track.get("partial")) or (
        int(track.get("available_periods") or 0) < need)
    track["evidence_label"] = eps_evidence_label("insufficient" if _short else tier)
    if tier == "consolidated_year_end":
        # حکمِ مالک ۱۴۰۵-۰۷ + جزوۀ ص ۴: «اطلاعات و صورت‌های مالی تلفیقی مدنظر
        # ما نیست». باقی‌ماندۀ مستقلِ سه‌ساله هرچه باشد (دو سال مستقل + یک سال
        # تلفیقی هم همین‌طور)، آن سابقه کامل نیست: نه «رد» است نه «سبز» ⇒
        # `na + data_gap` با ذکرِ سال‌هایِ تلفیقی.
        track["pass"] = False
        track["na"] = True
        track["data_gap"] = True
        track["consolidated_years"] = cons_years
        _note = ("صورتهای مالی تلفیقی مدنظر نیست — سال‌های %s فقط تلفیقی منتشر "
                 "شده‌اند و سابقۀ سه‌سالۀ غیرتلفیقی کامل نیست."
                 % "، ".join(cons_years))
        _prior = str(track.get("reason") or "")
        track["reason"] = (_prior + " " + _note) if _prior else _note
    return track


def eps_trend_3y(conn: sqlite3.Connection, symbol: str, years: int = 3,
                 sector: str = "") -> Optional[dict]:
    """شاخص ۲ — واگرد به `eps_assessment` (همان نردبانی که کارت می‌خواند).

    بیمه پیش‌گیت است و `None` برمی‌گرداند (قراردادِ فراخواننده‌هایِ مسیرِ اسکرینر؛
     کارت از `eps_assessment` همان حکم را با `na=True` می‌گیرد).
    تاریخچۀ v8 (فقط ۱۲ماههٔ حسابرسی‌شدهٔ غیرتلفیقی، حسابرسی با norm_fa، توالیِ
    سال‌ها) درونِ `eps_ladder` به‌عنوانِ سطوحِ ۱ و ۲ زنده مانده است — آن‌چه عوض
    شد این بود که نبودنِ سطحِ ۱ دیگر به‌تنهایی `data_gap` نیست.
    """
    if is_insurance_sector(sector):
        return None
    return eps_assessment(conn, symbol, years=years, sector=sector)


# ==================================== شاخص ۳: حاشیه سود ناخالص (Gross Margin)
def margin_reference(conn: sqlite3.Connection, symbol: str, ref=None,
                     rows=None) -> Optional[dict]:
    """ردیفی که شاخص ۳ از آن حاشیه می‌سازد — همان پلکان، با اولویتِ عددِ موجود.

    مسیرِ تک‌نمادی با یک کوئری اضافه کار می‌کند؛ `bulk_scan` ردیف‌هایِ ازپیش‌خوانده
    را می‌دهد (`rows=annual[key]`) تا به‌ازایِ هر نماد کوئریِ دوم زده نشود. بی‌این،
    دو نماد (`وكادو`، `سيتا`) حاشیه‌شان `None` می‌ماند در حالی که تلفیقیِ حسابرسی‌
    شدۀ *خودِ شرکت* با هر دو عدد درِ بانک بود — شرطِ «غیرتلفیقی» مالِ شاخص ۲ است،
    نه مالِ حاشیه (بندِ P-2 سیاست).
    """
    if row_carries(ref, MARGIN_NEED):
        return ref
    # بانکِ بی‌جدول (آزمونِ واحد با `sqlite3.connect(":memory:")`) نباید بشکند:
    # «سالِ دیگرِ دارایِ عدد» نداریم ⇒ همان ردیفِ داده‌شده برمی‌گردد.
    try:
        if rows is not None:
            return pick_reference(rows, need=MARGIN_NEED) or ref
        return reference_annual(conn, symbol, need=MARGIN_NEED) or ref
    except sqlite3.Error:
        return ref


def ind4_vote(annual, s2m_d, pot_d, exempt: bool, mcap=None):
    """سه‌حالۀ رأیِ شاخص ۴ — درِ **هر سه** مسیر (کارت، `scan_symbol`، `bulk_scan`).

    سه حالتِ «None» با هم یکی نیستند ولی هر سه نظر ندادن‌اند، و هیچ‌کدام «رد» نیست:
      * معافیتِ هلدینگ/صندوق (رأی ۱۶) — مدلِ کسب‌وکار فروشِ عملیاتیِ ماهانه ندارد؛
      * نبودِ فروشِ سالانۀ راستی‌آزمایی‌شده (نه گزارشِ ماهانه، نه صورتِ مالیِ
        واحددار) — چیزی که هرگز ساخته نشده مردود نیست؛
      * نبودِ ارزشِ بازار — مخرجِ کسر غایب است، نه بزرگ. (این حالت پس از
        ادغام با مأموریت `False` است، چون کارت/ردیفِ Task 7 همین را منتشر
        می‌کنند؛ دو حالتِ بالا همچنان `None` می‌مانند.)
    بی‌این سه‌حالگی، ۱۰۳ ردیفِ بی‌ارزش‌بازار و چند ردیفِ بی‌شاهدِ فروش درِ قیف
    «رد» می‌خوردند (بندِ ۵ مأموریت: فیلدِ گمشده با رأی جایگزین نشود). ردِ واقعی
    فقط وقتی است که عدد باشد و زیرِ آستانه بماند.
    """
    if exempt:
        return None
    # ترتیب مهم است (Task 7): بی‌شاهدِ فروشِ سالانه (نبودِ گزارشِ ماهانه **و**
    # صورتِ مالیِ واحددار / فروشِ صفر) «سنجیده نشد» است — نه «رد». این پیش از
    # بررسیِ ارزشِ بازار می‌آید تا نمادِ بی‌فروش حتی با ارزشِ بازارِ صفر هم None
    # بگیرد، نه Falseِ ساختگی (گاردِ C7b).
    if not annual or _f(annual.get("annual_sales_mrl")) <= 0:
        return None
    # ارزشِ بازارِ صفر: مخرج ساخته نمی‌شود ⇒ «سنجیده نشد» (None)، نه «رد».
    # کارت هم همین حالت را `available=False, pass=None, na=True` می‌خواند.
    if mcap is not None and _f(mcap) <= 0:
        return None
    return bool((s2m_d or {}).get("pass") or (pot_d or {}).get("pass"))


def margin_tier(pct) -> Optional[str]:
    """برچسبِ نمایشیِ طبقهٔ حاشیهٔ ناخالص (Task 6) — **نه** دروازهٔ تازه.

    حکم همچنان با کفِ ۲۰٪ (`margin_min`) و استانداردِ ۳۰٪ (`margin_ideal`)
    سنجیده می‌شود؛ ۵۰٪ فقط نامِ نمایشیِ «خوب» است و هیچ pass/optimalی نمی‌سازد.
    `None` یعنی حاشیه ساخته نشده (N/A مالی/هلدینگ/صندوق/بی‌سطر)، نه صفر.
    """
    x = _fn(pct)
    if x is None:
        return None
    if x < 20:
        return "below_floor"
    if x < 30:
        return "floor"
    if x < 50:
        return "standard"
    return "good"


# طبقه‌هایی که «سود ناخالص» برایشان تعریف نشده است (سند فاز ۱، بند ۴٫۴:
# «مالی/بانکی/هلدینگ/صندوق: N/A با دلیلِ سود ناخالص تعریف نشده؛ نه False»).
# این گیت «قابلِ‌اعمال بودن» شاخص ۳ است، نه دروازهٔ تازه: ۲۰/۳۰ برای
# تولیدی/خدماتی دست‌نخورده می‌ماند.
MARGIN_NA_KINDS = ("financial", "holding", "fund", "bank")

_MARGIN_NA_REASONS = {
    "bank": ("این نماد بانک/مؤسسهٔ اعتباری است؛ «سود ناخالص» برای این طبقه "
             "تعریف نشده است (درآمد از تسهیلات، سپرده و کارمزد است، نه فروش "
             "کالا). شاخص ۳ برای این طبقه سنجیده نمی‌شود."),
    "financial": ("این نماد در طبقهٔ مالی/اعتباری است؛ «سود ناخالص» برای این "
                  "طبقه تعریف نشده است (درآمد از خدمات مالی و کارمزد است، نه "
                  "فروش کالا). شاخص ۳ برای این طبقه سنجیده نمی‌شود."),
    "holding": ("این نماد هلدینگ/سرمایه‌گذاری است؛ «سود ناخالص» برای این طبقه "
                "تعریف نشده است (درآمد از پرتفوی است، نه فروش عملیاتی). "
                "شاخص ۳ برای این طبقه سنجیده نمی‌شود."),
    "fund": ("این نماد صندوق است؛ صندوق «فروش» و «بهای تمام‌شده» ندارد که "
             "حاشیهٔ ناخالص از آن‌ها ساخته شود. شاخص ۳ برای صندوق سنجیده "
             "نمی‌شود."),
}

_MARGIN_NA_REMEDIATION = {
    "bank": ("این N/A به ماهیتِ طبقه (بانک/اعتباری) برمی‌گردد، نه شکافِ داده؛ "
             "شاخص ۳ برای طبقه‌های بانکی سنجیده نمی‌شود."),
    "financial": ("این N/A به ماهیتِ طبقه (مالی/اعتباری) برمی‌گردد، نه شکافِ "
                  "داده؛ شاخص ۳ برای طبقه‌های مالی سنجیده نمی‌شود."),
    "holding": ("این N/A به ماهیتِ طبقه (هلدینگ/سرمایه‌گذاری) برمی‌گردد، نه "
                "شکافِ داده؛ شاخص ۳ برای هلدینگ سنجیده نمی‌شود."),
    "fund": ("این N/A به ماهیتِ طبقه (صندوق) برمی‌گردد، نه شکافِ داده؛ شاخص ۳ "
             "برای صندوق سنجیده نمی‌شود."),
}


def margin_class_na(profile, min_margin: float = 20.0,
                    optimal: float = 30.0) -> Optional[dict]:
    """N/Aِ طبقهٔ شاخص ۳ — مالی/بانکی/هلدینگ/صندوق، حتی با سود ناخالصِ ثبت‌شده.

    «سود ناخالص» برای این طبقه‌ها تعریف نشده است؛ عددِ قابلِ محاسبه هم نباید به
    حکم/برچسبِ حاشیه تبدیل شود. `data_gap=False` است (شکافِ داده نیست) و
    `margin_tier=None` (حاشیه ساخته نشد، نه `below_floor`). خروجی برایِ طبقهٔ
    دیگر `None` است تا گیت روی ۲۰/۳۰ِ تولیدی/خدماتی اثری نگذارد.

    دلیل از `margin_class`ِ همان پروفایل می‌آید تا بانک «بانک» خوانده شود،
    نه «هلدینگ/سرمایه‌گذاری»؛ حکم و امتیاز تغییری نمی‌کند (Task 10B2a1).
    """
    kind = str((profile or {}).get("kind") or "")
    if kind not in MARGIN_NA_KINDS:
        return None
    na_class = str((profile or {}).get("margin_class") or kind)
    if na_class not in _MARGIN_NA_REASONS:
        na_class = kind
    return {
        "margin_pct": None, "pass": False, "optimal": False, "ideal": False,
        "na": True, "band": "not_applicable",
        # تفکیکِ «N/Aِ طبقه» از «شکافِ داده» برایِ مصرف‌کننده‌ها (Task 10B2a1
        # fix round 1): `ind3_na` فقط `"class"` را N/Aِ ماهیت می‌شمارد.
        "na_kind": "class",
        "threshold": min_margin, "ideal_threshold": optimal,
        "margin_tier": None, "data_gap": False,
        "margin_class": na_class,
        "reason": _MARGIN_NA_REASONS[na_class],
        "remediation": _MARGIN_NA_REMEDIATION[na_class],
    }


def gross_margin(conn: sqlite3.Connection, symbol: str, min_margin: float = 20.0,
                 optimal: float = 30.0, ref: Optional[dict] = None,
                 rows=None) -> Optional[dict]:
    """حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰.

    ممیزی v8: فرمول v7.3 درست بود؛ **منبع** غلط بود — `ORDER BY period_end DESC
    LIMIT 1` آخرین گزارش را می‌داد که معمولاً ۳ماههٔ حسابرسی‌نشده است. اکنون
    آخرین صورت مالی **سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی** مبنا قرار میگیرد.
    تأیید: `net_profit` و `operating_profit` در این شاخص هیچ نقشی ندارند.
    """
    # مرجعِ این شاخص با «توانِ محاسبه» گزینش می‌شود، نه تنها با مبنایِ صورتِ مالی:
    # `margin_reference` همان پلکانِ مشترک است، فقط ردیفِ دارایِ عدد را ترجیح
    # می‌دهد (بندِ P-2 سیاست: شرطِ غیرتلفیقی مالِ شاخص ۲ است، نه حاشیه).
    row = margin_reference(conn, symbol, ref=ref, rows=rows)
    if not row:
        return None
    rev, gp = _f(row.get("revenue")), row.get("gross_profit")
    if rev <= 0 or gp is None:
        return None                      # بانکی/مالی/صندوق — بهای تمام‌شده ندارد
    gp = _f(gp)
    margin = (gp / rev) * 100.0
    parent_only = bool(row.get("audited")) and not row.get("consolidated")
    # برچسبِ منبع از خودِ پرچم‌ها ساخته میشود، نه از بریدنِ عنوانِ کدال:
    # `title[:60]` جمله را وسطِ کلمه می‌برید («… (حسابرسی ش») و کاربر متنِ
    # ناقص را دلیلِ داوری می‌دید.
    src = ("سالانهٔ حسابرسی‌شدهٔ شرکت اصلی" if parent_only else
           "تنزل منبع: " + ("تلفیقی" if row.get("consolidated") else "شرکت اصلی") +
           ("ِ حسابرسی‌شده" if row.get("audited") else "ِ حسابرسی‌نشده"))
    fy = str(row.get("fiscal_year") or "").strip()
    if fy:
        src += " — سال مالی " + fy
    margin_pct = round(margin, 1)
    return {
        "margin_pct": margin_pct,
        "gross_profit_bt": round(normalize_mrl_to_btom(gp), 1),
        "revenue_bt": round(normalize_mrl_to_btom(rev), 1),
        "period_end": str(row.get("period_end"))[:10],
        "basis": src,
        # ردپایِ بندِ ۵ مأموریت: «کدامِ گزارش» نه فقط «چه دوره‌ای». بی‌`tracing_no`
        # خواننده نمی‌تواند ردیفِ منبع را درِ کدال بازبینی کند، و بی‌`unit` معلوم
        # نیست عدد مقیاسش را از کجا آورده (بندِ P-4 سیاست).
        "ref_tracing_no": row.get("tracing_no"),
        "ref_company": str(row.get("company_name") or ""),
        "fiscal_year": fy or None,
        "unit": row.get("unit_norm"),
        "unit_label": CU.label(row.get("unit_norm")),
        "unit_valid": CU.is_valid(row.get("unit_norm")),
        "source": "کدال — صورت سود و زیان سالانه",
        "pass": margin >= min_margin,
        "optimal": margin >= optimal,
        "threshold": min_margin,
        "optimal_threshold": optimal,
        # برچسبِ نمایشی از همان عددِ خامِ حکم ساخته می‌شود (نه گردشدۀ نمایش):
        # ۱۹٫۹۶٪ که «۲۰٫۰» دیده می‌شود هنوز زیرِ کف است و برچسبش نباید
        # «کف» بشود؛ ۵۰٪ هم دروازه نیست (Task 6).
        "margin_tier": margin_tier(margin),
        "formula": "(سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰",
    }


# ── بلوکِ جدیدِ fts_engine.py (تک‌منبعِ طبقه + سالانه‌سازی) ──────────────────
# این فایل منبعِ جای‌گزینی است؛ خودِ `_audit/splice_fund.py` آن را درِ
# fts_engine.py می‌گذارد (جای `annualized_sales` و کامنتِ بالایِ آن).
# ==================== شاخص ۴: فروش سالانهٔ Annualized به ارزش بازار + پتانسیل سود
# ═══════════════════════════════════════════════════════════════════════════
#  طبقۀ شرکت — تک‌مرجعِ «مبنای درآمد» (کارت، موتور و bulk یک چیز می‌خوانند)
# ═══════════════════════════════════════════════════════════════════════════
# «فروش» برای بانک معنا ندارد؛ جزوه برای شرکت‌های مالی «درآمد تسهیلات اعطایی +
# سپرده‌گذاری + سرمایه‌گذاری + اوراق + کارمزد» را می‌نویسد و برای تولیدی
# «فروش داخلی + صادراتی». پیش از این این جدول در `api/fundamental.py` بود و
# `bulk_scan` به آن دسترسی نداشت ⇒ موتور برای طبقۀ مالی همان مسیرِ تولیدی را
# می‌رفت و فروش سالانۀ شاخص ۴ بین کارت و اسکرینر واگرا می‌شد (۵۰ نماد).
_FIN_TOKENS = tuple(norm_fa(x) for x in
                    ("اعتباري", "اعتباری", "بيمه", "بیمه",
                     "ليزينگ", "لیزینگ", "کارگزاري", "کارگزاری", "اوراق"))
# بانک‌ها در `_HOLD_TOKENS` هم می‌آیند (چون «بانک» آن‌جاست)، پس `kind`شان
# «holding» است. برایِ دلیلِ N/Aِ شاخص ۳ باید بانک را از هلدینگ جدا کنیم —
# وگرنه ۱۶ ردیفِ بانکی «سرمایه‌گذاری/هلدینگ» خوانده می‌شدند (Task 10B2a1).
_BANK_TOKENS = tuple(norm_fa(x) for x in ("بانک", "بانك"))
_HOLD_TOKENS = tuple(norm_fa(x) for x in
                     ("بانک", "سرمایه گذاری", "سرمایه‌گذاری", "هلدینگ",
                      "واسطه گری", "واسطه‌گری", "نهادهای مالی واسط"))
_SVC_TOKENS = tuple(norm_fa(x) for x in
                    ("خدمات", "حمل", "ترابری", "فناوري", "فناوری", "مخابرات",
                     "بازرگاني", "بازرگانی", "پخش", "رستوران", "گردش"))
_PROFILE_LABEL = {"production": "تولیدی / صادراتی", "financial": "مالی و بانکی",
                  "service": "خدماتی", "fund": "صندوق",
                  "holding": "هلدینگ / سرمایه‌گذاری"}


NON_COMPANY_TOKENS = tuple(norm_fa(t) for t in (
    "صندوق", "اوراق", "اختيار", "اختیار", "حق تقدم", "حق‌تقدم",
    "خیریه", "شهرداری", "فدراسیون", "موسسه", "پرورشگاه", "وقف", "بنیاد",
))


def classify_identity(symbol, sector, company_name, has_instrument):
    """Universe gate: only real operating companies enter the FTS table."""
    sec = str(sector or "").strip()
    name = str(company_name or "").strip()
    if not has_instrument:
        return {"kind": "non_company", "applicable": False,
                "reason": "no_instrument"}
    # بیمه پیش از هر دروازهٔ توکنی: صنعتِ «بيمه وصندوق بازنشستگي به جزتامين
    # اجتماعي» کلمهٔ «صندوق» را در نامش دارد ولی شرکتِ عملیاتی است. وتویِ بیمه
    # جای دیگری است (risk_gates، Task 8)، نه در جهانِ نمادها.
    if is_insurance_sector(sec):
        return {"kind": "company", "applicable": True, "reason": ""}
    if fund_class_match(sec, name):
        return {"kind": "fund", "applicable": False, "reason": "fund"}
    text = norm_fa(sec) + " " + norm_fa(name)
    if any(t in text for t in NON_COMPANY_TOKENS):
        return {"kind": "non_company", "applicable": False,
                "reason": "fund_or_non_operating"}
    if not sec and not name:
        return {"kind": "non_company", "applicable": False,
                "reason": "no_identity"}
    return {"kind": "company", "applicable": True, "reason": ""}


def company_profile(sector: str = "", company_name: str = "") -> dict:
    """طبقۀ شرکت + مبنای درآمد + اینکه چکِ فیزیکی (تناژ) برایش معنا دارد یا نه."""
    both = norm_fa(sector) + " " + norm_fa(company_name)
    if fund_class_match(sector, company_name):
        kind, applicable = "fund", False
        basis = "صندوق — درآمد پرتفوی و تغییرات خالص دارایی‌ها"
    elif any(t in both for t in _HOLD_TOKENS):
        kind, applicable = "holding", False
        basis = ("هلدینگ/سرمایه‌گذاری/بانکی — درآمد عملیاتی از پرتفوی، سود "
                 "تسهیلات/سپرده و سرمایه‌گذاری‌ها (بدون «فروش کالا» و تناژ فیزیکی)")
    elif any(t in both for t in _FIN_TOKENS):
        kind, applicable = "financial", False
        basis = ("مالی/بانکی — جمع درآمد تسهیلات اعطایی + سپرده‌گذاری + "
                 "سرمایه‌گذاری‌ها + اوراق بدهی + کارمزد (نه «فروش کالا»)")
    elif any(t in both for t in _SVC_TOKENS):
        kind, applicable = "service", False
        basis = "خدماتی — کارمزد و درآمد عملیاتی (بدون تناژ فیزیکی)"
    else:
        kind, applicable = "production", True
        basis = "تولیدی/عمرانی — جمع فروش داخلی + صادراتی (ردیف «جمع» جدول فروش)"
    # دلیلِ N/Aِ شاخص ۳ باید کلاس را دقیق بگوید: بانک در `kind` زیرِ «holding»
    # می‌افتد ولی «سرمایه‌گذاری/هلدینگ» خواندنش غلط است. این کلید فقط برایِ
    # متنِ دلیل است؛ حکم/امتیاز/N/Aِ شاخص ۳ دست‌نخورده می‌ماند.
    margin_class = kind
    if kind == "holding" and any(t in both for t in _BANK_TOKENS):
        margin_class = "bank"
    label = ("بانک / مؤسسهٔ اعتباری" if margin_class == "bank"
             else _PROFILE_LABEL[kind])
    return {"kind": kind, "margin_class": margin_class,
            "label": label, "revenue_basis": basis,
            "volume_applicable": applicable,
            "volume_note": ("تناژ/تعداد محصول در گزارش فعالیت ماهانه معنادار است؛ "
                            "رشد ریالی بدون رشد تناژ = افزایش قیمت."
                            if applicable else
                            "این شرکت کالای وزن‌شدنی تولید نمی‌کند؛ چک فیزیکی روی "
                            "مبنای متناسبِ همان طبقه (درآمد واقعی پس از تورم) سنجیده "
                            "میشود نه تن محصول."),
            "pricing_note": ("درآمد به دلار/بورس کالا گره خورده (صادراتی)."
                             if applicable else
                             "درآمد ریالیِ نرخ‌گذاری‌شده — ریسک سرکوب نرخ وجود دارد.")}


# طبقه‌هایی که «فروش کالا» ندارند و مبنایشان درآمدِ صورتِ مالیِ سالانه است
_OP_BASIS_KINDS = ("financial", "service", "fund", "holding")
ANNUALIZATION_SCALE = (3, 4, 5, 6, 9, 12)


def annualize_rows(rows, fs_rev, op_basis: bool = False, fs_unit_known: bool = True) -> dict:
    """خالصِ سالانه‌سازی — **یک** قاعده برای مسیرِ SQL و مسیرِ کل‌بازار.

    قاعده (رأیِ مالک، OWNER_RULINGS ردیف ۴ + سند v2.1):
      ۰) `op_basis` (طبقۀ مالی/خدماتی/صندوق/هلدینگ) → درآمدِ صورتِ مالیِ سالانه
         با ضریب ۱٫۰؛ گزارشِ ماهانه جای آن را نمی‌گیرد.
      ۱) تجمیعیِ YTDِ بلندترینِ ماهِ دارایِ گزارش × ۱۲÷م  (م = همان ماه)
      ۲) دوازده‌ماهۀ کامل ⇒ خودِ YTD (×۱٫۰)
      ۳) بی‌گزارشِ ماهانه → فروشِ صورتِ مالیِ سالانۀ کدال
      ۴) گیتِ واحدِ مشکوک: >۴× یا <۰٫۲۵× فروشِ سالانه ⇒ مبنای کدال +
         `reconciled=False`
    م از «بلندترینِ ماهِ دارایِ گزارشِ تجمیعی در آخرین سالِ مالی» خوانده می‌شود،
    نه از تقویم — تا نمادی که ماهِ جاافتاده دارد درست annualize شود.
    `rows`: [(سال, ماه، فروشِ ماه، تجمیعی), …] — ردیف‌هایِ تازه‌ترینِ سالِ مالی اول.
    برگردان: {} یعنی «قابل محاسبه نبود» (هیچ‌وقت صفرِ ساختگی نه).

    `fs_rev` **باید** با مقیاسِ خودِ ردیف به میلیون‌ریال تبدیل شده باشد
    (`fs_amount_mrl`)، و `fs_unit_known` بگوید آن تبدیل شاهدِ واحد داشته یا نه.
    بی‌شاهدِ واحد، هیچ یک از سه قاعدۀ وابسته به مقیاس (۰، ۳، ۴) اجرا نمی‌شود:
    ضریبِ حدسیِ ۱e۶ رویِ عددی که منبعش مقیاسش را نگفته گذاشته نمی‌شود. این
    «بی‌رأی» است، نه رأیِ منفی.
    """
    if op_basis:
        if fs_rev is None or not fs_unit_known or _f(fs_rev) <= 0:
            return {}
        return {"annual_sales_mrl": fs_rev, "months_used": 12, "reconciled": True,
                "operational_revenue_basis": True,
                "basis": "درآمد عملیاتیِ صورت مالی سالانه — جایگزینِ «فروش» برایِ طبقه"}
    annual, months, basis, reconciled = 0.0, 0, "", True
    if rows:
        year = int(rows[0][0] or 0)
        cur = sorted((r for r in rows if int(r[0] or 0) == year),
                     key=lambda r: -int(r[1] or 0))
        if cur:
            months = int(cur[0][1] or 0)
            ytd = _f(cur[0][3])
            if months >= 1 and ytd > 0:
                annual = ytd if months >= 12 else ytd * 12.0 / months
                basis = (("تجمیعی %02d/%d × ۱۲÷%d (=×%.2f)"
                          % (months, year, months, 12.0 / months))
                         if months < 12 else
                         "تجمیعی ۱۲ ماهِ کاملِ سال مالی %d (×۱٫۰)" % year)
    # هر دو شاخۀ وابسته به مقیاسِ صورتِ مالی از `fsr` می‌گذرند: ردیفی که واحدش
    # اعلام نشده نه صفرِ واقعی است و نه مبنایِ محاسبه.
    fsr = _f(fs_rev) if fs_unit_known else 0.0
    if annual <= 0 and fsr > 0:
        annual, months = fsr, 12
        basis = "مراجعه به فروش صورت مالی سالانه (بی‌گزارش ماهانه)"
    if annual <= 0:
        return {}
    # گیتِ «واحد مشکوک» فقط برای سالانه‌سازیِ واقعی (۰ < م < ۱۲) معنا دارد؛
    # گزارشی که خودش ۱۲ ماهِ کامل را پوشش می‌دهد مستقیم پذیرفته می‌شود.
    if (fsr > 0 and 0 < months < 12
            and (annual > fsr * 4.0 or annual < fsr * 0.25)):
        reconciled = False
        annual, months = fsr, 12
        basis = "ضریب پویا مردود شد (واحد مشکوک) → فروش سالانهٔ کدال"
        witness = True
    else:
        # ردیفِ مرجعِ بی‌واحد تنها شاهدِ مقیاسِ `monthly_sales` را از کار می‌اندازد
        # (آن جدول ستونِ واحدِ پول ندارد). بی‌شاهد، عددِ ماهانه **راستی‌آزمایی‌نشده**
        # می‌ماند و رأیِ وابسته به مقیاس داده نمی‌شود — «قابل محاسبه نبود»، نه صفر
        # و نه PASSِ ساختگی (بندِ ۵ مأموریت).
        witness = fs_unit_known
    return {"annual_sales_mrl": annual, "months_used": months, "basis": basis,
            "reconciled": reconciled and witness, "unit_unverified": not witness,
            "operational_revenue_basis": False}


def annualize_label(months) -> str:
    """برچسبِ سالانه‌سازیِ شاخص ۴ (Task 7) — «سالانه‌شده از دورهٔ N ماهه».

    همان متنی که پنلِ جزئیات از قبل می‌ساخت، حالا تک‌مرجع است: کارت و ردیفِ
    `bulk_scan` هم همین را می‌دهند تا UI برچسب را از عدد بازنسازد. `0`/None
    یعنی دوره‌ای برایِ سالانه‌سازی نیست ⇒ رشتهٔ خالی (نه «دورهٔ ۰ ماهه»).
    """
    m = int(_f(months))
    return ("سالانه‌شده از دورهٔ %d ماهه" % m) if m else ""


def i4_acceptance_path(sales_pass, potential_pass) -> Optional[str]:
    """مسیرِ پذیرشِ شاخص ۴ (Task 7) — **فقط نامِ مسیر، نه دروازهٔ تازه**.

    دروازه همان ORِ سند v2.1 است: اول «فروش سالانه ÷ ارزش بازار ≥ ۰٫۳۳×»
    (`sales_to_mcap`) و بعد «پتانسیل سود ناخالص ÷ ارزش بازار ≥ ۴۰٪»
    (`profit_potential` — مسیر دوم). وقتی هر دو پاس‌اند مسیرِ اول نام می‌گیرد،
    و وقتی هیچ‌کدام نیست (یا شاخص معاف/بی‌داده است) `None`.
    """
    if sales_pass:
        return "sales_to_mcap"
    if potential_pass:
        return "profit_potential"
    return None


def ind4_reason_text(exempt=False, available=True, margin_present=True,
                     sales_pass=False, potential_pass=False) -> str:
    """متنِ دلیلِ شاخص ۴ — تک‌مرجعِ `ind4_valuation` (کارت) و ردیفِ bulk.

    چهار حالتِ همان تابعِ کارت: معاف (N/A)، دادهٔ ناکافی، نبودِ حاشیه، و مسیرِ
    پذیرش/بی‌مسیر. هیچ آستانه‌ای این‌جا ساخته نمی‌شود؛ فقط متنِ حکمِ موجود.
    """
    if exempt:
        return ("این نماد از شرط «نسبت فروش به ارزش بازار» معاف است "
                "(طبقهٔ مالی/بانکی/هلدینگ/صندوق)؛ شاخص ۴ داوری نمی‌شود (N/A).")
    if not available:
        return ("دادهٔ ارزش بازار یا فروش سالانه برای محاسبه نسبت در دسترس "
                "نیست.")
    if not margin_present:
        return "هیچ حاشیه‌ای (ناخالص یا جایگزین) برای این طبقه محاسبه نشد."
    if sales_pass:
        return "قبولی با نسبت فروش/ارزش‌بازار"
    if potential_pass:
        return "قبولی با پوشش پتانسیل سود"
    return "نه نسبت فروش و نه پوشش پتانسیل به حد نصاب نرسید."


def annualized_sales(conn: sqlite3.Connection, symbol: str,
                     ref: Optional[dict] = None, series=None, profile=None,
                     exempt=None) -> Optional[dict]:
    """فروش سالانۀ شاخص ۴ — **تک‌پیاده‌سازیِ کارت، اسکرینر و bulk**.

    `api/fundamental.dynamic_annualized_sales` به همین تابع واگرد می‌کند؛ طبقه
    از `company_profile` (همین فایل) و حکمِ معافیت از `ind4_exempt` (تک‌مرجع)
    می‌آید، پس «مبنای درآمد» و «N/A» برای هر سه مسیر یک تصمیم است.

    خروجی ابرمجموعهِ کلیدهایِ هر دو مسیرِ پیشین است: annual_sales_mrl/bt،
    months_used، scale_factor، basis، reconciled، revenue_basis،
    operational_revenue_basis، na، ytd_sales_bt، scale_table.
    """
    pred, params = sym_in(conn, "symbol", symbol)
    if series is None:
        series = conn.execute(
            "SELECT year, month, monthly_revenue, ytd_revenue, title FROM monthly_sales "
            "WHERE " + pred + " AND ytd_revenue IS NOT NULL AND ytd_revenue>0 "
            "ORDER BY year DESC, month DESC", params).fetchall()
        series = [list(r[:-1]) for r in series if not title_entity_suffix(r[-1] or "")]
    series = _dedupe_ym([list(r) for r in series])
    ref_row = ref if ref is not None else reference_annual(conn, symbol)
    # مقیاس از خودِ ردیفِ مرجع، نه از ثابتِ ماژول (`fs_amount_mrl` بی‌واحد → None).
    fs_rev = fs_amount_mrl(ref_row, "revenue")
    fs_unit_known = CU.is_valid((ref_row or {}).get("unit_norm"))
    prof = profile or company_profile()
    _na = (prof.get("kind") == "holding") if exempt is None else bool(exempt)
    if _na:
        return {"annual_sales_mrl": 0.0, "annual_sales_bt": None, "months_used": 0,
                "scale_factor": 0.0,
                "basis": "N/A — هلدینگ/سرمایه‌گذاری/واسطۀ مالی (سند v2.1 F-04)",
                "reconciled": True, "revenue_basis": prof.get("revenue_basis", ""),
                "operational_revenue_basis": False, "na": True}
    core = annualize_rows(series, fs_rev,
                          op_basis=(prof.get("kind") in _OP_BASIS_KINDS)
                          and _f(fs_rev) > 0 and fs_unit_known,
                          fs_unit_known=fs_unit_known)
    if not core:
        return None
    core["fs_unit"] = (ref_row or {}).get("unit_norm")
    core["fs_unit_label"] = CU.label((ref_row or {}).get("unit_norm"))
    months = core["months_used"]
    annual = core["annual_sales_mrl"]
    out = dict(core)
    out.update({"annual_sales_bt": round(normalize_mrl_to_btom(annual), 1),
                "scale_factor": round(12.0 / max(months, 1), 4),
                "revenue_basis": prof.get("revenue_basis", ""),
                "na": False,
                "ytd_sales_bt": round(normalize_mrl_to_btom(
                    annual / max(12.0 / max(months, 1), 1e-9)), 1),
                "scale_table": [{"months": m, "factor": round(12.0 / m, 2)}
                                for m in ANNUALIZATION_SCALE]})
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  شاخص ۴ — تک‌مرجعِ «سندِ فروش ندارد» (معافیت/ N/A)
# ═══════════════════════════════════════════════════════════════════════════
# برای این طبقه «فروش» معنا ندارد؛ سند v2.1 (F-04) محاسبهٔ نسبتِ فروش÷ارزشِ
# بازار را برایشان «غیرمجاز» می‌داند و حکمِ جزوه «N/A به‌جای عدد ساختگی» است
# (کلیدِ کانفیگ: holdings_sales_na). این فهرست، اشتراکِ دو فهرستِ پیشین است:
# fts_engine (سرمایه‌گذاری/چندرشته) و api/fundamental._HOLD_TOKENS
# (بانک/واسطه‌گری/نهادهای مالی واسط/هلدینگ) — تا اسکرینر و کارت جزئیات روی
# یک نماد دو جواب متفاوت ندهند. از این پس تنها ind4_exempt این را می‌سنجد.
_HOLDING_SECTOR_KEYS = ("سرمایه گذاری", "سرمایه‌گذاری", "چندرشته", "هلدینگ",
                        "بانک", "واسطه گری", "واسطه‌گری", "نهادهای مالی واسط")


def _hold_norm(text) -> str:
    """نرمالِ مقایسهٔ طبقه: norm_fa + حذفِ فاصله.

    norm_fa نیم‌فاصله را می‌اندازد ولی فاصلهٔ معمولی را نه؛ دادهٔ واقعی
    «سرمايه گذاري» و «چند رشته اي» را با فاصله می‌نویسد. بی‌این‌گام، دو توکنِ
    «سرمایه‌گذاری» و «چندرشته» در فهرست بالا هرگز به داده نمی‌خوردند (توکنِ
    مرده) و نوشتارِ هر نماد جواب را عوض می‌کرد.
    """
    return norm_fa(text).replace(" ", "")


_HOLDING_SECTOR_TOKENS = tuple(_hold_norm(k) for k in _HOLDING_SECTOR_KEYS)


def holding_class_match(sector_norm, company_name: str = "") -> bool:
    """آیا نامِ طبقه (صنعت یا نامِ شرکت) در طبقهٔ معافِ شاخص ۴ است؟"""
    s = _hold_norm(sector_norm) + " " + _hold_norm(company_name)
    return any(t in s for t in _HOLDING_SECTOR_TOKENS)


# صندوقِ سرمایه‌گذاری پنج‌شاخصهٔ FTS را نمی‌گذراند: «رشد فروش»، «حاشیهٔ سود
# ناخالص» و «فروش ÷ ارزش بازار» برای سبدِ دارایی معنا ندارد. رأی ۱۵ (صاحبِ
# جزوه) داوری را «FTS ندارد» می‌کند نه REJECT. تک‌مرجع همین تابع است — کارتِ
# جزئیات (api/fundamental.company_profile)، اسکرینر (bulk_scan/screener) و
# دروازهٔ مستر همگی همین را می‌خوانند تا یک نماد دو جواب نگیرد.
_FUND_TOKEN = _hold_norm("صندوق")


def fund_class_match(sector_norm, company_name: str = "") -> bool:
    """آیا نماد صندوقِ سرمایه‌گذاری است (از صنعت یا از نامِ شرکت)؟

    استثنا: صنعتِ بیمه و صندوقِ بازنشستگی (۱۲۹ نماد، کدِ صنعت ۶۶). نامِ آن
    صنعت «بيمه وصندوق بازنشستگي به جزتامين اجتماعي» است و توکنِ «صندوق» در وسطش
    می‌نشیند، ولی این‌ها شرکتِ عملیاتیِ دارای صورتِ مالی‌اند، نه سبدِ دارایی.
    رأی ۱ برای بیمه «وتو/هشدار» را لازم می‌داند نه «معافیت» — پس نمادی که
    بیمه است هیچ‌جهت صندوقِ FTS-نامزود نیست. بی‌این استثنا، دو شرکتِ بیمه‌ایِ
    دارایِ داده (آسیا، اتكام) بی‌صدا از پنج‌شاخصه خارج می‌شدند.
    """
    if is_insurance_sector(sector_norm):
        return False
    return _FUND_TOKEN in (_hold_norm(sector_norm) + " " + _hold_norm(company_name))


def company_name_of(conn, symbol) -> str:
    """نامِ شرکت از خودِ دیتابیس (نه از رشته‌ای که فراخوان آورده).

    چرا داخلِ قاعده و نه به‌عنوانِ آرگومان: کارت جزئیات نام را از فراخوان
    (cname_of با ترتیبِ period_end) می‌گرفت و اسکرینر هرگز نامی نمی‌دید؛ با
    تک‌منبعِ DB هر دو مسیر دقیقاً یک رشته مقایسه می‌کنند.
    """
    if conn is None:
        return ""
    try:
        pred, params = sym_in(conn, "symbol", symbol)
        row = conn.execute(
            "SELECT company_name FROM financial_statements "
            "WHERE %s AND company_name IS NOT NULL "
            "%s, tracing_no DESC LIMIT 1" % (pred, CP.latest_order_sql()), params).fetchone()
    except sqlite3.Error:
        return ""
    return (row[0] if row else "") or ""


def company_name_map(conn: sqlite3.Connection) -> dict:
    """نقشهٔ SI.key(symbol) -> نامِ شرکت، تک‌کوئری (همان ردیفِ company_name_of).

    «آخرین» اینجا هم دقیقاً `codal_periods.latest_order_sql()` است (دورۀ canonical
    اول، بی‌دوره آخر، سپس tracing_no DESC)؛ اگر ترتیبش فرق کند، اسکرینر و کارت
    برای یک نماد دو طبقهٔ مختلف می‌بینند.
    """
    out = {}
    try:
        rows = conn.execute(
            "SELECT symbol, company_name, period_end, tracing_no "
            "FROM financial_statements WHERE company_name IS NOT NULL").fetchall()
    except sqlite3.Error:
        return out
    best = {}
    for sym, name, pe, tn in rows:
        key = SI.key(sym)
        if not key:
            continue
        rank = (CP.desc_sort_key(pe), int(tn or 0))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, name)
    for key, (_rank, name) in best.items():
        out[key] = name or ""
    return out


def company_name_for(conn: sqlite3.Connection, symbol: str) -> str:
    """نامِ شرکتِ یک نماد — همان ردیفی که company_name_map برای کل بازار می‌دهد.

    رتبه‌بندی باید عیناً یکی باشد (period_end DESC سپس tracing_no DESC)، و
    ردیفِ بی‌نام هم «برنده» شمرده می‌شود و ته‌اش رشتهٔ خالی است — دقیقاً مثلِ
    company_name_map. اگر این دو فرق کنند (مثلاً فیلترکردنِ NULL)، «صندوق بودن»
    یک نماد بین اسکرینر و کارت دو جواب می‌شود، و رأی ۱۵ همان واگرایی را ممنوع
    کرده است.
    """
    al = [a for a in SI.variants(conn, symbol) if a]
    if not al:
        return ""
    try:
        row = conn.execute(
            "SELECT company_name FROM financial_statements "
            "WHERE symbol IN (%s) "
            "%s, tracing_no DESC LIMIT 1" % (",".join("?" * len(al)), CP.latest_order_sql()),
            al).fetchone()
    except sqlite3.Error:
        return ""
    return (row[0] if row else "") or ""


def has_operating_sales(conn: sqlite3.Connection, symbol: str) -> Optional[int]:
    """آیا جدیدترین صورتِ مالیِ این نماد سطرِ «درآمد عملیاتی» دارد؟

    سه‌مقدار و از شواهدِ خودِ اسکرپ (نه از نامِ صنعت/نماد):
      1    → «جمع درآمدهای عملیاتی» مچ شد؛ مفهومِ فروش وجود دارد.
      0    → شیتِ سود و زیان خوانده شد ولی چنین سطری نداشت — یعنی صندوق/
             سبدگردانی که فقط «جمع درآمدها»ی سرمایه‌گذاری منتشر می‌کند.
      None → با پارسرِ جدید بازخوانی نشده (یا ستون هنوز مهاجرت نشده).
    """
    try:
        # sym_in، نه `symbol = ?`: دیتابیس بعضی نمادها را با ي/ك عربی ذخیره کرده
        # و با مقایسهٔ خام، همان نماد بسته به نوشتارِ ورودی دو جواب متفاوت
        # می‌گرفت (امتیاز ۲ در برابر ۳ روی شارپيلن/شارپیلن و هانيكو/هانیکو).
        # norm_fa سمت SQL هم راه‌حل نیست — v9.7.3 روی همین بانک اندازه گرفت.
        pred, params = sym_in(conn, "symbol", symbol)
        row = conn.execute(
            "SELECT has_operating_sales FROM financial_statements "
            "WHERE %s ORDER BY tracing_no DESC LIMIT 1" % pred, params).fetchone()
    except sqlite3.OperationalError:
        return None            # DB قدیمی که هنوز migrate_schema ندیده است
    return None if row is None else row[0]


def ind4_exempt(conn, symbol: str, sector_norm: str = "", *,
                holdings_na: bool = True,
                _precomputed: Optional[set] = None,
                company_name: Optional[str] = None) -> bool:
    """تک‌مرجعِ معافیتِ شاخص ۴ («تخمین فروش ۱۲ ماهه ÷ ارزش بازار»).

    قاعده = (نامِ طبقه در صنعت یا در نامِ شرکت) **یا** (شاهدِ صورتِ مالی:
    has_operating_sales == 0 — صندوق/سبدگردانی که فقط «جمع درآمدها» را منتشر
    می‌کند). هر دو مسیرِ اسکرینر (bulk_scan/scan_symbol) و کارت جزئیات
    (api/fundamental) همین یک تابع را صدا می‌زنند، پس داوری نمی‌تواند واگرا
    شود.

      * شاهدِ None («با پارسرِ جدید بازخوانی نشده») معافیت **نمی‌آورد** — صفرِ
        بی‌داده به‌جای عدد ساختگی هم نیست؛ همان سه‌مقدارهٔ has_operating_sales.
      * holdings_na=False یعنی کاربر کلیدِ کانفیگِ معافیت را خاموش کرده (مثل
        امروز فقط مسیرِ کارت این گیت را می‌گذراند؛ مسیرهای موتور پیش‌فرض
        روشن‌اند).
      * conn=None یعنی اتصال در دسترس نیست (مسیرِ کلاسِ FTSEngine که فقط
        دیکشنریِ نماد را می‌بیند) — آن‌جا فقط شاهدِ نامی سنجیده می‌شود.
      * _precomputed مجموعهٔ no_sales_symbols است تا اسکنِ کل بازار به‌ازای هر
        نماد یک کوئری نزند (الگوی ضدِN+1ِ همان‌جا).
    """
    if not holdings_na:
        return False
    # اولِ صنعت (بی‌کوئری)، بعدِ نامِ شرکت از DB — تا اسکنِ کل بازار برای
    # نمادهایی که صنعتشان در طبقهٔ معاف است، کوئریِ اضافه نزند.
    if holding_class_match(sector_norm):
        return True
    # نام را اگر فراخواننده دارد، دوباره کوئری نزن (scan_symbol قبلاً خوانده).
    if holding_class_match("", company_name if company_name is not None
                           else company_name_of(conn, symbol)):
        return True
    if _precomputed is not None:
        return SI.key(symbol) in _precomputed
    if conn is None:
        return False
    return has_operating_sales(conn, symbol) == 0


def no_sales_concept(conn: sqlite3.Connection, symbol: str, sector: str = "",
                     _precomputed: Optional[set] = None,
                     holdings_na: bool = True,
                     company_name: Optional[str] = None) -> bool:
    """نامِ قدیمیِ همان قاعده — فقط واگرد به ind4_exempt (منطق این‌جا نیست)."""
    return ind4_exempt(conn, symbol, sector, holdings_na=holdings_na,
                       _precomputed=_precomputed, company_name=company_name)


def no_sales_symbols(conn: sqlite3.Connection) -> set:
    """نمادهایی که جدیدترین صورتِ مالی‌شان سطرِ درآمدِ عملیاتی ندارد (۰).

    تک‌کوئریِ کل‌بازاری — همان الگوی m141_map/avg_trade_value_hmt؛ اسکنِ ۶۰۹
    نماد نباید ۶۰۹ کوئری بسازد.

    «آخرین» باید دقیقاً همان قاعدهٔ has_operating_sales باشد: بزرگ‌ترین
    tracing_no روی **همهٔ املايِ یک نماد**. اگر به‌ازای نوشتارِ خام گروه ببندیم،
    نمادی که دو املا دارد یک‌جا معاف و جای دیگر معاف نمی‌شود و bulk_scan با
    scan_symbol می‌جنگد (dev/confidence_engine_v973.py این را می‌گیرد)."""
    try:
        rows = conn.execute(
            "SELECT f.symbol, f.has_operating_sales, f.tracing_no "
            "FROM financial_statements f "
            "JOIN (SELECT symbol, MAX(tracing_no) mt FROM financial_statements "
            "      GROUP BY symbol) m ON m.mt = f.tracing_no "
            "WHERE f.has_operating_sales IS NOT NULL").fetchall()
    except sqlite3.OperationalError:
        return set()
    best = {}
    for sym, flag, tn in rows:
        if not sym:
            continue
        key = SI.key(sym)
        cur = best.get(key)
        if cur is None or (tn or 0) > cur[1]:
            best[key] = (flag, tn or 0)
    return {k for k, (flag, _tn) in best.items() if flag == 0}


def sales_to_marketcap(conn: sqlite3.Connection, symbol: str, market_cap_rials: float,
                       min_ratio: float = 1.0, annual: Optional[dict] = None,
                       sector: str = "", _no_sales: Optional[set] = None,
                       holdings_na: bool = True) -> Optional[dict]:
    """فروش سالانه ÷ ارزش بازار روز — جزوه: باید ≥ min_ratio (پیش‌فرض ۱.۰) باشد.
    شرکت‌های سرمایه‌گذاری/هلدینگ معاف (N/A) هستند.
    `_no_sales` مجموعهٔ از پیش ساخته‌شده (no_sales_symbols) است تا اسکنِ کل بازار
    به ازای هر نماد یک کوئری نزند.
    """
    if no_sales_concept(conn, symbol, sector, _precomputed=_no_sales,
                        holdings_na=holdings_na):
        mcap = _f(market_cap_rials)
        return {"sales_to_mcap": None,
                "annual_sales_bt": None,
                "mcap_ht": round(mcap / 1e13, 2),
                "annualize_basis": "معافیت هلدینگ/سرمایه‌گذاری (مبنای P/NAV)",
                # رأی ۱۶: «pass» برایِ شاخصی که سنجیده نشده معنا ندارد؛ True بودنش
                # در این dict تنها منبعِ امتیازِ رایگانِ باقی‌مانده بود (داوریِ
                # واقعی را ind4_exempt/applicable می‌کند، نه این کلید).
                "pass": None,
                "is_exempt": True,
                "threshold": min_ratio,
                "formula": "معافیت هلدینگ بر مبنای P/NAV"}
    a = annual or annualized_sales(conn, symbol)
    mcap = _f(market_cap_rials)
    if not a or mcap <= 0:
        return None
    ratio = (a["annual_sales_mrl"] * MRL_TO_RIAL) / mcap
    return {"sales_to_mcap": round(ratio, 2),
            "annual_sales_bt": a["annual_sales_bt"],
            "mcap_ht": round(mcap / 1e13, 2),
            "annualize_basis": a["basis"],
            "pass": ratio >= min_ratio,
            "threshold": min_ratio,
            "formula": "فروش سالانهٔ Annualized ÷ ارزش بازار روز"}


def gross_profit_potential(conn: sqlite3.Connection, symbol: str, market_cap_rials: float,
                           min_pct: float = 40.0, gm: Optional[dict] = None,
                           annual: Optional[dict] = None) -> Optional[dict]:
    """پتانسیل سود ناخالص به ارزش بازار = (فروش سالانه × حاشیه ناخالص) ÷ ارزش بازار × ۱۰۰.
    آستانهٔ استاندارد v2.1 و جزوه: حداقل ۴۰٪.
    """
    mcap = _f(market_cap_rials)
    if mcap <= 0:
        return None
    g = gm if gm is not None else gross_margin(conn, symbol)
    a = annual or annualized_sales(conn, symbol)
    if not g or not a:
        return None
    # حاشیهٔ N/A (مالی/هلدینگ/صندوق) «صفر» نیست؛ پتانسیل هم ساخته نمی‌شود.
    if g.get("na") or g.get("margin_pct") is None:
        return None
    # رأی ۱۶: ردیفِ N/A (هلدینگ/سرمایه‌گذاری) «عددِ صفر» نیست، «نظرِ نداده» است —
    # وگرنه این‌جا ۰٫۰ ساخته می‌شد در جایی که کارت هیچ عددی نمی‌داد.
    if a.get("na") or _f(a.get("annual_sales_mrl")) <= 0:
        return None
    est_gp_mrl = a["annual_sales_mrl"] * (g["margin_pct"] / 100.0)
    pct = (est_gp_mrl * MRL_TO_RIAL / mcap) * 100.0
    return {"potential_pct": round(pct, 1),
            "est_gross_profit_bt": round(normalize_mrl_to_btom(est_gp_mrl), 1),
            "margin_used_pct": g["margin_pct"],
            "mcap_ht": round(mcap / 1e13, 2),
            "pass": pct >= min_pct,
            "threshold": min_pct,
            "formula": "(فروش سالانه × حاشیه سود ناخالص) ÷ ارزش بازار × ۱۰۰"}


def i4_potential_margin(margin, ref):
    """(حاشیه، مبنا) — فقط برایِ پتانسیلِ شاخص ۴؛ هرگز به i3/فیلتر صنعت نمی‌رود.

    قراردادِ کارت (`api.fundamental.ind4_valuation`): اگر حاشیهٔ ناخالص N/A باشد
    (طبقهٔ مالی/بانکی/هلدینگ/صندوق یا نبودِ سطرِ سود ناخالص) ولی نسبتِ سود خالص
    به درآمد در بازهٔ (۰, ۱۰۰] باشد، همان «حاشیهٔ سود خالص (جایگزینِ مالی)»
    مبنایِ پتانسیل می‌شود و صریحاً برچسب می‌خورد. این تابع نسخهٔ دومِ قاعده
    نیست؛ همان شرطِ کارت است تا ردیفِ `bulk_scan`/`scan_symbol` و کارت یک عدد
    بدهند (پاریتیِ ۱۰B2a2). صفرِ حاشیه مثلِ کارت «حاشیه نیست» است و پتانسیلی
    نمی‌سازد.
    """
    if margin is not None:
        return (margin or None), "gross_margin"
    if not ref:
        return None, "gross_margin"
    rev = _f(ref.get("revenue"))
    net = _fn(ref.get("net_profit"))
    if rev > 0 and net is not None and 0 < (net / rev * 100.0) <= 100.0:
        return round(net / rev * 100.0, 1), "net_margin_proxy"
    return None, "gross_margin"

# ============================ شاخص ۵: فیلتر صنعت (قیمت‌گذاری آزاد / دستوری)
def sector_filter(sector: str, cfg: dict = None, market_cap_rials: float = 0.0,
                  total_market_cap_rials: float = 0.0,
                  gpm: Optional[float] = None,
                  sales_growth: Optional[float] = None) -> dict:
    """تفکیک تگ صنعت به «قیمت‌گذاری آزاد/بورس کالا» و «قیمت‌گذاری دستوری».
    شامل استثنای دارویی با GPM >= آستانهٔ cfg و بانک با رشد مثبت درآمدهای تسهیلاتی.
    """
    cfg = cfg or {}
    # تطبیق روی «هستۀ» برچسبِ صنعت، بی بندِ «به جز …» — وگرنه استثنایِ داخلِ
    # نام، خودِ نام را دستوری می‌کند (توضیحِ کامل در `sector_core`).
    s = sector_core(sector)
    mandatory = [norm_fa(t) for t in (cfg.get("mandatory_sectors")
                                      or MANDATORY_PRICING_TOKENS)]
    free = [norm_fa(t) for t in (cfg.get("free_sectors") or FREE_PRICING_TOKENS)]

    # استثنای دارویی — **به‌طورِ پیش‌فرض خاموش است** (رأیِ مالک ۱۴۰۵-۰۷-۱۱: چنین
    # آستانه‌ای در جزوه نیست). کلیدِ `pharma_margin_exempt_min` تنها وقتی خوانده
    # می‌شود که کاربر خودش عددی non-zero بگذارد؛ با ۰ دارو مثل هر صنعتِ دیگرِ
    # خارج از دو فهرست داوری می‌شود («خنثی»)، نه معاف و نه رد.
    _pharma_min = _th(cfg, "pharma_margin_exempt_min")
    if "دارو" in s and _pharma_min > 0:
        if gpm is not None and gpm >= _pharma_min:
            mode = "free"
            hit_free = ["دارویی ممتاز (حاشیۀ ناخالص ≥ %.0f٪)" % _pharma_min]
            hit_mand = []
        elif gpm is not None:
            mode = "mandatory"
            hit_mand = ["دارویی عادی (قیمت‌گذاری دستوری)"]
            hit_free = []
        else:
            mode = "neutral"
            hit_mand, hit_free = [], []
    # استثنای بانک‌ها: اگر رشد درآمد مثبت داشته باشد تایید می‌شود
    elif any(k in s for k in ("بانک", "بانك", "اعتباری", "اعتباري")):
        if sales_growth is not None and sales_growth > 0:
            mode = "free"
            hit_free = ["بانک رشد درآمدی و ارزی"]
            hit_mand = []
        else:
            mode = "neutral"
            hit_mand = []
            hit_free = []
    else:
        hit_mand = [t for t in mandatory if t and t in s]
        hit_free = [t for t in free if t and t in s]
        if hit_mand:
            mode = "mandatory"
        elif hit_free:
            mode = "free"
        else:
            mode = pricing_mode(sector)

    exclude = str(cfg.get("industry_mode", "Exclude_Mandatory_Pricing")) != "Rank_Only"
    share = ((_f(market_cap_rials) / _f(total_market_cap_rials) * 100.0)
             if total_market_cap_rials else 0.0)
    label = {"mandatory": "قیمت‌گذاری دستوری", "free": "قیمت‌گذاری آزاد / بورس کالا",
             "neutral": "خنثی — نیازمند بررسی موردی"}.get(mode, "سایر")
    return {"verdict": mode, "label": label, "sector": sector,
            "matched_tokens": hit_mand or hit_free,
            "fts_top_industry": bool(hit_mand or hit_free),
            "pass": (mode != "mandatory") if exclude else True,
            "exclusion_active": exclude,
            "market_share_pct": round(share, 3)}


# ================================= فیلترهای حذف خودکار (پیش‌غربالگری خروجی)
def market_sessions(conn: sqlite3.Connection, n: int = 8) -> list:
    """جدول نشست‌های معاملاتی بازار (تازه‌ترین در ابتدا) از daily_prices."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT d_even FROM daily_prices ORDER BY d_even DESC LIMIT ?", (n,))]


def is_suspended(conn: sqlite3.Connection, symbol: str, max_stale_sessions: int = 3,
                 _sessions: list = None) -> bool:
    """نماد تعلیق = آخرین روز معاملاتیِ خودِ نماد از آخرین نشستِ بازار عقب‌تر باشد.

    `market_watch.d_even` روزِ معاملاتیِ همان نماد است؛ با آستانهٔ ۳ نشست روی
    market.db فعلی فقط ۱۱ نماد از ۱۰۱۵ نماد دارای صورت مالی علامت می‌خورند
    (بدون false-positive انبوه روی قراردادهای اختیار معامله).
    """
    sess = _sessions if _sessions is not None else market_sessions(conn)
    if len(sess) < 2:
        return False
    cut_idx = min(max(int(max_stale_sessions), 0), len(sess) - 1)
    cutoff = sess[cut_idx]
    pred18, params = sym_in(conn, "i.l_val18", symbol, SI.BOARD)
    pred30 = pred18.replace("i.l_val18", "i.l_val30")
    row = conn.execute(
        "SELECT m.d_even FROM market_watch m JOIN instruments i ON i.ins_code=m.ins_code "
        "WHERE " + pred18 + " OR " + pred30 + " ORDER BY m.d_even DESC LIMIT 1",
        (*params, *params)).fetchone()
    if not row or row[0] is None:
        return False                 # بدون تابلو (نماد فقط-کدال) → تعلیق تلقی نمیشود
    return int(row[0]) < int(cutoff)

# ============================================ v9.7 — ماده ۱۴۱ و نقدشوندگی
# هر دو به‌صورت «نقشهٔ تک‌کوئری» روی کل بازار محاسبه میشوند تا scan_all
# و bulk_scan به N+1 نیفتند.

def m141_map(conn: sqlite3.Connection) -> dict:
    """نمادهای مشمول ماده ۱۴۱ قانون تجارت → {symbol_norm: bool}.

    تعریف قانونی: زیان انباشته به‌قدری است که نصف سرمایه را از بین برده،
    یعنی  دارایی خالص ≤ نصف سرمایه  (capital > 0).
    مبنای محاسبه: «آخرین» صورت‌مالی سالانهٔ هر نماد (بزرگ‌ترین period_end؛
    در تساوی، تازه‌ترین publish_date). نمادهای بدون صورت‌مالی سالانهٔ
    قابل‌استفاده در نقشه نمی‌آیند → مشمول نمی‌شوند (نه اینکه مردود شوند).

    چرا فیلتر تک‌نمادی روی این کوئری نمی‌چسبد: کلیدهای خروجی SI.key(symbol)
    است، ولی ستونِ دیتابیس نوشتار خام (گاهی عربی: ي/ك/ى) دارد. اگر در SQL
    بنویسیم `symbol = ?`، نمادهایی که دیتابیس‌شان عربی‌نویسی است بی‌صدا
    «پیدا نمی‌شوند» و m141 = False برمی‌گردد — یعنی خطای داده‌ای که هیچ‌وقت
    در لاگ دیده نمی‌شود. تست dev/fts_m141_parity_v97.py همین را روی ۲۲۴ نماد
    گرفت. راه‌حلِ همین‌جا «کلیدِ نرمال در Python» است (کوئری کل‌بازار است و
    از قبل همه‌چیز را می‌خواند). برای کوئریِ تک‌نماد، `symbol_aliases`/`sym_in`
    باید استفاده شود — نه `WHERE SI.key(symbol)=?`، که به اندازه‌گیریِ
    v9.7.3 روی همین بانک ۵۷۴ برابر اسکنِ ایندکسی هزینه دارد.
    """
    rows = conn.execute("""
        SELECT symbol, capital, total_equity, period_end, publish_date, period_months, title
        FROM financial_statements
        WHERE (period_months >= 12 OR period_months IS NULL)
          AND capital > 0 AND total_equity IS NOT NULL
        ORDER BY symbol, %s, %s""" % (CP.order_expr(), CP.pub_order_expr())).fetchall()
    out = {}
    for sym, cap, eq, _pe, _pd, _pm, _t in rows:
        key = SI.key(sym)
        if key in out:                      # فقط جدیدترین سال مالی ملاک است
            continue
        # «سالانہ بودن» هم از همان `effective_months` — وگرنه نقشۀ ماده ۱۴۱ با
        # پنجرۀ سالانۀ کارت دو «آخرین سالِ مالی» مختلف می‌داد.
        months, _src = CP.effective_months(_pe, _pm, _t)
        if months is None or months < 12:
            continue
        try:
            cap, eq = float(cap), float(eq)
        except (TypeError, ValueError):
            continue
        out[key] = eq <= 0.5 * cap
    return out


def avg_trade_value_hmt(conn: sqlite3.Connection, sessions: int = 30) -> dict:
    """میانگین ارزش معاملات روزانه به «همت» → {symbol_norm: float}.

    منبع: daily_prices.q_tot_cap = ارزش ریالی معاملات همان روز. میانگین روی
    `sessions` نشستِ اخیرِ خودِ نماد گرفته میشود (نه کل جدول) تا نمادی که
    مدتی است معامله ندارد، نقدشونده به‌نظر نرسد.

    تک‌کوئری و کل‌بازاری است؛ scan_all/bulk_scan آن را یک‌بار می‌سازند و برای
    هر نماد از نقشه می‌خوانند. برای scan_symbol تنها (یک کوئری ~۳۵ms) قابل‌قبول
    است. فیلتر تک‌نمادی به همان دلیلِ norm_fa در m141_map اعمال نشده.
    """
    sess = market_sessions(conn)[:max(int(sessions), 1)]
    if not sess:
        return {}
    cutoff = min(int(s) for s in sess)
    rows = conn.execute("""
        SELECT i.l_val18, AVG(d.q_tot_cap), COUNT(*)
        FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code
        WHERE d.q_tot_cap > 0 AND d.d_even >= ?
        GROUP BY i.l_val18""", (cutoff,)).fetchall()
    # همت = ۱۰^۱۰ ریال
    return {SI.key(sym): (val or 0.0) / 1e10
            for sym, val, _n in rows if sym}


# =================================================== اسکن کامل ۵ شاخص
def scan_symbol(conn: sqlite3.Connection, symbol: str, market_cap_rials: float = 0.0,
                total_market_cap_rials: float = 0.0, sector: str = "",
                cfg: dict = None, _sessions: list = None,
                m141_hit: Optional[bool] = None,
                avg_trade_val: Optional[float] = None,
                _no_sales: Optional[set] = None) -> dict:
    """اجرای هر ۵ شاخص روی یک نماد → خروجی کارت بنیادی (endpoint /api/fts/{symbol}).

    cfg = پیش‌شرط‌های fts_thresholds.json (None = پیش‌فرض جزوه).
    m141_hit / avg_trade_val: اگر از بیرون داده شوند، کوئری تکراری زده نمیشود
    (scan_all هر دو نقشه را یک‌بار می‌سازد و به ازای هر نماد پاس میدهد).
    """
    cfg = cfg or {}
    mcap = _f(market_cap_rials)
    ref = reference_annual(conn, symbol)
    # طبقه از همان `company_profile`ِ کارت + نامِ شرکتِ همان نماد (یک کوئری، دو مصرف)
    cname = company_name_for(conn, symbol)
    prof = company_profile(sector, cname)
    # صندوق داوری ندارد (رأی ۱۵): مسیرِ پذیرش هم نباید برایش ساخته شود، ولو
    # صورتِ مالی‌اش سطرِ درآمدِ عملیاتی داشته باشد (Task 7 M6).
    _is_fund = fund_class_match(sector, cname)
    # گیتِ کانفیگِ معافیت (holdings_sales_na) — همان که مسیرِ کارت می‌گذراند:
    # خاموش یعنی «معافیتِ N/A اعمال نشود»، تا زیرِ هر حالتِ کانفیگ دو مسیر
    # یک داوری بدهند (پیش از این فقط کارت آن را می‌خواند).
    _hold_na = bool(cfg.get("holdings_sales_na", True))
    _exempt = ind4_exempt(conn, symbol, sector, holdings_na=_hold_na,
                          _precomputed=_no_sales)

    # قاعدهٔ ۱الف/۱ب مشترک با کارت (Task 2/3) — import محلی تا چرخهٔ
    # api.fundamental → fts_engine هنگامِ بارگذاری نشکند.
    from api.fundamental import (axis1_state, ind1a_fs_growth,
                                 ind1b_volume_growth, v10_thresholds,
                                 MONTHLY_BAD_YTD_REASON,
                                 MONTHLY_NO_PRIOR_REASON,
                                 MONTHLY_NO_SERIES_REASON)
    th1b = v10_thresholds(cfg)
    series = monthly_series(conn, symbol)
    g = revenue_growth_yoy(conn, symbol, min_growth=_th(cfg, "growth_min"),
                           growth_target=_th(cfg, "v10_monetary_growth_min"),
                           sector=sector, series=series)
    # دلیلِ شکاف را همان متنِ کارت می‌گوییم (Task 4) — پیش از این رشتهٔ خالی
    # بود و `axis1_state` به متنِ عمومی می‌افتاد، پس i1_reason دو مسیر یکی نبود.
    if not series:
        # ردیفِ ماهانه هست ولی تجمیعی‌اش نامعتبر است ⇒ BAD_YTD، نه NO_SERIES
        # (Task 10B2a1 C1؛ همان تفکیکِ کارت و bulk_scan).
        reason1a = (MONTHLY_BAD_YTD_REASON if monthly_has_rows(conn, symbol)
                    else MONTHLY_NO_SERIES_REASON)
    elif g is None:
        reason1a = MONTHLY_BAD_YTD_REASON
    elif g.get("data_gap"):
        reason1a = MONTHLY_NO_PRIOR_REASON
    else:
        reason1a = ""
    monetary = {"pass": bool(g and g.get("pass")),
                "monetary_pct": (g or {}).get("growth_pct"),
                "data_gap": bool(g is None or g.get("data_gap")),
                "reason": reason1a, "year": (g or {}).get("year"),
                "months": (g or {}).get("months") or 0}
    if prof["kind"] in FS_GROWTH_KINDS and not series:
        # خدماتی/مالی/هلدینگِ بی‌گزارشِ ماهانه: رشد از صورتِ مالی — همان
        # قاعده‌ای که کارت و `bulk_scan` دارند (Task 2). بی‌این، /api/fts/{symbol}
        # برایِ ۳۴ نمادِ بی‌گزارشِ ماهانه حکمِ دیگری از اسکرینر می‌داد.
        fg = ind1a_fs_growth(conn, symbol, prof, th=th1b)
        monetary = {"pass": bool(fg.get("pass")),
                    "monetary_pct": fg.get("monetary_pct"),
                    "data_gap": bool(fg.get("data_gap"))
                    or fg.get("monetary_pct") is None,
                    "reason": fg.get("reason") or "",
                    "year": fg.get("year"), "months": fg.get("months") or 0}
        g = {"growth_pct": (None if fg.get("monetary_pct") is None
                            else round(fg["monetary_pct"], 1)),
             "pass": bool(fg.get("pass")),
             "threshold": _th(cfg, "growth_min"),
             "data_gap": bool(fg.get("data_gap")),
             "denominator_basis": fg.get("basis") or "",
             "revenue_basis": (prof or {}).get("revenue_basis", "")}
    volume = ind1b_volume_growth(conn, symbol, monetary=monetary, series=series,
                                 th=th1b, profile=prof)
    axis1, axis1_reason = axis1_state(monetary, volume)
    e = eps_trend_3y(conn, symbol, years=int(cfg.get("eps_years", 3) or 3), sector=sector)
    # گیتِ طبقهٔ شاخص ۳ (سند فاز ۱، بند ۴٫۴): مالی/بانکی/هلدینگ/صندوق N/A است،
    # حتی اگر صورت مالی سود ناخالص داشته باشد؛ ۲۰/۳۰ِ تولیدی/خدماتی دست‌نخورده.
    m_min = _f(cfg.get("margin_min", 20.0)) or 20.0
    m_opt = _f(cfg.get("margin_optimal", 30.0)) or 30.0
    gm = margin_class_na(prof, min_margin=m_min, optimal=m_opt)
    if gm is None:
        gm = gross_margin(conn, symbol, min_margin=m_min, optimal=m_opt, ref=ref)
    # حاشیهٔ جایگزینِ پتانسیل (Task 10B2a2) — همان قاعدهٔ کارت/ردیفِ bulk؛
    # فقط به `gross_profit_potential` می‌رود، نه به حکم/دلیل/فیلترِ شاخص ۳.
    pot_margin, pot_margin_basis = i4_potential_margin(
        None if (gm is None or gm.get("na")) else gm.get("margin_pct"), ref)
    annual = annualized_sales(conn, symbol, ref=ref, profile=prof, exempt=_exempt)
    s2m = sales_to_marketcap(conn, symbol, mcap,
                             min_ratio=_th(cfg, "sales_to_mcap_min"),
                             annual=annual, sector=sector, _no_sales=_no_sales,
                             holdings_na=_hold_na)
    pot = None
    if pot_margin is not None:
        pot = gross_profit_potential(conn, symbol, mcap,
                                     min_pct=_th(cfg, "profit_potential_min"),
                                     gm={"margin_pct": pot_margin}, annual=annual)
    # دلیلِ خالی‌بودنِ حکمِ ۳ — همان متنِ کارت/ردیفِ bulk (Task 10B2a1/10B2a2):
    # N/Aِ طبقه از خودِ `gm`، شکافِ داده از `margin_gap_detail`.
    if gm is not None and gm.get("na"):
        i3_reason = gm.get("reason") or ""
    elif gm is None:
        from api.fundamental import margin_gap_detail as _margin_gap_detail
        i3_reason = _margin_gap_detail(ref).get("reason") or ""
    else:
        i3_reason = ""
    # `i3_na` فقط سیگنالِ N/Aِ طبقه است (Task 10B2a1 fix round 1): شکافِ داده
    # (`gm is None`) حکمِ None دارد ولی پرچمِ N/Aِ ماهیت نمی‌گیرد — همان
    # قراردادِ bulk (`bool(class_na)`) و `ind3_na`ِ کارت.
    i3_na = bool(gm is not None and gm.get("na"))
    sec = sector_filter(sector, cfg=cfg, market_cap_rials=mcap,
                        total_market_cap_rials=total_market_cap_rials,
                        gpm=(gm.get("margin_pct") if gm else None),
                        sales_growth=(g.get("growth_pct") if g else None))

    # رژیمِ «سندِ فروش ندارد» (گارد F-04b): هلدینگ/سرمایه‌گذاری بر مبنای P/NAV
    # داوری می‌شود، و از این رو صندوق/سبدگردانی که صورتِ مالی‌شان اصلاً سطرِ
    # «درآمد عملیاتی» ندارد هم — تا رقمِ سرمایه‌گذاری به‌جای فروش حساب نشود.
    is_holding = no_sales_concept(conn, symbol, sector, _precomputed=_no_sales,
                                  holdings_na=_hold_na, company_name=cname) or _is_fund
    sales_pass = bool(s2m and s2m.get("pass"))
    pot_pass = bool(pot and pot.get("pass"))
    i4_available = bool(annual) and mcap > 0 and not is_holding
    if is_holding:
        # رأی ۱۶ (۱۴۰۵/۰۷/۰۳): معافیت یعنی «نظر نمی‌دهد»، نه پاسِ رایگان. نمادی
        # که مدلِ کسب‌وکارش فروشِ عملیاتیِ ماهانه ندارد، معیارِ سنجشِ این شاخص را
        # ندارد؛ تظاهر به پاس‌شدن، نمرهٔ ۲۹۷ نماد را کاذب بالا می‌برد و قیفِ
        # ص ۲ (۸۰۰ → ۵۰ → ۱۰ → ۵-۷) را مخدوش می‌کند. کارتِ جزئیات همین را
        # می‌کرد و موتور به آن تراز شد.
        passes_s2m = None
        path4 = None
        i4_reason = ind4_reason_text(exempt=True)
    else:
        # سه‌حالۀ مشترک با `bulk_scan` (تابعِ `ind4_vote`): بی‌شاهدِ فروشِ سالانه
        # «رد» نیست، «سنجیده نشد» است. پیش از این همین‌جا `bool(None or None)`
        # صفر می‌شد و نمادِ بی‌داده مردود شمرده می‌شد.
        passes_s2m = ind4_vote(annual, s2m, pot, False, mcap=mcap)
        # همان نامِ مسیرِ ردیفِ bulk (Task 7): اول فروش÷ارزش بازار، بعد پتانسیل.
        path4 = i4_acceptance_path(sales_pass, pot_pass)
        # متنِ دلیل از تک‌مرجعِ `ind4_reason_text` — همان قراردادِ کارت/bulk.
        if not annual or mcap <= 0:
            i4_reason = ind4_reason_text(available=False)
        else:
            i4_reason = ind4_reason_text(
                margin_present=pot_margin is not None,
                sales_pass=sales_pass, potential_pass=pot_pass)

    passes = {"1_growth": axis1,
              "2_eps_trend": (None if not e or e.get("data_gap") else bool(e["pass"])),
              # رأی ۱۶ برایِ شاخص ۳ هم: حاشیه‌ای که هرگز ساخته نشد «سنجیده نشده»
              # است نه «رد». شاخص ۴ درِ همین دیکشنری از قبل سه‌حالۀ None داشت؛
              # این ستون bool بود ⇒ `bulk_scan` (None) با `/api/fts` (False) دو
              # شکلِ متفاوت برایِ یکِ نمادِ بدونِ سطرِ سود ناخالص می‌داد.
              # N/Aِ طبقه (مالی/هلدینگ/صندوق) هم None است تا همین پاریتی حفظ شود.
              "3_gross_margin": (None if gm is None or gm.get("na")
                                 else bool(gm["pass"])),
              "4_sales_to_mcap": passes_s2m,
              "5_industry": bool(sec["pass"])}
    # شمارش فقط پاس‌های *واقعی* است؛ None (معاف/بی‌داده) امتیاز نمی‌گیرد.
    score = sum(1 for v in passes.values() if v)
    # جزوه ص ۶ در مقایسهٔ دزاگرس/هجرت: «سه آیتم اول مهم‌تر هستند پس اولویت ما
    # دزاگرس است» — یعنی سه‌از‌پنج می‌تواند بر چهار‌از‌پنج ببرد. پس شمارشِ تختِ
    # پنج‌تایی تنها معیارِ داوری نیست: F1-F3 بلاک‌اند و F4/F5 فقط مرتب‌سازیِ دوم.
    # مقیاسِ ۰-۵ دست‌نخورده می‌ماند (مصرف‌کننده‌های ftsScoreOf به آن وابسته‌اند)؛
    # چیزی که عوض می‌شود معنای رتبه‌بندی و «STRONG» است.
    primary = sum(1 for k in ("1_growth", "2_eps_trend", "3_gross_margin") if passes[k])

    reasons = []
    if bool(cfg.get("reject_insurance", True)) and is_insurance_sector(sector):
        reasons.append("صنعت بیمه — حذف خودکار")
    if is_suspended(conn, symbol, int(cfg.get("suspended_max_stale_sessions", 3) or 3),
                    _sessions=_sessions):
        reasons.append("نماد تعلیق — حذف خودکار")
    if sec["verdict"] == "mandatory" and sec["exclusion_active"]:
        reasons.append("قیمت‌گذاری دستوری — حذف خودکار")

    # ---- v9.7: ماده ۱۴۱ (زیان انباشته) + آستانهٔ نقدشوندگی ----
    # هر دو نقشه کل‌بازاری‌اند؛ scan_all/bulk_scan یک‌بار می‌سازند و پاس می‌دهند
    # (m141_hit / avg_trade_val) تا به N+1 نیفتد. این شاخه‌های None فقط برای
    # فراخوانی تکیِ /api/fts/{symbol} است.
    key = SI.key(symbol)
    if m141_hit is None:
        m141_hit = bool(m141_map(conn).get(key, False))
    if cfg.get("filter_m141") and m141_hit:
        reasons.append("ماده ۱۴۱ — زیان انباشته")
    min_liq = _f(cfg.get("min_trade_val", 0.0)) or 0.0
    if avg_trade_val is None:
        avg_trade_val = avg_trade_value_hmt(conn).get(key)
    if min_liq > 0 and avg_trade_val is not None and avg_trade_val < min_liq:
        reasons.append("نقدشوندگی کمتر از آستانه")

    return {
        "symbol": symbol, "sector": sector, "pricing_mode": sec["verdict"],
        "market_cap_rials": mcap, "score": score, "passes": passes,
        "primary_score": primary,
        "excluded": bool(reasons), "exclusion_reasons": reasons,
        # رأی ۱۵: تک‌مرجعِ «صندوق است؟» برایِ این مسیر هم ثبت می‌شود. بی‌این،
        # مصرف‌کننده‌هایی که scan_symbol می‌خوانند (ماتریسِ تایید سه‌گانه) صندوق را
        # «مردود» داوری می‌کردند در حالی که bulk_scan همان نماد را applicable=False
        # می‌داد — دو جواب برایِ یک نماد، درست همان چیزی که رأی ممنوعش کرد.
        "applicable": not fund_class_match(sector, cname),
        "i1_reason": axis1_reason,
        "i1_na": bool(axis1 is None),
        # همان پرچمِ شکافِ ۱بِ ردیفِ bulk — فقط وقتی محور قابلِ‌اعمال است
        # معنا دارد؛ برایِ طبقهٔ غیرقابلِ‌اعمال صریحاً False است تا سه مسیر
        # یک مقدار بدهند (Task 10B2a1).
        "i1b_data_gap": (bool(volume.get("data_gap"))
                         if volume.get("applicable") else False),
        # برچسبِ شاهدِ EPS (Task 5) — صنعتِ بیمه `eps_trend_3y=None` می‌دهد،
        # ولی سطحِ جدول/کارت برایِ آن هم «دادهٔ ناکافی» می‌نویسد؛ این‌جا همان
        # مقدارِ قرارداد را نگه می‌داریم تا سه مسیر یک برچسب بدهند.
        "eps_evidence_label": ((e or {}).get("evidence_label")
                               or eps_evidence_label("insufficient")),
        # برچسبِ نمایشیِ طبقهٔ حاشیه (Task 6) — همان مقداری که
        # `detail.gross_margin` و ردیفِ bulk_scan می‌دهند؛ None یعنی N/A.
        "margin_tier": (gm or {}).get("margin_tier"),
        # «چرا حکمِ ۳ خالی است»: N/Aِ طبقه (مالی/هلدینگ/صندوق) یا شکافِ داده؛
        # جدول با همین پرچم N/A خاکستری می‌نشاند (Task 6 fix).
        "i3_na": i3_na,
        # دلیلِ ۳ — همان متنِ کارت/ردیفِ bulk (Task 10B2a1/10B2a2).
        "i3_reason": i3_reason,
        # نامِ مسیرِ پذیرش و برچسبِ سالانه‌سازی (Task 7) — همان قراردادِ ردیفِ
        # bulk_scan؛ معاف/بی‌داده بی‌مسیر و بی‌برچسب است. `mcap <= 0` هم مثلِ
        # کارت «بی‌داده» است: نه دوره‌ای برایِ سالانه‌سازی، نه برچسبی.
        "i4_acceptance_path": path4,
        # کلیدهایِ N/A/دسترس‌پذیری و حاشیهٔ مصرفیِ پتانسیل (Task 10B2a2) —
        # همان قراردادِ کارت و ردیفِ bulk تا پاریتی سه‌مسیره سنجیده شود.
        "i4_available": i4_available,
        "i4_exempt": bool(is_holding),
        "i4_na": bool(is_holding),
        "i4_reason": i4_reason,
        "margin_used_pct": pot_margin if i4_available else None,
        "margin_basis": pot_margin_basis if i4_available else None,
        "annualize_months": (0 if (is_holding or mcap <= 0)
                             else int((annual or {}).get("months_used") or 0)),
        "annualize_label": ("" if (is_holding or mcap <= 0)
                            else annualize_label((annual or {}).get("months_used"))),
        "m141": bool(m141_hit),
        "avg_trade_val_hmt": None if avg_trade_val is None else round(avg_trade_val, 3),
        "detail": {"growth": g, "eps_trend": e, "gross_margin": gm,
                   "sales_to_mcap": s2m, "profit_potential": pot, "sector": sec},
        "verdict": ("EXCLUDED" if reasons else
                    "STRONG" if score >= 4 and primary == 3 else
                    "WATCH" if score >= 3 else "REJECT"),
    }


def scan_all(conn: sqlite3.Connection, limit: int = 0, cfg: dict = None) -> list[dict]:
    """غربالگری ۵ شاخصی کل نمادهای دارای صورت مالی → حداکثر `watchlist_max` سهم برتر.

    نمادهای تعلیق و — وقتی `reject_insurance` روشن است (پیش‌فرض) — صنعت بیمه پیش از رتبه‌بندی حذف میشوند (بخش ۲ دستور کار).
    """
    cfg = cfg or {}
    # مخرجِ کسرِ «سهم از کل بازار» — عددِ رسمیِ TSETMC، نه جمعِ ردیف‌های تابلو.
    # جمعِ دستی یک شرکت را چند بار می‌شمرد (فولاد و فولاد3 یک ISIN) و نشست‌های
    # قدیمی را هم نگه می‌داشت: ۷۰۳۸۶ همت در برابر ۲۴۸۵۷ همتِ واقعی.
    total_mcap = mstat_engine.market_total_rials(conn)[0]
    # ارزش بازار از همان ستونِ رسمیِ `mcap_bulk_expr` (همان کارت و bulk_scan) —
    # «قیمتِ آخرین × سهامِ ثبتی» نبود، چون آن عدد هیچ‌وقت در تابلو خوانده نمیشود
    # و شاخص ۴ دو مبنایِ مختلف می‌ساخت.
    rows = conn.execute("""
        SELECT f.symbol, """ + mcap_bulk_expr(conn) + """ AS mcap,
               COALESCE(i.sector_name, sg.sector_name, 'سایر') AS sector,
               m.d_even AS d_even
        FROM (SELECT DISTINCT symbol FROM financial_statements) f
        LEFT JOIN instruments i ON i.l_val18 = f.symbol
        LEFT JOIN market_watch m ON m.ins_code = i.ins_code
        LEFT JOIN (SELECT DISTINCT symbol,
               CASE WHEN company_name LIKE '%صندوق%' THEN 'صندوق سرمایه گذاری'
                    WHEN company_name LIKE '%بیمه%' OR company_name LIKE '%بيمه%' THEN 'بيمه'
                    WHEN company_name LIKE '%بانك%' OR company_name LIKE '%بانک%' THEN 'بانك'
                    ELSE 'سایر' END AS sector_name
             FROM codal_notices WHERE symbol NOT IN (SELECT l_val18 FROM instruments)) sg
             ON sg.symbol = f.symbol
    """).fetchall()
    sessions = market_sessions(conn)
    stale_cut = (sessions[min(int(cfg.get("suspended_max_stale_sessions", 3) or 3),
                              len(sessions) - 1)] if len(sessions) > 1 else 0)
    # v9.7: نقشه‌های ماده ۱۴۱ و نقدشوندگی یک‌بار ساخته میشوند (نه به ازای نماد)
    m141 = m141_map(conn)
    liq = avg_trade_value_hmt(conn)
    no_sales = no_sales_symbols(conn)

    # v9.7.3: یک نماد = یک ردیف. حلقهٔ قبلاً روی «DISTINCT symbol» خام می‌چرخید
    # و برای هر گروهِ دودیک (۲۱ گروه در financial_statements) دو بار امتیاز
    # می‌داد — آن هم یکی با join به تابلو و یکی بدون join (sector='سایر'، mcap=0)
    # که جای واچ‌لیستِ سهمِ اصلی را می‌گرفت.
    best, order = {}, []
    for r in rows:
        key = SI.key(r[0])
        if not key:
            continue
        if key not in best:
            order.append(key)
            best[key] = r
            continue
        cur = best[key]
        score_r = (1 if _f(r[1]) > 0 else 0, 1 if r[3] else 0, 1 if r[2] != "سایر" else 0)
        score_c = (1 if _f(cur[1]) > 0 else 0, 1 if cur[3] else 0, 1 if cur[2] != "سایر" else 0)
        if score_r > score_c:
            best[key] = r

    out = []
    for key in order:
        sym, mcap, sector, d_even = best[key]
        if bool(cfg.get("reject_insurance", True)) and is_insurance_sector(sector):
            continue
        if d_even and stale_cut and int(d_even) < int(stale_cut):
            continue
        out.append(scan_symbol(conn, sym, mcap or 0.0, total_mcap, sector,
                               cfg=cfg, _sessions=sessions,
                               m141_hit=bool(m141.get(key, False)),
                               avg_trade_val=liq.get(key),
                               _no_sales=no_sales))
    # رتبهٔ اول = سه محورِ بلاکر (جزوه ص ۶)، رتبهٔ دوم = جمعِ پنج‌تایی، بعد ارزش
    # بازار و در نهایت نماد — تا ترتیبِ پایدار بماند.
    out.sort(key=lambda r: (-r.get("primary_score", 0), -r["score"],
                            -_f(r.get("market_cap_rials")), r["symbol"]))
    # فیلتر نهایی: ردیفهای excluded (تعلیق/بیمه/دستوری) جای واچ‌لیست را نمیگیرند
    clean = [r for r in out if not r["excluded"]]
    cap = int(cfg.get("watchlist_max", 50) or 50)
    return clean[:cap] if limit <= 0 else clean[:max(limit, cap)]


# ============================================================ اسکن دسته‌ای
def has_market_cap_col(conn: sqlite3.Connection, table: str) -> bool:
    """آیا جدولِ `table` ستونِ `market_cap` دارد؟

    بانک‌هایِ پیش ازِ ارتقا این ستون را ندارند؛ مسیرِ کارت با `MCAP_ERR_NO_COL`
    صادقانه می‌گوید «دسترس نیست». موتورِ دسته‌ای هم باید همین را بگوید، نه اینکه
    کوئری‌اش وسطِ اسکنِ کل بازار با OperationalError بجدد.

    عمداً بی‌کش: کلیدِ کشِ پیشین `(id(conn), table)` بود و آدرسِ آزادشدهٔ یکِ
    اتصالِ بسته ممکن است به اتصالِ تازه داده شود — آن‌جا «ستون نیست» از بانکِ
    کهنه به بانکِ سالم نشت می‌کرد. خودِ PRAGMA ۳۶µs هزینه دارد.
    """
    try:
        return any((r[1] or "").lower() == "market_cap"
                   for r in conn.execute('PRAGMA table_info("%s")' % table))
    except sqlite3.Error:
        return False


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """آیا جدولِ `table` ستونِ `column` را دارد؟ (بی‌کش — دلیلش درِ
    `has_market_cap_col`)"""
    try:
        return any((r[1] or "").lower() == column.lower()
                   for r in conn.execute('PRAGMA table_info("%s")' % table))
    except sqlite3.Error:
        return False


def mcap_dead_band_sql(board: str = "m") -> str:
    """عبارتِ SQL «ردیفِ تابلو بانِ معاملۀ مرده دارد؟» (آری = بی‌اعتبار)

    تابلو برایِ هر سهم `allowed_min`/`allowed_max` (مجازِ قیمتِ همان نشست) را
    خودش منتشر می‌کند. اگر هر دو **پر باشند** و `max <= min`، آن instrument در آن
    نشست هیچِ بازۀ مجازِ معاملۀ ندارد؛ «قیمت × سهام»ِ چنین ردیفی ارزشِ بازار
    نیست. نشار: `p_closing = 1.0` با `allowed_min = allowed_max = 1.0` و صفردیدۀ
    معامله — همان ۴٬۰۰۰٬۰۰۰ ریالی که نسبتِ ۱۴۱۳٫۷۵× می‌ساخت.

    بانِ پر نشده (۰/NULL — فیکچرها و DB‌هایِ ستون‌خالی) عمداً رد **نمی‌کند**:
    نبودِ شاهد ≠ شاهدِ بی‌اعتباری. نه آستانه است نه clampِ عددی؛ فقط دو فیلدِ
    خودِ منبع با هم مقایسه می‌شوند. تک‌تعریفِ کارت (`get_tsetmc_market_cap_info`)
    و موتور (`mcap_bulk_expr`).
    """
    return ("(COALESCE(%s.allowed_min, 0) > 0 AND COALESCE(%s.allowed_max, 0) > 0"
            " AND %s.allowed_max <= %s.allowed_min)" % (board, board, board, board))


def mcap_bulk_expr(conn: sqlite3.Connection, alias: str = "i",
                   board: str = "m") -> str:
    """عبارتِ SQL ارزش بازار — همان سلسله‌مراتبِ `get_tsetmc_market_cap_info`.

    ۱) `market_watch.market_cap` رسمی  ۲) آخرین `daily_prices.market_cap` معتبر.
    ستونِ نبود ⇒ `NULL` — یعنی «ارزش بازار در دسترس نیست» (شاخص ۴ data_gap)،
    هرگز جعلِ «قیمتِ آخرین × سهامِ ثبتی».
    """
    if not has_market_cap_col(conn, "market_watch"):
        return "NULL"
    expr = "CASE WHEN %s.market_cap > 0 THEN %s.market_cap END" % (board, board)
    if has_market_cap_col(conn, "daily_prices"):
        expr = ("COALESCE(%s, (SELECT d.market_cap FROM daily_prices d"
                " WHERE d.ins_code = %s.ins_code AND d.market_cap > 0"
                " ORDER BY d.d_even DESC LIMIT 1))" % (expr, alias))
    # دروازهٔ بانِ مرده (تک‌تعریف درِ `mcap_dead_band_sql`) — اگر جدولِ تابلو این
    # ستون‌ها را نداشت (نسخۀ کهنه/فیکچرِ ناقص) دروازه حذف می‌شود و عدد می‌ماند.
    if has_column(conn, "market_watch", "allowed_max") and \
            has_column(conn, "market_watch", "allowed_min"):
        expr = "CASE WHEN NOT %s THEN %s END" % (mcap_dead_band_sql(board), expr)
    return expr


def bulk_scan(conn: sqlite3.Connection, cfg: dict = None) -> list[dict]:
    """غربالگری ۵ شاخصی کل بازار با چند کوئری تک‌گذر (برای /api/screener).

    همان تعریفِ هر شاخصِ scan_symbol — فقط بدون N+1 کوئری. خروجی ستون‌های
    جدول بنیادی کدال است: پنج محور + score (۰..۵) + excluded.
    """
    cfg = cfg or {}
    # قاعدهٔ ۱الف/۱ب مشترک با کارت در `api.fundamental` است (axis1_state و
    # ind1b_from_parts). import محلی است تا جهتِ وابستگی (api → engine) هنگامِ
    # بارگذاریِ ماژول نشکند؛ engine فقط در زمانِ فراخوانی از کارت می‌خواند.
    from api.fundamental import (axis1_state, ind1b_from_parts,
                                 margin_gap_detail,
                                 physical_volume_lookup, physical_volume_map,
                                 v10_thresholds,
                                 MONTHLY_BAD_YTD_REASON,
                                 MONTHLY_NO_PRIOR_REASON,
                                 MONTHLY_NO_SERIES_REASON)
    th1b = v10_thresholds(cfg)
    # کمیتِ فیزیکی یک‌بار برایِ کلِ بازار — در حلقه فقط lookup، نه کوئریِ N+1.
    phys_vol, vol_col, vol_col_prev = physical_volume_map(conn)
    g_min = _th(cfg, "growth_min")
    g_target = _th(cfg, "v10_monetary_growth_min")
    eps_years = max(1, int(_th(cfg, "eps_years")))
    m_min = _th(cfg, "margin_min")
    m_opt = _th(cfg, "margin_optimal")
    s2m_min = _th(cfg, "sales_to_mcap_min")
    pot_min = _th(cfg, "profit_potential_min")

    # ۱) صورت‌های مالی سالانه — مرجع + سری EPS
    # v9.7.3: کلید = SI.key(symbol). با کلیدِ خام، یک شرکت با دو نوشتار
    # (داریک/داريك) دو ردیف اسکنر می‌ساخت و نوشتارِ بی‌داده امتیاز ۰ می‌گرفت.
    annual, disp_of = {}, {}
    for sym, pe, pm, title, rev, gp, op, np_, eps, cn, un, tn in conn.execute(
            "SELECT symbol, " + FS_COLS + ", tracing_no FROM financial_statements "
            "WHERE period_months>=12 OR period_months IS NULL "
            "ORDER BY symbol, %s" % CP.order_expr()):
        key = SI.key(sym)
        if not key:
            continue
        # همان قاعدۀ کارت، درِ قیف: «سالانہ بودن» را `effective_months` می‌گوید
        # (ستونِ تهی از عنوان، و دورۀ گذارِ شش‌ماهۀ با ستونِ ۱۲ رد). بی‌این یکی
        # از دو مسیر پنجره‌هایِ متفاوتی می‌دید و گاردِ پاریتی قرمز می‌شد.
        months, months_src = CP.effective_months(pe, pm, title)
        if months is None or months < 12:
            continue
        annual.setdefault(key, []).append(
            {"period_end": pe, "period_months": months, "months_source": months_src,
             "tracing_no": tn,
             "fiscal_year": CP.fiscal_year(pe), "title": title or "",
             "company_name": str(cn or ""),
             "conflicts": row_conflicts(pe, title, months),
             "audited": _is_audited(title), "consolidated": _is_consolidated(title),
             "other_entity": bool(title_entity_suffix(title)),
             "unit_norm": un, "unit_valid": CU.is_valid(un),
             "revenue": _fn(rev), "gross_profit": _fn(gp), "net_profit": _fn(np_),
             "basic_eps": _fn(eps)})
        if key not in disp_of:
            disp_of[key] = sym
        # نمادی که نوشتارش با norm_fa یکی است (فارسی) را به‌عنوان نمایش انتخاب کن
        if sym == key:
            disp_of[key] = sym

    # SQL بالا «ORDER BY symbol, period_end DESC» است؛ حالا که چند نماد زیر یک
    # کلید نرمال ادغام می‌شوند، لیستِ هر کلید «گروه‌گروه بر اساس املا» می‌آید،
    # نه newest-first. با collation باینری «ي» عربی قبل از «ی» فارسی می‌افتد،
    # پس bulk صورت‌مالیِ قدیمیِ املای عربی را برمی‌داشت
    # (مثلاً وسینا: ردیف ۱۴۰۳ با gross_profit = NULL) در حالی که
    # annual_statements در مسیر scan سراسری بر اساس period_end DESC مرتب
    # می‌کند و ردیف ۱۴۰۴ را می‌دید → شاخص ۳ بین دو مسیر واگرا می‌شد.
    # این مرتب‌سازی همان ترتیب را برای هر دو مسیر می‌سازد.
    for key in annual:
        annual[key].sort(key=lambda r: CP.desc_sort_key(r["period_end"]), reverse=True)

    def _ref(sym, need=None):
        """مرجعِ شاخص‌های ۳ و ۴ درِ bulk — همان `pick_reference` که مسیرِ
        تک‌نمادی (`reference_annual`) می‌زند.

        پیش از این این‌جا سلسلۀ لایهٔ دومِ خودش را داشت (`_solo_annual` با
        «≥۲ ردیفِ همگن» و افزودنِ تلفیقی درِ انتها) و یکِ قاعدهٔ جدا برایِ
        `_ref`؛ نتیجه دو جواب برایِ یکِ نماد بود (وسینا/مبين/فولاد). تنها چیزی
        که لازم بود این است که ردیفِ هر سالِ مالی با `statement_rank` انتخاب
        شود — که حالا درِ هر دو مسیر همین کار می‌کند.
        """
        return pick_reference(annual.get(sym) or [], need=need)



    # ۲) گزارش‌های ماهانه — رشد تجمیعی + فروش Annualized
    # کلید نرمال + مرتب‌سازی/حذف تکرارِ (سال,ماه) پس از ادغام دو نوشتار.
    ms = {}
    for sym, y, mo, mrev, ytd, ytdp, ms_title in conn.execute(
            "SELECT symbol, year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, title "
            "FROM monthly_sales WHERE ytd_revenue IS NOT NULL AND ytd_revenue>0 "
            "ORDER BY symbol, year DESC, month DESC"):
        key = SI.key(sym)
        if not key or title_entity_suffix(ms_title or ""):
            # همان بندِ ۲.۱: سریِ ماهانهٔ یکِ شرکتِ فرعی، فروشِ این نماد نیست
            # (کوئریِ تک‌نمادیِ `monthly_series` هم همین را می‌گذارد).
            continue
        ms.setdefault(key, []).append((int(y or 0), int(mo or 0), _f(mrev), _f(ytd), _f(ytdp)))
    for key in ms:
        ms[key].sort(key=lambda r: (-r[0], -r[1]))
        ms[key] = _dedupe_ym(ms[key])
    # همهٔ نمادهایِ ماهانه — حتی آن‌هایی که هیچ ردیفِ YTDِ مثبت ندارند (مثلِ
    # غنوش با تجمیعیِ منفیِ یک ماه). گزارشِ ماهانه داشتن یعنی «شرکتِ فقط-ماهانه»؛
    # نبودِ سریِ قابلِ‌استفاده باید ردیفِ شکافِ داده بسازد، نه حذفِ شرکت از جهان.
    ms_all = set()
    for (sym,) in conn.execute("SELECT DISTINCT symbol FROM monthly_sales"):
        k = norm_fa(sym) if sym else ""
        if k:
            ms_all.add(k)

    # ۳) تابلو + صنعت + ارزش بازار
    # ارزش بازار از **همان** منبعِ کارت است: `market_watch.market_cap` رسمی و در
    # نبودش آخرین `daily_prices.market_cap` معتبر (هرگز «قیمتِ آخرین × سهامِ
    # ثبتی» — آن ضربهٔ پشتیبان در `api/fundamental.py:2153` صریحاً حذف شد، ولی
    # bulk هنوز همان را می‌ساخت؛ یعنی شاخص ۴ دو مبنایِ مختلف داشت).
    mcap_of, sector_of, dev_of, board_of = {}, {}, {}, {}
    for sym, mcap, sector, d_even in conn.execute("""
        SELECT i.l_val18,
               %s,
               COALESCE(i.sector_name, ''), m.d_even
        FROM instruments i LEFT JOIN market_watch m ON m.ins_code = i.ins_code"""
            % mcap_bulk_expr(conn)):
        key = SI.key(sym)
        mcap_of[key] = _f(mcap)
        sector_of[key] = sector or ""
        if d_even:
            dev_of[key] = int(d_even)
        # نماد نمایش = تیکرِ واقعیِ تابلو (instruments.l_val18) تا با
        # price_history هم‌خوان بماند؛ نوشتار فارسی اولویت دارد.
        if key and (key not in board_of or sym == key):
            board_of[key] = sym
    # همان مبنای scan_symbol/scan_all: کلِ ارزشِ بازار از عددِ رسمیِ TSETMC.
    total_mcap = mstat_engine.market_total_rials(conn)[0]
    sessions = market_sessions(conn)
    stale_cut = (sessions[min(int(cfg.get("suspended_max_stale_sessions", 3) or 3),
                              len(sessions) - 1)] if len(sessions) > 1 else 0)
    # v9.7: ماده ۱۴۱ + نقدشوندگی — دو نقشهٔ تک‌کوئری، بیرون حلقه
    m141 = m141_map(conn)
    liq = avg_trade_value_hmt(conn)
    no_sales = no_sales_symbols(conn)
    # نامِ شرکت برای طبقهٔ صندوق (رأی ۱۵) — تک‌کوئری، بیرون حلقه
    cname_of = company_name_map(conn)
    do_m141 = bool(cfg.get("filter_m141"))
    min_liq = _f(cfg.get("min_trade_val", 0.0)) or 0.0
    _hold_na = bool(cfg.get("holdings_sales_na", True))
    # نقشهٔ تک‌گذرِ رشدِ صورتِ مالی (Task 2). یک کوئری برایِ کلِ بازار؛ در حلقه
    # فقط خوانده می‌شود — هیچ فراخوانیِ per-symbol این‌جا نیست.
    fs_growth = fs_growth_map(conn, th={"monetary_growth_min": g_min})

    out = []
    # جهانِ اسکن = شرکت‌های دارایِ صورتِ مالیِ سالانه + شرکت‌هایِ فقط-ماهانه‌ای که
    # در تابلو ابزار دارند (`board_of`). ۷۳ شرکتِ واقعی فقط گزارشِ ماهانه
    # می‌فرستند و پیش از این از جدول غایب بودند. نام‌هایِ ماهانهٔ بی‌ابزار (۵۷
    # فانتوم) عمداً وارد نمی‌شوند؛ صندوق/غیرشرکت هم در همان فیلترِ پایین حذف
    # می‌شود. این تغییر فقط دامنهٔ حلقه است — هیچ فرمول/آستانه‌ای عوض نمی‌شود.
    universe = set(annual) | {k for k in ms_all if k in board_of}
    for key in sorted(universe):
        sym = key                                   # کلید = نوشتار نرمال (فارسی)
        sym_out = board_of.get(key) or disp_of.get(key) or key
        sector = sector_of.get(key, "")
        cname = cname_of.get(key, "")
        identity = classify_identity(key, sector, cname,
                                     key in board_of or bool(sector))
        # جهانِ مالک: صندوق‌ها (و نمادهای بی‌ابزار) در جدول نمی‌آیند. کارتِ
        # جزئیات همچنان برای صندوق «FTS ندارد» می‌دهد؛ این‌جا فقط ردیف حذف
        # می‌شود. بیمه شرکت است و می‌ماند (وتوی‌اش در risk_gates).
        if identity["kind"] in ("non_company", "fund"):
            continue
        prof = company_profile(sector, cname)
        mcap = mcap_of.get(key, 0.0)
        ref = _ref(key)

        # ۱) رشد فروش تجمیعی ÷ همان دورۀ سالِ قبل — از تک‌قاعدۀ `ytd_denominator`
        # (ستونِ «مقایسه با دورۀ مشابه» ← ردیفِ سال−۱/همان ماه). این‌جا نسخهٔ سوم
        # همان سلسلۀ‌مراتب نوشته شده بود که تنها ستونِ رسمی را می‌دید و در نبودش
        # `next(...)` دستی؛ نتیجه: نمادی که مخرجش در ردیفِ ماهانۀ سالِ قبل بود،
        # در اسکرین data_gap و در کارت «رشد» می‌گرفت.
        recs = ms.get(key) or []
        i1_basis = None
        growth = None
        monetary = {"pass": False, "monetary_pct": None, "data_gap": True,
                    "reason": "", "year": None, "months": 0}
        if prof["kind"] in FS_GROWTH_KINDS and not recs:
            # خدماتی/مالی/هلدینگِ بی‌گزارشِ ماهانه: رشد از نقشهٔ صورتِ مالی.
            fg = fs_growth.get(key) or {}
            growth = fg.get("monetary_pct")
            i1_basis = fg.get("basis")
            monetary = {"pass": bool(fg.get("pass")), "monetary_pct": growth,
                        "data_gap": bool(fg.get("data_gap")) or growth is None,
                        "reason": fg.get("reason") or "",
                        "year": fg.get("year"), "months": fg.get("months") or 0}
        else:
            d = ytd_denominator(recs)
            if d and d["ytd_prev"]:
                growth = (d["ytd_now"] / d["ytd_prev"] - 1.0) * 100.0
                monetary = {"pass": growth >= g_min, "monetary_pct": growth,
                            "data_gap": False, "reason": "",
                            "year": d["year"], "months": d["month"]}
            else:
                # دلیلِ همان شکاف را می‌گوییم که کارت می‌گوید — نه رشتهٔ خالی
                # که `axis1_state` را به متنِ عمومی می‌انداخت (Task 4).
                # «هیچ گزارش ماهانه‌ای نیست» فقط وقتی درست است که واقعاً هیچ
                # ردیفی در `monthly_sales` نباشد. ردیفی که تجمیعیِ صفر/منفی
                # دارد (`ms_all` ولی `recs` خالی) گزارش دارد، پس دلیلش
                # «تجمیعی نامعتبر» است، نه «هیچ گزارش» (Task 10A M1).
                monetary["reason"] = (MONTHLY_NO_PRIOR_REASON if d
                                      else (MONTHLY_BAD_YTD_REASON
                                            if (recs or key in ms_all)
                                            else MONTHLY_NO_SERIES_REASON))
        # ۱ب: حکمِ کمیت/تناژ فقط برایِ تولیدی‌ها (همان `company_profile` که کارت
        # می‌خواند). مالی/خدماتی/هلدینگ N/A است، نه False — `axis1_state` همین
        # را می‌فهمد. شکافِ داده در ۱الف هم به None می‌رسد، نه «رد».
        if prof["volume_applicable"]:
            qty_now, qty_prev = physical_volume_lookup(
                phys_vol.get(key) or {}, monetary.get("year"),
                monetary.get("months") or 0, vol_col_prev)
            volume = ind1b_from_parts(monetary, recs, qty_now, qty_prev, vol_col,
                                      th=th1b, profile=prof)
        else:
            volume = {"applicable": False, "pass": False,
                      "basis": "not_applicable", "reason": ""}
        i1, i1_reason = axis1_state(monetary, volume)

        # ۲) روند EPS — همان نردبانی که کارت می‌خواند: `eps_assessment`.
        # پیش از این bulk سلسلۀ‌مراتبِ دومِ خودش را داشت («۲ ردیفِ همگن یا بیشتر»
        # و لایۀ تلفیقی برایِ نمایش) و تنها درِ شاخۀ تنزل به eps_trend_3y سر می‌زد؛
        # نتیجه دو جوابِ متفاوت برایِ یکِ نماد درِ /api/screener و /api/fundamental
        # بود (مبين، شسپا، فولاد). بهایِ این وحدت یک کوئریِ ایندکسی به‌ازایِ نماد
        # است (ix_fs_symbol) — عددش درِ گزارشِ این دور سنجیده شده.
        _eps = eps_assessment(conn, key, years=eps_years, sector=sector)
        eps_series = _eps.get("eps_series")
        data_gap2 = bool(_eps.get("data_gap"))
        # همان پیش‌گیتِ کارت: برایِ صنعتِ بیمه شاخص ۲ رأی نمی‌دهد
        # (`eps_trend_3y` بی‌این، کارت را از اسکرینر جدا می‌کرد — سنجشِ
        # dev/fts_engine_paths_parity_v1076.py: ۳۰ نماد واگرا). «رأی نمی‌دهد»
        # یعنی None + i2_na، همان قراردادِ آزمونِ جزوه
        # (`i2_na: true, i2_pass: null`) — نه رد، نه قبول.
        _ins2 = is_insurance_sector(sector)
        # رأیِ ۱۶ رویِ I2 هم: سابقۀ ناکافی «سنجیده نشده» است، نه «رد»؛
        # `i2_na` (ص ۴ جزوه — مبنایِ تلفیقی) درِ قیف NOT_APPLICABLE می‌شود.
        i2 = None if (data_gap2 or _ins2) else bool(_eps.get("pass"))
        eps_avail = int(_eps.get("years_available") or 0)

        # ۳) حاشیه سود ناخالص = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰
        # دو مقدار، هرکدام سرِ جای خودش: `margin_raw` برایِ **داوری** (همان کاری
        # که `gross_margin()` می‌کند — `pass` از عددِ خام ساخته می‌شود و فقط
        # `margin_pct` گرد می‌خورد) و `margin` گردِ یک‌رقمی برایِ **نمایش،
        # پتانسیل سود و فیلتر صنعت** (چیزی که کارتpublish می‌کند). اگر داوری هم
        # با عددِ گرد شده می‌شد، حاشیۀ ۱۹٫۹۶٪ «≥ ۲۰» می‌شد — واگراییِ واقعیِ
        # این دور درِ لخزر/كمينا/شرنگي/سجام، که بندِ تازهٔ گاردِ پاریتی گرفتش.
        # گیتِ طبقه (سند فاز ۱، بند ۴٫۴): مالی/بانکی/هلدینگ/صندوق N/A است،
        # حتی اگر سود ناخالص در صورت مالی ثبت شده باشد — «حاشیهٔ عدددارِ
        # بی‌مفهوم» ساخته نمی‌شود و حکم/برچسب هم نمی‌گیرد.
        class_na = margin_class_na(prof, min_margin=m_min, optimal=m_opt)
        margin_raw = margin = None
        if class_na is None:
            # همان `margin_reference`ِ کارت، رویِ همان ردیف‌هایِ ازپیش‌خوانده: اگر
            # مرجعِ اصلی سودِ ناخالص نداشت، سالِ دارایِ عدد جانشین می‌شود و `basis`
            # آن را اعلام می‌کند. بی‌این، کارت و قیف دو عددِ متفاوت می‌دادند.
            mref = ref
            if not row_carries(ref, MARGIN_NEED):
                mref = pick_reference(annual.get(key) or [], need=MARGIN_NEED) or ref
            if mref and _f(mref["revenue"]) > 0 and mref["gross_profit"] is not None:
                margin_raw = (mref["gross_profit"] / _f(mref["revenue"])) * 100.0
                margin = round(margin_raw, 1)
        # رأی ۱۶ روی شاخص ۳: حاشیه‌ای که هرگز ساخته نشد سنجیده نشده، نه رد —
        # همان قاعده‌ای که برای شاخص ۴ و در api/screener جاری است. (حاشیۀ صفرِ
        # واقعی عدد دارد و می‌ماند: `margin is not None and margin < m_min`.)
        i3 = (None if margin_raw is None else margin_raw >= m_min)
        # دلیلِ خالی‌بودنِ حکمِ ۳ (Task 10B2a1): N/Aِ طبقه از خودِ گیت؛ شکافِ
        # داده از همان متنِ کارت (`margin_gap_detail`) — نه رشتهٔ خالی که جدول
        # مجبور شود «شکاف داده»یِ عمومی نشان دهد.
        if class_na is not None:
            i3_reason = class_na.get("reason") or ""
        elif margin_raw is None:
            i3_reason = margin_gap_detail(ref).get("reason") or ""
        else:
            i3_reason = ""

        # ۴) فروش سالانۀ Annualized ÷ ارزش بازار (+ پتانسیل سود ناخالص)
        # تک‌قاعده: `annualize_rows` — همان چیزی که کارت و `scan_symbol` می‌خوانند،
        # با این فرق که ردیف‌های ماهانه از پیش خوانده شده‌اند. پیش از این این‌جا
        # نسخۀ بی‌`op_basis` نوشته شده بود: طبقۀ مالی/خدماتی/هلدینگ در کارت
        # «درآمد صورت مالی سالانه» می‌گرفت و در اسکرینر «YTD×۱۲÷م» — ۵۰ نماد
        # واگرا در سنجشِ این دور (docs/fts-notes/FUND_LIVE_AUDIT.md).
        fs_rev = fs_amount_mrl(ref, "revenue") if ref else None
        fs_unit_known = bool(ref) and CU.is_valid(ref.get("unit_norm"))
        prof = company_profile(sector, cname_of.get(key, ""))
        core = annualize_rows(recs or [], fs_rev,
                              op_basis=(prof.get("kind") in _OP_BASIS_KINDS)
                              and _f(fs_rev) > 0 and fs_unit_known,
                              fs_unit_known=fs_unit_known)
        annual_sales = _f(core.get("annual_sales_mrl"))
        months_used = int(core.get("months_used") or 0)
        # شاخص ۴ و پتانسیل سود از **خودِ توابعِ مشترک** می‌آیند (نسخۀ سومِ فرمول
        # این‌جا حذف شد): `sales_to_marketcap` تصمیمِ معافیت را از `ind4_exempt`
        # می‌گیرد و `gross_profit_potential` همان (فروش × حاشیه) ÷ ارزش است.
        # نامِ متغیر عمداً `ann_core` است: `annual` نقشۀ ردیف‌هایِ سالانۀ صورتِ
        # مالی است و `_ref` درِ همان حلقه بسته (closure) به آن بسته شده —
        # بازمسما‌گذاریِ `annual` کلِ اسکن را از ردیفِ دوم خراب می‌کند.
        ann_core = dict(core)
        if ann_core:
            ann_core["annual_sales_bt"] = round(normalize_mrl_to_btom(annual_sales), 1)
        s2m_d = sales_to_marketcap(conn, key, mcap, min_ratio=s2m_min, annual=ann_core,
                                   sector=sector, _no_sales=no_sales,
                                   holdings_na=_hold_na) if ann_core else None
        # تصمیمِ معافیت از همان تک‌مرجع (`ind4_exempt`) — نه از بازخوانیِ خروجیِ
        # `sales_to_marketcap`؛ آن تابع وقتی فروشِ سالانه نیست None می‌دهد و
        # معافیتِ نمادهای بی‌درآمد (سيلور/پايدار/پويا) بی‌صدا می‌افتاد.
        is_holding = ind4_exempt(conn, key, sector, holdings_na=_hold_na,
                                 _precomputed=no_sales)
        # حاشیهٔ **جایگزینِ** پتانسیل (Task 10B2a2): کارت برایِ حاشیهٔ N/A با
        # نسبتِ سود خالص در (۰,۱۰۰] پتانسیل می‌سازد؛ این‌جا همان قاعده با
        # متغیرِ جدا (`pot_margin`) تکرار می‌شود و **هرگز** به `i3` یا
        # `sector_filter` نمی‌رود. `margin` (حاشیهٔ ناخالص) دست‌نخورده می‌ماند.
        pot_margin, pot_margin_basis = i4_potential_margin(margin, ref)
        pot_d = None
        if ann_core and pot_margin is not None and mcap > 0 and not is_holding:
            pot_d = gross_profit_potential(conn, key, mcap, min_pct=pot_min,
                                           gm={"margin_pct": pot_margin},
                                           annual=ann_core)
        s2m = (s2m_d or {}).get("sales_to_mcap")
        pot = (pot_d or {}).get("potential_pct")

        path4 = None
        sales_pass = pot_pass = False
        if is_holding:
            # رأی ۱۶: معاف = «نظر نمی‌دهد» (None)، نه امتیازِ رایگان — همان چیزی
            # که کارتِ جزئیات می‌داد؛ موتور بالاخره به آن تراز شد.
            i4 = None
            i4_reason = ind4_reason_text(exempt=True)
        else:
            # حکمِ پاس از خودِ همان دو تابعِ مشترک خوانده می‌شود (مقایسۀ عددِ خام
            # با آستانه). پیش‌ازین این‌جا با مقدارِ **گردشدۀ منتشرشده** مقایسه
            # می‌شد: نسبتِ ۰٫۳۲۹۹ به ۰٫۳۳ گرد می‌شد و «≥ ⅓» می‌شد — سه نماد
            # (سجام/نمرينو/بپيوند) درِ اسکرینر پاس و درِ /api/fts مردود بودند.
            sales_pass = bool((s2m_d or {}).get("pass"))
            pot_pass = bool((pot_d or {}).get("pass"))
            # از این دور همان `ind4_vote`ِ کارت این‌جا هم می‌نشیند: بی‌شاهدِ فروشِ
            # سالانه (مثلاً ردیفِ مرجعِ بی‌واحد در برابرِ نبودِ گزارشِ ماهانه) رأی
            # نمی‌دهد، نه اینکه «رد» بخورد.
            i4 = ind4_vote(ann_core, s2m_d, pot_d, False, mcap=mcap)
            # نامِ مسیرِ پذیرفته‌شده (Task 7): اول فروش÷ارزش بازار، بعد
            # پتانسیلِ ۴۰٪. خودِ آستانه‌ها و OR دست‌نخورده‌اند.
            path4 = i4_acceptance_path(sales_pass, pot_pass)
            # متنِ دلیل همان قراردادِ `ind4_valuation` (Task 10B2a1): معاف/
            # دادهٔ ناکافی/نبودِ حاشیه/مسیرِ پذیرش یا بی‌مسیر — یک متن، دو مسیر.
            if not ann_core or mcap <= 0:
                i4_reason = ind4_reason_text(available=False)
            else:
                i4_reason = ind4_reason_text(
                    margin_present=pot_margin is not None,
                    sales_pass=sales_pass, potential_pass=pot_pass)

        # چهار حالتِ N/A/دسترس‌پذیریِ شاخص ۴ — همان چیزی که کارت در
        # `indicators["4"]` می‌گوید (`available`/`exempt`/`na`) و پاریتیِ
        # ۱۰B2a2 رویِ هر ۷۸۵ ردیف می‌سنجد. حاشیهٔ مصرفی هم فقط برایِ پتانسیل
        # است؛ `gross_margin` بالا حاشیهٔ شاخص ۳ می‌ماند.
        i4_available = bool(ann_core) and mcap > 0 and not is_holding

        # ۵) فیلتر صنعت (قیمت‌گذاری آزاد/بورس کالا در برابر دستوری)
        sec = sector_filter(sector, cfg=cfg, market_cap_rials=mcap,
                            total_market_cap_rials=total_mcap,
                            gpm=margin, sales_growth=growth)
        i5 = bool(sec["pass"])

        reasons = []
        if bool(cfg.get("reject_insurance", True)) and is_insurance_sector(sector):
            reasons.append("صنعت بیمه")
        if stale_cut and key in dev_of and dev_of[key] < int(stale_cut):
            reasons.append("نماد تعلیق")
        if sec["verdict"] == "mandatory" and sec["exclusion_active"]:
            reasons.append("قیمت‌گذاری دستوری")
        # v9.7 — ماده ۱۴۱ و نقدشوندگی
        hit141 = bool(m141.get(key, False))
        liq_hmt = liq.get(key)
        if do_m141 and hit141:
            reasons.append("ماده ۱۴۱ — زیان انباشته")
        if min_liq > 0 and liq_hmt is not None and liq_hmt < min_liq:
            reasons.append("نقدشوندگی کمتر از آستانه")

        out.append({
            "symbol": sym_out, "symbol_norm": key, "sector_name": sector,
            "pricing_mode": sec["verdict"],
            "rev_growth": None if growth is None else round(growth, 1),
            # مبنایِ شاخص ۱: None = YTD ماهانه؛ "fs_interim"/"fs_annual" = صورتِ مالی.
            "i1_basis": i1_basis,
            "eps_series": eps_series,
            "eps_last": (eps_series[-1] if eps_series else None),
            "eps_data_gap": bool(data_gap2),
            # دو پرچمِ شفافیت برایِ جدول: «چه‌قدر از سابقه تلفیقی است» و
            # «محور سنجیده شد یا نظر داده نشد». بدونِ این‌ها ردیفِ `na` رویِ
            # جدول همان ✗ «رد» را می‌گیرد در حالی که جزوه (ص ۴) تلفیقی را
            # مبنایِ داوری نمی‌داند — نه مردود و نه مطلوب.
            "eps_consolidated": bool(_eps.get("consolidated_used")),
            "i2_na": bool(_eps.get("na")) or _ins2,
            # برچسبِ شاهدِ EPS (Task 5) — همان مقدارِ `indicators["2"]`ِ کارت؛
            # جدول آن را زیرِ سلولِ EPS می‌نویسد و سری را هم نگه می‌دارد.
            "eps_evidence_label": (_eps.get("evidence_label")
                                   or eps_evidence_label("insufficient")),
            "eps_years_available": min(eps_avail, eps_years),
            "eps_years_required": eps_years,
            "gross_margin": None if margin is None else round(margin, 1),
            # برچسبِ نمایشیِ طبقهٔ حاشیه (Task 6) — از عددِ خامِ حکم (نه
            # گردشدۀ نمایش)؛ None برایِ نمادی که حاشیه‌اش ساخته نشده (N/A).
            "margin_tier": margin_tier(margin_raw),
            # N/Aِ طبقه (مالی/بانکی/هلدینگ/صندوق): علت و باند از خودِ موتور
            # می‌آید؛ شکافِ داده نیست و ستونِ حکم هم شمارش نمی‌شود. (شکافِ داده
            # هم `i3_pass=None` است؛ تفکیکش در `i3_reason` می‌ماند.)
            "i3_na": bool(class_na),
            "i3_band": (class_na or {}).get("band"),
            "i3_reason": i3_reason,
            "sales_to_mcap": None if s2m is None else round(s2m, 2),
            "profit_potential_pct": None if pot is None else round(pot, 1),
            # حاشیه و مبنایِ مصرفیِ **پتانسیل** (نه شاخص ۳): برایِ طبقهٔ مالیِ
            # غیربانکی/تولیدیِ بی‌سود ناخالص، «حاشیهٔ سود خالص (جایگزینِ مالی)»
            # است و با برچسبِ `net_margin_proxy` از حاشیهٔ ناخالص جدا می‌شود.
            # در حالتِ معاف/بی‌داده هیچ‌کدام معنا ندارند (کارت هم نمی‌دهد).
            "margin_used_pct": pot_margin if i4_available else None,
            "margin_basis": pot_margin_basis if i4_available else None,
            # `available/exempt/na`ِ شاخص ۴ — همان کلیدهایِ کارت تا سه مسیر
            # (bulk، کارت، scan) با یک قرارداد مقایسه شوند (پاریتیِ ۱۰B2a2).
            "i4_available": i4_available,
            "i4_exempt": bool(is_holding),
            "i4_na": bool(is_holding),
            "annual_sales_bt": round(normalize_mrl_to_btom(annual_sales), 1),
            # معاف یا بی‌ارزش‌بازار (mcap<=0) سالانه‌سازی ندارد — همان ۰/""ی
            # که کارت در شاخهٔ insufficient-data می‌دهد؛ ردیف نباید بگوید
            # «۱۲ ماه» و هم‌زمان برچسبش خالی باشد.
            "annualize_months": 0 if (is_holding or mcap <= 0) else months_used,
            # برچسبِ سالانه‌سازی و نامِ مسیرِ پذیرش (Task 7) — همان چیزی که
            # کارت می‌دهد؛ برایِ معاف/بی‌داده رشتهٔ خالی و None (نه متنِ گمراه).
            "annualize_label": ("" if (is_holding or mcap <= 0)
                                else annualize_label(months_used)),
            "i4_acceptance_path": path4,
            # دلیلِ حکمِ ۴ — همان متنِ کارت (`ind4_valuation`): معاف/دادهٔ
            # ناکافی/نبودِ حاشیه/مسیرِ پذیرش/بی‌مسیر (Task 10B2a1).
            "i4_reason": i4_reason,
            # «مقیاسِ این عدد از کجا آمد»: واحدِ خودِ ردیفِ مرجع، و پرچمِ
            # راستی‌آزمایی‌نشدن وقتی آن واحد اعلام نشده (`unit_unverified`). بی‌این
            # دو ستون، عددِ شاخص ۴ بی‌شاهدِ مقیاس هم «سنجیده‌شده» به‌نظر می‌رسید.
            "fs_unit": CU.label((ref or {}).get("unit_norm")),
            "unit_unverified": bool(core.get("unit_unverified")),
            "mcap": mcap, "score": int(sum(1 for _p in (i1, i2, i3, i4, i5) if _p)),
            # همان قاعدهٔ ص ۶ جزوه در مسیرِ bulk (پاریتیِ scan_symbol ⇄ bulk_scan)
            "primary_score": int(sum(1 for _p in (i1, i2, i3) if _p)),
            "i1_pass": i1, "i2_pass": i2, "i3_pass": i3, "i4_pass": i4, "i5_pass": i5,
            # تفکیکِ ۱الف/۱ب و دلیلِ حکم — همان چیزی که کارت در
            # `indicators["1"]` می‌دهد؛ بی‌این، جدول مجبور بود «ب» را از
            # نام/صنعت حدس بزند و دلیلِ وتو را نداشت.
            "i1a_pass": bool(monetary.get("pass")),
            "i1b_pass": bool(volume.get("pass")),
            "i1b_applicable": bool(volume.get("applicable")),
            # شکافِ دادهٔ ۱ب (Task 10B2a1): `pass=False` تنها یعنی «رد» نیست؛
            # اگر دادهٔ کمیت/تورم نبود، جدول باید N/A خاکستری بنشاند نه ✗ سرخ.
            "i1b_data_gap": bool(volume.get("data_gap")),
            "i1b_basis": volume.get("basis"),
            "i1_reason": i1_reason,
            # «سنجیده نشد» یک حالتِ سوم است، نه «رد». جدول با همین پرچم N/A
            # خاکستری می‌نشاند و هرگز ✗ سرخ برایِ ردیفِ بی‌داده نمی‌کشد.
            "i1_na": bool(i1 is None),
            "excluded": bool(reasons), "exclusion_reasons": " · ".join(reasons),
            "identity_kind": identity["kind"],
            "identity_reason": identity["reason"],
            # رأی ۱۵: صندوق داوری FTS ندارد (نه رد) — و در جهانِ مالک اصلاً به
            # این جدول نمی‌آید. امتیازِ عددی دست‌نخورده می‌ماند چون sortِ پایین
            # و ستونِ «امتیاز» عدد می‌خواهند.
            "applicable": identity["applicable"],
            "m141": hit141,
            "avg_trade_val_hmt": None if liq_hmt is None else round(liq_hmt, 3),
            # optimal هم از عددِ خام است، نه گردشدۀ نمایش: ۲۹٫۹۶٪ که «۳۰٫۰»
            # دیده می‌شود هنوز ایده‌آل نیست (همان قاعدهٔ band/tier).
            "margin_optimal": margin_raw is not None and margin_raw >= m_opt,
            "growth_excellent": growth is not None and growth >= g_target,
        })
    out.sort(key=lambda r: (r["excluded"], -r.get("primary_score", 0), -r["score"],
                            -r["mcap"], r["symbol"]))
    return out


def load_fts_config(path: str = "fts_thresholds.json") -> dict:
    """بارگذاری آستانه‌های FTS از فایل کانفیگ با اولویت‌بندی مسیر."""
    import json
    import os
    candidates = [
        os.path.join(os.getcwd(), path),
        os.path.join(os.path.dirname(__file__), path),
        os.path.join(os.path.dirname(__file__), "..", path),
    ]
    for c in candidates:
        if os.path.isfile(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


class FtsEngine:
    """کلاس تطبیقی برای دسترسی شی‌گرا به توابع موتور FTS."""
    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_fts_config()

    def evaluate_symbol(self, symbol_data: dict) -> dict:
        """ارزیابی تک‌نماد بر اساس ۵ شاخص FTS v2.1."""
        sym = symbol_data.get("symbol", "")
        sector = symbol_data.get("sector", "")
        mcap = _f(symbol_data.get("market_cap", 0.0))
        sales_curr = _f(symbol_data.get("sales_current_cumulative", 0.0))
        sales_prev = _f(symbol_data.get("sales_previous_cumulative", 0.0))
        rev = _f(symbol_data.get("operating_revenue", 0.0))
        gp = _f(symbol_data.get("gross_profit", 0.0))
        eps_hist = symbol_data.get("eps_history_3y", [])
        months = int(symbol_data.get("months_reported", 3) or 3)

        # F-01
        growth = ((sales_curr / sales_prev - 1.0) * 100.0) if sales_prev > 0 else None
        f01_pass = growth is not None and growth >= 40.0

        # F-02
        f02_pass = (len(eps_hist) >= 3 and eps_hist[0] < eps_hist[1] < eps_hist[2] and eps_hist[2] > 0)

        # F-03
        gpm = (gp / rev * 100.0) if rev > 0 else 0.0
        f03_pass = gpm >= 20.0

        # F-04
        # توجه: این مسیرِ کلاسِ FTSEngine است و فقط دیکشنریِ نماد را می‌بیند؛
        # conn ندارد، پس شاهدِ صورتِ مالی (no_sales/has_operating_sales) اینجا
        # سنجیده نمی‌شود — ولی سیبِ معاف و گیتِ holdings_sales_na از همان
        # تک‌مرجعِ مشترکِ ind4_exempt می‌آیند تا فهرستِ دومِ دست‌ساز نسازیم.
        is_holding = ind4_exempt(None, sym, sector, holdings_na=bool(
            self.config.get("holdings_sales_na", True)))
        ann_sales = sales_curr * (12.0 / months) if (months > 0 and not is_holding) else 0.0
        s2m = (ann_sales / mcap) if (mcap > 0 and not is_holding) else None
        pot = (ann_sales * (gpm / 100.0) / mcap * 100.0) if (mcap > 0 and not is_holding) else None
        if is_holding:
            f04_pass = True
        else:
            f04_pass = bool((s2m is not None and s2m >= 1.0) or (pot is not None and pot >= 40.0))

        # F-05
        sec_res = sector_filter(sector, cfg=self.config, gpm=gpm, sales_growth=growth)
        f05_pass = bool(sec_res.get("pass"))

        passes = {
            "F01_sales_growth": {"passed": f01_pass, "growth_pct": round(growth, 1) if growth else None},
            "F02_eps_trend": {"passed": f02_pass, "eps_values": eps_hist},
            "F03_gross_margin": {"passed": f03_pass, "gpm_pct": round(gpm, 1)},
            "F04_sales_to_cap": {"passed": f04_pass, "sales_to_cap_ratio": round(s2m, 2) if s2m else None, "is_exempt": is_holding},
            "F05_industry_gate": {"passed": f05_pass, "pricing_type": sec_res.get("label", "")}
        }
        passed_count = sum(1 for p in passes.values() if p["passed"])
        verdict = "SUPER_FUNDAMENTAL" if passed_count == 5 else "PASSED" if passed_count >= 4 else "WATCHLIST" if passed_count == 3 else "REJECTED"

        return {
            "symbol": sym,
            "name": symbol_data.get("name", sym),
            "sector": sector,
            "overall_passed": passed_count == 5,
            "passed_count": passed_count,
            "fts_verdict": verdict,
            "total_score": round(passed_count * 20.0, 1),
            "indicators": passes
        }



