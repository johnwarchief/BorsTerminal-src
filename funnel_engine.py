# -*- coding: utf-8 -*-
"""funnel_engine.py — داورِ canonicalِ قیف FTS (بک‌اند، تنها نسخه).

چرا این فایل هست: تا پیش از این «حکمِ نهاییِ قیف» درِ مرورگر ساخته می‌شد
(`frontend/src/features/master/lib/ftsFunnel.ts` → `buildFunnel`) و بک‌اند فقط
پرچم و پنج شاخص خام می‌داد. رأیِ مالک (۱۴۰۵-۰۷-۱۶): یک داورِ canonical درِ
بک‌اند؛ فرانت فقط نمایشِ همان حکم.

قراردادِ این ماژول (هیچ‌کدام مذاکره‌پذیر نیست):

  ۱) ورودیِ خام = ردیف‌هایِ تابلو (با پرچم‌هایِ `tape_flags`) + ردیف‌هایِ
     اسکرینر (با i1..i5 و `tech_*`). هیچ فرمولِ فیلتر یا آستانه‌ای اینجا
     دوباره نوشته نمی‌شود — فقط *خواندن* ستونی که موتورِ دیگر ساخته.
  ۲) زنجیره **اشتراکِ ترتیبی** است، نه OR:
        U ∩ F1  F2 ∩ F3   و هر F رویِ بازماندۀ قبلی.
     ترتیبِ کاربر درِ شمارشِ هر مرحله («ورودی → ماندگار → حذف‌شده») و درِ
     traceِ هر نماد ثبت می‌شود، حتی اگر مجموعۀ نهایی تصادفاً یکی شود.
  ۳) تکنیکال: اول هفتگی. نزولی ⇒ رد، خنثی ⇒ رد، صعودی ⇒ آنگاه روزانه.
     «سنجیده نشد» رد نیست (PENDING). ستاپ‌ها (جت/فیب/CHoCH/کف دوقلو) شاهداند
     و هیچ‌وقت وتوی هفتگی را نمی‌شکنند — رأیِ صریحِ مالک.
  ۴) بنیادی سه حالت: hard (هر پنج) / standard (I1∧I2I3 بلاکر، I4/I5 شاهد)
     / exception. بی‌داده هیچ‌وقت pass نمی‌شود. I4/I5 شکستِ بلاکر را جبران
     نمی‌کنند.
  ۵) استثنا فقط صریح و ثبت‌شده است، و هرگز canonical را بازنویسی نمی‌کند:
        canonical = REJECT   و   effective = PASS WITH EXCEPTION
     با برچسبِ «استثنای بنیادی: I2» + زمانِ اعمال درِ trace.
  ۶) تحویل: بازمانده‌ها، رتبه‌بندیِ شفاف با داده‌هایِ موجود — هیچ وزنِ ساختگی
     و هیچ scoreِ اختراعی نیست: (حکمِ نهایی → بی‌استثنا → امتیازِ بنیادیِ موجود
     → امتیازِ تکنیکالِ موجود → رتبۀ رسمیِ بک‌اند → نماد).
  ۷) سقفِ پنهان ممنوع: هیچ slice/LIMIT درِ این فایل نیست. هرچه ورودی باشد
     همان پردازش می‌شود؛ کم‌کردنِ جامععه وظیفۀ فراخوان نیست.

خروجی `evaluate()` یک دیکشنریِ JSON-پذیر است که عیناً درِ `/api/funnel` می‌نشیند
و فرانت بدونِ هیچ داوریِ تازه‌ای نمایشش می‌دهد.
"""
from __future__ import annotations

import re
import time
from typing import Any, Iterable

import funnel_registry as REG

ENGINE_VERSION = "1"

# وضعیت‌هایِ چهارحالته — همان معنا درِ کلِ قیف (UNAVAILABLE ≠ REJECT).
PASS, REJECT, PENDING, UNAVAILABLE = "pass", "reject", "pending", "unavailable"
# پنجمین وضعیتِ رسمی: مرحلۀ بعدی اجرا نشده چون مرحلۀ قبل نماد را رد کرده.
# این «سنجیده نشد» نیس — یک حکمِ قطعیِ زنجیره‌ای است و درِ trace هم همین‌طور
# نوشته می‌شود (رأیِ مالک: «هیچ نمادی نباید با وضعیت سنجیده نشده خارج شود»).
NOT_REQUIRED = "not_required"
# ششمین وضعیتِ رسمی — بیرون از خودِ جامعۀ غربالگری، نه رد، نه «سنجیده نشده»:
# نمادی که وضعیتِ رسمیِ بازار اجازهٔ غربال شدن نمی‌دهد اصلاً candidate نیست.
# (رأیِ مالک ۱۴۰۵-۰۷-۱۶: «NOT_IN_SCREENING_UNIVERSE ≠ REJECT و ≠ سنجیده نشده»)
NOT_IN_UNIVERSE = "not_in_universe"
# هفتمین وضعیت — مخصوصِ **یک شاخص**: خودِ منبع می‌گوید این شاخص برایِ این
# نماد نظر نمی‌دهد (مبنایِ تلفیقی، نبودِ سطرِ بهای تمام‌شده، طبقۀ صندوق).
# با `not_required` (گامِ پیشین رد کرد) یکی نیست، و با `pending` (داده نرسید)
# هم نیست — رأیِ مالک ۱۴۰۵-۰۷-۲۱: «کاربرد ندارد» و «قابل ارزیابی نیست» دو
# وضعیتِ جدااند.
NOT_APPLICABLE = "not_applicable"

# گیتها و فیلترهایِ تکنیکال از رجیستری می‌آیند (تعریف آنجاست، داوری اینجا)
TECH_GATE_IDS = REG.TECH_GATE_IDS
STATUSES = (PASS, REJECT, PENDING, UNAVAILABLE, NOT_REQUIRED, NOT_IN_UNIVERSE,
            NOT_APPLICABLE)

# ── واجدِ شرایطِ غربالگری ────────────────────────────────────────────────
# هیچ آستانه‌ای از خودِ این فایل نیامده. سه سیگنالی که مصرف می‌شود هر سه درِ
# ردیفِ تابلو از خودِ سازوکارِ رسمیِ بازار می‌آیند:
#   `is_live`       ← `api/market.py:551-552` (ردیفِ نشستِ جدید vs snapshotِ کهنه)
#   `st_code/title` ← آخرینِ لاگِ `instrument_state.c_etaval(_title)`
#                     (`api/market.py:799-806, 861`) — «مجاز»، «مجاز-محفوظ»،
#                     «مجاز-متوقف»، «ممنوع»، «ممنوع-محفوظ»، «ممنوع-متوقف»
#   `stop_state`    ← `stop_reasons.vaziyat_desc` (`api/market.py:869`) با متنِ
#                     «تعلیق شده» / «مشمول فرایند تعلیق» — همان چیزی که بجِ
#                     «متوقف» تابلو است (`tapeBadges.ts:142-161`).
#
# رأیِ صریحِ مالک (۱۴۰۵-۰۷-۱۶): «زنده» با «امروز معامله داشت» یکی نیست. سنجشِ
# همین نشستِ market.db (۱۴۰۵-۰۷-۱۶، `market_watch` در d_even=20261007):
#   ردیفِ نشستِ جاری (is_live)  = 3992   ← جامعۀ پویا، نه عددِ ثابت
#   از آنها بدونِ هیچ معامله‌ای = 1705   ← پس live ⊃ «معامله داشت»؛ حجمِ امروز
#   از آنها با معاملۀ امروز    = 2287   ← ملاکِ غربالگری نیست
# ردیف‌هایِ کهنه (d_even نشست‌هایِ پیشین، تا 20260821) نمادهایی هستند که درِ
# تازۀترین نشستِ تابلو اصلاً حاضر نیستند؛ اینها بیرون می‌مانند.
#
# نکته‌ای که یک بار غلط شد و اینجا ثبت می‌شود: `instrument_state` لاگِ *تغییرِ*
# وضعیت است، نه وضعیتِ جاریِ همهٔ نمادها — درِ همین بانک تنها ۴۹۶ نماد از ۵۸۶۵
# ردیفِ وضعیت دارد. پس «ردیفِ وضعیت ندارد» یعنی «هیچ وتوی ثبت‌شدۀ معتبر نیست»،
# نه «غیرمجاز»؛ بی‌این تفکیک جامعۀ غربالگری به ۷ نماد می‌افتاد.
PERMITTED_TITLES = ("مجاز",)        # «مجاز…»: اجازهٔ معامله دارد
FORBIDDEN_TITLES = ("ممنوع",)       # «ممنوع…»: اجازه ندارد
STOPPED_MARK = "متوقف"              # پسوندِ «-متوقف» در همان برچسبِ رسمی


def _fa_digits(v) -> str:
    """رقمِ فارسی با همان قاعدۀ AGENTS (chr(0x06F0+d)) — رقمِ دست‌کاری‌شده درِ
    متنِ فارسی می‌دزدد، پس عددِ نمایشی از همین‌جا فارسی می‌رود."""
    return "".join(chr(0x06F0 + int(c)) if c.isdigit() else c for c in str(v))


def _state_reason(row: dict, title: str, session_day: int | None = None) -> str:
    """برچسبِ زمان‌مندِ وضعیت — رأیِ مالک (§۸): «ممنوع-متوقف (طی معاملات)».

    لاگِ وضعیتِ TSETMC رویداد-محور و ساعت‌مند است: یک نماد می‌تواند درِ همان نشست
    اول مجاز باشد و بعد متوقف شود (سنجشِ زنده: «آوند۴» ۱۴:۰۸:۰۷ مجاز-متوقف ←
    ۱۴:۰۸:۰۸ مجاز-محفوظ ← ۱۴:۲۴:۴۲ مجاز ← ۱۴:۲۴:۵۷ ممنوع-متوقف). پس «توقفِ
    امروز» غلط است؛ آنچه معلوم است این است که وتو درِ *همین* نشستِ تابلو ثبت
    شده یا درِ نشستی پیش‌تر.
    """
    st_d = _num(row.get("st_d"))
    d = _num(session_day if session_day else row.get("d_even"))
    hhmm = ""
    h = _num(row.get("st_h"))
    if h:
        s = f"{int(h):06d}"
        hhmm = f"{s[:2]}:{s[2:4]}"
    same_session = bool(st_d and d and st_d == d)
    if same_session:
        return f"{title} (طی معاملات" + (f" — ساعت {_fa_digits(hhmm)}" if hhmm else "") + ")"
    if st_d:
        return f"{title} — از نشستِ {_fa_digits(int(st_d))}"
    return f"وضعیتِ ثبت‌شدۀ نماد: {title}"


def screening_eligibility(row: dict, session_day: int | None = None) -> tuple[bool, str, str]:
    """(قابل‌غربال؟، کدِ علت، علتِ فارسی) — فقط از دادهٔ رسمیِ خودِ ردیف.

    وتوها به ترتیبِ قطعیت خوانده می‌شوند: نبودِ ردیفِ نشستِ جاری، سپس تعلیقِ
    صریح (`stop_reasons`)، سپس آخرینِ وضعیتِ ثبت‌شدۀ نماد. نبودِ هیچ‌یک از
    اینها «مجاز» نیست بلکه «وتویی ثبت نشده» است — و غربالگری می‌شود.

    بندِ اول همان دروازهٔ *موجودِ* تابلوخوانی است، نه یک اختراع: `is_live`
    (`api/market.py:551-552`) که هر هفت پرچمِ تابلو به آن AND می‌شوند
    (`tape_flags._alive`: «پنج فیلتر دربارهٔ «امروز» حرف می‌زنند… ردیفی که
    آخرینِ نشستِ بانکِ خودش دیروز است نمی‌تواند بگوید حجمِ امروزِ من سه برابر
    مبناءست») و همان چیزی که خودِ تابلو به‌صورت `live_count`/`fossil_count`
    منتشر می‌کند (`api/market.py:1039-1041`) و «نبض بازار» هم با همان
    `d_even = MAX(d_even)` جامعه می‌بندد (`mstat_engine.load_snapshot`).
    """
    title = str(row.get("st_title") or "").strip()
    code = str(row.get("st_code") or "").strip()
    if row.get("is_live") is False:
        return False, "NOT_LIVE_SESSION", "درِ تازۀترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)"
    if row.get("stop_state"):
        return False, "STOPPED", f"متوقف: {row.get('stop_state')}"
    if title.startswith(FORBIDDEN_TITLES):
        return False, "FORBIDDEN_STATE", _state_reason(row, title, session_day)
    if STOPPED_MARK in title:
        return False, "STOPPED", _state_reason(row, title, session_day)
    if title.startswith(PERMITTED_TITLES):
        return True, "PERMITTED_STATE", f"وضعیتِ ثبت‌شدۀ نماد: {title}"
    if title or code:
        return True, "NO_BLOCKING_STATE", f"وتوی معتبری ثبت نشده (وضعیت: {title or code})"
    return True, "NO_BLOCKING_STATE", "وضعیتی برایِ این نماد ثبت نشده — وتویی نیست"


# برچسبِ کوتاهِ هر علت، کنارِ همان جایی که علت ساخته می‌شود. رابطِ کاربر این
# واژگان را از پاسخِ سرور می‌خواند (`universe.exclusion_labels`) و دومی نمی‌سازد.
EXCLUSION_LABEL = {
    "NOT_LIVE_SESSION": "ردیفِ نشستِ کهنه",
    "STOPPED": "متوقف",
    "FORBIDDEN_STATE": "ممنوع",
    "NUMERIC_SUFFIX": "پسوندِ عددی",
}


# ستونِ پرچمِ هر فیلتر درِ ردیفِ تابلو — نام‌ها از رجیستری می‌آیند، نه از
# یک فهرستِ دستیِ دیگر.
FLAG_OF = {f.filter_id: f.filter_id for f in REG.FILTERS}


def _why_of(row: dict) -> list[dict]:
    """دفترچۀ ردیف‌محورِ دلیل‌ها (همان ردیفِ ورودی، کلیدِ زیرخطی)."""
    key = "_funnel_why"
    if key not in row:
        row[key] = []
    return row[key]  # type: ignore[no-any-return]


def _tri(v: Any) -> bool | None:
    """سه‌حالۀ صادقانه: 1/0/«نبود» ⇒ True/False/None (هیچ‌چیز pass نیست)."""
    if v is None or v == "" or v == "—":
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "آری", "✓"):
            return True
        if s in ("0", "false", "no", "خیر", "✗"):
            return False
        return None
    return bool(v)


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


_SYM_TRANS = str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})


def norm_symbol(v: Any) -> str:
    """یک شکلِ نوشتاریِ نماد — تنها تعریفِ این تبدیل درِ کلِ قیف.

    بانک هر دو املا را نگه می‌دارد («ك/ي/ى» عربی درِ بعضی نمادها، «ک/ی» فارسی درِ
    بقیه). وقتی matrix با کلیدِ نرمال‌شده ساخته شود و جستجو با رشتهٔ خام، ردیفِ
    همان نماد بی‌سروصدا «در تابلو نیست» می‌شود و کاندیدِ واقعی در رابط گم می‌شود —
    سنجدش درِ ۱۴۰۵-۰۷-۱۹: از ۴۹۰ ردیفِ گم‌شده ۳۸۷ فقط اختلافِ املا داشتند و ۱۹
    کاندیدِ درستِ presetِ custom پشتِ «not_in_board» پنهان بود. پس هر لایه
    (ساختِ matrix، پیوندِ ردیفِ اسکرینر، فیلترِ `symbols=`) همین یک تابع را صدا
    می‌زند. `ى→ی` هم نمادِ هم‌نامی نمی‌سازد: رویِ ۵۸۶۳ نمادِ یکتایِ واقعیِ تابلو
    صفر برخورد سنجیده شد.
    """
    return str(v or "").strip().translate(_SYM_TRANS)


