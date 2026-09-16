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
# چرا `WHERE norm_fa(symbol)=?` راه‌حل نیست (روی همین market.db اندازه گرفته شد):
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
del _c


def symbol_aliases(symbol, limit: int = 27) -> tuple:
    """همهٔ نوشتارهای خامِ یک نماد که norm_fa یکسانی تولید می‌کنند.

    بدون کوئری و بدون تابع سمت SQL: جای‌گذاریِ هر کاراکترِ «چند-نویشتاری»
    با تمام نمونه‌های همان دسته (ی/ي/ى و ک/ک). ورودی خالی → تاپل خالی.

    ترتیب خروجی **قطعی** است (اول خودِ ورودی، سپس جایگشت‌ها به ترتیب
    ساخت) تا خروجی اسکنرها و لاگ‌ها بین اجراها عوض نشود؛ به همین دلیل از
    set() استفاده نمی‌شود (هشِ رشته‌ها در پایتون تصادفی است).

    سقف limit از آنجاست که نمادی با ۳ کاراکتر «ی‌کلاس» ۲۷ جایگشت می‌دهد؛
    ۴ تا ۸۱ می‌شود که بی‌معناست. در عمل نمادهای TSETMC ۰ تا ۲ بار این
    کاراکترها را دارند، پس سقف عملاً فعال نمی‌شود.
    """
    s = "" if symbol is None else str(symbol)
    if not s:
        return ()
    base = s.replace(_ZWNJ, "")
    out, seen = [], set()
    for cand in (s, base):
        if cand and cand not in seen:
            seen.add(cand)
            out.append(cand)
    pos = [i for i, ch in enumerate(base) if ch in _CHAR_CLASS]
    variants = [base]
    for i in pos:
        if len(variants) >= max(int(limit), 1):
            break
        nxt = []
        for v in variants:
            for al in _CHAR_CLASS[base[i]]:
                if v[i] == al:
                    if v not in nxt:
                        nxt.append(v)
                else:
                    w = v[:i] + al + v[i + 1:]
                    if w not in nxt:
                        nxt.append(w)
        variants = nxt
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return tuple(out)


def sym_in(col: str, symbol, alias_limit: int = 27):
    """(شرح SQL, پارامترها) برای تطبیق «هر نوشتارِ این نماد» با ایندکس.

    مثال:  pred, params = sym_in("symbol", "داریک")
           f"SELECT ... WHERE {pred}"  →  "symbol IN (?,?,?)"
    اگر ناماد تهی باشد، شرطی برمی‌گردد که هیچ‌وقت درست نمی‌شود (به‌جای
    خطای SQL) — یعنی رفتار «بدون داده» حفظ می‌شود.
    """
    al = symbol_aliases(symbol, limit=alias_limit)
    if not al:
        return "1=0", []
    return "%s IN (%s)" % (col, ",".join("?" * len(al))), list(al)


def register_sql(conn):
    """norm_fa را به‌عنوان تابع SQLite ثبت می‌کند (برای فیلترهای سمت SQL).

    توجه: این تابع در مسیرِ «کوئری تک‌نمادی» استفاده **نمی‌شود** — همان‌طور
    که بالاتر اندازه گرفته شد، ۵۷۴ برابر کند از ایندکس است. جای درستش
    build-side است: کوئری‌های کل‌بازاری که از قبل جدول را کامل می‌خوانند
    (m141_map، ساخت نقشه‌ها) و هر فیلتر SQL که در آینده روی نوشتار لازم باشد.
    """
    try:
        conn.create_function("norm_fa", 1, norm_fa, deterministic=True)
    except Exception:
        pass                       # اتصال read-only / نسخهٔ بی‌deterministic
    return conn



# ================================================== شاخص ۵: دیکشنری قیمت‌گذاری
# همهٔ توکن‌ها به نوشتار نرمال (ی/ک فارسی) ذخیره میشوند و با norm_fa(sector) سنجیده‌اند.
# فهرست با ۵۵ sector_name واقعیِ جدول instruments راستی‌آزمایی شده است.

# قیمت‌گذاری دستوری / کنترل‌شده (حذف از سبد FTS):
#   خودرو و ساخت قطعات · مواد و محصولات دارویی · محصولات غذایی و آشامیدنی · قند و شکر
#   لاستیک و پلاستیک · عرضه برق، گاز، بخار و آب گرم (نیروگاه) · بیمه و صندوق بازنشستگی
#   شوینده‌ها (تگ مستقل در TSETMC ندارد؛ برای پوشش نام‌های شرکتی نگه داشته شده)
# سند v2.1: «دارو» و «غذای عمومی» دیگر یک‌جا رد نمی‌شوند؛
#   دارو فقط با حاشیهٔ ناخالص > ۵۰٪ مجاز است (توسط گیت GPM در F-03 سنجیده می‌شود)،
#   و غذا تنها در صورت کنترل شدید — که «قند و شکر» نمایندهٔ آن است.
MANDATORY_PRICING_TOKENS = (
    "خودرو", "نقلیه موتور", "قند و شکر", "لاستیک",
    "شوینده", "نیروگاه", "عرضه برق", "تولید برق", "توزیع برق", "بیمه",
)

# قیمت‌گذاری آزاد / بورس کالا (اولویت مثبت):
FREE_PRICING_TOKENS = (
    "سیمان", "آهک", "شیمیایی", "پتروشیمی", "فلزات", "کانه", "کانی", "کاشی", "سرامیک", "شیشه",
    "فرآورده‌های نفتی", "نفت", "زغال سنگ", "معادن", "محصولات فلزی",
    "مس", "فولاد", "سرب و روی",
)

# صنعت بیمه — حذف قطعی از خروجی (بخش ۲ دستور کار).
INSURANCE_TOKENS = ("بیمه", "بازنشستگی")


def pricing_mode(sector: str) -> str:
    """طبقه‌بندی صنعت: 'mandatory' | 'free' | 'neutral' (همیشه نرمال‌سازی‌شده)."""
    s = norm_fa(sector)
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
    return "تلفیقی" in norm_fa(title)


