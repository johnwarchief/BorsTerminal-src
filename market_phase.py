# -*- coding: utf-8 -*-
"""market_phase.py — تنها تعریفِ «جلسه در کدام مرحلۀِ خود است» در BorsTerminal.

چرا این فایل هست (بند ۵ مأموریت، رأیِ مالک 1405-07-20): تا پیش از این
«بازار باز است یا نه» فقط یک ساعتِ دیواریِ ثابت بود
(`frontend/src/shared/lib/marketHours.ts`) و هیچ‌جا درِ برنامه وضعیتِ **رسمیِ**
بازار خوانده نمی‌شد؛ همان پاسخِ رسمیِ بورس `MarketData/GetMarketOverview`
سه فیلدِ `marketState` / `marketStateTitle` / `marketActivityHEven` را
می‌فرستد و دور ریخته می‌شد (سنجشِ زنده 1405-07-20 ۱۸:۵۷:
`marketState="F"`، عنوان «بسته»، نشستِ فعالیت 20261010 ساعت ۱۸:۵۷:۱۱).
نتیجه: دادهٔ دیروز می‌توانست زنده خوانده شود و نبودِ داده با «بازار بد است».

چه چیزی را می‌گوییم و چه چیزی را نمی‌گوییم
──────────────────────────────────────────
• مرحل از وضعیتِ رسمی می‌آید. اگر وضعیتِ رسمیِ ناشناخته برسد، مرحل `unknown`
  است با خودِ مقدارِ خامِ حفظ‌شده — حرفِ نا‌شناخته را به «باز» یا «بسته»
  ترجمه نمی‌کنیم.
• «حراجِ پیش‌گشایش» و «پیش‌بستن» را **ادعا نمی‌کنیم**: منبعِ معتبری که درِ این
  ساختِ مرزهایشان را نشان بدهد درِ دسترس نبود، پس این دو درِ `UNVERIFIED`
  می‌مانند و به `continuous`/`pre_open`ِ ساعتی بدل نمی‌شوند. (بند ۳.۱ مأموریت:
  دقیقاً مشخص شود کدام بخش بررسی شده و کدام نشده.)
• هیچ آستانهٔ تازه‌ای اینجا نیست. «چه معیاری در این مرحل معنا دارد» یک
  ساختار است نه عدد: پیش از آغازِ معاملات، جریانِ محقق‌شدۀ پول تعریف ندارد؛
  فشارِ صف هست ولی پولِ تحقق‌یافته نیست. آستانهٔ همتِ «مساعد/نامساعد» همان
  `HEMAT_GOOD`/`HEMAT_BAD`ِ خودِ سندِ FTS می‌ماند (mstat_engine) و از این
  فایل صدا نمی‌شود.
• تعطیلی/پایانِ نشست: آخرینِ نشستِ معتبر با تاریخِ **خودش** اعلام می‌شود
  (`session_day`)، و `is_live` صفر می‌خورد تا رابط نداند دادهٔ گذشته را زنده.
"""
from __future__ import annotations

import datetime

# ── مرزهایِ اعلام‌شدۀ خودِ بازار (نه حدسِ برنامه) ─────────────────────────────
# این سه فقط برایِ تفکیکِ «پیش از آغازِ معاملات» از «بستهشدۀ پس از نشست»
# به‌کار می‌روند، و فقط وقتی که وضعیتِ رسمیِ بازار بسته بگوید و روزِ کاری باشد.
SESSION_START = datetime.time(9, 0)     # آغازِ معاملاتِ عادی
SESSION_END = datetime.time(12, 30)     # پایانِ معاملاتِ عادی

PRE_OPEN, CONTINUOUS, CLOSED, HOLIDAY, UNKNOWN = (
    "pre_open", "continuous", "closed", "holiday", "unknown")

PHASES = (PRE_OPEN, CONTINUOUS, CLOSED, HOLIDAY, UNKNOWN)

LABEL = {
    PRE_OPEN: "پیش از آغازِ معاملات",
    CONTINUOUS: "معاملات جاری",
    CLOSED: "پایانِ نشست",
    HOLIDAY: "تعطیلِ رسمی",
    UNKNOWN: "مرحل نامشخص",
}