def _symbols(rows: list[dict]) -> list[str]:
    """نام‌هایِ نمادِ یک گام، به همان ترتیبِ عبور — فهرستِ منتقل‌شده به گامِ بعد."""
    return [str(r.get("symbol") or "") for r in rows]


# «حذفِ پسوندِ عددی» — همان درِ تبِ تابلو (`tapeFts.isNumericSuffixSymbol`
# با /[0-9۰-۹]$/ و پیش‌فرضِ روشن). نمادی که رقمِ آخر دارد نسخهٔ افزودۀِ همان
# برند است («خودرو۲»، حق‌تقدم، اختیارِ سررسیددار) و جزوه آن را تابلویِ اصلی
# نمی‌شمارد. رقم‌ها با chr() ساخته می‌شوند، نه با نوشتنِ «۰-۹» درِ متنِ سورس.
_SUFFIX_RE = re.compile("[0-9" + "".join(chr(0x06F0 + d) for d in range(10)) + "]$")


def has_numeric_suffix(symbol: Any) -> bool:
    """آیا نوشتارِ نماد به رقم ختم می‌شود؟ ( LATIN و فارسی، عینِ regexِ تابلو )"""
    return bool(_SUFFIX_RE.search(norm_symbol(symbol)))


def _tape_unmeasurable(r: dict[str, Any], fid: str) -> bool:
    """آیا پرچمِ این ردیف اصلاً ساخته‌شدنی بود؟

    `tape_flags` درِ جایِ سنجش‌ناشدنی NaN می‌گذارد و تابلو همان را False می‌کند
    (آینۀ ExecFilterِ خودِ سایت، که چنین ردیفی را بیرون می‌اندازد). این False درِ
    قیف دو معنی داشت: «سنجید و نخورد» و «سنجیده نشد». دومی از شواهدِ خودِ ردیف
    خوانده می‌شود — همان آستانه‌هایِ `tape_flags`، نه عددِ تازه — تا UNAVAILABLE
    از REJECT جدا بماند و «بی‌داده» رأیِ قطعی نسازد.
    """
    from tape_flags import LOW_BASE_SESSIONS, VOL_BASE_SESSIONS

    # همان قاعدۀ رابط (tapeAlgorithms.tapeFilterVerdict): ردیفی که ستون‌هایِ
    # فرمول را اصلاً ندارد (پنلِ قدیمی، ردیفِ ساختهٔ تست) فرمول‌سنجی‌شدنی نیست،
    # پس پرچمِ بک‌اند تنها داوریِ صادق است و «ساخته‌نشدن» از آن «سنجیده‌نشدن»
    # نمی‌سازیم.
    if (r.get("hist_sessions") is None and r.get("prior30_vol") is None
            and r.get("min_low_29") is None and r.get("tmin") is None):
        return False

    if fid == "f_roobi":
        # کف‌روبی تاریخچۀ ۳۰-نشست نمی‌خواهد؛ آستانۀِ مجازِ پایین و صفِ سطرِ اول می‌خواهد
        return not (_num(r.get("tmin")) and _num(r.get("buy_q1_cnt")) is not None
                    and _num(r.get("buy_q1_vol")) is not None)
    if _num(r.get("z_tot_tran")) is None:
        return True
    if fid == "f_clock" and not _num(r.get("p_closing")):
        return True
    if fid == "f_noqteh":
        # کفِ فایل از [ih][0..28] خوانده می‌شود، نه ستونِ نمایشی
        return not _num(r.get("min_low_29")) or (_num(r.get("hist_sessions")) or 0) < LOW_BASE_SESSIONS
    return (_num(r.get("hist_sessions")) or 0) < VOL_BASE_SESSIONS


def _unmeasured_why(r: dict[str, Any], fid: str) -> str | None:
    """چرا سنجش ممکن نبود؟ همان شاخه‌هایِ `_tape_unmeasurable`، با متنِ علت.

    «داده در دسترس نیست» به‌تنهایی چیزی نمی‌گوید؛ ردیف باید بگوید *کدام* ورودی
    کم است (آستانۀ مجاز، صفِ سطرِ اول، پنجرۀ ۳۰ نشست…) تا کاربر بداند این
    «رد» نیست و کجا باید تازه شود. None یعنی سنجش‌شدنی بود.
    """
    from tape_flags import LOW_BASE_SESSIONS, VOL_BASE_SESSIONS

    if (r.get("hist_sessions") is None and r.get("prior30_vol") is None
            and r.get("min_low_29") is None and r.get("tmin") is None):
        # ردیف بی‌ستون‌هایِ فرمول (پنلِ قدیمی/ساختۀ تست) — همان شاخۀ بالا
        return None
    if fid == "f_roobi":
        if not _num(r.get("tmin")):
            return "آستانۀ مجازِ پایینِ این نشست نرسیده"
        if _num(r.get("buy_q1_cnt")) is None or _num(r.get("buy_q1_vol")) is None:
            return "صفِ خریدِ سطرِ اولِ این نماد نرسیده"
        return None
    if _num(r.get("z_tot_tran")) is None:
        return "تعدادِ معاملاتِ این نشست نرسیده"
    if fid == "f_clock" and not _num(r.get("p_closing")):
        return "قیمتِ پایانیِ این نشست نرسیده"
    if fid == "f_noqteh":
        if not _num(r.get("min_low_29")):
            return "کمینۀِ ۲۹ نشستِ پیش نرسیده"
        if (_num(r.get("hist_sessions")) or 0) < LOW_BASE_SESSIONS:
            return f"سابقۀِ نماد به ۲۹ نشست نمی‌رسد ({_fa_digits(int(_num(r.get('hist_sessions')) or 0))} نشست)"
        return None
    hist = _num(r.get("hist_sessions")) or 0
    if not _num(r.get("prior30_vol")):
        return "جمعِ حجمِ ۳۰ نشستِ پیش نرسیده"
    if hist < VOL_BASE_SESSIONS:
        return f"پنجرۀِ ۳۰ نشستِ فایل کامل نیست ({_fa_digits(int(hist))} نشست)"
    return None


def _tape_unmeasurable(r: dict[str, Any], fid: str) -> bool:
    """بولینِ همان سنجش — تنها تعریف درِ `_unmeasured_why` است."""
    return _unmeasured_why(r, fid) is not None


# ── «دلیل»ِ دیدنی: کدام بندِ فایل خورد، با عددِ خودِ همان ردیف ──────────────
# رأیِ مالک (۱۴۰۵-۰۷-۲۲): «{فیلتر} — نشانه در این نماد نیست» رویِ ۱۰۲۷ ردیفِ
# یکسان هیچ چیزی نمی‌گفت. متنِ تازه همان چهار/شش قیدِ خودِ فایل را به ترتیب
# می‌سنجد و اولینِ قیدِ ردشده را با عددِ ردیف می‌نویسد. آستانه‌ها ازِ خودِ
# `tape_flags` خوانده می‌شوند — عددِ دومی اینجا نوشته نمی‌شود — و اگر چیزی
# قابلِ اثبات نبود None برمی‌گردد تا متنِ عمومیِ صادق بماند.
def _fa_num(v: float, digits: int = 2) -> str:
    """رقمِ فارسی با ممیزِ فارسی (٫) — نقطۀ لاتین درِ متنِ RTL شکستِ عدد است."""
    return _fa_digits(f"{float(v):.{digits}f}").replace(".", "٫")


def _fa_n(v: float) -> str:
    """آستانه درِ متن — عددِ درست‌محور بی‌اعشار می‌آید (۳ نه ۳٫۰)."""
    f = float(v)
    return _fa_digits(str(int(f))) if f.is_integer() else _fa_num(f)


def _row_ratio(r: dict[str, Any]) -> float | None:
    """حجمِ این نشست ÷ مبناءِ فایل (Σ[ih][0..29]÷۳۰)؛ None یعنی مبناء نبود."""
    from tape_flags import VOL_BASE_SESSIONS
    hist = _num(r.get("hist_sessions")) or 0
    p30 = _num(r.get("prior30_vol"))
    tvol = _num(r.get("tvol"))
    if not p30 or p30 <= 0 or hist < VOL_BASE_SESSIONS or tvol is None:
        return None
    return tvol / (p30 / VOL_BASE_SESSIONS)


def _row_plp(r: dict[str, Any]) -> float | None:
    """`plp` عینِ `tape_flags.plp_series`: خامِ امروز، وگرنه درصدِ آخرین."""
    raw = r.get("plp_raw")
    return _num(raw) if raw is not None else _num(r.get("percent_last"))


def _row_bp(r: dict[str, Any]) -> float | None:
    """سرانۀِ سفارشِ خریدِ حقوقی ÷ سرانۀِ فروشِ حقوقی؛ None یعنی سنجیده نشد."""
    bc, sc = _num(r.get("buy_count_i")), _num(r.get("sell_count_i"))
    if not bc or bc <= 0 or not sc or sc <= 0:
        return None
    si = _num(r.get("sell_i_vol")) or 0.0
    bi = _num(r.get("buy_i_vol")) or 0.0
    if si <= 0:
        return None
    return (bi / bc) / (si / sc)


def _row_ladder(r: dict[str, Any]) -> float | None:
    """سقفِ پلکانِ جت ([ih][2..59].PriceMax)؛ None یعنی پنجره کامل نیست."""
    from tape_flags import JET_LADDER
    hist = _num(r.get("hist_sessions")) or 0
    if hist < max(JET_LADDER) + 1:
        return None
    return max((_num(r.get(f"h{k}_max")) or 0.0) for k in JET_LADDER)


def _param_num(sp: dict[str, Any] | None, key: str, default: float) -> float:
    """مقدارِ مؤثرِ یک پارامتر. نبودش یعنی پیش‌فرضِ فایل، نه صفر."""
    v = (sp or {}).get(key)
    try:
        f = float(v)                                   # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return f if f > 0 else default


def _tape_miss(r: dict[str, Any], fid: str,
               sp: dict[str, Any] | None = None) -> str | None:
    """اولین قیدِ ردشده درِ همان فایل، با عددِ ردیف — یا None.

    `sp` پارامترهایِ *مؤثر* همین درخواست است. تا پیش از این `params` فقط درِ
    نمایش (`parameter_set`) می‌نشست و `_tape_miss` هیچ‌وقت آن را نمی‌خواند —
    یعنی «ضریبِ حجم» و «آستانۀ ساعت» تنظیمِ دیدنیِ بی‌اثر بودند (همان برچسبِ
    مرده). حالا عددِ انتخابیِ کاربر درِ همان قید می‌نشیند و درِ دلیل هم با همان
    عدد نوشته می‌شود.
    """
    import tape_flags as TF

    pl, pc = _num(r.get("p_last")), _num(r.get("p_closing"))
    tvol, tno = _num(r.get("tvol")), _num(r.get("z_tot_tran"))
    plp = _row_plp(r)
    ratio = _row_ratio(r)

    def vol_over(mult: float) -> str | None:
        if ratio is None or ratio > mult:
            return None
        return f"حجمِ امروز {_fa_num(ratio)}× مبناءست، فایل بیش از {_fa_n(mult)}× می‌خواهد"

    def trades_over(n: float) -> str | None:
        if tno is None or tno > n:
            return None
        return f"تعدادِ معامله {_fa_digits(int(tno))} است، فایل بیش از {_fa_n(n)} می‌خواهد"

    def closing_ge() -> str | None:
        if pc is None or pl is None or pc <= 0:
            return None
        if pl >= pc:
            return None
        return f"آخرینِ {_fa_n(pl)} زیرِ پایانیِ {_fa_n(pc)} ماند، فایل `pl >= pc` می‌خواهد"

    def plp_pos() -> str | None:
        if plp is None or plp > 0:
            return None
        return f"تغییرِ آخرین {_fa_num(plp)}٪ است، فایل بالایِ صفر می‌خواهد"

    def bp_ge(mult: float) -> str | None:
        bp = _row_bp(r)
        if bp is None or bp >= mult:
            return None
        return (f"سرانۀِ خریدِ حقوقی {_fa_num(bp)}× سرانۀِ فروشِ حقوقی است، "
                f"فایل دستِ‌کم {_fa_n(mult)}× می‌خواهد")

    if fid == "f_clock":
        # آستانه ازِ تنظیمِ همین استراتژی می‌آید؛ نبودش یعنی همان ۲٪ِ فایل.
        delta = _param_num(sp, "clock_delta", TF.CLOCK_DELTA)
        mult = _param_num(sp, "vol_mult", 1.0)
        for chk in (
            lambda: (None if (pc and pl is not None and pl >= pc * (1 + delta)) else
                     f"اختلافِ آخرین و پایانی "
                     f"{_fa_num(100 * (pl - pc) / pc) if (pc and pl is not None) else '—'}٪ است، "
                     f"دستِ‌کم {_fa_num(delta * 100)}٪ بالا می‌خواهد"
                     + (" (تنظیمِ همین استراتژی)" if delta != TF.CLOCK_DELTA else "")),
            lambda: vol_over(mult),
            lambda: trades_over(TF.CLOCK_TRADES),
        ):
            if (msg := chk()) is not None:
                return msg
        return None

    if fid == "f_susp":
        for chk in (lambda: vol_over(TF.SUSP_VOL_MULT), lambda: trades_over(TF.SUSP_TRADES)):
            if (msg := chk()) is not None:
                return msg
        return None

    if fid == "f_roobi":
        tmin = _num(r.get("tmin"))
        zd1, qd1 = _num(r.get("buy_q1_cnt")), _num(r.get("buy_q1_vol"))
        for chk in (
            lambda: (None if (pl is not None and tmin and pl == tmin) else
                     f"آخرینِ {_fa_n(pl) if pl is not None else '—'} رویِ کفِ مجازِ "
                     f"{_fa_n(tmin) if tmin else '—'} ننشست"),
            lambda: (None if (zd1 is not None and zd1 > TF.ROOBI_ZD1_MIN) else
                     f"صفِ خریدِ سطرِ اول {_fa_digits(int(zd1)) if zd1 is not None else '—'} سفارش دارد، "
                     f"فایل بیش از {_fa_digits(TF.ROOBI_ZD1_MIN)} می‌خواهد"),
            lambda: (None if (plp is not None and plp < TF.ROOBI_MAX_CHANGE) else
                     f"تغییرِ آخرین {_fa_num(plp) if plp is not None else '—'}٪ است، "
                     f"فایل زیرِ {_fa_n(TF.ROOBI_MAX_CHANGE)}٪ می‌خواهد"),
            lambda: (None if (qd1 is not None and qd1 > TF.ROOBI_QD1_MIN) else
                     f"حجمِ صفِ اولِ خرید {_fa_digits(int(qd1)) if qd1 is not None else '—'} است، "
                     f"فایل بیش از {_fa_digits(TF.ROOBI_QD1_MIN)} می‌خواهد"),
        ):
            if (msg := chk()) is not None:
                return msg
        return None

    if fid == "f_noqteh":
        low = _num(r.get("min_low_29"))
        dist = None
        if pc and low not in (None, 0):
            hist = _num(r.get("hist_sessions")) or 0
            if hist >= TF.LOW_BASE_SESSIONS:
                dist = round((pc - low) / pc * 100, 2)
        for chk in (
            lambda: (None if (dist is not None and dist < TF.NOQTEH_MAX_DIST) else
                     f"فاصله تا کمینۀِ ۲۹ نشست {_fa_num(dist) if dist is not None else '—'}٪ است، "
                     f"فایل زیرِ {_fa_n(TF.NOQTEH_MAX_DIST)}٪ می‌خواهد"),
            lambda: vol_over(1.0),
            lambda: trades_over(TF.NOQTEH_TRADES),
        ):
            if (msg := chk()) is not None:
                return msg
        return None

    if fid == "f_jet":
        def ladder_miss() -> str | None:
            res = _row_ladder(r)
            if res is None or pl is None:
                return None              # پنجره کامل نبود — ادعایِ «نگذشتن» مجاز نیست
            if res <= 0 or pl > res:
                return None
            return f"آخرینِ {_fa_n(pl)} از سقفِ پلکانِ ۵۹ نشست ({_fa_n(res)}) نگذشت"

        for chk in (lambda: vol_over(TF.JET_VOL_MULT), lambda: bp_ge(TF.JET_BUYER_POWER),
                    closing_ge, plp_pos, ladder_miss,
                    lambda: trades_over(TF.JET_MIN_TRADES)):
            if (msg := chk()) is not None:
                return msg
        return None

    if fid in ("f_smart", "f_legal"):
        checks = [lambda: vol_over(TF.SMART_VOL_MULT), lambda: bp_ge(TF.SMART_BP_GE),
                  closing_ge, plp_pos]
        if fid == "f_legal":
            bi, sn = _num(r.get("buy_i_vol")), _num(r.get("sell_n_vol"))
            cap = (TF.LEGAL_SHARE_OF_TVOL * tvol) if tvol is not None else None

            def legal_buy_miss() -> str | None:
                if cap is None or bi is None or bi > cap:
                    return None
                return (f"حجمِ خریدِ حقوقی {_fa_n(bi)} نصفِ حجمِ نشست "
                        f"({_fa_n(cap)}) را پر نمی‌کند")

            def legal_sell_miss() -> str | None:
                if cap is None or sn is None or sn > cap:
                    return None
                return (f"حجمِ فروشِ حقیقی {_fa_n(sn)} نصفِ حجمِ نشست "
                        f"({_fa_n(cap)}) را پر نمی‌کند")
            checks += [legal_buy_miss, legal_sell_miss]
        for chk in checks:
            if (msg := chk()) is not None:
                return msg
        return None

    return None