def _is_amendment(title: str) -> bool:
    return "اصلاحیه" in norm_fa(title)


FS_COLS = ("period_end, period_months, title, revenue, gross_profit, "
           "operating_profit, net_profit, basic_eps")


def annual_statements(conn: sqlite3.Connection, symbol: str, require_audit: bool = True,
                      exclude_consolidated: bool = True, limit: int = 12) -> list[dict]:
    """صورت‌های مالی سالانه (۱۲ ماهه) — جدیدترین در ابتدا، یکی به ازای هر سال مالی.

    پیش‌فرض: فقط «حسابرسی‌شده» و فقط «شرکت اصلی» (غیرتلفیقی) — شرط شاخص ۲.
    """
    pred, params = sym_in("symbol", symbol)
    # پنجرهٔ خواند عمداً بزرگ است و غربال در Python انجام می‌شود:
    # `limit*4` (یعنی ۴ ردیف برای limit=1) باعث می‌شد صورت‌مالیِ ۱۲ماههٔ
    # حسابرسی‌شده‌ای که در ترتیب period_end عقب‌تر از ۴ ردیف اول می‌افتد هرگز
    # دیده نشود؛ آن‌وقت reference_annual به شاخهٔ تنزل (تلفیقی/حسابرسی‌نشده)
    # می‌غلتید و حاشیهٔ سود ناخالصِ همان نماد با bulk_scan فرق می‌کرد.
    # سقف تازه از ایندکس ix_fs_symbol خوانده می‌شود، پس هزینه تقریباً صفر است.
    window = max(int(limit), 1) * 12 + 48
    rows = conn.execute(
        f"SELECT {FS_COLS} FROM financial_statements "
        f"WHERE {pred} AND period_months>=12 ORDER BY period_end DESC LIMIT ?",
        (*params, window)).fetchall()
    out, seen_years = [], set()
    for pe, pm, title, rev, gp, op, np_, eps in rows:
        t = title or ""
        if exclude_consolidated and _is_consolidated(t):
            continue
        if require_audit and not _is_audited(t):
            continue
        yr = str(pe or "")[:4]
        if not yr or yr in seen_years:
            continue
        seen_years.add(yr)
        out.append({"period_end": pe, "fiscal_year": yr, "period_months": pm, "title": t,
                    "audited": _is_audited(t), "consolidated": _is_consolidated(t),
                    "amended": _is_amendment(t), "revenue": _fn(rev), "gross_profit": _fn(gp),
                    "operating_profit": _fn(op), "net_profit": _fn(np_), "basic_eps": _fn(eps)})
        if len(out) >= limit:
            break
    return out


def reference_annual(conn: sqlite3.Connection, symbol: str) -> Optional[dict]:
    """آخرین صورت مالی سالانهٔ «حسابرسی‌شدهٔ غیرتلفیقی»؛ در نبودش سلسله‌مراتب تنزل:
    سالانهٔ غیرتلفیقی → سالانهٔ اخیر. (منبع قطعی شاخص‌های ۳ و ۴)"""
    for req_aud in (True, False):
        got = annual_statements(conn, symbol, require_audit=req_aud,
                                exclude_consolidated=True, limit=1)
        if got:
            return got[0]
    got = annual_statements(conn, symbol, require_audit=False,
                            exclude_consolidated=False, limit=1)
    return got[0] if got else None


# ============================================================ تبدیل واحد
def normalize_mrl_to_btom(value_million_rials) -> float:
    """میلیون ریال → میلیارد تومان (حذف ۴ رقم سمت راست — قاعدهٔ جزوه)."""
    return _f(value_million_rials) / 10_000.0


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



MRL_TO_RIAL = 1e6                        # جداول کدال همگی «میلیون ریال» هستند


# =============================================== شاخص ۱: رشد فروش تجمیعی (YoY)
def revenue_growth_yoy(conn: sqlite3.Connection, symbol: str, min_growth: float = 40.0,
                       inflation_min: float = 58.0, sector: str = "") -> Optional[dict]:
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
    pred, params = sym_in("symbol", symbol)
    rows = conn.execute(
        "SELECT year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, period_end "
        "FROM monthly_sales WHERE " + pred + " AND ytd_revenue IS NOT NULL "
        "AND ytd_revenue>0 "
        "ORDER BY year DESC, month DESC LIMIT 30", params).fetchall()
    rows = _dedupe_ym(rows)
    if not rows:
        return None
    cur = rows[0]
    year, month, ytd_now = int(cur[0] or 0), int(cur[1] or 0), _f(cur[3])
    if ytd_now <= 0 or not month:
        return None

    # مخرج ۱) ستون رسمی «مقایسه با دورهٔ مشابه سال قبل» اگر پر باشد (فعلاً ۰٪ پوشش)
    ytd_prev, basis = _f(cur[4]), "ستون مقایسهٔ دورهٔ مشابه سال قبل در همان گزارش"
    if ytd_prev <= 0:
        # مخرج ۲) جستجوی ردیف (سال−۱، همان ماه) — تجمیعیِ همان دوره
        prev = next((r for r in rows[1:]
                     if int(r[0] or 0) == year - 1 and int(r[1] or 0) == month), None)
        if prev is None or _f(prev[3]) <= 0:
            return {"growth_pct": None, "pass": False, "threshold": min_growth,
                    "ytd_now_bt": round(normalize_mrl_to_btom(ytd_now), 1),
                    "ytd_prev_bt": None, "period": f"{month:02d}/{year}",
                    "denominator_basis": "ناموجود — ردیف تجمیعی همان دورهٔ سال قبل نیست",
                    "revenue_basis": _revenue_basis(sector), "data_gap": True}
        ytd_prev = _f(prev[3])
        basis = f"تجمیعی {month:02d}/{year - 1} از گزارش فعالیت ماهانه (نه ماه قبل)"

    growth = (ytd_now / ytd_prev - 1.0) * 100.0
    return {
        "growth_pct": round(growth, 1),
        "ytd_now_bt": round(normalize_mrl_to_btom(ytd_now), 1),
        "ytd_prev_bt": round(normalize_mrl_to_btom(ytd_prev), 1),
        "period": f"{month:02d}/{year}",
        "denominator_basis": basis,
        "revenue_basis": _revenue_basis(sector),
        "pass": growth >= min_growth,
        "threshold": min_growth,
        "beats_inflation": growth >= inflation_min,
        "inflation_min": inflation_min,
        "data_gap": False,
    }


