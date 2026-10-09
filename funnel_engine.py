# -*- coding: utf-8 -*-
"""funnel_engine.py — داورِ canonicalِ قیف FTS (بک‌اند، تنها نسخه).

چرا این فایل هست: تا پیش از این «حکمِ نهاییِ قیف» درِ مرورگر ساخته می‌شد
(`frontend/src/features/master/lib/ftsFunnel.ts` → `buildFunnel`) و بک‌اند فقط
پرچم و پنج شاخص خام می‌داد. رأیِ مالک (۱۴۰-۰۷-۱۶): یک داورِ canonical درِ
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
STATUSES = (PASS, REJECT, PENDING, UNAVAILABLE, NOT_REQUIRED, NOT_IN_UNIVERSE)

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


# ── ۱) تابلوخوانی: اشتراکِ ترتیبیِ زنجیره ─────────────────────────────────
def tape_stage(rows: list[dict], chain: tuple[str, ...],
               params: dict[str, dict[str, Any]] | None = None) -> dict:
    """U ∩ F1  F2 … با شمارۀ واقعیِ هر مرحله رویِ بازماندۀ مرحلۀ قبل."""
    params = params or {}
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
            if v is False:
                removed.append(sym)
            else:
                # True ماند؛ None هم حذف نمی‌شود ولی «سنجیده نشد» برچسب
                # می‌گیرد — قانونِ مالک: UNAVAILABLE ≠ REJECT.
                matched.append(r)
                if v is None:
                    unmeasured.append(sym)
        dropped[fid] = removed
        for r in survivors:
            if _tri(r.get(flag)) is False:
                _why_of(r).append({"stage": "tape", "seq": len(steps) + 1, "filter_id": fid,
                                   "status": REJECT, "reason_code": f"TAPE_{fid.upper()}_NO_MATCH",
                                   "human_reason": f"{f.name} — نشانه در این نماد نیست",
                                   "input_count": before, "output_count": len(matched),
                                   "source": f.source_file, "formula_version": f.formula_version})
            elif _tri(r.get(flag)) is None:
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
            "removed_count": before - len(matched),
            "unmeasured_count": len(unmeasured),
            "parameter_set": params.get(fid) or {p.param_id: p.value for p in f.params if p.value is not None},
            "source_ref": f"{f.source_file}#{f.source_sha256}",
            "formula_version": f.formula_version,
            "backend_impl": f.backend_impl,
            # سه‌حالته و افتراقی: چیزی حذف شده (reject)، هیچ‌چیز حذف نشده ولی
            # بعضی پرچم‌ها ساخته نشده‌اند (pending)، یا همه‌چیز سنجیده و خورده شده.
            "status": REJECT if removed else (PENDING if unmeasured else PASS),
        })
        survivors = matched
    return {"survivors": survivors, "steps": steps, "dropped": dropped}


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
              "tech_range_break", "tech_fib_zone", "tech_exit_verdict",
              "tech_hourglass_active", "tech_hourglass_action")


def technical_stage(rows: list[dict], tech: dict[str, dict] | None = None,
                    sigs: dict[str, str] | None = None) -> dict:
    """گیتِ روند — داور همان `trend.matrix` بک‌اند است، نه محاسبۀ دوباره.

    `tech` ردیف‌هایِ `funnel_tech_scan` است (نماد → ستون‌هایِ tech_*). چرا لازم
    شد: `api/screener.py` تکنیکال را فقط برایِ `watchlist_max=50` ردیفِ اول
    می‌ساخت، پس رسیدگانِ تابلو که درِ آن پنجاه نبودند هیچ رأیی نداشتند — یعنی
    یک سقفِ *تصمیم*، نه نمایش. با این ورودی، هر نمادی که به این گام می‌رسد
    داوری می‌شود؛ چیزی حذف نمی‌شود و چیزی هم حدس زده نمی‌شود:

      سابقهٔ قیمتی دارد ولی اسکن هنوز نوبتش نشده  ⇒ PENDING / TECH_SCAN_PENDING
      هیچ سابقهٔ قیمتی در بانک ندارد               ⇒ UNAVAILABLE / TECH_NO_HISTORY
      اسکن شده و تحلیل رأیی نداده                  ⇒ UNAVAILABLE / TECH_UNMEASURED

    بی‌`sigs` (فراخوانیِ مستقیمِ گارد) رفتارِ پیشین می‌ماند: TECH_UNMEASURED.
    """
    kept, steps, dropped = [], [], []
    counts = {PASS: 0, REJECT: 0, PENDING: 0, UNAVAILABLE: 0}
    for r in rows:
        sym = str(r.get("symbol") or "")
        t = (tech or {}).get(sym)
        if t:
            r = {**r, **{k: t[k] for k in _TECH_KEYS
                         if t.get(k) is not None and r.get(k) in (None, "")}}
        w = (r.get("tech_trend_w") or "").strip() or None
        d = (r.get("tech_trend_d") or "").strip() or None
        mat = (r.get("tech_matrix_decision") or "").strip() or None
        why: list[dict[str, str]] = []
        if not (w or d or mat):
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
            "why": why,
        })
    return {"survivors": kept, "decisions": steps, "counts": counts, "dropped": dropped}


# ── ۳) بنیادی: سه حالتِ سخت‌گیری، بلاکرهایِ واقعی ──────────────────────────
BLOCKERS = ("i1", "i2", "i3")
SUPPORTING = ("i4", "i5")
IND_LABEL = {"i1": "I1 رشد فروش", "i2": "I2 EPS سه‌ساله", "i3": "I3 حاشیه سود ناخالص",
             "i4": "I4 فروش ۱۲ماه ÷ ارزش بازار", "i5": "I5 نرخ‌گذاری"}


def fundamental_stage(rows: list[dict], mode: str = "standard",
                      exceptions: dict[str, list[str]] | None = None,
                      now: int | None = None) -> dict:
    """I1∧I2∧I3 بلاکر (standard)، هر پنج (hard)، استثنایِ صریح (exception).

    canonical هرگز عوض نمی‌شود؛ فقط `effective` با برچسب جابه‌جا می‌شود.
    """
    exceptions = exceptions or {}
    now = now or int(time.time())
    kept, steps, dropped = [], [], []
    counts = {PASS: 0, REJECT: 0, PENDING: 0, UNAVAILABLE: 0}
    for r in rows:
        sym = str(r.get("symbol") or "")
        marks = {k: _tri(r.get(f"{k}_pass")) for k in (*BLOCKERS, *SUPPORTING)}
        detail = [{
            "indicator": k.upper(), "label": IND_LABEL[k], "status": marks[k],
            "value": _num(r.get({"i1": "rev_growth", "i2": "eps_last", "i3": "gross_margin",
                                 "i4": "sales_to_mcap"}.get(k, "") or "_")),
            "threshold": r.get({"i1": "growth_min", "i3": "margin_min", "i4": "sales_to_mcap_min"}.get(k, "") or "_"),
            "as_of": r.get("as_of"), "source": "codal",
        } for k in (*BLOCKERS, *SUPPORTING)]
        missing = [k for k in BLOCKERS if marks[k] is None]
        blocked = [k for k in BLOCKERS if marks[k] is False]
        support_missing = [k for k in SUPPORTING if marks[k] is None]
        why: list[dict[str, str]] = []
        if mode == "hard":
            fail = [k for k in (*BLOCKERS, *SUPPORTING) if marks[k] is False]
            miss = [k for k in (*BLOCKERS, *SUPPORTING) if marks[k] is None]
            if fail:
                status = REJECT
                why += [{"code": f"FUND_{k.upper()}_REJECT", "text": f"{IND_LABEL[k]} تأیید نشده"} for k in fail]
            elif miss:
                status = PENDING
                why += [{"code": f"FUND_{k.upper()}_MISSING", "text": f"{IND_LABEL[k]} سنجیده نشده"} for k in miss]
            else:
                status = PASS
        else:  # standard و exception هر دو canonical را یکسان می‌سنجند
            if blocked:
                status = REJECT
                why += [{"code": f"FUND_{k.upper()}_REJECT",
                         "text": f"{IND_LABEL[k]} زیرِ کف — بلاکرِ جزوه"} for k in blocked]
            elif missing:
                status = PENDING
                why += [{"code": f"FUND_{k.upper()}_MISSING",
                         "text": f"{IND_LABEL[k]} گزارشش نرسیده — رد نیست، سنجیده نشده"} for k in missing]
            elif support_missing and mode == "hard":
                status = PENDING
            else:
                status = PASS
        canonical = status
        granted = [k.upper() for k in exceptions.get(sym, []) if k.upper() in ("I1", "I2", "I3")]
        effective = status
        if mode == "exception" and status == REJECT and granted:
            failed = {k.upper() for k in blocked}
            if failed and failed <= set(granted):
                # فقط بلاکرهایِ واقعاً‌ردشده بخشوده می‌شوند؛ بی‌این، استثنا
                # جایِ هر چیزی را می‌گرفت.
                effective = PASS
                why.append({"code": "EXCEPTION_APPLIED",
                            "text": "استثنای بنیادی: " + "، ".join(sorted(granted))})
        if status == PASS and support_missing:
            why.append({"code": "FUND_SUPPORT_MISSING",
                        "text": "شاهدِ بنیادی کامل نیست: " + "، ".join(k.upper() for k in support_missing)})
        counts[status] += 1
        row_out = dict(r)
        row_out["_fund_canonical"] = canonical
        row_out["_fund_effective"] = effective
        row_out["_fund_exceptions"] = sorted(granted) if effective == PASS and granted else []
        if effective == PASS:
            kept.append(row_out)
        else:
            dropped.append(sym)
        steps.append({
            "stage": "fundamental", "symbol": sym, "mode": mode,
            "canonical": canonical, "effective": effective,
            "exceptions": row_out["_fund_exceptions"],
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
             chain: tuple[str, ...] = ()) -> dict:
    """یک ردیفِ آمادهِ رندر برایِ جدول — با traceِ همان نماد."""
    sym = str(r.get("symbol") or "")
    return {
        "symbol": sym,
        "name": r.get("name") or "",
        "sector": r.get("sector_name") or r.get("sector") or "",
        "last": _num(r.get("p_last")),
        "closing": _num(r.get("p_closing")),
        "change_pct": _num(r.get("percent_change")),
        "vol_ratio": _num(r.get("vol_ratio")),
        "patterns": patterns if patterns is not None
        else [_LABEL_OF[f] for f in REG.filter_ids() if _tri(r.get(f)) is True],
        "status": status or {},
        "why": why or {},
        "chain": list(chain),
        "score": _num(r.get("score")),
        "primary_score": _num(r.get("primary_score")),
        "weekly": r.get("tech_trend_w"), "daily": r.get("tech_trend_d"),
        "branch": BRANCH_OF.get(str(r.get("tech_trend_d") or ""), None),
        "matrix": r.get("tech_matrix_decision"),
        "tech_status": r.get("tech_status"),
        "tech_points": _num(r.get("tech_points")),
        "evidence": [k for k in ("tech_jet", "tech_choch_bull", "tech_double_bottom",
                                 "tech_range_break") if _tri(r.get(k)) is True],
        "fib_zone": r.get("tech_fib_zone"),
        "hourglass": _tri(r.get("tech_hourglass_active")),
        "inds": {k: _tri(r.get(f"{k}_pass")) for k in (*BLOCKERS, *SUPPORTING)},
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
def resolve_chain(preset: str, custom: Iterable[str] | None) -> tuple[str, ...]:
    p = REG.PRESET_BY_ID.get(preset)
    if p is None:
        raise KeyError(f"presetِ ناشناخته: {preset}")
    if p.preset_id != "custom":
        return p.chain
    chain = tuple(custom or ())
    for fid in chain:
        if fid not in REG.BY_ID:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
    return chain


def status_matrix(market: list[dict], tape: dict, tech: dict, fund: dict,
                  hand: dict) -> tuple[dict, dict]:
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
                       "human_reason": f"{step['label']} — نشانه در این نماد نیست",
                       "stage_ref": step["source_ref"]}
        elif sym in survivors:
            tape_st = {"status": PASS, "reason_code": "TAPE_PASSED",
                       "human_reason": "همۀ فیلترهایِ زنجیره را خورده شده"}
        else:
            tape_st = {"status": UNAVAILABLE, "reason_code": "TAPE_NO_FLAG",
                       "human_reason": "پرچم این نماد در این نشست ساخته نشده"}

        if tape_st["status"] != PASS:
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
          chain: tuple[str, ...]) -> dict:
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
            entries[stage_key].append(_display(
                r, patterns=None,
                status={stage_key: st[stage_key]},
                why={stage_key: [dict(i) for i in items[stage_key]]},
                chain=chain))
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
        for key, dec in (("technical", t), ("fundamental", f), ("handover", h)):
            if not dec:
                continue
            w0 = (dec.get("why") or [{}])[0]
            step_rows.append({
                "stage": key, "status": dec.get("effective") or dec.get("status") or dec.get("final") or PENDING,
                "reason_code": w0.get("code", ""), "human_reason": w0.get("text", ""),
                "input_count": None, "output_count": None,
                "source": "funnel_engine", "timestamp": None})
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
             as_of: int | None = None) -> dict:
    """قیفِ کامل رویِ کلِ جامعۀ ورودی. هیچ جایی slice نمی‌زند."""
    as_of = as_of or int(time.time())
    screen_by = {str(r.get("symbol") or ""): r for r in screen_rows}
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
        sym = str(r.get("symbol") or "").strip().replace("ي", "ی").replace("ك", "ک")
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
        ok, code, human = screening_eligibility(r, session_day)
        r["_screening_eligible"] = ok
        r["_exclusion_code"] = code
        r["_exclusion_reason"] = human
        (screening if ok else excluded).append(r)

    tape = tape_stage(screening, chain, params)
    tech = technical_stage(tape["survivors"], tech_scan, tech_sigs)
    fund = fundamental_stage(tech["survivors"], fund_mode, exceptions, now=as_of)
    hand = handover_stage(fund["survivors"], tape, tech, fund,
                          assembly_vetoed=[str(r.get("symbol") or "") for r in screening
                                           if _tri(r.get("assembly_veto")) is True])

    view = _view(screening, tape, tech, fund, hand, chain)
    matrix, coverage = status_matrix(joined, tape, tech, fund, hand)
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
        "as_of": as_of,
        "preset": preset,
        "chain": list(chain),
        "fund_mode": fund_mode,
        "universe": {"board": len(board_rows), "screened": len(screen_rows),
                     "joined": len(joined), "duplicate_rows": dupes,
                     "market": len(joined), "screening": len(screening),
                     "excluded": len(excluded),
                     "exclusion_counts": exclusion_counts,
                     "exclusion_labels": {k: EXCLUSION_LABEL.get(k, k)
                                          for k in exclusion_counts}},
        "stages": {
            "tape": {"steps": tape["steps"],
                     "input": len(screening), "matched": len(tape["survivors"]),
                     "removed": len(screening) - len(tape["survivors"])},
            "technical": {"counts": tech["counts"], "matched": len(tech["survivors"])},
            "fundamental": {"counts": fund["counts"], "matched": len(fund["survivors"]),
                            "mode": fund_mode},
            "handover": {"counts": hand["counts"], "matched": len(hand["entries"])},
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