def _tape_pass_text(r: dict, chain: tuple[str, ...]) -> tuple[str, str]:
    """نامِ برچسب‌هایی که همین ردیف واقعاً دارد — یک متن، دو مصرف (ماتریس و جدول)."""
    hits = [REG.BY_ID[f].name for f in chain
            if f in REG.BY_ID and _tri(r.get(FLAG_OF.get(f, f))) is True]
    if hits:
        return "TAPE_PASSED", "خورده شده: " + " · ".join(hits)
    if not chain:
        return "TAPE_NO_FILTER_DEFINED", "گامِ تابلو برایِ این شخص فیلتری ندارد"
    return "TAPE_PASSED_UNFLAGGED", "پرچمِ هیچ فیلترِ انتخابی رویِ این ردیف True نیست"


def _tape_pass_why(r: dict, chain: tuple[str, ...], params: dict[str, dict[str, Any]]) -> None:
    """دفترچۀ دلیل برایِ ردیفی که گامِ تابلو را خورده است.

    بی‌این، ردیفِ عبوری هیچ سطرِ دلیلی نداشت و جدول «تأیید» می‌نوشید — مالک
    (۱۴۰۵-۰۷-۲۰): «ینی چی تایید؟ باید برچسب‌هایِ تابلوخوانی را بنویسه». اینجا هم
    فقط آنچه درِ همان ردیف واقعاً True است نام برده می‌شود؛ عددی ساخته نمی‌شود.
    """
    code, text = _tape_pass_text(r, chain)
    _why_of(r).append({"stage": "tape", "seq": 0, "filter_id": ",".join(chain),
                       "status": PASS, "reason_code": code, "human_reason": text})


def _tape_stage_union(rows: list[dict], chain: tuple[str, ...],
                      params: dict[str, dict[str, Any]]) -> dict:
    """اجتماع: هر فیلتر رویِ کلِ جامعۀ ورودی شمرده می‌شود و عبور = کم‌از‌یک نشانه.

    «سنجیده‌نشده» رأیِ ورود نیست: ردیفی که هیچ فیلتری True‌اش نباشد ولی بعضی‌شان
    بی‌پرچم باشد، مثلِ پیشین UNAVAILABLE می‌ماند، و ردیفی که همه را صریح False
    دارد REJECT است با دلیلی که **همۀ** قیدها را نام می‌برد (درِ اشتراک فقطِ اولی
    نوشته می‌شد، چون صف واقعاً ترتیبی است).
    """
    steps: list[dict] = []
    matched_syms: set[str] = set()
    for fid in chain:
        f = REG.BY_ID.get(fid)
        if f is None:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
        flag = FLAG_OF[fid]
        yes = [r for r in rows if _tri(r.get(flag)) is True]
        no = [r for r in rows if _tri(r.get(flag)) is False]
        unknown = [r for r in rows if _tri(r.get(flag)) is None]
        matched_syms |= {str(r.get("symbol") or "") for r in yes}
        steps.append({
            "stage": "tape", "seq": len(steps) + 1, "filter_id": fid, "label": f.name,
            "input_count": len(rows), "matched_count": len(yes),
            "removed_count": len(no), "unmeasured_count": len(unknown),
            # درِ اجتماع چیزی به «بازماندۀ مرحلۀ قبل» تحویل داده نمی‌شود؛ هر
            # فیلتر شمارشِ مستقلِ خودش را رویِ همان جامعۀ ورودی دارد.
            "not_forwarded_count": 0,
            "parameter_set": params.get(fid) or {p.param_id: p.value for p in f.params
                                                 if p.value is not None},
            "source_ref": f"{f.source_file}#{f.source_sha256}",
            "formula_version": f.formula_version, "backend_impl": f.backend_impl,
            "status": REJECT if len(matched_syms) == 0 and no else PASS,
            "logic": "or",
        })
    survivors: list[dict] = []
    dropped: dict[str, list[str]] = {fid: [] for fid in chain}
    for r in rows:
        sym = str(r.get("symbol") or "")
        if sym in matched_syms:
            survivors.append(r)
            _tape_pass_why(r, chain, params)
            continue
        falses = [fid for fid in chain if _tri(r.get(FLAG_OF[fid])) is False]
        unknowns = [fid for fid in chain if _tri(r.get(FLAG_OF[fid])) is None]
        for fid in falses:
            dropped[fid].append(sym)
        if falses:
            parts = []
            for fid in falses[:3]:
                miss = _tape_miss(r, fid, params.get(fid))
                parts.append(f"{REG.BY_ID[fid].name} — {miss}" if miss
                             else REG.BY_ID[fid].name)
            if len(falses) > 3:
                parts.append(f"و {_fa_digits(len(falses) - 3)} قیدِ دیگر")
            r["_tape_why_text"] = "هیچ‌یک از فیلترهایِ انتخابی نخورد: " + " · ".join(parts)
            _why_of(r).append({"stage": "tape", "seq": 0,
                               "filter_id": ",".join(falses), "status": REJECT,
                               "reason_code": "TAPE_UNION_NO_MATCH",
                               "human_reason": r["_tape_why_text"],
                               "source": REG.BY_ID[falses[0]].source_file,
                               "formula_version": REG.BY_ID[falses[0]].formula_version})
        elif unknowns:
            fids = unknowns[0]
            why_txt = _unmeasured_why(r, fids) or "مبنایِ تاریخچۀ فایل را ندارد"
            r["_tape_why_text"] = f"{REG.BY_ID[fids].name} — {why_txt}، پس رد نشده"
            _why_of(r).append({"stage": "tape", "seq": 0,
                               "filter_id": ",".join(unknowns), "status": UNAVAILABLE,
                               "reason_code": f"TAPE_{fids.upper()}_UNMEASURED",
                               "human_reason": r["_tape_why_text"]})
    return {"survivors": survivors, "steps": steps, "dropped": dropped, "logic": "or"}


def filter_counts(rows: list[dict], chain: Iterable[str] = (),
                  logic: str = "and") -> dict[str, dict[str, int]]:
    """نامزدِ هر فیلتر درِ **همان مجموعه‌ای که الان رویِ میز است** (رأیِ مالک ۱۴۰۵-۰۷-۲۱).

    پیش از این عددِ کنارِ هر چیپ همیشه شمارِ مستقلِ همان فیلتر درِ کلِّ بازار
    بود؛ پس با یک چیپِ روشن، بقیه نمی‌گفتند از آن نامزدها چندتا با فیلترِ دیگر
    هم‌خوان‌اند. حالا مبنایِ شمارشِ هر چیپ، ردیف‌هایی است که *بقیۀ* چیپ‌هایِ
    روشن را پاس کرده‌اند (leave-one-out — تا خودِ چیپِ روشن هم به شمارۀ کلِّ
    ردیف‌ها نچسبد). درِ «اجتماع» همان قاعده با اتحادِ بقیه است.

    `matched + removed + unmeasured == input` برایِ هر چیپ برقرار می‌ماند، و
    `universe` همان جامعۀ کل است. بی‌هیچ چیپِ روشن، مبنایِ شمارش کلِّ جامعۀ
    غربالگری است — یعنی عددِ دیروز دست‌نخورده می‌ماند تا کاربر چیزی انتخاب کند.
    """
    ids = [f.filter_id for f in REG.FILTERS]
    bits: list[tuple[int, int]] = []
    for r in rows:
        p = u = 0
        for j, fid in enumerate(ids):
            t = _tri(r.get(FLAG_OF[fid]))
            if t is True:
                p |= 1 << j
            elif t is None:
                u |= 1 << j
        bits.append((p, u))
    sel = set(chain or ())
    universe = len(rows)
    out: dict[str, dict[str, int]] = {}
    for j, fid in enumerate(ids):
        others = [k for k, g in enumerate(ids) if g in sel and g != fid]
        mask = 0
        for k in others:
            mask |= 1 << k
        yes = no = un = base = 0
        for p, u in bits:
            if others and not ((p & mask) != 0 if logic == "or" else (p & mask) == mask):
                continue
            base += 1
            if p >> j & 1:
                yes += 1
            elif u >> j & 1:
                un += 1
            else:
                no += 1
        out[fid] = {"name": REG.BY_ID[fid].name, "matched": yes, "removed": no,
                    "unmeasured": un, "input": base, "universe": universe}
    return out


# ── ۱) تابلوخوانی: اشتراکِ ترتیبیِ زنجیره ─────────────────────────────────
def tape_stage(rows: list[dict], chain: tuple[str, ...],
               params: dict[str, dict[str, Any]] | None = None,
               logic: str = "and") -> dict:
    """U ∩ F1 ∩ F2 … (اشتراک) یا U ∪ F1 ∪ F2 … (اجتماع)، با شمارۀ واقعیِ هر فیلتر.

    `logic="or"` کلیدِ «اشتراک/اجتماع»ی است که مالک کنارِ همان چیپ‌هایِ تابلو
    خواست (۱۴۰۵-۰۷-۲۰). پیش‌فرض اشتراک است، پس رفتارِ امروز عوض نمی‌شود.
    """
    params = params or {}
    if (logic or "and").strip().lower() == "or" and chain:
        return _tape_stage_union(rows, chain, params)
    survivors = list(rows)
    steps: list[dict] = []
    dropped: dict[str, list[str]] = {}
    for fid in chain:
        f = REG.BY_ID.get(fid)
        if f is None:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
        flag = FLAG_OF[fid]
        before = len(survivors)
        matched: list[dict] = []
        removed: list[str] = []
        unmeasured: list[str] = []
        for r in survivors:
            sym = str(r.get("symbol") or "")
            v = _tri(r.get(flag))
            if v is False and _tape_unmeasurable(r, fid):
                # «سنجیده نشد» نه تأیید است نه رد: دلیلش درِ دفترچه UNAVAILABLE
                # است، ولی درِ فهرستِ منتقل‌شده به گامِ بعد هم نمی‌نشیند —
                # وگرنۀ «بی‌داده» خودش رأیِ ورود می‌شد. (رأیِ مالک برایِ پرچمِ
                # غایبِ مطلق — None — دست‌نخورده می‌ماند: آن ردیف حذف نمی‌شود.)
                unmeasured.append(sym)
            elif v is False:
                removed.append(sym)
            else:
                # True ماند؛ None هم حذف نمی‌شود ولی «سنجیده نشد» برچسب
                # می‌گیرد — قانونِ مالک: UNAVAILABLE ≠ REJECT.
                matched.append(r)
                if v is None:
                    unmeasured.append(sym)
        dropped[fid] = removed
        for r in survivors:
            # دفترچۀ دلیل همان داوریِ بالا را می‌نویسد، نه محاسبۀ دوم: اگر
            # پرچم False ولی سنجش‌ناشدنی بود، دلیل UNAVAILABLE است نه NO_MATCH.
            fv = _tri(r.get(flag))
            sym = str(r.get("symbol") or "")
            if fv is False and _tape_unmeasurable(r, fid):
                why_txt = _unmeasured_why(r, fid) or "مبنایِ تاریخچۀ فایل را ندارد"
                r["_tape_why_text"] = f"{f.name} — {why_txt}، پس رد نشده"
                _why_of(r).append({"stage": "tape", "seq": len(steps) + 1, "filter_id": fid,
                                   "status": UNAVAILABLE, "reason_code": f"TAPE_{fid.upper()}_UNMEASURED",
                                   "human_reason": r["_tape_why_text"],
                                   "input_count": before, "output_count": len(matched),
                                   "source": f.source_file, "formula_version": f.formula_version})
            elif fv is False:
                # «کدام بندِ فایل نخورد» با عددِ خودِ ردیف؛ اگر چیزی قابلِ اثبات
                # نبود همان متنِ عمومیِ صادق می‌ماند (ادعایِ جعلی ساخته نمی‌شود).
                miss = _tape_miss(r, fid, params.get(fid))
                r["_tape_why_text"] = (f"{f.name} — {miss}" if miss
                                       else f"{f.name} — نشانه در این نماد نیست")
                _why_of(r).append({"stage": "tape", "seq": len(steps) + 1, "filter_id": fid,
                                   "status": REJECT, "reason_code": f"TAPE_{fid.upper()}_NO_MATCH",
                                   "human_reason": r["_tape_why_text"],
                                   "input_count": before, "output_count": len(matched),
                                   "source": f.source_file, "formula_version": f.formula_version})
            elif fv is None:
                _why_of(r).append({"stage": "tape", "seq": len(steps) + 1, "filter_id": fid,
                                   "status": UNAVAILABLE, "reason_code": f"TAPE_{fid.upper()}_UNMEASURED",
                                   "human_reason": f"{f.name} — پرچم این نماد ساخته نشده",
                                   "input_count": before, "output_count": len(matched),
                                   "source": f.source_file, "formula_version": f.formula_version})
        steps.append({
            "stage": "tape",
            "seq": len(steps) + 1,
            "filter_id": fid,
            "label": f.name,
            "input_count": before,
            "matched_count": len(matched),
            # حسابِ گام باید ببندد: ورودی = عبورکرده + ردشده + سنجیده‌نشده.
            # پیش از این removed = before - matched بود و «سنجیده‌نشده» داخلِ
            # «رد» حل می‌شد؛ حالا هر سه جدا شمرده می‌شوند.
            "removed_count": len(removed),
            "unmeasured_count": len(unmeasured),
            "not_forwarded_count": before - len(matched),
            "parameter_set": params.get(fid) or {p.param_id: p.value for p in f.params if p.value is not None},
            "source_ref": f"{f.source_file}#{f.source_sha256}",
            "formula_version": f.formula_version,
            "backend_impl": f.backend_impl,
            # سه‌حالته و افتراقی: چیزی حذف شده (reject)، هیچ‌چیز حذف نشده ولی
            # بعضی پرچم‌ها ساخته نشده‌اند (pending)، یا همه‌چیز سنجیده و خورده شده.
            "status": REJECT if removed else (PENDING if unmeasured else PASS),
        })
        survivors = matched
    for r in survivors:
        # دلیلِ عبور هم درِ همان دفترچه نوشته می‌شود تا ستونِ «دلیل» برایِ ردیفِ
        # قبول‌شده خالی نماند (جدول آن‌وقت «تأیید» می‌گذاشت).
        _tape_pass_why(r, chain, params)
    return {"survivors": survivors, "steps": steps, "dropped": dropped, "logic": "and"}