def _revenue_basis(sector: str) -> str:
    """برچسب مبنای درآمد — بانک/بیمه «درآمد» است نه «فروش» (توضیحی، نه محاسباتی)."""
    s = norm_fa(sector)
    if any(k in s for k in ("بانک", "اعتباري", "اعتباری", "بیمه", "لیزینگ", "اوراق تامین")):
        return "بانکی/مالی — جمع تسهیلات اعطایی + سپرده‌گذاری + سرمایه‌گذاری + اوراق + کارمزد"
    if any(k in s for k in ("صندوق", "سرمایه گذاري")):
        return "صندوق — درآمد پرتفوی"
    return "تولیدی/خدماتی — جمع فروش داخلی + صادراتی"


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
                return "توقف رشد سود در %s (بدون افزایش نسبت به سال قبل)" % _ylab(i + 1)
            pct = round((vals[i + 1] / vals[i] - 1.0) * 100.0, 1) if vals[i] else None
            tail = (" (%.1f٪ افت)" % pct) if pct is not None else ""
            return "افت سود در %s نسبت به سال قبل%s" % (_ylab(i + 1), tail)
    return "روند اکیداً صعودی نیست"

# ============================================ شاخص ۲: روند ۳ سالهٔ EPS (اصلی)
def eps_trend_3y(conn: sqlite3.Connection, symbol: str, years: int = 3,
                 sector: str = "") -> Optional[dict]:
    """EPS سال‌های مالی متوالی — باید اکیداً صعودی و همگی مثبت باشد.

    ممیزی v8 (رفع باگ‌های v7.3):
      ۱. فقط صورت مالی **۱۲ ماههٔ حسابرسی‌شده** (v7.3 حسابرسی را نمی‌سنجید)
      ۲. فقط **شرکت اصلی / غیرتلفیقی** با norm_fa — در v7.3 «تلفيقي» با ی عربی
         جست میشد و ۱۳۳۹ عنوان «تلفیقی» با ی فارسی هیچ‌گاه حذف نمیشدند
      ۳. سال‌های مالی باید **متوالی** باشند (فاصلهٔ سال = ۱) — v7.3 سه رکورد آخر
         را بدون توجه به فاصله برمی‌داشت
      ۴. حذف بیمه روی **sector_name** (در v7.3 روی نماد تست میشد و هرگز اجرا نمیشد)
    """
    if is_insurance_sector(sector):
        return None
    need = max(int(years or 3), 2)
    stmts = annual_statements(conn, symbol, require_audit=True,
                              exclude_consolidated=True, limit=need + 2)
    usable = [s for s in stmts if s["basic_eps"] is not None]
    if len(usable) < need:
        return {"eps_series": None, "years_required": need,
                "years_available": len(usable), "pass": False, "data_gap": True,
                "reason": f"کمتر از {need} صورت مالی ۱۲ماههٔ حسابرسی‌شدهٔ غیرتلفیقی",
                "source": "کدال — صورت‌های مالی سالانه (حسابرسی شده، شرکت اصلی)"}

    window = usable[:need]                              # جدید → قدیمی
    gap_ok = all(int(window[i]["fiscal_year"]) - int(window[i + 1]["fiscal_year"]) == 1
                 for i in range(len(window) - 1))
    series = [w["basic_eps"] for w in reversed(window)]  # قدیمی → جدید
    rising = all(series[i] < series[i + 1] for i in range(len(series) - 1))
    positive = all(v > 0 for v in series)
    if not gap_ok:
        reason = "سال‌های مالی متوالی نیست (" + " ← ".join(
            w["fiscal_year"] for w in reversed(window)) + ")"
    elif not (rising and positive):
        reason = eps_trend_reason(series, [w["fiscal_year"] for w in reversed(window)])
    else:
        reason = ""
    return {
        "eps_series": [round(v, 2) for v in series],
        # v9.8.1 — «ثبت سود خالص و EPS برای ۳ سال اخیر»: سود خالصِ همان پنجرهٔ
        # EPS هم برمی‌گردد (هر دو جزو شاخص ۲ خواسته شده؛ UI مقدار اضافه را نادیده میگیرد)
        "net_profit_series": [None if w["net_profit"] is None
                              else round(_fn(w["net_profit"]), 1)
                              for w in reversed(window)],
        "fiscal_years": [w["fiscal_year"] for w in reversed(window)],
        "period_ends": [str(w["period_end"])[:10] for w in reversed(window)],
        "years_required": need, "years_available": len(usable),
        "consecutive_years": gap_ok, "strictly_rising": rising, "all_profitable": positive,
        "consolidated_used": False, "audited_only": True,
        "pass": bool(rising and positive and gap_ok),
        "data_gap": False,
        "reason": reason,
        "source": "کدال — صورت سود و زیان، ۱۲ماههٔ حسابرسی‌شدهٔ شرکت اصلی (غیرتلفیقی)",
    }