# چه چیزی در هر مرحل **قابلِ محاسبه** است. این جدول رأی نمی‌دهد؛ فقط می‌گوید
# کدام عدد معنا دارد. `realized_flow` = پولِ تحقق‌یافته (از خودِ معاملات)،
# `order_pressure` = فشارِ صف (از دفترِ سفارش)، `session_vs_threshold` =
# مقایسهٔ جمعِ نشست با آستانهٔ تمام‌روزِ سندِ FTS.
COMPUTABLE = {
    PRE_OPEN: {"realized_flow": False, "order_pressure": True,
               "session_vs_threshold": False, "close_price_final": False},
    CONTINUOUS: {"realized_flow": True, "order_pressure": True,
                 "session_vs_threshold": True, "close_price_final": False},
    CLOSED: {"realized_flow": True, "order_pressure": False,
             "session_vs_threshold": True, "close_price_final": True},
    HOLIDAY: {"realized_flow": True, "order_pressure": False,
              "session_vs_threshold": True, "close_price_final": True},
    UNKNOWN: {"realized_flow": False, "order_pressure": False,
              "session_vs_threshold": False, "close_price_final": False},
}

WHY_NOT = {
    "realized_flow": "هنوز معامله‌ای ثبت نشده؛ جمعِ صف با پولِ تحقق‌یافته یکی نیست",
    "session_vs_threshold": "جمعِ نشست کامل نشده، پس با آستانۀِ تمام‌روز سنجیده نمی‌شود",
    "close_price_final": "قیمت پایانیِ نهایی هنوز ساخته نشده",
    "order_pressure": "دفترِ سفارشِ همین نشست در دسترس نیست",
}

# وضعیتِ رسمیِ TSETMC → مرحل. فقط نگاشت‌هایی که **سنجیده** شده‌اند.
# 'F' با عنوان «بسته» (پروبِ زنده 1405-07-20). هر مقدارِ دیگر ⇒ UNKNOWN.
OFFICIAL_CLOSED = {"F"}
OFFICIAL_OPEN = set()          # هنوز سنجیده نشده — خالی عمدی است