# ── ۲) تکنیکال: هفتگی اول، بعد روزانه ─────────────────────────────────────
BRANCH_OF = {
    "up": "جت / پولبک",
    "down": "فیبوناچی / CHoCH",
    "range": "کف دوقلو / آخرین ساختار حمایت-مقاومت",
}

# ستون‌هایی که `funnel_tech_scan` برایِ هر نماد نگه می‌دارد و گامِ تکنیکال
# می‌خواند — همان نام‌هایِ `/api/screener`، پس یک داوری دو منبع دارد.
_TECH_KEYS = ("tech_trend_w", "tech_trend_d", "tech_trend_m", "tech_alignment",
              "tech_status", "tech_matrix_decision", "tech_matrix_setup",
              "tech_jet", "tech_choch_bull", "tech_choch_bear", "tech_double_bottom",
              "tech_range_break", "tech_fib_zone",
              # شاهدِ همان برچسب: عمقِ اصلاح و نقاطِ موج. رأیِ مالک ۲۰۲۶-۱۰-۱۸:
              # جدول باید «مقدارِ اصلاح» و «نقاطِ مبنایِ محاسبه» را نشان دهد، نه
              # فقط خوردن/نخوردنِ یکِ برچسب.
              "tech_fib_pct", "tech_fib_leg_dir", "tech_fib_leg_from", "tech_fib_leg_to",
              "tech_fib_leg_high", "tech_fib_leg_low",
              "tech_exit_verdict",
              "tech_exit_signals", "tech_hourglass_active", "tech_hourglass_action")



def _strategy_verdict(r: dict, st: dict[str, str], sigs: dict[str, str] | None, sym: str,
                      w: str | None, d: str | None, mat: str | None) -> tuple[str, list[dict]]:
    """داوریِ گامِ تکنیکال درِ «تکنیکال اول» — ازِ تنظیم، نه ازِ ارث.

    رأیِ مالک: قواعدِ استراتژیِ قدیمی خودکار منتقل نمی‌شود و شرطِ هر تایم‌فریم
    قابلِ انتخاب است:
      weekly_mode=off         هیچ وتویی ازِ هفتگی نمی‌آید (پیش‌فرضِ همین استراتژی)
      weekly_mode=require_up  همان قاعدۀ کلاسیک (رأیِ ۱۲): نزولی/خنثی ⇒ رد
      weekly_mode=reject_down فقط نزولی رد می‌شود؛ خنثی و بی‌داده رد نیست
      daily_mode=require_up   روزانۀ صعودی هم لازم است
    «بی‌داده» هیچ‌وقت رد نیست: PENDING/UNAVAILABLE سرِ جایش می‌ماند.
    """
    why: list[dict] = []
    wm = st.get("weekly_mode") or "off"
    dm = st.get("daily_mode") or "off"
    if not (w or d or mat):
        if sigs is not None and not sigs.get(sym):
            return UNAVAILABLE, [{"code": "TECH_NO_HISTORY",
                                  "text": "هیچ سابقۀ قیمتی در بانکِ محلی برایِ این نماد نیست"}]
        if sigs is not None:
            return PENDING, [{"code": "TECH_SCAN_PENDING",
                              "text": "داوریِ تکنیکال این نماد هنوز ساخته نشده — اسکن در جریان است"}]
        return UNAVAILABLE, [{"code": "TECH_UNMEASURED", "text": "تکنیکال این نماد سنجیده نشده"}]
    if wm == "require_up":
        if mat == "UNKNOWN":
            return PENDING, [{"code": "WEEKLY_UNMEASURED",
                              "text": "هفتگی به اندازهٔ کافی پیوت ندارد — رأی دادن حدس است"}]
        if w in ("down", "range"):
            return REJECT, [{"code": "WEEKLY_TREND_" + ("DOWN" if w == "down" else "NEUTRAL"),
                             "text": f"روند هفتگی {w} — شرطِ «فقط صعودی» ازِ تنظیماتِ استراتژی"}]
        if w != "up":
            return PENDING, [{"code": "WEEKLY_UNCLASSIFIED", "text": "هفتگی دسته‌بندی نشده"}]
        why.append({"code": "WEEKLY_TREND_UP", "text": "روند هفتگی صعودی (شرطِ برآورده)"})
    elif wm == "reject_down":
        if w == "down":
            return REJECT, [{"code": "WEEKLY_TREND_DOWN",
                             "text": "روند هفتگی نزولی — شرطِ «فقط نزولی رد شود»"}]
        why.append({"code": "WEEKLY_NOT_VETOING",
                    "text": f"هفتگی «{w or '-'}» وتو نیست (تنظیم: فقط نزولی رد می‌شود)"})
    else:
        why.append({"code": "WEEKLY_GATE_NOT_APPLIED",
                    "text": f"شرطِ هفتگی اعمال نمی‌شود (هفتگی: {w or '-'})"})
    if dm == "require_up":
        if d == "up":
            why.append({"code": "DAILY_TREND_UP", "text": "روند روزانه صعودی (شرطِ برآورده)"})
        elif d is None:
            return PENDING, why + [{"code": "DAILY_UNMEASURED",
                                    "text": "روزانه دسته‌بندی نشده — شرطِ روزانه سنجیده نشد"}]
        else:
            return REJECT, why + [{"code": "DAILY_TREND_NOT_UP",
                                   "text": f"روند روزانه «{d}» است و شرطِ «روزانۀ صعودی» لازم است"}]
    return PASS, why

def _hourglass_verdict(r: dict, sigs: dict[str, str] | None, sym: str) -> tuple[str, list[dict]]:
    """دروازۀِ «ساعتِ شنی»: رأی از سیگنالِ هفتگیِ MA52/RSI(5)، نه از داورِ روند.

    متنِ جزوه (jozve_FTS_handwright_pages_25-34.md:74 و چارت ۳ سطر ۱۴): «MA = 52
    تایم هفتگی؛ RSI = 5 تایم هفتگی» و «در تایم هفتگی یا بالاتر فقط کار می‌کند».
    همان سیگنال درِ production ساخته می‌شود (`api/chart.py` → `out["hourglass"]`
    → `funnel_tech_scan.tech_hourglass_active`)؛ این‌جا فقط *مصرف* می‌شود، چیزی
    محاسبه یا وضع نمی‌شود. آستانه‌ها رأیِ مالک‌اند و از همین رجیستری می‌آیند.

    چرا این شاخه لازم بود: `technical_gate` درِ رجیستری تعریف شده بود ولی هیچ‌جا
    خوانده نمی‌شد — یعنی `hourglass` و `custom[]` عیناً یکِ خروجی داشتند و
    «تغییرِ preset» برایِ کاربر فقط عوض‌شدنِ یکِ عنوان بود.
    """
    hg = _tri(r.get("tech_hourglass_active"))
    if hg is None:
        if sigs is not None and not sigs.get(sym):
            return UNAVAILABLE, [{"code": "TECH_NO_HISTORY",
                                  "text": "هیچ سابقۀ قیمتی در بانکِ محلی برایِ این نماد نیست"}]
        if sigs is not None:
            return PENDING, [{"code": "TECH_SCAN_PENDING",
                              "text": "داوریِ تکنیکال این نماد هنوز ساخته نشده — اسکن در جریان است"}]
        return UNAVAILABLE, [{"code": "TECH_UNMEASURED", "text": "تکنیکال این نماد سنجیده نشده"}]
    action = str(r.get("tech_hourglass_action") or "").strip()
    if hg:
        return PASS, [{"code": "HOURGLASS_WEEKLY_ACTIVE",
                       "text": "ساعتِ شنیِ هفتگی فعال — زیرِ MA=۵۲ هفتگی با RSI(۵)ِ اشباعِ کف"
                               + (f" ({action})" if action else "")}]
    return REJECT, [{"code": "HOURGLASS_INACTIVE",
                     "text": "ساعتِ شنیِ هفتگی فعال نیست — شرطِ MA=۵۲ و RSI(۵)ِ هفتگی ندارد"}]


#: وقتی ستونِ یک شرط مقدارِ داوری‌شده ندارد: «رد» یا «سنجیده نشد»؟
#: کمربندِ فیبو و روندِ روزانه **پاسخِ صریحِ** تحلیل‌اند (na/null یعنی «در این
#: ناحیه نیست») ⇒ reject؛ ولی بج‌هایِ بولیِ بی‌تحلیل و آرایۀ شاهدِ غایب یعنی
#: «ساخته نشد» ⇒ unmeasured. رأیِ مالک: بیداده نه قبول است نه رد.
_TECH_ABSENT_REJECT = ("tech_trend_d", "tech_fib_zone")


def _tech_signals(row: dict) -> list | None:
    raw = row.get("tech_exit_signals")
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    try:
        import json
        got = json.loads(str(raw))
    except Exception:  # noqa: BLE001 — دادهٔ خراب = سنجیده‌نشده، نه صفر
        return None
    return got if isinstance(got, list) else None



def _fib_evidence(row: dict, tf) -> dict:
    """شاهدِ کمربندِ فیبو: عمقِ اصلاح، نقاطِ موج، و فاصله تا لبه‌ها.

    رأیِ مالک: جدول باید مقدارِ اصلاح و نقاطِ مبنایِ محاسبه را نشان دهد. این‌ها
    عددِ تازه نیستند — `_fts_fib_zones` همان‌ها را می‌ساخت و اسکن فقط برچسبِ
    کمربند را نگه می‌داشت. بی‌ستونِ شاهد ⇒ None، نه صفر.
    """
    lp, hp = tf.param("fib_lo"), tf.param("fib_hi")
    lo = lp.value if lp else None
    hi = hp.value if hp else None
    pct = _num(row.get("tech_fib_pct"))
    out: dict[str, Any] = {"band_lo": lo, "band_hi": hi, "retrace_pct": pct,
                           "where": None, "distance_pct": None, "leg": None}
    if row.get("tech_fib_leg_from") or row.get("tech_fib_leg_dir"):
        out["leg"] = {"direction": str(row.get("tech_fib_leg_dir") or ""),
                      "from": row.get("tech_fib_leg_from"), "to": row.get("tech_fib_leg_to"),
                      "low": _num(row.get("tech_fib_leg_low")),
                      "high": _num(row.get("tech_fib_leg_high"))}
    if pct is not None and lo is not None and hi is not None:
        if pct < lo:
            out["where"], out["distance_pct"] = "below", round(lo - pct, 2)
        elif pct > hi:
            out["where"], out["distance_pct"] = "above", round(pct - hi, 2)
        else:
            out["where"], out["distance_pct"] = "inside", 0.0
    return out


def _fib_reason(tf, ev: dict, status: str) -> str:
    """یک خطِ عددی: چه عمقی، رویِ چه موجی، چقدر تا کمربند."""
    pct, lo, hi = ev.get("retrace_pct"), ev.get("band_lo"), ev.get("band_hi")
    band = f"{_fa_num(lo)}-{_fa_num(hi)}%" if lo is not None else "-"
    if pct is None:
        return (f"{tf.name}: عمقِ اصلاح درِ این ردیف ساخته نشده — داوریِ این نماد "
                "پیشِ افزودنِ ستونِ شاهد ساخته شده (بازنشانیِ اسکن لازم دارد)")
    leg = ev.get("leg") or {}
    basis = ""
    if leg.get("from"):
        arrow = "سقف به کف" if leg.get("direction") == "down" else "کف به سقف"
        basis = (f" | موجِ {arrow} {leg['from']} تا {leg.get('to')}"
                 f" ({_fa_n(leg.get('low'))} تا {_fa_n(leg.get('high'))})")
    if status == PASS:
        return f"اصلاحِ {_fa_num(pct)}% داخلِ کمربندِ {band}{basis}"
    side = {"below": "پایین‌تر از", "above": "بالاتر از"}.get(ev.get("where"), "خارج از")
    gap = ev.get("distance_pct")
    return (f"اصلاحِ {_fa_num(pct)}% — {side} {band}"
            + (f"، {_fa_num(gap)} واحدِ درصدی فاصله" if gap else "") + basis)


def _tech_check(row: dict, tf, gate_status: str, settings: dict | None = None) -> dict:
    """خوردنِ یک شرطِ تکنیکال از همان ستونی که `funnel_tech_scan` ساخته است."""
    out: dict = {"filter_id": tf.filter_id, "label": tf.name, "role": tf.role,
                 "column": tf.column, "source": tf.source, "origin": tf.origin}
    if tf.column == "tech_fib_zone":
        out["measure"] = _fib_evidence(row, tf)
    if tf.role == "gate":
        # خاموش‌بودنِ شرطِ هفتگی باید *دیده* شود، نه اینکه غیبش بزنند.
        if (settings or {}).get("weekly_mode") == "off":
            out.update({"status": NOT_REQUIRED, "value": row.get(tf.column),
                        "reason_code": "WEEKLY_GATE_NOT_APPLIED",
                        "human_reason": "شرطِ روند هفتگی درِ این استراتژی خاموش است "
                                        "(تنظیم: اعمال نشود) — وتویی ازِ هفتگی نمی‌آید"})
            return out
        # گیتِ هفتگی را دوباره حساب نمی‌کنیم: رأیِ خودِ داورِ رسمی برگردانده می‌شود.
        out.update({"status": gate_status, "value": row.get(tf.column),
                    "reason_code": "TECH_GATE_" + gate_status.upper(),
                    "human_reason": "وتوی رسمیِ روند هفتگی (همان داورِ `trend_matrix`)"})
        return out
    val = row.get(tf.column)
    want = tf.expect or {}
    if "signal" in want:
        # معنای «دیدنِ شاهد» به نقشِ فیلتر است: درِ `risk` شاهدِ ثبت‌شده نماد را
        # حذف می‌کند (نه اینکه شرط برآورده شده باشد) و نبودش یعنی «پاک است».
        sigs = _tech_signals(row)
        got = want["signal"] in (sigs or [])
        if sigs is None:
            status = UNAVAILABLE
        elif tf.role == "risk":
            status = REJECT if got else PASS
        else:
            status = PASS if got else REJECT
        tok = want["signal"].upper()
        if status == UNAVAILABLE:
            code, txt = f"TECH_{tok}_ABSENT", "لایۀ شاهد ساخته نشده (بی‌تحلیل)"
        elif tf.role == "risk":
            code = "TECH_RISK_" + tok
            txt = (f"«{tf.name}» رویِ این نماد ثبت شده — با انتخابِ شما رد می‌شود"
                   if status == REJECT else f"«{tf.name}» ثبت نشده")
        else:
            code = "TECH_" + tok
            txt = f"«{tf.name}» ثبت شده" if status == PASS else f"«{tf.name}» ثبت نشده"
        out.update({"status": status, "value": ",".join(sigs or []) or None,
                    "signal": want["signal"], "reason_code": code, "human_reason": txt})
        return out
    if "truthy" in want:
        hit = val in (1, True)
        if val in (1, True, 0, False):
            status = (REJECT if (hit and tf.role == "risk") else
                      (PASS if hit else REJECT))
        else:
            status = REJECT if tf.column in _TECH_ABSENT_REJECT else UNAVAILABLE
    else:  # equals
        target = want.get("equals")
        if val is None or val == "":
            status = REJECT if tf.column in _TECH_ABSENT_REJECT else UNAVAILABLE
        else:
            status = PASS if str(val) == str(target) else REJECT
    reason = None
    if tf.column == "tech_fib_zone":
        reason = _fib_reason(tf, out["measure"], status)
    out.update({"status": status, "value": val,
                "reason_code": tf.filter_id.upper() + "_" + status.upper(),
                "human_reason": reason or (
                    f"{tf.name}: خورده شد" if status == PASS else
                    (f"{tf.name} — ستونِ {tf.column} مقدارِ داوری‌شده ندارد"
                     if status == UNAVAILABLE else f"{tf.name}: نخورد"))})
    return out