# ==================================== شاخص ۳: حاشیه سود ناخالص (Gross Margin)
def gross_margin(conn: sqlite3.Connection, symbol: str, min_margin: float = 20.0,
                 optimal: float = 30.0, ref: Optional[dict] = None) -> Optional[dict]:
    """حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰.

    ممیزی v8: فرمول v7.3 درست بود؛ **منبع** غلط بود — `ORDER BY period_end DESC
    LIMIT 1` آخرین گزارش را می‌داد که معمولاً ۳ماههٔ حسابرسی‌نشده است. اکنون
    آخرین صورت مالی **سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی** مبنا قرار میگیرد.
    تأیید: `net_profit` و `operating_profit` در این شاخص هیچ نقشی ندارند.
    """
    row = ref or reference_annual(conn, symbol)
    if not row:
        return None
    rev, gp = _f(row.get("revenue")), row.get("gross_profit")
    if rev <= 0 or gp is None:
        return None                      # بانکی/مالی/صندوق — بهای تمام‌شده ندارد
    gp = _f(gp)
    margin = (gp / rev) * 100.0
    return {
        "margin_pct": round(margin, 1),
        "gross_profit_bt": round(normalize_mrl_to_btom(gp), 1),
        "revenue_bt": round(normalize_mrl_to_btom(rev), 1),
        "period_end": str(row.get("period_end"))[:10],
        "basis": "سالانهٔ حسابرسی‌شدهٔ شرکت اصلی" if row.get("audited") and not row.get("consolidated")
                 else "تنزل منبع: " + str(row.get("title") or "")[:60],
        "pass": margin >= min_margin,
        "optimal": margin >= optimal,
        "threshold": min_margin,
        "optimal_threshold": optimal,
        "formula": "(سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰",
    }


# ==================== شاخص ۴: فروش سالانهٔ Annualized به ارزش بازار + پتانسیل سود
def annualized_sales(conn: sqlite3.Connection, symbol: str,
                     ref: Optional[dict] = None) -> Optional[dict]:
    """فروش سالانه از گزارش‌های فعالیت ماهانه (Annualize) — شرط صریح جزوه.

    روش (v9.8.1 — اولویتِ فرمول دستور کار «فروش ۳ ماهه × ۴»):
      ۱. سه گزارش ماهانهٔ متوالیِ آخرِ همان سال مالی → فروش فصلی؛
         Annualized = فروش ۳ ماهه × ۴
      ۲. بدون سه ماه متوالی → تجمیعی YTD × ۱۲ ÷ ماه (روش قبلی؛ پوششِ بانک
         و نمادی که ماهش پرش دارد)
      ۳. اگر ۱۲ ماه کامل باشد، خودِ YTD همان فروش سالانه است
      ۴. راستی‌آزمایی با فروش صورت مالی سالانه: اگر Annualized بیش از ۴× یا
         کمتر از ۰.۲۵× فروش سالانهٔ مرجع باشد، واحد/ساختار گزارش مشکوک است →
         مبنا به فروش سالانهٔ کدال برمی‌گردد و `reconciled=False` ثبت میشود.
    """
    pred, params = sym_in("symbol", symbol)
    rows = conn.execute(
        "SELECT year, month, monthly_revenue, ytd_revenue FROM monthly_sales "
        "WHERE " + pred + " AND ytd_revenue IS NOT NULL AND ytd_revenue>0 "
        "ORDER BY year DESC, month DESC", params).fetchall()
    rows = _dedupe_ym(rows)
    ref_row = ref if ref is not None else reference_annual(conn, symbol)
    fs_rev = _f(ref_row.get("revenue")) if ref_row else 0.0

    annual, months, basis = 0.0, 0, ""
    if rows:
        year = int(rows[0][0] or 0)
        cur_year = [r for r in rows if int(r[0] or 0) == year]
        cur_year.sort(key=lambda r: -int(r[1] or 0))     # جدیدترین ماه اول
        # ۱) فرمول دستور کار: فروش ۳ ماههٔ متوالی × ۴ (پلِ دی/بهمن مرز سال مالی
        #    را میشکند → همان‌جا به YTD برمی‌گردیم)
        if len(cur_year) >= 3:
            m0, m1, m2 = (int(cur_year[i][1] or 0) for i in range(3))
            tri = [_f(cur_year[i][2]) for i in range(3)]     # monthly_revenue
            if m0 - m1 == 1 and m1 - m2 == 1 and all(v > 0 for v in tri):
                annual = sum(tri) * 4.0
                months = 3
                basis = f"فروش ۳ ماهه ({m2:02d}–{m0:02d}/{year}) × ۴"
        # ۲) تنزل به YTD × ۱۲ ÷ ماه — مبنای عمومی (بانک/سال ناقص/ماه پرش‌دار)
        if annual <= 0:
            months = max(int(r[1] or 0) for r in cur_year)
            ytd = _f(cur_year[0][3])
            if ytd > 0 and months >= 1:
                annual = ytd if months >= 12 else ytd * 12.0 / months
                basis = (f"تجمیعی {months:02d}/{year} × ۱۲÷{months}" if months < 12
                         else f"تجمیعی ۱۲ ماه سال مالی {year}")
    if annual <= 0 and fs_rev > 0:
        annual, months, basis = fs_rev, 12, "مراجعه به فروش صورت مالی سالانه (بدون گزارش ماهانه)"
    if annual <= 0:
        return None

    reconciled = True
    # گیتِ «واحد مشکوک» فقط برای سالانهسازیِ واقعی (۰ < ماه < ۱۲) معنا دارد؛
    # گزارشی که خودش ۱۲ ماه کامل را پوشش میدهد مستقیم پذیرفته میشود.
    if fs_rev > 0 and 0 < months < 12 and (annual > fs_rev * 4.0 or annual < fs_rev * 0.25):
        reconciled = False
        annual, months, basis = fs_rev, 12, "Annualized ماهانه مردود شد (واحد مشکوک) → فروش سالانهٔ کدال"
    return {"annual_sales_mrl": annual,
            "annual_sales_bt": round(normalize_mrl_to_btom(annual), 1),
            "months_used": months, "basis": basis, "reconciled": reconciled}