def _d_even_to_date(d) -> datetime.date | None:
    try:
        n = int(d)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    try:
        return datetime.date(n // 10000, (n // 100) % 100, n % 100)
    except ValueError:
        return None


def is_tehran_weekend(day: datetime.date) -> bool:
    """تعطیلِ رسمیِ بازار پنجشنبه و جمعه است (همان قاعدۀِ marketHours.ts).

    شنبه روزِ معاملاتی است؛ `weekday()`ِ پایتون شنبه را ۵ می‌دهد، پس نوشتنِ
    (4, 5) «جمعه + شنبه» را تعطیل می‌شمرد و نشستِ امروز را بی‌صدا تعطیل
    اعلام می‌کرد (سنجشِ همین فایل درِ دورِ اول — کنترلِ منفیِ گارد).
    """
    return day.weekday() in (3, 4)


def resolve(official_state=None, official_title=None, activity_day=None,
            activity_h_even=None, updated_at=None, board_day=None,
            now=None) -> dict:
    """مرحل + دلیل + تازگی، از وضعیتِ رسمی. خالص و تست‌پذیر (بی‌شبکه، بی‌SQL).

    `now` datetimeِ تهران است (تزریقی، تا تست ساعتِ دیواریِ ماشین را برندارد).
    """
    now = now or datetime.datetime.now()
    st = (str(official_state).strip().upper() or None) if official_state is not None else None
    title = (str(official_title).strip() or None) if official_title else None
    act = _d_even_to_date(activity_day) or _d_even_to_date(board_day)
    today = now.date()
    official_seen = st is not None or title is not None
    officially_closed = st in OFFICIAL_CLOSED or bool(title and "بسته" in title)
    officially_open = st in OFFICIAL_OPEN or bool(title and title.endswith("باز"))
    # «امروز» یعنی همان روزی که خودِ بازار برایش فعالیت گزارش کرده، نه
    # روزِ تقویمیِ ماشینِ کاربر.
    same_day = bool(act and act == today)
    weekend = bool(act and is_tehran_weekend(act))

    if officially_open:
        # وضعیتِ رسمی می‌گوید باز است. مرزهایِ دقیقِ «حراجِ پیش‌گشایش» و
        # «پیش‌بستن» منبعِ معتبرِ تأییدشده ندارند، پس ادعا نمی‌شوند (بند ۳.۱).
        phase, source = CONTINUOUS, "tsetmc_marketState"
    elif officially_closed:
        # تعطیلی اول می‌آید: پنجشنبه/جمعه بودنِ خودِ روز با «نشستِ تمام‌شده»
        # یکی نیست، و بی‌این ترتیب، نشستِ شنبه بی‌صدا تعطیل خوانده می‌شد.
        if weekend:
            phase = HOLIDAY
        elif same_day and now.time() < SESSION_START:
            phase = PRE_OPEN
        elif same_day and now.time() < SESSION_END:
            # بازار «بسته» می‌گوید ولی ساعتِ دیواری داخلِ پنجرۀِ معاملات است:
            # میان‌پردهٔ حراج، قطعِ موقت، یا سینکِ میانیِ نشست. مرحلِ تازه
            # اختراع نمی‌شود؛ صریح «نامشخص» می‌ماند.
            phase = UNKNOWN
        else:
            phase = CLOSED
        source = "tsetmc_marketState"
    elif official_seen:
        phase, source = UNKNOWN, "tsetmc_marketState_unmapped"
    else:
        # هیچ وضعیتِ رسمی‌ای نرسیده (پایگاهِ کهنه/بی‌سینک). ساعت فقط «احتمال»
        # می‌دهد و همین اعلام می‌شود؛ درِ پنجرۀِ معاملات بی‌وضعیتِ رسمی
        # UNKNOWN است، نه «باز».
        if weekend:
            phase, source = HOLIDAY, "calendar"
        elif same_day and now.time() < SESSION_START:
            phase, source = PRE_OPEN, "calendar"
        elif same_day and now.time() >= SESSION_END:
            phase, source = CLOSED, "calendar"
        else:
            phase, source = UNKNOWN, "none"

    comp = COMPUTABLE[phase]
    return {
        "phase": phase,
        "label": LABEL[phase],
        "phase_source": source,
        "official": bool(official_seen and source == "tsetmc_marketState"),
        "official_state": st,
        "official_state_title": title,
        "session_day": int(act.strftime("%Y%m%d")) if act else None,
        "activity_h_even": int(activity_h_even) if activity_h_even else None,
        "is_live": phase == CONTINUOUS,
        # داوریِ «مساعد/نامساعد» فقط رویِ نشستی که *تعریفِ تمام‌شده* دارد:
        # معاملاتِ جاری (با قیدِ partial پایین)، نشستِ بسته، و تعطیلِ رسمی —
        # که درِ تعطیلی هم عددِ همان نشستِ آخر با تاریخِ خودش می‌آید.
        # پیش از آغاز و مرحلِ نامشخص: هیچ حکمی نه مثبت و نه منفی.
        "verdict_allowed": phase in (CONTINUOUS, CLOSED, HOLIDAY),
        "computable": dict(comp),
        "not_computable": [k for k, v in comp.items() if not v],
        "why_not": {k: WHY_NOT[k] for k, v in comp.items() if not v},
        "data_updated_at": updated_at,
        "clock_now": now.strftime("%Y-%m-%d %H:%M:%S"),
        # دو مرزِ اعلام‌شدۀ بازار، برایِ اینکه رابط بگوید از کجا آمده است
        "session_start": SESSION_START.strftime("%H:%M"),
        "session_end": SESSION_END.strftime("%H:%M"),
    }


def from_db(conn, now=None) -> dict:
    """همان resolve از جدولِ market_index (نویسنده: test_tsetmc.save_market_index)."""
    try:
        r = conn.execute(
            "SELECT d_even, updated_at, market_state, market_state_title,"
            " activity_h_even FROM market_index ORDER BY d_even DESC LIMIT 1"
        ).fetchone()
    except Exception:
        r = None                                   # پایگاهِ کهنه: ستون‌ها نیست
    try:
        board = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()
        board_day = board[0] if board else None
    except Exception:
        board_day = None
    if r:
        return resolve(official_state=r[2], official_title=r[3], activity_day=r[0],
                       activity_h_even=r[4], updated_at=r[1], board_day=board_day,
                       now=now)
    return resolve(activity_day=None, board_day=board_day, now=now)