def technical_stage(rows: list[dict], tech: dict[str, dict] | None = None,
                    sigs: dict[str, str] | None = None,
                    gate: str | None = None,
                    tech_chain: tuple[str, ...] = (),
                    settings: dict[str, str] | None = None) -> dict:
    """گیتِ تکنیکال — داور همان موتورِ production است، نه محاسبۀ دوباره.

    `tech` ردیف‌هایِ `funnel_tech_scan` است (نماد → ستون‌هایِ tech_*). چرا لازم
    شد: `api/screener.py` تکنیکال را فقط برایِ `watchlist_max=50` ردیفِ اول
    می‌ساخت، پس رسیدگانِ تابلو که درِ آن پنجاه نبودند هیچ رأیی نداشتند — یعنی
    یک سقفِ *تصمیم*، نه نمایش. با این ورودی، هر نمادی که به این گام می‌رسد
    داوری می‌شود؛ چیزی حذف نمی‌شود و چیزی هم حدس زده نمی‌شود:

      سابقهٔ قیمتی دارد ولی اسکن هنوز نوبتش نشده  ⇒ PENDING / TECH_SCAN_PENDING
      هیچ سابقهٔ قیمتی در بانک ندارد               ⇒ UNAVAILABLE / TECH_NO_HISTORY
      اسکن شده و تحلیل رأیی نداده                  ⇒ UNAVAILABLE / TECH_UNMEASURED

    بی‌`sigs` (فراخوانیِ مستقیمِ گارد) رفتارِ پیشین می‌ماند: TECH_UNMEASURED.
    `gate` دروازۀِ خودِ preset است (`REG.TREND_GATE` یا `REG.HOURGLASS_GATE`).
    """
    gate = gate or REG.TREND_GATE
    st = dict(settings or {})
    kept, steps, dropped = [], [], []
    counts = {PASS: 0, REJECT: 0, PENDING: 0, UNAVAILABLE: 0}
    for r in rows:
        sym = str(r.get("symbol") or "")
        t = (tech or {}).get(sym)
        if t:
            # اسکنِ تمامِ جهان تازه‌ترین منبع است؛ ستون‌های tech_* رویِ ردیف از
            # پاسخِ کش‌شدۀ /api/screener می‌آیند (کشِ ۱۲ ساعته). بی‌این ترتیب،
            # رأیِ کهنهٔ اسکرینر رأیِ تازهٔ اسکن را درِ همان ۵۰ ردیفِ اول سایه
            # می‌کرد — یعنی دو منبع، یک داوریِ غیرقابل‌اتکا.
            r = {**r, **{k: t[k] for k in _TECH_KEYS if t.get(k) is not None}}
        w = (r.get("tech_trend_w") or "").strip() or None
        d = (r.get("tech_trend_d") or "").strip() or None
        mat = (r.get("tech_matrix_decision") or "").strip() or None
        why: list[dict[str, str]] = []
        if gate == REG.HOURGLASS_GATE:
            status, why = _hourglass_verdict(r, sigs, sym)
        elif gate == REG.NO_GATE:
            status, why = _strategy_verdict(r, st, sigs, sym, w, d, mat)
        elif not (w or d or mat):
            if sigs is not None and not sigs.get(sym):
                status = UNAVAILABLE
                why.append({"code": "TECH_NO_HISTORY",
                            "text": "هیچ سابقۀ قیمتی در بانکِ محلی برایِ این نماد نیست"})
            elif sigs is not None:
                status = PENDING
                why.append({"code": "TECH_SCAN_PENDING",
                            "text": "داوریِ تکنیکال این نماد هنوز ساخته نشده — اسکن در جریان است"})
            else:
                status = UNAVAILABLE
                why.append({"code": "TECH_UNMEASURED", "text": "تکنیکال این نماد سنجیده نشده"})
        elif mat == "UNKNOWN":
            # کمتر از دو پیوتِ کاملِ هفتگی: رأی دادن درِ اینجا یعنی حدس زدن.
            status = PENDING
            why.append({"code": "WEEKLY_UNMEASURED", "text": "هفتگی به اندازهٔ کافی پیوت ندارد"})
        elif w == "down":
            status = REJECT
            why.append({"code": "WEEKLY_TREND_DOWN", "text": "روند هفتگی نزولی — وتوی قطعی"})
        elif w == "range":
            status = REJECT
            why.append({"code": "WEEKLY_TREND_NEUTRAL", "text": "روند هفتگی خنثی — وتوی قطعی"})
        elif w == "up":
            status = PASS
            why.append({"code": "WEEKLY_TREND_UP", "text": "روند هفتگی صعودی"})
            why.append({"code": "DAILY_BRANCH",
                        "text": f"روزانه {d or '—'} ⇒ شاخهٔ {BRANCH_OF.get(d or '', '—')}"})
        else:
            status = PENDING
            why.append({"code": "WEEKLY_UNCLASSIFIED", "text": "هفتگی دسته‌بندی نشده"})
        # ستاپ‌ها شاهداند: هیچ‌وقت وتوی هفتگی را نمی‌شکنند (رأیِ مالک).
        evidence = [k for k in ("tech_jet", "tech_choch_bull", "tech_double_bottom", "tech_range_break")
                    if _tri(r.get(k)) is True]
        # شرط‌های انتخابی کاربر روی رأی گیت می‌نشینند و گیت را نمی‌شکنند: هیچ
        # ترکیبی از فیلترهای اختیاری نمادِ مردودِ هفتگی را ردیف نمی‌کند.
        checks: list[dict] = []
        for tf in (REG.get_tech_filter(fid) for fid in tech_chain):
            chk = _tech_check(r, tf, status, st)
            checks.append(chk)
            if chk["filter_id"] in TECH_GATE_IDS:
                continue
            if chk["status"] == REJECT and status == PASS:
                status = REJECT
                why.append({"code": chk["reason_code"], "text": chk["human_reason"]})
            elif chk["status"] == UNAVAILABLE and status == PASS:
                status = PENDING
                why.append({"code": "TECH_FILTER_UNMEASURED",
                            "text": f"{chk['label']} سنجیده نشد؛ حکمِ قطعی داده نمی‌شود"})
            elif chk["status"] == PASS and status == PASS:
                why.append({"code": chk["reason_code"], "text": chk["human_reason"]})
        counts[status] += 1
        if status == PASS:
            kept.append(r)
        else:
            dropped.append(sym)
        steps.append({
            "stage": "technical", "symbol": sym, "status": status,
            "weekly": w, "daily": d, "branch": BRANCH_OF.get(d or "", None),
            "matrix": mat, "evidence": evidence,
            "points": _num(r.get("tech_points")) if r.get("tech_points") is not None else None,
            "checks": checks,
            # زمانِ ساختِ همین داوری از خودِ ردیفِ `funnel_tech_scan`. تاریخِ
            # خودِ ماشه (یکِ_specificِ نماد درِ کدام کندل خورده) درِ بانکِ اسکن
            # ذخیره نمی‌شود، پس اینجا عددی نمی‌سازیم: این ستون «تاریخِ داوری»
            # خوانده می‌شود.
            "scan_as_of": (t or {}).get("as_of"),
            "why": why,
        })
    # شمارشِ هر شرط رویِ همان ورودیِ گام — برایِ عددِ کنارِ چیپ‌ها (همان کاری که
    # `filter_counts` برایِ تابلو می‌کند).
    fcounts: dict[str, dict] = {}
    for st in steps:
        for chk in st.get("checks") or []:
            b = fcounts.setdefault(chk["filter_id"], {PASS: 0, REJECT: 0, UNAVAILABLE: 0, PENDING: 0})
            b[chk["status"]] = b.get(chk["status"], 0) + 1
    return {"survivors": kept, "decisions": steps, "counts": counts, "dropped": dropped,
            "chain": list(tech_chain), "filter_counts": fcounts}


# ── ۳) بنیادی: عبور با حداقلِ سه شاخصِ PASS، سه حالتِ سخت‌گیری ─────────────
BLOCKERS = ("i1", "i2", "i3")
SUPPORTING = ("i4", "i5")
IND_KEYS = (*BLOCKERS, *SUPPORTING)
IND_LABEL = {"i1": "I1 رشد فروش", "i2": "I2 EPS سه‌ساله", "i3": "I3 حاشیه سود ناخالص",
             "i4": "I4 فروش ۱۲ماه ÷ ارزش بازار", "i5": "I5 نرخ‌گذاری"}
# رأیِ مالک (مأموریت ۱۴۰۵-۰۷-۲۱): نمادی از غربال بنیادی عبور می‌کند که **حداقل
# سه شاخص PASS** داشته باشد — حتی اگر بعضی شاخص‌ها رد شده باشند یا داده نداشته
# باشند. شاخصِ فاقد داده هرگز PASS شمرده نمی‌شود.
FUND_MIN_PASS = 3
# چهارحالۀ یک شاخص — همان واژۀ رسمیِ قیف، نه واژۀ تازه:
#   PASS / REJECT (=FAIL) / PENDING (=داده‌ای نیست) / NOT_REQUIRED (=کاربرد ندارد)
NA_SIGNALS = {"i2": "i2_na", "i3": "i3_na", "i4": "i4_na"}
# «نظر ندادنِ عمدی» را خودِ اسکرینر می‌گوید (api/screener.py:514): سابقۀ
# تلفیقی برایِ I2، و معافیتِ صنعت/کسب‌وکار برایِ I3 و I4. نبودِ حکم با
# بی‌کاربرد بودن یکی نیست — رأیِ ۱۳ و ۱۶ جزوه.


def _ind_state(k: str, mark: bool | None, row: dict) -> str:
    """چهارحالۀ یک شاخص — PASS / REJECT / PENDING / NOT_APPLICABLE.

    سیگنالِ NOT_APPLICABLE فقط از خودِ داده خوانده می‌شود (`i2_na`/`i3_na`/
    `i4_na`): جزوه مبنایِ تلفیقی یا نبودِ سطرِ بهای تمام‌شده را «نظر ندادن»
    می‌داند، نه «رد» و نه «داده نرسیده». هیچ شاخصِ بی‌داده‌ای به PASS یا FAIL
    جعلی تبدیل نمی‌شود.
    """
    if row.get(NA_SIGNALS.get(k, "_")) is True:
        return NOT_APPLICABLE
    if mark is None:
        return PENDING
    return PASS if mark else REJECT


def _fund_note(n_pass: int, n_fail: int, n_unknown: int, n_na: int) -> str:
    """علتِ عبور، ساخته‌شده از شمارِ واقعیِ خودِ داوری — نه متنِ ثابت."""
    parts = [f"{_fa_digits(n_pass)} شاخص تأیید شد"]
    if n_fail:
        parts.append(f"{_fa_digits(n_fail)} شاخص رد شد")
    if n_unknown:
        parts.append(f"اطلاعات {_fa_digits(n_unknown)} شاخص موجود نیست")
    if n_na:
        parts.append(f"{_fa_digits(n_na)} شاخص برایِ این نماد کاربرد ندارد")
    return "عبور با ملاحظات: " + "؛ ".join(parts)


def _fund_counts(states: dict[str, str]) -> tuple[int, int, int, int]:
    """(PASS, FAIL, بی‌داده, بی‌کاربرد) از وضعیت‌هایِ چهارحالۀ یک ردیف."""
    return (sum(1 for s in states.values() if s == PASS),
            sum(1 for s in states.values() if s == REJECT),
            sum(1 for s in states.values() if s == PENDING),
            sum(1 for s in states.values() if s == NOT_APPLICABLE))


def indicator_states(row: dict) -> dict[str, str]:
    """وضعیتِ چهارحالۀ هر شاخص از ردیفِ خام — تنها تعریفِ این نگاشت.

    جدولِ غربالگری و قیف هر دو همین را می‌خوانند؛ بی‌این، یک ردیف درِ دو
    صفحه دو حکم می‌گرفت (همان اشتباهی که درِ `_screen_verdict` ثبت شده بود).
    """
    return {k: _ind_state(k, _tri(row.get(f"{k}_pass")), row) for k in IND_KEYS}


def passes_fundamental(row: dict) -> bool:
    """قاعدهٔ عبور: حداقل `FUND_MIN_PASS` شاخصِ واقعاً PASS (رأیِ مالک ۱۴۰۵-۰۷-۲۱)."""
    return _fund_counts(indicator_states(row))[0] >= FUND_MIN_PASS


def fund_caveat(row: dict) -> bool:
    """آیا این عبور «با ملاحظات» است؟ (رد یا دادهٔ ناقص رویِ میز هست)"""
    n_pass, n_fail, n_unknown, n_na = _fund_counts(indicator_states(row))
    return n_pass >= FUND_MIN_PASS and bool(n_fail or n_unknown or n_na)