def sales_to_marketcap(conn: sqlite3.Connection, symbol: str, market_cap_rials: float,
                       min_ratio: float = 1.0, annual: Optional[dict] = None) -> Optional[dict]:
    """فروش سالانه ÷ ارزش بازار روز — جزوه: باید ≥ min_ratio (پیش‌فرض ۱.۰) باشد.

    اصلاح v8: در v7.3 نسبت به‌صورت P/S = mcap ÷ rev محاسبه و «≤ ۳» پاس میشد —
    یعنی هم جهت نسبت برعکس بود و هم صورت مالیِ ۳ماهه به‌جای فروش سالانه.
    """
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
                           min_pct: float = 30.0, gm: Optional[dict] = None,
                           annual: Optional[dict] = None) -> Optional[dict]:
    """پتانسیل سود ناخالص به ارزش بازار = (فروش سالانه × حاشیه ناخالص) ÷ ارزش بازار × ۱۰۰.

    اصلاح v8: در v7.3 این تابع با `if not gm['pass']: return None` به شاخص ۳ قفل
    شده بود → برای شرکت‌های با حاشیه <۲۰٪ خروجی «ناموجود» میشد نه «رد». اکنون
    مستقل محاسبه و فقط بر پایهٔ آستانهٔ خودش داوری میشود.
    """
    mcap = _f(market_cap_rials)
    if mcap <= 0:
        return None
    g = gm if gm is not None else gross_margin(conn, symbol)
    a = annual or annualized_sales(conn, symbol)
    if not g or not a:
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

# ============================ شاخص ۵: فیلتر صنعت (قیمت‌گذاری آزاد / دستوری)
def sector_filter(sector: str, cfg: dict = None, market_cap_rials: float = 0.0,
                  total_market_cap_rials: float = 0.0) -> dict:
    """تفکیک تگ صنعت به «قیمت‌گذاری آزاد/بورس کالا» و «قیمت‌گذاری دستوری».

    اصلاح v8:
      * لیست‌های `mandatory_sectors` / `free_sectors` **از پنل تنظیمات کدال** خوانده
        میشوند (در v7.3 `bad_sectors`/`good_sectors` هرگز به این تابع پاس نمیشد و
        فیلدهای UI کاملاً مرده بودند).
      * تطبیق با norm_fa → خطای ی/ک عربی-فارسی ممکن نیست.
      * «سهم بازار» از شرط رد/قبولی شاخص ۵ **خارج** شد (جزو ۵ محور نیست) و فقط
        به‌عنوان دادهٔ تکمیلی برمی‌گردد.
      * `industry_mode` = Exclude_Mandatory_Pricing (پیش‌فرض) → دستوری = مردود
        `industry_mode` = Rank_Only → دستوری فقط برچسب می‌خورد، رد نمی‌شود
    """
    cfg = cfg or {}
    s = norm_fa(sector)
    mandatory = [norm_fa(t) for t in (cfg.get("mandatory_sectors")
                                      or MANDATORY_PRICING_TOKENS)]
    free = [norm_fa(t) for t in (cfg.get("free_sectors") or FREE_PRICING_TOKENS)]

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
             "neutral": "خنثی — نیازمند بررسی موردی"}[mode]
    return {"verdict": mode, "label": label, "sector": sector,
            "matched_tokens": hit_mand or hit_free,
            # v9.8.1 — برچسب «صنعت برتر FTS»: صنعتی که در یکی از دو فهرستِ
            # قیمت‌گذاری FTS شناخته شده (فلزات/سیمان/پتروشیمی/دارو/غذا/…) —
            # «برتر» یعنی برچسب‌دار، نه لزوماً قبول (دارو برچسب میخورد ولی رد)
            "fts_top_industry": bool(hit_mand or hit_free),
            "pass": (mode != "mandatory") if exclude else True,
            "exclusion_active": exclude,
            "market_share_pct": round(share, 3)}     # تکمیلی — در داوری نقشی ندارد


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
    pred18, params = sym_in("i.l_val18", symbol)
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

    چرا فیلتر تک‌نمادی روی این کوئری نمی‌چسبد: کلیدهای خروجی norm_fa(symbol)
    است، ولی ستونِ دیتابیس نوشتار خام (گاهی عربی: ي/ك/ى) دارد. اگر در SQL
    بنویسیم `symbol = ?`، نمادهایی که دیتابیس‌شان عربی‌نویسی است بی‌صدا
    «پیدا نمی‌شوند» و m141 = False برمی‌گردد — یعنی خطای داده‌ای که هیچ‌وقت
    در لاگ دیده نمی‌شود. تست dev/fts_m141_parity_v97.py همین را روی ۲۲۴ نماد
    گرفت. راه‌حلِ همین‌جا «کلیدِ نرمال در Python» است (کوئری کل‌بازار است و
    از قبل همه‌چیز را می‌خواند). برای کوئریِ تک‌نماد، `symbol_aliases`/`sym_in`
    باید استفاده شود — نه `WHERE norm_fa(symbol)=?`، که به اندازه‌گیریِ
    v9.7.3 روی همین بانک ۵۷۴ برابر اسکنِ ایندکسی هزینه دارد.
    """
    rows = conn.execute("""
        SELECT symbol, capital, total_equity, period_end, publish_date
        FROM financial_statements
        WHERE period_months >= 12 AND capital > 0 AND total_equity IS NOT NULL
        ORDER BY symbol, period_end DESC, publish_date DESC""").fetchall()
    out = {}
    for sym, cap, eq, _pe, _pd in rows:
        key = norm_fa(sym)
        if key in out:                      # فقط جدیدترین سال مالی ملاک است
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
    return {norm_fa(sym): (val or 0.0) / 1e10
            for sym, val, _n in rows if sym}


# =================================================== اسکن کامل ۵ شاخص
def scan_symbol(conn: sqlite3.Connection, symbol: str, market_cap_rials: float = 0.0,
                total_market_cap_rials: float = 0.0, sector: str = "",
                cfg: dict = None, _sessions: list = None,
                m141_hit: Optional[bool] = None,
                avg_trade_val: Optional[float] = None) -> dict:
    """اجرای هر ۵ شاخص روی یک نماد → خروجی کارت بنیادی (endpoint /api/fts/{symbol}).

    cfg = پیش‌شرط‌های fts_thresholds.json (None = پیش‌فرض جزوه).
    m141_hit / avg_trade_val: اگر از بیرون داده شوند، کوئری تکراری زده نمیشود
    (scan_all هر دو نقشه را یک‌بار می‌سازد و به ازای هر نماد پاس میدهد).
    """
    cfg = cfg or {}
    mcap = _f(market_cap_rials)
    ref = reference_annual(conn, symbol)

    g = revenue_growth_yoy(conn, symbol, min_growth=_f(cfg.get("growth_min", 40.0)) or 40.0,
                           inflation_min=_f(cfg.get("inflation_min", 58.0)) or 58.0,
                           sector=sector)
    e = eps_trend_3y(conn, symbol, years=int(cfg.get("eps_years", 3) or 3), sector=sector)
    gm = gross_margin(conn, symbol, min_margin=_f(cfg.get("margin_min", 20.0)) or 20.0,
                      optimal=_f(cfg.get("margin_optimal", 30.0)) or 30.0, ref=ref)
    annual = annualized_sales(conn, symbol, ref=ref)
    s2m = sales_to_marketcap(conn, symbol, mcap,
                             min_ratio=_f(cfg.get("sales_to_mcap_min", 1.0)) or 1.0,
                             annual=annual)
    pot = gross_profit_potential(conn, symbol, mcap,
                                 min_pct=_f(cfg.get("profit_potential_min", 30.0)) or 30.0,
                                 gm=gm, annual=annual)
    sec = sector_filter(sector, cfg=cfg, market_cap_rials=mcap,
                        total_market_cap_rials=total_market_cap_rials)

    passes = {"1_growth": bool(g and g["pass"]),
              "2_eps_trend": bool(e and e["pass"]),
              "3_gross_margin": bool(gm and gm["pass"]),
              "4_sales_to_mcap": bool(s2m and s2m["pass"]),
              "5_industry": bool(sec["pass"])}
    score = sum(passes.values())

    reasons = []
    if is_insurance_sector(sector):
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
    key = norm_fa(symbol)
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
        "excluded": bool(reasons), "exclusion_reasons": reasons,
        "m141": bool(m141_hit),
        "avg_trade_val_hmt": None if avg_trade_val is None else round(avg_trade_val, 3),
        "detail": {"growth": g, "eps_trend": e, "gross_margin": gm,
                   "sales_to_mcap": s2m, "profit_potential": pot, "sector": sec},
        "verdict": ("EXCLUDED" if reasons else
                    "STRONG" if score >= 4 else "WATCH" if score >= 3 else "REJECT"),
    }


def scan_all(conn: sqlite3.Connection, limit: int = 0, cfg: dict = None) -> list[dict]:
    """غربالگری ۵ شاخصی کل نمادهای دارای صورت مالی → حداکثر `watchlist_max` سهم برتر.

    نمادهای تعلیق و صنعت بیمه پیش از رتبه‌بندی حذف میشوند (بخش ۲ دستور کار).
    """
    cfg = cfg or {}
    total_mcap = conn.execute(
        "SELECT SUM(p_closing * total_shares) FROM market_watch").fetchone()[0] or 0.0
    rows = conn.execute("""
        SELECT f.symbol, COALESCE(m.p_closing * i.total_shares, 0) AS mcap,
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

    # v9.7.3: یک نماد = یک ردیف. حلقهٔ قبلاً روی «DISTINCT symbol» خام می‌چرخید
    # و برای هر گروهِ دودیک (۲۱ گروه در financial_statements) دو بار امتیاز
    # می‌داد — آن هم یکی با join به تابلو و یکی بدون join (sector='سایر'، mcap=0)
    # که جای واچ‌لیستِ سهمِ اصلی را می‌گرفت.
    best, order = {}, []
    for r in rows:
        key = norm_fa(r[0])
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
        if is_insurance_sector(sector):
            continue
        if d_even and stale_cut and int(d_even) < int(stale_cut):
            continue
        out.append(scan_symbol(conn, sym, mcap or 0.0, total_mcap, sector,
                               cfg=cfg, _sessions=sessions,
                               m141_hit=bool(m141.get(key, False)),
                               avg_trade_val=liq.get(key)))
    out.sort(key=lambda r: (-r["score"], -_f(r.get("market_cap_rials")), r["symbol"]))
    # فیلتر نهایی: ردیفهای excluded (تعلیق/بیمه/دستوری) جای واچ‌لیست را نمیگیرند
    clean = [r for r in out if not r["excluded"]]
    cap = int(cfg.get("watchlist_max", 50) or 50)
    return clean[:cap] if limit <= 0 else clean[:max(limit, cap)]