def fundamental_stage(rows: list[dict], mode: str = "standard",
                      exceptions: dict[str, list[str]] | None = None,
                      now: int | None = None) -> dict:
    """عبور = حداقل `FUND_MIN_PASS` شاخص PASS (رأیِ مالک ۱۴۰۵-۰۷-۲۱).

    پیش از این سه بلاکر (I1∧I2∧I3) حکم را تنهایی می‌دادند؛ حالا شمارِ شاخص‌هایِ
    واقعاً‌تأییدشده ملاک است، پس «۳ PASS + ۲ فاقد داده» و «۴ PASS + ۱ رد» عبور
    می‌کنند — با نشانِ «عبور با ملاحظات». کمتر از سه PASS عبور نیست؛ و اگر
    نماد هنوز شاخصِ سنجیده‌نشده دارد، حکمش PENDING است نه ردِ قطعی (بی‌داده ≠
    مردود). حالتِ `hard` همان سخت‌گیریِ همیشگی را نگه می‌دارد (هر پنج)، چون
    کلیدِ سخت‌گیریِ خودِ مالک است و زیرِ قاعدهٔ عمومی نمی‌آید.

    امتیازِ عددی (`score`/`primary_score`) و ترتیبِ رتبه‌بندی هیچ‌کدام دست
    نمی‌خورند؛ ملاحظات فقط *نشان* داده می‌شود، نه وزنِ پنهان.
    """
    exceptions = exceptions or {}
    now = now or int(time.time())
    kept, steps, dropped = [], [], []
    counts = {PASS: 0, REJECT: 0, PENDING: 0, UNAVAILABLE: 0}
    for r in rows:
        sym = str(r.get("symbol") or "")
        marks = {k: _tri(r.get(f"{k}_pass")) for k in IND_KEYS}
        states = indicator_states(r)
        detail = [{
            "indicator": k.upper(), "label": IND_LABEL[k], "status": marks[k],
            "state": states[k],
            "value": _num(r.get({"i1": "rev_growth", "i2": "eps_last", "i3": "gross_margin",
                                 "i4": "sales_to_mcap"}.get(k, "") or "_")),
            "threshold": r.get({"i1": "growth_min", "i3": "margin_min", "i4": "sales_to_mcap_min"}.get(k, "") or "_"),
            "as_of": r.get("as_of"), "source": "codal",
        } for k in IND_KEYS]
        n_pass, n_fail, n_unknown, n_na = _fund_counts(states)
        failed = [k for k in IND_KEYS if states[k] == REJECT]
        unknown = [k for k in IND_KEYS if states[k] == PENDING]
        why: list[dict[str, str]] = []
        granted = [k.upper() for k in exceptions.get(sym, []) if k.upper() in ("I1", "I2", "I3")]
        # استثنا همان کاری را می‌کند که همیشه می‌کرد: شاخصِ بخشوده‌شده جایِ
        # ردشده را می‌گیرد. بی‌این، «استثنای صریح» زیرِ قاعدهٔ تازه بی‌اثر می‌شد.
        grant_keys = [k for k in ("i1", "i2", "i3") if k.upper() in granted and states[k] != PASS]
        # canonical بدونِ بخشش سنجیده می‌شود، effective با آن — دو حکمِ جدا.
        counted = n_pass + (len(grant_keys) if mode == "exception" else 0)

        def _verdict(n: int) -> str:
            if mode == "hard":
                return REJECT if failed else (PENDING if unknown else PASS)
            if n >= FUND_MIN_PASS:
                return PASS
            return PENDING if unknown else REJECT
        status = _verdict(n_pass)
        caveat = bool(n_fail or n_unknown or n_na)
        if mode == "hard":
            why += ([{"code": f"FUND_{k.upper()}_REJECT", "text": f"{IND_LABEL[k]} تأیید نشده"} for k in failed]
                    or [{"code": f"FUND_{k.upper()}_MISSING", "text": f"{IND_LABEL[k]} سنجیده نشده"} for k in unknown])
        else:  # standard و exception هر دو با قاعدهٔ «حداقل سه PASS» می‌سنجند
            if status == PENDING:
                why += [{"code": f"FUND_{k.upper()}_MISSING",
                         "text": f"{IND_LABEL[k]} گزارشش نرسیده — رد نیست، سنجیده نشده"} for k in unknown]
            elif status == REJECT:
                why.append({"code": "FUND_BELOW_MIN_PASS",
                            "text": f"{_fa_digits(n_pass)} شاخص از {_fa_digits(FUND_MIN_PASS)} تأیید لازم"})
            # نامِ شاخص‌هایِ ردشده نوشته می‌شود؛ «با ملاحظات» باید بگوید
            # کدام‌ها رد شده‌اند، نه فقط این‌که چندتا.
            why += [{"code": f"FUND_{k.upper()}_REJECT", "text": f"{IND_LABEL[k]} زیرِ کف"} for k in failed]
            if status == PASS and unknown:
                why += [{"code": f"FUND_{k.upper()}_MISSING",
                         "text": f"{IND_LABEL[k]} سنجیده نشده"} for k in unknown]
        canonical = status
        effective = _verdict(counted)
        if effective == PASS and canonical != PASS:
            why.append({"code": "EXCEPTION_APPLIED",
                        "text": "استثنای بنیادی: " + "، ".join(sorted(granted))})
        if effective == PASS and caveat:
            why.append({"code": "FUND_PASSED_WITH_CAVEATS", "text": _fund_note(n_pass, n_fail, n_unknown, n_na)})
        counts[status] += 1
        row_out = dict(r)
        row_out["_fund_canonical"] = canonical
        row_out["_fund_effective"] = effective
        row_out["_fund_caveat"] = bool(effective == PASS and caveat)
        row_out["_fund_exceptions"] = sorted(granted) if effective == PASS and granted else []
        if effective == PASS:
            kept.append(row_out)
        else:
            dropped.append(sym)
        steps.append({
            "stage": "fundamental", "symbol": sym, "mode": mode,
            "canonical": canonical, "effective": effective,
            "caveat": row_out["_fund_caveat"],
            "exceptions": row_out["_fund_exceptions"],
            "indicators_passed": n_pass, "indicators_failed": n_fail,
            "indicators_unknown": n_unknown, "indicators_na": n_na,
            "min_pass_required": FUND_MIN_PASS,
            "score": _num(r.get("score")), "primary_score": _num(r.get("primary_score")),
            "indicators": detail, "why": why,
        })
    return {"survivors": kept, "decisions": steps, "counts": counts, "dropped": dropped}


# ── ۴) تحویل: رتبۀ شفاف با دادهٔ موجود ───────────────────────────────────
def handover_stage(rows: list[dict], tape: dict, tech: dict, fund: dict,
                   assembly_vetoed: Iterable[str] = ()) -> dict:
    """بهترین‌ها اول — بی‌scoreِ ساختگی. ترتیبِ ثابت و بازتولیدشدنی."""
    veto = {str(s) for s in assembly_vetoed}
    tech_by = {d["symbol"]: d for d in tech["decisions"]}
    fund_by = {d["symbol"]: d for d in fund["decisions"]}
    rank_by = {str(r.get("symbol")): i for i, r in enumerate(rows)}
    out = []
    for r in rows:
        sym = str(r.get("symbol") or "")
        f = fund_by.get(sym) or {}
        t = tech_by.get(sym) or {}
        exc = f.get("exceptions") or []
        out.append({
            "symbol": sym,
            "name": r.get("name") or "",
            "final": REJECT if sym in veto else PASS,
            "exception": bool(exc),
            # «عبور با ملاحظات» از همان یک داوریِ بنیادی می‌آید؛ اینجا داورِ
            # دوم ساخته نمی‌شود، فقط پرچمِ نشان به جدولِ تحویل می‌رسد.
            "fund_caveat": bool(f.get("caveat")),
            "fund_passed": _num(f.get("indicators_passed")),
            "fund_score": _num(r.get("score")),
            "tech_points": _num(r.get("tech_points")),
            "backend_rank": rank_by.get(sym),
            "weekly": t.get("weekly"), "daily": t.get("daily"), "branch": t.get("branch"),
            "exceptions": exc,
            "assembly_veto": sym in veto,
            "why": ([{"code": "ASSEMBLY_VETO", "text": "وتوی مجمع — زمان‌بندیِ ورود"}]
                    if sym in veto else list(t.get("why") or []) + list(f.get("why") or [])),
            "chain": [s["filter_id"] for s in tape["steps"]],
        })
    # ترتیبِ ترجیحیِ مالک: حکمِ نهایی → بی‌استثنا → قدرتِ بنیادی → شواهدِ
    # تکنیکال → رتبۀ رسمیِ بک‌اند → نماد (برایِ پایداری). هیچ وزنِ پنهانی نیست.
    out.sort(key=lambda e: (e["final"] != PASS, e["exception"],
                            -(e["fund_score"] if e["fund_score"] is not None else -1),
                            -(e["tech_points"] if e["tech_points"] is not None else -1),
                            e["backend_rank"] if e["backend_rank"] is not None else 10 ** 9,
                            e["symbol"]))
    for i, e in enumerate(out, 1):
        e["display_rank"] = i
    return {"entries": out, "counts": {
        PASS: sum(1 for e in out if e["final"] == PASS),
        REJECT: sum(1 for e in out if e["final"] == REJECT),
        "exception": sum(1 for e in out if e["exception"]),
    }}


# ── نمایش ──────────────────────────────────────────────────────────────────
# این بلوک فقط «ستون‌هایی که جدول می‌خواند» را از همان ردیفِ ورودی برمی‌دارد.
# هیچ قیاسِ آستانه‌ای درِ آن نیست؛ اگر روزی چیزی شبیه `if x > th` اینجا ظاهر شد،
# آن یک داورِ دوم است نه نمایش.
_LABEL_OF = {"f_clock": "ساعت", "f_susp": "مشکوک", "f_jet": "جت", "f_roobi": "کف‌روب",
             "f_noqteh": "نقطه", "f_smart": "پول هوشمند", "f_legal": "کد به کد"}


def _display(r: dict, *, patterns: list[str] | None = None,
             status: dict[str, str] | None = None,
             why: dict[str, list[dict]] | None = None,
             chain: tuple[str, ...] = (),
             tech: dict | None = None,
             fund: dict | None = None) -> dict:
    """یک ردیفِ آمادهِ رندر برایِ جدول — با traceِ همان نماد.

    `tech` همان گامِ داوریِ تکنیکال است. بی‌آن، پنج ستونِ جدولِ تکنیکال از
    `tech_trend_w/d`ِ ردیفِ تابلو خوانده می‌شدند که فقط درِ مسیرِ اسکرینر پر
    می‌شوند؛ درِ غربالگری پس «هفتگی/روزانه/شاخه/شواهد/امتیاز» برایِ همهٔ ردیف‌ها
    '—' می‌ماند (سنجشِ زنده: ۵ ستونِ خالی در ۱۹ ردیفِ دیدنی) در حالی که همان
    داوری درِ متنِ «دلیل» نوشته شده بود. داوریِ دوم اینجا ساخته نمی‌شود؛ فقط
    خروجیِ همان گام به ستون‌هایش می‌رسد."""
    sym = str(r.get("symbol") or "")
    tv = tech or {}
    w = r.get("tech_trend_w") or tv.get("weekly")
    d = r.get("tech_trend_d") or tv.get("daily")
    ev = [k for k in ("tech_jet", "tech_choch_bull", "tech_double_bottom",
                      "tech_range_break") if _tri(r.get(k)) is True] or (tv.get("evidence") or [])
    pts = r.get("tech_points")
    return {
        "symbol": sym,
        "name": r.get("name") or "",
        "sector": r.get("sector_name") or r.get("sector") or "",
        "last": _num(r.get("p_last")),
        "closing": _num(r.get("p_closing")),
        # بدنۀِ همین نشست، عیناً از همان ردیفِ تابلو (`p_first`/`p_max`/`p_min`
        # که از ۱۴۰۵-۰۷-۱۹ رویِ سیم می‌آیند). ستونِ «کندل روز» درِ قیف همین
        # سه را می‌خواهد؛ نبودنشان «—» است، نه کندلِ ساختگی.
        "first": _num(r.get("p_first")), "high": _num(r.get("p_max")),
        "low": _num(r.get("p_min")),
        "change_pct": _num(r.get("percent_change")),
        "vol_ratio": _num(r.get("vol_ratio")),
        # حجمِ همین نشست برایِ ستونِ «حجم» جدولِ استراتژی — بدونِ آن ستون همیشه
        # «—» می‌ماند (ردیفِ قیف حجم نمی‌آورد و رابط حق ساختنش را ندارد).
        "tvol": _num(r.get("tvol")),
        "patterns": patterns if patterns is not None
        else [_LABEL_OF[f] for f in REG.filter_ids() if _tri(r.get(f)) is True],
        "status": status or {},
        "why": why or {},
        "chain": list(chain),
        "score": _num(r.get("score")),
        "primary_score": _num(r.get("primary_score")),
        "weekly": w, "daily": d,
        "branch": BRANCH_OF.get(str(d or ""), None) or tv.get("branch"),
        "matrix": r.get("tech_matrix_decision") or tv.get("matrix"),
        "tech_status": r.get("tech_status") or tv.get("status"),
        "tech_points": _num(pts) if pts is not None else _num(tv.get("points")),
        "evidence": ev,
        "fib_zone": r.get("tech_fib_zone"),
        "hourglass": _tri(r.get("tech_hourglass_active")),
        # چهارحالۀ هر شاخص از خودِ گامِ بنیادی خوانده می‌شود (نه دوباره ساختنش):
        # PASS / REJECT / PENDING (=بی‌داده) / NOT_REQUIRED (=کاربرد ندارد).
        "inds": {d["indicator"].lower(): d.get("state") or _tri(r.get(f"{d['indicator'].lower()}_pass"))
                 for d in (fund or {}).get("indicators") or []} or
                {k: _tri(r.get(f"{k}_pass")) for k in IND_KEYS},
        "fund_caveat": bool((fund or {}).get("caveat")),
        "fund_passed": _num((fund or {}).get("indicators_passed")),
        "fund_min_pass": FUND_MIN_PASS,
        "ind_values": {"i1": _num(r.get("rev_growth")), "i2": _num(r.get("eps_last")),
                       "i3": _num(r.get("gross_margin")), "i4": _num(r.get("sales_to_mcap"))},
        # برآوردِ فروشِ ۱۲ ماهه (میلیارد تومان) — برایِ اینکه رابط بتواند
        # نسبتِ **زنده** را با ارزشِ بازارِ همین ردیف نشان بدهد بدونِ اینکه
        # حکمِ موتور را دوباره بسازد (رأیِ مالک ۱۴۰۵-۰۷-۱۷، بندِ ۱).
        "annual_sales_bt": _num(r.get("annual_sales_bt")),
        "pricing_mode": r.get("pricing_mode"),
        "excluded": bool(r.get("excluded")),
        "exclusion_reasons": r.get("exclusion_reasons") or "",
        "assembly_veto": _tri(r.get("assembly_veto")) is True,
        "assembly_why": r.get("assembly_why") or "",
        "as_of": r.get("as_of"),
        "is_live": r.get("is_live"),
        # رتبۀ رسمیِ بک‌اند همان است که اسکرینر ساخته؛ اینجا فقط حمل می‌شود.
        "rank": r.get("_backend_rank"),
    }


# ── حلقۀ اصلی ─────────────────────────────────────────────────────────────
def gate_of(preset: str) -> str:
    """دروازۀ تکنیکال از خودِ preset — همان چیزی که `evaluate` مصرف می‌کند."""
    p = REG.PRESET_BY_ID.get(preset)
    return p.technical_gate if p else REG.TREND_GATE


def resolve_chain(preset: str, custom: Iterable[str] | None) -> tuple[str, ...]:
    p = REG.PRESET_BY_ID.get(preset)
    if p is None:
        raise KeyError(f"presetِ ناشناخته: {preset}")
    chain = tuple(custom or ())
    for fid in chain:
        if fid not in REG.BY_ID:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
    # رأیِ مالک (۱۴۰۵-۰۷-۲۰): چیپ‌هایِ خودِ تابلو غربالگری را می‌سازند، پس
    # انتخابِ فعالِ کاربر بر زنجیرۀ پیش‌فرضِ شخص بردگی می‌کند. بی‌انتخاب، همان
    # شخصِ قبلی می‌ماند (رفتارِ امروز دست‌نخورده).
    if chain:
        return chain
    return p.chain