# ============================================================ اسکن دسته‌ای
def bulk_scan(conn: sqlite3.Connection, cfg: dict = None) -> list[dict]:
    """غربالگری ۵ شاخصی کل بازار با چند کوئری تک‌گذر (برای /api/screener).

    همان تعریفِ هر شاخصِ scan_symbol — فقط بدون N+1 کوئری. خروجی ستون‌های
    جدول بنیادی کدال است: پنج محور + score (۰..۵) + excluded.
    """
    cfg = cfg or {}
    g_min = _f(cfg.get("growth_min", 40.0)) or 40.0
    inf_min = _f(cfg.get("inflation_min", 58.0)) or 58.0
    eps_years = int(cfg.get("eps_years", 3) or 3)
    m_min = _f(cfg.get("margin_min", 20.0)) or 20.0
    m_opt = _f(cfg.get("margin_optimal", 30.0)) or 30.0
    s2m_min = _f(cfg.get("sales_to_mcap_min", 1.0)) or 1.0
    pot_min = _f(cfg.get("profit_potential_min", 30.0)) or 30.0

    # ۱) صورت‌های مالی سالانه — مرجع + سری EPS
    # v9.7.3: کلید = norm_fa(symbol). با کلیدِ خام، یک شرکت با دو نوشتار
    # (داریک/داريك) دو ردیف اسکنر می‌ساخت و نوشتارِ بی‌داده امتیاز ۰ می‌گرفت.
    annual, disp_of = {}, {}
    for sym, pe, pm, title, rev, gp, op, np_, eps in conn.execute(
            "SELECT symbol, " + FS_COLS + " FROM financial_statements "
            "WHERE period_months>=12 ORDER BY symbol, period_end DESC"):
        key = norm_fa(sym)
        if not key:
            continue
        annual.setdefault(key, []).append(
            {"period_end": pe, "fiscal_year": str(pe or "")[:4], "title": title or "",
             "audited": _is_audited(title), "consolidated": _is_consolidated(title),
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
    # پس _ref/_solo_annualِ bulk صورت‌مالیِ قدیمیِ املای عربی را برمی‌داشتند
    # (مثلاً وسینا: ردیف ۱۴۰۳ با gross_profit = NULL) در حالی که
    # annual_statements در مسیر scan سراسری بر اساس period_end DESC مرتب
    # می‌کند و ردیف ۱۴۰۴ را می‌دید → شاخص ۳ بین دو مسیر واگرا می‌شد.
    # این مرتب‌سازی همان ترتیب را برای هر دو مسیر می‌سازد.
    for key in annual:
        annual[key].sort(key=lambda r: str(r["period_end"] or ""), reverse=True)

    def _solo_annual(sym):
        # همراستا با مسیر جزئیات (eps_trend_3y): اول سالانهٔ حسابرسی‌شده را ترجیح بده،
        # و اگر کافی نبود، ردیف‌های میان‌دوره/سالانه‌شده را هم بپذیر تا شاخص ۲ بین
        # اسکرینر و /api/fundamental واگرا نشود.
        last = []
        for req_aud in (True, False):
            out, seen = [], set()
            for r in annual.get(sym, []):
                if r["consolidated"] or (req_aud and not r["audited"]):
                    continue
                if not r["fiscal_year"] or r["fiscal_year"] in seen:
                    continue
                seen.add(r["fiscal_year"])
                out.append(r)
            last = out
            if len(out) >= 2:
                return out
        return last

    def _ref(sym):
        for req_aud in (True, False):
            out, seen = [], set()
            for r in annual.get(sym, []):
                if r["consolidated"] or (req_aud and not r["audited"]):
                    continue
                if r["fiscal_year"] in seen:
                    continue
                seen.add(r["fiscal_year"])
                out.append(r)
            if out:
                return out[0]
        dedup, seen = [], set()
        for r in annual.get(sym, []):
            if not r["fiscal_year"] or r["fiscal_year"] in seen:
                continue
            seen.add(r["fiscal_year"])
            dedup.append(r)
        return dedup[0] if dedup else None

    # ۲) گزارش‌های ماهانه — رشد تجمیعی + فروش Annualized
    # کلید نرمال + مرتب‌سازی/حذف تکرارِ (سال,ماه) پس از ادغام دو نوشتار.
    ms = {}
    for sym, y, mo, mrev, ytd, ytdp in conn.execute(
            "SELECT symbol, year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev "
            "FROM monthly_sales WHERE ytd_revenue IS NOT NULL AND ytd_revenue>0 "
            "ORDER BY symbol, year DESC, month DESC"):
        key = norm_fa(sym)
        if not key:
            continue
        ms.setdefault(key, []).append((int(y or 0), int(mo or 0), _f(mrev), _f(ytd), _f(ytdp)))
    for key in ms:
        ms[key].sort(key=lambda r: (-r[0], -r[1]))
        ms[key] = _dedupe_ym(ms[key])

    # ۳) تابلو + صنعت + ارزش بازار
    mcap_of, sector_of, dev_of, board_of = {}, {}, {}, {}
    total_mcap = 0.0
    for sym, mcap, sector, d_even in conn.execute("""
        SELECT i.l_val18, COALESCE(m.p_closing * i.total_shares, 0),
               COALESCE(i.sector_name, ''), m.d_even
        FROM instruments i LEFT JOIN market_watch m ON m.ins_code = i.ins_code"""):
        key = norm_fa(sym)
        mcap_of[key] = _f(mcap)
        sector_of[key] = sector or ""
        if d_even:
            dev_of[key] = int(d_even)
        # نماد نمایش = تیکرِ واقعیِ تابلو (instruments.l_val18) تا با
        # price_history هم‌خوان بماند؛ نوشتار فارسی اولویت دارد.
        if key and (key not in board_of or sym == key):
            board_of[key] = sym
        total_mcap += _f(mcap)
    sessions = market_sessions(conn)
    stale_cut = (sessions[min(int(cfg.get("suspended_max_stale_sessions", 3) or 3),
                              len(sessions) - 1)] if len(sessions) > 1 else 0)
    # v9.7: ماده ۱۴۱ + نقدشوندگی — دو نقشهٔ تک‌کوئری، بیرون حلقه
    m141 = m141_map(conn)
    liq = avg_trade_value_hmt(conn)
    do_m141 = bool(cfg.get("filter_m141"))
    min_liq = _f(cfg.get("min_trade_val", 0.0)) or 0.0

    out = []
    for key in sorted(annual.keys()):
        sym = key                                   # کلید = نوشتار نرمال (فارسی)
        sym_out = board_of.get(key) or disp_of.get(key) or key
        sector = sector_of.get(key, "")
        mcap = mcap_of.get(key, 0.0)
        ref = _ref(key)

        # ۱) رشد فروش تجمیعی ÷ همان دورهٔ سال قبل
        growth = None
        recs = ms.get(key)
        if recs:
            y, mo, _, ytd, ytdp = recs[0]
            prev = ytdp if ytdp > 0 else next(
                (r[3] for r in recs[1:] if r[0] == y - 1 and r[1] == mo), 0.0)
            if ytd > 0 and prev > 0:
                growth = (ytd / prev - 1.0) * 100.0
        i1 = growth is not None and growth >= g_min

        # ۲) روند EPS سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی
        solo = [r for r in _solo_annual(key) if r["basic_eps"] is not None]
        eps_series, i2, data_gap2 = None, False, False
        if is_insurance_sector(sector):
            data_gap2 = False
        elif len(solo) < eps_years:
            # هم‌راستاسازی با مسیر جزئیات: اگر سطرهای سالانهٔ اسکنر کافی نبود،
            # همان محاسبهٔ eps_trend_3y برای این نماد صدا زده می‌شود (منبع واحد حقیقت)
            # تا شاخص ۲ بین /api/screener و /api/fundamental واگرا نشود.
            _det = None
            if not is_insurance_sector(sector):
                try:
                    _det = eps_trend_3y(conn, key, years=eps_years, sector=sector)
                except Exception:
                    _det = None
            if _det and _det.get("eps_series"):
                eps_series = _det["eps_series"]
                i2 = bool(_det.get("pass"))
                data_gap2 = bool(_det.get("data_gap"))
            elif len(solo) >= 2:
                # ۲ سال از ۳: داده هست ولی گیتِ ۳ساله رد است — «سابقهٔ ناقص»، نه شکاف.
                # سری به بلندای eps_years ساخته می‌شود؛ جای سالِ غایب None می‌ماند
                # (قاعدهٔ «سطر هرگز حذف نمی‌شود» — همان الگوی /api/fundamental).
                ser = [round(r["basic_eps"], 1) for r in reversed(solo)]
                eps_series = ([None] * (eps_years - len(ser)) + ser) or None
                i2, data_gap2 = False, True
            else:
                data_gap2 = True                  # «بدون داده» نه «مردود» — تفکیک برای UI
        else:
            win = solo[:eps_years]
            gap_ok = all(int(win[i]["fiscal_year"]) - int(win[i + 1]["fiscal_year"]) == 1
                         for i in range(len(win) - 1))
            ser = [w["basic_eps"] for w in reversed(win)]
            i2 = bool(gap_ok and all(ser[k] < ser[k + 1] for k in range(len(ser) - 1))
                      and all(v > 0 for v in ser))
            eps_series = [round(v, 1) for v in ser]

        # ۳) حاشیه سود ناخالص = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰
        margin = None
        if ref and _f(ref["revenue"]) > 0 and ref["gross_profit"] is not None:
            margin = (ref["gross_profit"] / ref["revenue"]) * 100.0
        i3 = margin is not None and margin >= m_min

        # ۴) فروش سالانهٔ Annualized ÷ ارزش بازار (+ پتانسیل سود ناخالص)
        # v9.8.1: همان اولویتِ annualized_sales — اول «فروش ۳ ماههٔ متوالی × ۴»،
        # بعد YTD × ۱۲ ÷ ماه. بدون این، پاریتیِ scan_symbol ⇄ bulk_scan روی
        # شاخص ۴ میشکست (گارد ۱۳ confidence_engine_v973).
        annual_sales, months_used = 0.0, 0
        if recs:
            y = recs[0][0]
            cy = sorted([r for r in recs if r[0] == y],
                         key=lambda r: -int(r[1] or 0))
            tri = [_f(r[2]) for r in cy[:3]]
            if len(cy) >= 3:
                m0, m1, m2 = (int(cy[i][1] or 0) for i in range(3))
                if m0 - m1 == 1 and m1 - m2 == 1 and all(v > 0 for v in tri):
                    annual_sales = sum(tri) * 4.0
                    months_used = 3
            if annual_sales <= 0:
                months_used = max(r[1] for r in cy)
                ytd = cy[0][3]
                if ytd > 0 and months_used >= 1:
                    annual_sales = ytd if months_used >= 12 else ytd * 12.0 / months_used
        fs_rev = _f(ref["revenue"]) if ref else 0.0
        if annual_sales <= 0:
            annual_sales, months_used = fs_rev, 12
        elif (fs_rev > 0 and 0 < months_used < 12
              and (annual_sales > fs_rev * 4.0 or annual_sales < fs_rev * 0.25)):
            annual_sales, months_used = fs_rev, 12      # واحد مشکوک → فروش سالانهٔ کدال
        s2m = (annual_sales * MRL_TO_RIAL / mcap) if mcap > 0 and annual_sales > 0 else None
        pot = None
        if s2m is not None and margin is not None:
            pot = (annual_sales * (margin / 100.0) * MRL_TO_RIAL / mcap) * 100.0
        i4 = s2m is not None and s2m >= s2m_min

        # ۵) فیلتر صنعت (قیمت‌گذاری آزاد/بورس کالا در برابر دستوری)
        sec = sector_filter(sector, cfg=cfg, market_cap_rials=mcap,
                            total_market_cap_rials=total_mcap)
        i5 = bool(sec["pass"])

        reasons = []
        if is_insurance_sector(sector):
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
            "eps_series": eps_series,
            "eps_last": (eps_series[-1] if eps_series else None),
            "eps_data_gap": bool(data_gap2),
            "eps_years_available": min(len(solo), eps_years),
            "eps_years_required": eps_years,
            "gross_margin": None if margin is None else round(margin, 1),
            "sales_to_mcap": None if s2m is None else round(s2m, 2),
            "profit_potential_pct": None if pot is None else round(pot, 1),
            "annual_sales_bt": round(normalize_mrl_to_btom(annual_sales), 1),
            "annualize_months": months_used,
            "mcap": mcap, "score": int(sum([i1, i2, i3, i4, i5])),
            "i1_pass": i1, "i2_pass": i2, "i3_pass": i3, "i4_pass": i4, "i5_pass": i5,
            "excluded": bool(reasons), "exclusion_reasons": " · ".join(reasons),
            "m141": hit141,
            "avg_trade_val_hmt": None if liq_hmt is None else round(liq_hmt, 3),
            "margin_optimal": margin is not None and margin >= m_opt,
            "growth_excellent": growth is not None and growth >= inf_min,
        })
    out.sort(key=lambda r: (r["excluded"], -r["score"], -r["mcap"], r["symbol"]))
    return out