def status_matrix(market: list[dict], tape: dict, tech: dict, fund: dict,
                  hand: dict, flow: str = "tape_first") -> tuple[dict, dict]:
    """وضعیتِ هر چهار گام برایِ **تک‌تکِ** نمادهایِ جامعۀ تابلو.

    قاعدۀ مالک: هیچ نمادی گم نمی‌شود و هیچ «سنجیده نشده»ای بی‌دلیل نیست. سه
    دلیلِ مجاز و افتراقی وجود دارد:
      UNAVAILABLE                 منبعی برایِ سنجشِ آن گام نیست (مثلاً پوششِ کدال)
      NOT_REQUIRED                گامِ قبل نماد را رد کرده، پس این گام اجرا نمی‌شود
      NOT_IN_UNIVERSE             نماد اصلاً عضو جامعۀ غربالگری نیست (وضعیتِ
                                  رسمیِ بازار اجازه نمی‌دهد) — نه رد، نه بی‌حکم
    جمعِ شمارشِ هر گام باید دقیقاً با جامعۀ تابلو بخواند و جمعِ بدونِ
    `not_in_universe` با جامعۀ غربالگری؛ گاردِ `dev/funnel_engine_v1.py`
    هر دو را می‌بندد.
    """
    survivors = {str(r.get("symbol") or "") for r in tape["survivors"]}
    # زنجیرۀ واقعی از خودِ خروجیِ گام خوانده می‌شود (نه از پارامتر)، تا دلیلِ
    # عبور همان پرچم‌هایی را نام ببرد که موتور واقعاً مصرف کرده است.
    chain = tuple(str(s.get("filter_id") or "") for s in tape["steps"])
    dropped_first: dict[str, dict] = {}
    for step in tape["steps"]:
        for sym in tape["dropped"].get(step["filter_id"], []):
            dropped_first.setdefault(sym, step)
    tech_by = {d["symbol"]: d for d in tech["decisions"]}
    fund_by = {d["symbol"]: d for d in fund["decisions"]}
    hand_by = {e["symbol"]: e for e in hand["entries"]}

    matrix: dict[str, dict[str, dict]] = {}
    coverage: dict[str, dict[str, int]] = {
        "tape": {k: 0 for k in STATUSES}, "technical": {k: 0 for k in STATUSES},
        "fundamental": {k: 0 for k in STATUSES}, "handover": {k: 0 for k in STATUSES},
    }

    def code_of(decisions: dict, sym: str) -> str:
        w = (decisions.get(sym) or {}).get("why") or []
        return w[0].get("code", "") if w else ""

    def stop_text(stage_name: str, st: str, next_name: str) -> str:
        """علتِ اجرا‌نشدنِ گامِ بعد باید بگوید گامِ پیشی *چه* کرد: رد، هنوز
        نگفته، یا داوری‌پذیر نبود. «رد کرده» برایِ PENDING دروغ است."""
        if st == REJECT:
            return f"{stage_name} نماد را رد کرده؛ {next_name} اجرا نمی‌شود"
        if st == PENDING:
            return f"{stage_name} هنوز حکم نداده؛ {next_name} اجرا نمی‌شود"
        return f"{stage_name} داوری‌پذیر نبود؛ {next_name} اجرا نمی‌شود"

    for r in market:
        sym = str(r.get("symbol") or "")
        if not r.get("_screening_eligible"):
            # خارج از جامعۀ غربالگری: درِ هر چهار گام همان وضعیتِ مستقل، با
            # علتِ استخراج‌شده از وضعیتِ رسمیِ نماد. هیچ گامی اجرا نشده چون
            # نماد candidate نبوده — نه اینکه داوری‌اش نکرده باشیم.
            out_cell = {"status": NOT_IN_UNIVERSE,
                        "reason_code": r.get("_exclusion_code") or "STATE_NOT_RECORDED",
                        "human_reason": r.get("_exclusion_reason")
                        or "وضعیتِ رسمیِ نماد اجازهٔ غربال نمی‌دهد"}
            row = {stage: dict(out_cell) for stage in
                   ("tape", "technical", "fundamental", "handover")}
            matrix[sym] = row
            for stage, cell in row.items():
                coverage[stage][cell["status"]] = coverage[stage].get(cell["status"], 0) + 1
            continue
        t = tech_by.get(sym)
        f = fund_by.get(sym)
        h = hand_by.get(sym)
        step = dropped_first.get(sym)
        if step is not None:
            tape_st = {"status": REJECT,
                       "reason_code": f"TAPE_{step['filter_id'].upper()}_NO_MATCH",
                       # همان دلیلی که درِ دفترچه نوشته شد — ماتریس و جدولِ
                       # مرحله یک جمله دارند، نه دو تا.
                       "human_reason": r.get("_tape_why_text")
                                      or f"{step['label']} — نشانه در این نماد نیست",
                       "stage_ref": step["source_ref"]}
        elif sym in survivors:
            pcode, ptext = _tape_pass_text(r, chain)
            tape_st = {"status": PASS, "reason_code": pcode, "human_reason": ptext}
        elif r.get("_tape_why_text"):
            # سنجیده‌نشده با علتِ همان ورودی — «پرچم ساخته نشده» به‌تنهایی
            # نمی‌گوید کدام ورودی کم بوده است.
            tape_st = {"status": UNAVAILABLE, "reason_code": "TAPE_UNMEASURED",
                       "human_reason": r["_tape_why_text"]}
        else:
            tape_st = {"status": UNAVAILABLE, "reason_code": "TAPE_NO_FLAG",
                       "human_reason": "پرچم این نماد در این نشست ساخته نشده"}

        if flow != "tech_first" and tape_st["status"] != PASS:
            tech_st = {"status": NOT_REQUIRED,
                       "reason_code": "NOT_REQUIRED_AFTER_TAPE_REJECT"
                                      if tape_st["status"] == REJECT
                                      else "NOT_REQUIRED_AFTER_TAPE_STOP",
                       "human_reason": stop_text("تابلو", tape_st["status"], "تکنیکال")}
        elif t is None:
            tech_st = {"status": UNAVAILABLE, "reason_code": "TECH_NO_VERDICT",
                       "human_reason": "سریِ تکنیکال برای این نماد ساخته نشد"}
        else:
            tech_st = {"status": t["status"],
                       "reason_code": code_of(tech_by, sym) or "TECH_PASSED",
                       "human_reason": " · ".join(w["text"] for w in (t.get("why") or []))}

        if flow == "tech_first" and tech_st["status"] != PASS:
            # درِ جریانِ تازه، مردودشدنِ تکنیکال یعنی گامِ تابلو اجرا نشده است.
            tape_st = {"status": NOT_REQUIRED,
                       "reason_code": "NOT_REQUIRED_AFTER_TECHNICAL_REJECT"
                                      if tech_st["status"] == REJECT
                                      else "NOT_REQUIRED_AFTER_TECHNICAL_STOP",
                       "human_reason": stop_text("تکنیکال", tech_st["status"], "تابلو")}
        if tech_st["status"] != PASS:
            gate = "TAPE" if tape_st["status"] != PASS else "TECHNICAL"
            why_stage = "تابلو" if gate == "TAPE" else "تکنیکال"
            why_st = tape_st["status"] if gate == "TAPE" else tech_st["status"]
            fund_st = {"status": NOT_REQUIRED,
                       "reason_code": f"NOT_REQUIRED_AFTER_{gate}_"
                                      + ("REJECT" if why_st == REJECT else "STOP"),
                       "human_reason": stop_text(why_stage, why_st, "بنیادی")}
        elif f is None:
            fund_st = {"status": UNAVAILABLE, "reason_code": "FUND_NO_CODAL_COVERAGE",
                       "human_reason": "پوشش کدال این نماد در اسکرینر نیست"}
        else:
            fund_st = {"status": f["effective"],
                       "reason_code": code_of(fund_by, sym) or "FUND_PASSED",
                       "human_reason": " · ".join(w["text"] for w in (f.get("why") or [])),
                       "canonical": f["canonical"], "exceptions": f.get("exceptions") or []}

        if flow == "tech_first" and tape_st["status"] != PASS:
            fund_st = {"status": NOT_REQUIRED,
                       "reason_code": "NOT_REQUIRED_AFTER_TAPE_REJECT"
                                      if tape_st["status"] == REJECT
                                      else "NOT_REQUIRED_AFTER_TAPE_STOP",
                       "human_reason": stop_text("تابلو", tape_st["status"], "بنیادی")}
        if h is not None:
            hand_st = {"status": h["final"],
                       "reason_code": (h.get("why") or [{}])[0].get("code", "")
                                      or ("ASSEMBLY_VETO" if h.get("assembly_veto") else "FINAL_PASS"),
                       "human_reason": " · ".join(w["text"] for w in (h.get("why") or [])),
                       "display_rank": h.get("display_rank")}
        else:
            prior = [tape_st["status"], tech_st["status"], fund_st["status"]]
            if REJECT in prior:
                hand_st = {"status": REJECT, "reason_code": "NOT_ELIGIBLE_AFTER_PRIOR_REJECT",
                           "human_reason": "در گامِ پیشین رد شده"}
            elif PENDING in prior:
                hand_st = {"status": PENDING, "reason_code": "WAITING_FOR_DATA",
                           "human_reason": "در انتظارِ داده/گزارش"}
            else:
                hand_st = {"status": UNAVAILABLE, "reason_code": "NO_FINAL_SOURCE",
                           "human_reason": "منبعی برای حکم نهایی نبود"}

        row = {"tape": tape_st, "technical": tech_st, "fundamental": fund_st, "handover": hand_st}
        matrix[sym] = row
        for stage, cell in row.items():
            coverage[stage][cell["status"]] = coverage[stage].get(cell["status"], 0) + 1
    return matrix, coverage


def _view(screening: list[dict], tape: dict, tech: dict, fund: dict, hand: dict,
          chain: tuple[str, ...], flow: str = "tape_first") -> dict:
    """ردیف‌هایِ آمادهٔ رندر برایِ هر چهار گام + خطِ زمانِ هر نماد.

    فقط جامعۀ غربالگری اینجا می‌آید (ردیف‌هایِ خارج از جامعه درِ payload جدا
    می‌شوند و جدول را شلوغ نمی‌کنند). هیچ داوریِ تازه‌ای درِ این تابع نیست:
    وضعیتِ هر نماد از همان تصمیمی خوانده می‌شود که سه گامِ قبل گرفته‌اند.
    جایی که تصمیمی ثبت نشده `unavailable` می‌نشیند، نه `pass`.
    """
    tech_by = {d["symbol"]: d for d in tech["decisions"]}
    fund_by = {d["symbol"]: d for d in fund["decisions"]}
    hand_by = {e["symbol"]: e for e in hand["entries"]}
    tape_surv = {str(r.get("symbol") or "") for r in tape["survivors"]}
    dropped_at: dict[str, dict] = {}
    for step in tape["steps"]:
        for sym in tape["dropped"].get(step["filter_id"], []):
            dropped_at.setdefault(sym, step)

    entries: dict[str, list[dict]] = {"tape": [], "technical": [], "fundamental": [], "handover": []}
    timeline: dict[str, list[dict]] = {}
    for r in screening:
        sym = str(r.get("symbol") or "")
        t = tech_by.get(sym)
        f = fund_by.get(sym)
        h = hand_by.get(sym)
        tape_status = PASS if sym in tape_surv else REJECT if sym in dropped_at else PENDING
        if flow == "tech_first" and t is not None and t["status"] != PASS:
            # به گامِ تابلو نرسیده: «سنجیده نشد» نمی‌نویسیم، «اجرا نشده» می‌نویسیم
            tape_status = NOT_REQUIRED
        why = list(r.get("_funnel_why") or [])
        st = {"tape": tape_status,
              "technical": (t or {}).get("status", UNAVAILABLE if sym in tape_surv else PENDING),
              "fundamental": (f or {}).get("effective", UNAVAILABLE if t and t["status"] == PASS else PENDING),
              "handover": (h or {}).get("final", UNAVAILABLE if f and f["effective"] == PASS else PENDING)}
        # هر دلیل باید متنِ *خودش* را ببرد. پیش از این هر آیتمِ why متنِ aggregate
        # را می‌داشت، پس ردیفی که دو دلیل داشت همان متن را دوبار می‌دید
        # («روند هفتگی صعودی · روزانه up ⇒ …» ×۲ — ۱۱۷۳ ردیف از ۸۵۷ درِ سنجشِ
        # زنده) و ستونِ دلیل سرریز می‌کرد. اینجا تک‌تعریفِ جفتِ (code, text) است.
        items = {
            "technical": [{"code": w["code"], "text": w["text"]} for w in (t or {}).get("why") or []],
            "fundamental": [{"code": w["code"], "text": w["text"]} for w in (f or {}).get("why") or []],
            "handover": [{"code": w["code"], "text": w["text"]} for w in (h or {}).get("why") or []],
            "tape": [{"code": w.get("reason_code", ""), "text": w.get("human_reason", "")}
                     for w in why if w.get("stage") == "tape"],
        }
        for stage_key in ("tape", "technical", "fundamental", "handover"):
            if stage_key == "tape" and sym not in tape_surv and sym not in dropped_at:
                continue  # هرگز نرسیده به این گام
            if stage_key == "technical" and t is None:
                continue
            if stage_key == "fundamental" and f is None:
                continue
            if stage_key == "handover" and h is None and st["fundamental"] != PASS:
                continue
            row = _display(r, patterns=None,
                           status={stage_key: st[stage_key]},
                           why={stage_key: [dict(i) for i in items[stage_key]]},
                           chain=chain, tech=t, fund=f)
            if stage_key == "technical":
                # جدولِ تکنیکال «نتیجۀ هر شرط» را می‌خواهد، نه فقط حکمِ جمع.
                # همان دیکشنری‌هایی که `technical_stage` ساخته است بی‌داوریِ دوم
                # رویِ ردیف می‌نشینند؛ برایِ سه گامِ دیگر فرستاده نمی‌شوند چون
                # پاسخِ ۱۰ مگابایتی را بی‌جهتِ سوم و چهارم می‌کنند.
                row["checks"] = list((t or {}).get("checks") or [])
                row["scan_as_of"] = (t or {}).get("scan_as_of")
            entries[stage_key].append(row)
        step_rows = [{"stage": "universe", "status": PASS,
                      "reason_code": "IN_SCREENING_UNIVERSE",
                      "human_reason": "وضعیتِ رسمیِ نماد اجازهٔ غربال می‌دهد؛ "
                                      "در جامعۀ غربالگریِ این نشست",
                      "input_count": len(screening), "output_count": len(screening),
                      "source": "api/market + instrument_state/stop_reasons",
                      "timestamp": None}]
        for sp in tape["steps"]:
            hit = next((w for w in why if w.get("stage") == "tape" and w.get("seq") == sp["seq"]), None)
            step_rows.append({
                "stage": f"tape:{sp['filter_id']}", "seq": sp["seq"],
                "status": (PASS if sym in tape_surv or
                           all(sym not in tape["dropped"].get(x["filter_id"], []) for x in tape["steps"][:sp["seq"]])
                           else REJECT),
                "reason_code": (hit or {}).get("reason_code", "TAPE_PASSED"),
                "human_reason": (hit or {}).get("human_reason", f"{sp['label']} — خورده شد"),
                "input_count": sp["input_count"], "output_count": sp["matched_count"],
                "source": sp["source_ref"], "formula_version": sp["formula_version"],
                "filter_id": sp["filter_id"], "label": sp["label"],
                "parameter_set": sp["parameter_set"], "timestamp": None})
        for key, dec, io_counts in (
            ("technical", t, (len(screening) if flow == "tech_first" else len(tape["survivors"]),
                              len(tech["survivors"]))),
            ("fundamental", f, (len(tech["survivors"]), len(fund["survivors"]))),
            ("handover", h, (len(fund["survivors"]), len(hand["entries"]))),
        ):
            if not dec:
                continue
            w0 = (dec.get("why") or [{}])[0]
            step_rows.append({
                "stage": key, "status": dec.get("effective") or dec.get("status") or dec.get("final") or PENDING,
                "reason_code": w0.get("code", ""), "human_reason": w0.get("text", ""),
                # شمارۀ خودِ گام، نه None: «چند نماد وارد این گام شد و چند تا
                # بیرون آمد» باید درِ ردیفِ همین نماد هم خوانده شود، وگرنه
                # ردیابیِ زنجیره فقط درِ جمعِ کلِ مرحله ممکن است.
                "input_count": io_counts[0], "output_count": io_counts[1],
                "source": "funnel_engine", "timestamp": None})
        if flow == "tech_first":
            # گامِ تکنیکال پیش از فیلترهای تابلو درِ خطِ زمان می‌آید؛ جامعۀ ورودیِ
            # هر دو گام هم عوض می‌شود (تابلو رویِ ماندگانِ تکنیکال اجرا می‌شود).
            it = next((i for i, x in enumerate(step_rows) if x.get("stage") == "technical"), None)
            if it is not None:
                tech_row = step_rows.pop(it)
                tech_row["input_count"] = len(screening)
                at = next((i for i, x in enumerate(step_rows)
                           if str(x.get("stage") or "").startswith("tape:")), 1)
                step_rows.insert(at, tech_row)
        timeline[sym] = step_rows
    return {"entries": entries, "timeline": timeline}


def evaluate(board_rows: list[dict], screen_rows: list[dict], *,
             preset: str = "trend", custom_chain: Iterable[str] | None = None,
             session_day: int | None = None,
             fund_mode: str = "standard",
             params: dict[str, dict[str, Any]] | None = None,
             exceptions: dict[str, list[str]] | None = None,
             tech_scan: dict[str, dict] | None = None,
             tech_sigs: dict[str, str] | None = None,
             universe_priority: dict[str, int] | None = None,
             universe_status: dict[str, str] | None = None,
             drop_numeric_suffix: bool = False,
             tape_logic: str = "and",
             tech_chain: Iterable[str] | None = None,
             settings: dict[str, Any] | None = None,
             as_of: int | None = None) -> dict:
    """قیفِ کامل رویِ کلِ جامعۀ ورودی. هیچ جایی slice نمی‌زند."""
    as_of = as_of or int(time.time())
    # کلیدِ screen_by هم نرمال است تا پیوندِ تابلو↔اسکرینر با یک املا نشکند
    # (همان نقضِ بندِ ۷.۱ که ۳۸۷ ردیف را «در تابلو نیست» می‌شمرد).
    screen_by = {norm_symbol(r.get("symbol")): r for r in screen_rows}
    for i, r in enumerate(screen_rows):
        r["_backend_rank"] = i  # ترتیبِ خودِ /api/screener (screener.py:440)
    chain = resolve_chain(preset, custom_chain)

    # تابلوخوانی رویِ ردیفِ خودِ تابلو؛ ردیفِ اسکرینر به همان نماد می‌چسبد تا
    # مراحلِ بعدی از یک منبعِ واحدِ عدد بخوانند.
    # جامع = نماد، نه ردیف. دو ردیفِ هم‌نام درِ تابلو (املایِ دوگانه یا نوشتۀ
    # تکراری) دو نماد نیستند؛ بی‌این یکی‌کردن، matrix (کلیدش نماد) از coverage
    # (شمارشِ ردیف) کم می‌شد و جمعِ وضعیت‌ها با جامعۀ واقعی نمی‌خواند.
    seen: dict[str, dict] = {}
    dupes = 0
    for r in board_rows:
        sym = norm_symbol(r.get("symbol"))
        if not sym:
            continue
        if sym in seen:
            dupes += 1
            continue
        scr = screen_by.get(sym) or screen_by.get(str(r.get("symbol") or "")) or {}
        row = dict(r)
        row["symbol"] = sym
        for k, v in scr.items():
            row.setdefault(k, v)
        seen[sym] = row
    joined = list(seen.values())

    # ── جامعۀ تابلو ≠ جامعۀ غربالگری (رأیِ مالک ۱۴۰۵-۰۷-۱۶) ──────────────
    # «Live» هرگز برابر «امروز معامله داشته» نیست: ملاک، وضعیتِ رسمیِ نماد درِ
    # خودِ بازار است (`screening_eligibility`). نمادِ خارج از جامعۀ غربالگری
    # نه REJECT است نه «سنجیده نشده» — وضعیتی مستقل می‌گیرد و درِ جدولِ اصلی
    # نمایش داده نمی‌شود؛ فقط در خلاصه و بخشِ بازشوندهٔ «خارج از جامعه».
    screening: list[dict] = []
    excluded: list[dict] = []
    for r in joined:
        # «حذفِ پسوندِ عددی» (رأیِ مالک ۱۴۰۵-۰۷-۲۲، عینِ درِ تبِ تابلو و پیش‌فرضِ
        # روشن): نمادِ افزودهدار اصلاً candidate نیست، پس رد محسوب نمی‌شود —
        # مثلِ بقیۀ وتوها درِ «خارج از جامعۀ غربالگری» می‌نشیند و جمعِ پنج
        # وضعیت با جامعۀ ورودی می‌ماند.
        if drop_numeric_suffix and has_numeric_suffix(r.get("symbol")):
            ok, code, human = (False, "NUMERIC_SUFFIX",
                               "پسوندِ عددی دارد — نسخۀ افزودۀ همان برند، نه نمادِ اصلی")
        else:
            ok, code, human = screening_eligibility(r, session_day)
        r["_screening_eligible"] = ok
        r["_exclusion_code"] = code
        r["_exclusion_reason"] = human
        (screening if ok else excluded).append(r)

    preset_obj = REG.PRESET_BY_ID.get(preset)
    flow = (preset_obj.flow if preset_obj else "tape_first") or "tape_first"
    chosen_tech = REG.resolve_tech_chain(preset, tech_chain) if flow == "tech_first" else ()
    # تنظیماتِ همین استراتژی: پیش‌فرض ازِ رجیستری، انتخابِ کاربر رویِ آن سوار
    # می‌شود و مقدارِ *مؤثر* به موتور می‌رسد (نه به نمایش). بی‌این، «تنظیم» فقط
    # یک برچسبِ دیدنی بود — همان ایرادی که درِ `parameter_set` وجود داشت.
    stg = REG.validate_settings(preset, settings)
    if stg.get("clock_delta_pct"):
        eff = dict(params or {})
        fc = dict(eff.get("f_clock") or {})
        fc["clock_delta"] = float(stg["clock_delta_pct"]) / 100.0
        eff["f_clock"] = fc
        params = eff
    # آستانه باید رأی را عوض کند، نه فقط متنِ دلیل. پرچمِ `f_clock` درِ تابلو با
    # ۲٪ِ فایل ساخته می‌شود و گامِ تابلو همان ستون را می‌خواند؛ پس اگر تنظیمِ
    # همین استراتژی عددِ دیگری است، همان `clock_flag` رویِ ردیف‌ها دوباره اجرا
    # می‌شود (نه فرمولِ دوم). بی‌این، سنجشِ زنده نشان داد ۱٪ و ۲٪ و حتی ۵۰٪ هر سه
    # یک شمارۀِ یکسان می‌دادند — کنترلِ دیدنی، داوریِ بی‌اثر.
    from tape_flags import CLOCK_DELTA as _FILE_CLOCK_DELTA, rejudge_clock
    _cd = _param_num((params or {}).get("f_clock") or {}, "clock_delta", _FILE_CLOCK_DELTA)
    if abs(_cd - _FILE_CLOCK_DELTA) > 1e-12:
        for _r, _hit in zip(screening, rejudge_clock(screening, _cd)):
            _r["f_clock"] = bool(_hit)
    if flow == "tech_first":
        # تکنیکال رویِ **کلِ جامعۀ غربالگری** داوری می‌شود، بعد تابلو رویِ ماندگان.
        tech = technical_stage(screening, tech_scan, tech_sigs, gate=gate_of(preset),
                               tech_chain=chosen_tech, settings=stg)
        tape = tape_stage(tech["survivors"], chain, params, logic=tape_logic)
    else:
        tape = tape_stage(screening, chain, params, logic=tape_logic)
    # دروازۀِ تکنیکال از خودِ preset خوانده می‌شود (تا پیش از این `technical_gate`
    # فقط درِ رجیستری نوشته شده بود و هیچ‌جا مصرف نمی‌شد).
    gate = (REG.PRESET_BY_ID[preset].technical_gate if preset in REG.PRESET_BY_ID
            else REG.TREND_GATE)
    if flow != "tech_first":
        tech = technical_stage(tape["survivors"], tech_scan, tech_sigs, gate=gate,
                               tech_chain=chosen_tech, settings=stg)
    # درِ «تکنیکال اول» تابلو بعد از تکنیکال اجرا می‌شود، پس بنیادی باید رویِ
    # ماندگانِ *تابلو* بخواند، نه ماندگانِ تکنیکال — وگرنه نمادی که درِ گامِ ۲ رد
    # شده درِ گامِ ۳ و ۴ زنده می‌ماند (سنجشِ زندهٔ ۱۴-۰۷-۲۷: ردشدۀ تابلو درِ
    # handover هم آمد). درِ ترتیبِ قدیمی همین دو فهرست یکی است.
    fund = fundamental_stage(tape["survivors"] if flow == "tech_first" else tech["survivors"],
                             fund_mode, exceptions, now=as_of)
    hand = handover_stage(fund["survivors"], tape, tech, fund,
                          assembly_vetoed=[str(r.get("symbol") or "") for r in screening
                                           if _tri(r.get("assembly_veto")) is True])

    view = _view(screening, tape, tech, fund, hand, chain, flow=flow)
    matrix, coverage = status_matrix(joined, tape, tech, fund, hand, flow=flow)
    # ── برچسبِ وضعیتِ معاملاتی (جهانِ زنده) ───────────────────────────────
    # هیچ نمادی به‌خاطرِ وضعیتش از غربالگری حذف نمی‌شود و ترتیبِ داوریِ مالک
    # (`final → exception → fund_score → tech_points → backend_rank → symbol`)
    # هم دست‌نخورده می‌ماند؛ اینجا فقط **دیده می‌شود** که کدام نماد همین حالا
    # معامله دارد، تا UI بتواند «زنده‌ها» را رو‌به‌رو بگذارد. بی‌این، اولویتِ
    # نمایشِ TRADING_ACTIVE فقط درِ یکِ endpointِ جدا می‌ماند و به جدولِ قیف
    # هیچ‌وقت نمی‌رسید.
    if universe_priority or universe_status:
        for _rows in view["entries"].values():
            for _e in _rows:
                _sym = str(_e.get("symbol") or "")
                _e["universe_priority"] = (universe_priority or {}).get(_sym)
                _e["universe_status"] = (universe_status or {}).get(_sym)
        for _e in hand["entries"]:
            _sym = str(_e.get("symbol") or "")
            _e["universe_priority"] = (universe_priority or {}).get(_sym)
            _e["universe_status"] = (universe_status or {}).get(_sym)
    for r in excluded:
        # Inspector برایِ نمادِ خارج از جامعه هم باید علت بدهد، نه «پیدا نشد».
        view["timeline"][str(r.get("symbol") or "")] = [{
            "stage": "universe", "status": NOT_IN_UNIVERSE,
            "reason_code": r["_exclusion_code"], "human_reason": r["_exclusion_reason"],
            "input_count": len(joined), "output_count": len(screening),
            "source": "instrument_state/stop_reasons (api/market.py:861-869)",
            "timestamp": None}]
    exclusions = [{"symbol": str(r.get("symbol") or ""), "name": r.get("name") or "",
                   "sector": r.get("sector_name") or r.get("sector") or "",
                   "last": _num(r.get("p_last")), "reason_code": r["_exclusion_code"],
                   "human_reason": r["_exclusion_reason"], "st_code": r.get("st_code"),
                   "st_title": r.get("st_title"), "stop_state": r.get("stop_state"),
                   "is_live": r.get("is_live")} for r in excluded]
    exclusion_counts: dict[str, int] = {}
    for r in excluded:
        exclusion_counts[r["_exclusion_code"]] = exclusion_counts.get(r["_exclusion_code"], 0) + 1
    return {
        "status": "success",
        "engine_version": ENGINE_VERSION,
        "ruleset_version": REG.RULESET_VERSION,
        # تنظیماتِ مؤثرِ همین درخواست — تا trace و UI همان عددی را ببینند که
        # موتور واقعاً استفاده کرد، نه پیش‌فرضِ رجیستری را.
        "strategy_settings": stg,
        "as_of": as_of,
        "preset": preset,
        "chain": list(chain),
        # رابط باید منطقِ واقعیِ گامِ تابلو را از پاسخ بخواند، نه از store خودش.
        "tape_logic": tape.get("logic") or "and",
        "flow": flow,
        "technical_chain": list(tech.get("chain") or []),
        "fund_mode": fund_mode,
        "universe": {"board": len(board_rows), "screened": len(screen_rows),
                     "joined": len(joined), "duplicate_rows": dupes,
                     "market": len(joined), "screening": len(screening),
                     # همان پرچمی که موتور واقعاً مصرف کرد — رابط به‌جایِ حدسِ
                     # وضعیتِ خودِ store، این را می‌خواند.
                     "drop_numeric_suffix": bool(drop_numeric_suffix),
                     "excluded": len(excluded),
                     "exclusion_counts": exclusion_counts,
                     "exclusion_labels": {k: EXCLUSION_LABEL.get(k, k)
                                          for k in exclusion_counts}},
        "stages": {
            # «survivors» = فهرستِ صریحِ نمادهایی که به گامِ بعد رفته‌اند. بی‌آن،
            # انتقالِ بینِ گام‌ها فقط استنتاجی بود (از entries کمِ dropped) و
            # ادعایِ «تکنیکال ⊆ تابلو» را نمی‌شد از خودِ پاسخ خواند.
            "tape": {"steps": tape["steps"], "logic": tape.get("logic") or "and",
                     "input": (len(tech["survivors"]) if flow == "tech_first" else len(screening)),
                     "matched": len(tape["survivors"]),
                     "removed": (len(tech["survivors"]) if flow == "tech_first" else len(screening))
                                - len(tape["survivors"]),
                     # شمارشِ هر فیلتر رویِ نامزدِ جاری (leave-one-out از همین
                     # زنجیره و همین منطق) — برایِ عددِ کنارِ چیپ‌هایِ نوارِ
                     # غربالگری (رأیِ مالک ۱۴۰۵-۰۷-۲۱).
                     "filter_counts": filter_counts(
                         tech["survivors"] if flow == "tech_first" else screening,
                         chain, (tape.get("logic") or "and")),
                     "survivors": _symbols(tape["survivors"])},
            "technical": {"counts": tech["counts"], "matched": len(tech["survivors"]),
                          "input": len(screening) if flow == "tech_first" else len(tape["survivors"]),
                          "chain": list(tech.get("chain") or []),
                          "filter_counts": tech.get("filter_counts") or {},
                          "survivors": _symbols(tech["survivors"])},
            "fundamental": {"counts": fund["counts"], "matched": len(fund["survivors"]),
                            "input": len(tech["survivors"]),
                            "mode": fund_mode,
                            "survivors": _symbols(fund["survivors"])},
            "handover": {"counts": hand["counts"], "matched": len(hand["entries"]),
                         "input": len(fund["survivors"]),
                         "survivors": [str(e.get("symbol") or "") for e in hand["entries"]]},
        },
        "handover": hand["entries"],
        "exclusions": exclusions,
        "entries": view["entries"],
        "timeline": view["timeline"],
        "status_matrix": matrix,
        "coverage": coverage,
        "trace": {
            "tape_dropped": {k: v for k, v in tape["dropped"].items() if v},
            "technical": tech["decisions"],
            "fundamental": fund["decisions"],
        },
        "registry": REG.as_json(),
    }
