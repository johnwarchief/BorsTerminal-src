# -*- coding: utf-8 -*-
"""major_swings — جداکردنِ سقف/کفِ ماژور از پیوت‌هایِ کوچک، بی‌نگاه‌به‌آینده

چرا لازم شد: `_fts_classify_trend` (api/chart.py) جهتِ روند را از «دو سقف و دو کفِ
آخرِ پیوت» می‌سازد، و `_fts_swings` «مهم‌بودن» را فقط با پیروزیِ پنجره‌ای (fractal)
می‌سنجد — بی‌هیچ معیارِ بلندی. نتیجه: یکِ نوسانِ کوچک هم می‌تواند دو همسایۀ مخالفِ
آخر شود و رأیِ روند را برگرداند.

این فایل داورِ جهت را نمی‌سازد و جابه‌جا نمی‌کند: فقط فهرستِ پیوت‌ها را به «ماژور» و
«غیرماژور» درجه‌بندی می‌کند تا همان `_fts_classify_trend` دو Extreme را از بینِ
پیوت‌هایِ معتبرِ ماژور بردارد. (قاعدۀِ جزوه مقدم است: هفتگی وتو، روزانه شاخه.)

معیار و شاهدش (بی‌عددِ اختراعی) — اعداد ازِ اجرایِ `python _audit/major_swing_evidence.py`
رویِ ۱۳۰ نمادِ نمونه‌شده یکنواخت از ۷۹۰ نمادِ بانک (۱۱۰ نمادِ قابل‌استفاده)، با **همان**
`grade()`ِ محصول، نه با تقریبِ جدا:
    • بلندیِ پایِ تصمیم‌گیر: میانه ۸٫۶۳٪ قیمت = ۲٫۳۸×ATR، دهکم ۵٫۱۸٪ = ۱٫۴۷×ATR،
      کمینه ۰٫۹۶٪ = ۰٫۰۲×ATR؛ ۳ نماد از ۱۱۰ پایِ تصمیم‌گیرشان زیرِ ۱×ATR بود — همان
      دسته‌ای که قانونِ «دو پیوتِ آخر» بی‌تمایز می‌پذیرد.
    • تکانِ ±۲٪ آخرینِ ردیف (بدونِ نشانۀ تکمیل‌نشده = رفتارِ پیش ازِ این دور): ۵ جابه‌جاییِ
      رأی (۳ down→up، ۲ up→down).
    • حساسیتِ آستانه (تغییرِ رأی / به هفتگی نزدیک / از هفتگی دور / naِ بیشتر / پیوتِ
      نگه‌داشته‌شده):
          atr_1.0    2 (1.8%)   2  0  0   99.4%   ← تقریباً هیچ را فیلتر نمی‌کند
          atr_2.0    3 (2.7%)   2  1  0   90.5%   ← انتخابِ این دور
          atr_3.0    5 (4.5%)   3  2  0   74.6%
          atr_4.0    6 (5.5%)   5  1  0   56.9%   ← ۴۳٪ ساختار را دور می‌ریزد
          pct_5_and_ma100   11 (10.0%)  7  4  0  66.0%  ← پرنوسان‌ترینِ کاندید
      MA100 (قاعدۀِ جزوه برایِ «کفِ ارزندۀِ ماژور») به‌عنوانِ فیلتر رد شد: هم رأیِ بیشتری
      را عوض می‌کند (۱۰٪ در برابر ۲٫۷٪) و هم ساختارِ بیشتری دور می‌ریزد (۶۶٪ در برابر
      ۹۰٪) و نسبتِ near/farِ آن (۷/۴) انسجامِ بیشتری نمی‌سازد. پس MA100 فقط گزارش
      می‌شود (`ma100_ctx`) و درِ داوری نیست.
    • هیچ آستانه‌ای رأیِ نمادی را به `na` تبدیل نکرد (na_more = ۰ درِ همه)، پس این
      درجه‌بندی پوششِ داوری را کم نمی‌کند.
    • `no_grade` (کنترلِ مثبت) دقیقاً ۰ تغییر داد — یعنی سنجش، مسیرِ واقعی را می‌بیند.

عددِ ۲×ATR بی‌دلیل انتخاب نشده: میانۀِ پایِ تصمیم‌گیرِ نمادها ۲٫۳۸×ATR است، پس آستانه
«به اندازهٔ پایِ میانیِ بازار» یکِ فیلترِ ساختاری است نه تنظیمِ رویِ یکِ چارتِ خاص؛ و
درِ همان نقطه ۹۰٪ پیوت‌ها حفظ می‌شوند. با این حال `MAJOR_LEG_ATR_X` یکِ انتخابِ
implementation است، نه قاعدۀِ رسمیِ FTS؛ هیچ‌جا به‌عنوانِ قانونِ جزوه معرفی نشده و
درِ `_audit/MAJOR-SWING-EVIDENCE.json` (با SHAِ اجرا) قابلِ بازتولید است.

ضدِّ نگاه‌به‌آینده: درجه‌بندی فقط از کندل‌هایِ **بستهٔ پیشِ تأییدِ پیوت** (پنجرۀِ
بلندیِ پا و ATR درِ `confirm_idx`) استفاده می‌کند و زمانِ وقوعِ پیوت را از زمانِ
شناختش جدا می‌گیرد؛ هیچِ کندلِ بعد از `confirm_idx` برایِ ماژور/غیرماژور بودنِ آن
پیوت خوانده نمی‌شود. `forming()` هم دقیقاً برعکسِ همان قاعده است: چیزی که هنوز
پنجرۀِ تأییدِ کاملِ خود را ندیده، درِ فهرستِ پیوت‌هایِ قطعی **نمی‌نشیند** و فقط به‌عنوان
اطلاعِ موقتِ جدا منتشر می‌شود.
"""
from __future__ import annotations

from structure_engine3 import atr_series   # تک‌تعریفِ ATRِ Wilder درِ پروژه

# آستانه‌یِ ماژور: بلندیِ پا دست‌کم ۲×ATRِ همان نماد (شاهد بالا).
MAJOR_LEG_ATR_X = 2.0
# کفِ مطلقِ بی‌واحد، برایِ نمادهایِ بی‌نوسان که ATRشان به صفر نزدیک است و وگرنه
# هرِ پیوتی ماژور می‌شد. ۰٫۵٪ ازِ همان پنجره‌یِ سنجش انتخاب شد (بی‌عددِ تازه).
MAJOR_LEG_FLOOR_PCT = 0.005
# پنجرۀِ میانیِ ATR: بلندیِ پا با «نوسانِ عادلیِ همان دورۀِ نماد» سنجیده می‌شود، نه
# با ATRِ لحظهایِ دقیقاً رویِ پیوت. شاهد (سنجیدۀِ همین دور، خفولا رویِ چارتِ هفتگی):
# با `atr[confirm_idx]` یکِ کفِ ۲۱٪ی بعد ازِ ریزشِ بزرگ «غیرماژور» شمرده شد و رأیِ
# هفتگی از up به down برگشت — یعنی دقیقاً همان چیزی که مأموریت منع می‌کند، ولی از
# سمتِ خودش. میانیۀِ ۵۲ دورۀِ اخیر، همان عددی است که `_FTS_STALE_WINDOW` و MA52 درِ
# پروژه دارند؛ پس شمارۀِ تازه‌ای اختراع نشده.
ATR_WINDOW = 52
# پیوتِ «تازه‌شناخته»: چند کندل از تأییدش گذشته است. این نام فقط برایِ گزارش است؛
# رأیِ جهت با آن عوض نمی‌شود. عمداً از k خودِ سیستم گرفته شده تا عددِ تازه‌ای
# اختراع نشود.
RECENT_BARS = 3


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and x > 0 else None


def _span(base, here):
    """(نسبی، مطلق، مبنا)ِ فاصلۀِ دو قیمت."""
    b, h = _f(base), _f(here)
    if not b or not h:
        return None, None, None
    return abs(h - b) / b, abs(h - b), b


def leg_amp(swings, i):
    """بلندیِ پایِ ورودیِ پیوتِ iام: فاصلۀ نسبی تا نزدیک‌ترین پیوتِ مخالفِ پیشِ خود.

    بی‌این «ماژور» تنها با ارتفاعِ مطلقِ خودِ پیوت سنجیده می‌شد که در برابرِ
    فلات‌هایِ قیمتی (ردیف‌هایِ H==Lِ TSETMC) بی‌معناست.
    """
    s = swings[i]
    for j in range(i - 1, -1, -1):
        if swings[j]["kind"] != s["kind"]:
            return _span(swings[j]["price"], s["price"])[0]
    return None


def leg_amp_out(swings, i):
    """بلندیِ پایِ خروجیِ پیوت: فاصله تا نزدیک‌ترین پیوتِ مخالفِ **بعد از** آن.

    چرا لازم است: سقفِ ماژور را بازار با «ریزشی که بعدش آمد» تعریف می‌کند. بی‌این،
    قلهٔ ۳۰٬۵۰۷ِ خفولا که ۵۵٪ بعد از آن ریزش کرد چون ورودش ۰٫۲٪ بود غیرماژور
    شمرده می‌شد. نگاه‌به‌آینده نیست: آن پیوتِ مخالفِ بعدی خودش تا لحظۀِ ارزیابی
    تأیید شده، پس «دانستۀِ همین لحظه» است — نه کندلِ آینده. تا وقتی چنین پیوتی
    وجود ندارد، مقدارش `None` می‌ماند و پیوت با `out_pending` اعلام می‌شود.
    """
    s = swings[i]
    for j in range(i + 1, len(swings)):
        if swings[j]["kind"] != s["kind"]:
            return _span(s["price"], swings[j]["price"])[0]
    return None


def leg_moves(swings, i):
    """پاهایِ پیوتِ iام با (rel, abs, base) — پایهٔ درجۀبندیِ ماژور.

    قاعدۀِ حاکم: پا ماژور است اگر جابجاییِ **مطلقش** از `atr_x × ATR` بلندتر باشد
    (کفِ `floor_pct × مبنا` هم دارد). مبنا قیمتِ *آغازِ همان پا* است، نه قیمتِ
    پیوت: همان کاری که `structure_engine3._threshold` می‌کند اگر ATR بر قیمتِ مقصد
    تقسیم شود، درِ نمادی که از ۱۰۰ به ۶ ریخته، آستانه را تا ۳۳۰٪ بالا می‌برد و
    هرِ کفی را غیرماژور می‌کند (شاهدِ اندازه‌گیری‌شده درِ fixtureهایِ
    `dev/fts_trend_fixtures_v1075.py` دورِ اولِ همین مأموریت).
    """
    s = swings[i]
    moves = []
    for j in range(i - 1, -1, -1):
        if swings[j]["kind"] != s["kind"]:
            rel, mv, base = _span(swings[j]["price"], s["price"])
            if mv is not None:
                moves.append({"dir": "in", "rel": rel, "abs": mv, "base": base})
            break
    for j in range(i + 1, len(swings)):
        if swings[j]["kind"] != s["kind"]:
            rel, mv, base = _span(s["price"], swings[j]["price"])
            if mv is not None:
                moves.append({"dir": "out", "rel": rel, "abs": mv, "base": base})
            break
    return moves


def _atr_ref(atr, upto):
    """میانیۀِ ATRِ پنجرۀِ اخیر تا لحظۀِ `upto` (علی‌هذا، بی‌عددِ جدید)."""
    if not atr or upto is None:
        return None
    seg = [a for a in atr[max(0, int(upto) - ATR_WINDOW + 1):int(upto) + 1] if a]
    if not seg:
        seg = [a for a in atr[:max(1, int(upto) + 1)] if a]
    if not seg:
        return None
    seg = sorted(seg)
    m = len(seg) // 2
    return seg[m] if len(seg) % 2 else 0.5 * (seg[m - 1] + seg[m])


def grade(swings, series, atr_x=MAJOR_LEG_ATR_X, floor_pct=MAJOR_LEG_FLOOR_PCT,
          recent=RECENT_BARS):
    """همان دیکشنری‌هایِ `_fts_swings` + `major/leg_pct/leg_atr_x/recent/ma100_ctx`.

    ورودی باید فهرستِ **تأییدشده‌ها** باشد (`_fts_swings`)؛ چیزی که هنوز پنجره‌اش
    کامل نشده درِ این فهرست جایی ندارد و از همین رو درِ رأی هم نمی‌تواند بنشیند.
    """
    n = len(series)
    if not swings or n == 0:
        return []
    atr = atr_series(series)                       # خانه‌به‌خانه، warm-up ⇒ None
    # MA100 به‌عنوان زمینه (قاعدۀِ جزوه برایِ «کفِ ارزندۀِ ماژور») — بی‌نقش در فیلتر
    ma = []
    run = 0.0
    win = 100
    for i, c in enumerate(series):
        cl = _f(c.get("close")) or 0.0
        run += cl
        if i >= win:
            run -= (_f(series[i - win].get("close")) or 0.0)
        ma.append(run / win if i + 1 >= win else None)

    out = []
    for i, s in enumerate(swings):
        moves = leg_moves(swings, i)
        amp_in = next((m["rel"] for m in moves if m["dir"] == "in"), None)
        amp_out = next((m["rel"] for m in moves if m["dir"] == "out"), None)
        rels = [m["rel"] for m in moves if m["rel"] is not None]
        amp = max(rels) if rels else None
        ci = s.get("confirm_idx")
        av = _atr_ref(atr, ci)
        major = None
        leg_atr_x = None
        if moves:
            if av:
                # کافی است یکی از دو پا از آستانه بلندتر باشد؛ کفِ `floor_pct × مبنا`
                # برایِ نمادهایِ بی‌نوسان است که ATRشان به صفر نزدیک می‌شود.
                major = any(m["abs"] >= max(atr_x * float(av), floor_pct * m["base"])
                            for m in moves)
                best = max(moves, key=lambda m: m["abs"])
                leg_atr_x = round(best["abs"] / float(av), 4)
            else:
                major = any(m["rel"] >= floor_pct for m in moves)
        age = None if ci is None else (n - 1 - int(ci))
        m100 = ma[s["idx"]] if s.get("idx") is not None and s["idx"] < n else None
        ctx = None
        if m100 and s.get("price"):
            ctx = "below-ma100" if s["kind"] == "low" and float(s["price"]) <= m100 else \
                  "above-ma100" if s["kind"] == "high" and float(s["price"]) >= m100 else "mid-ma100"
        r = dict(s)
        r.update({"major": major, "leg_pct": None if amp is None else round(amp, 6),
                  "leg_pct_in": None if amp_in is None else round(amp_in, 6),
                  "leg_pct_out": None if amp_out is None else round(amp_out, 6),
                  "out_pending": amp_out is None,
                  "leg_atr_x": leg_atr_x, "recent": bool(age is not None and age < recent),
                  "confirm_age_bars": age, "ma100_ctx": ctx})
        out.append(r)
    return out


def summarize(graded):
    """`(majors, info)` از فهرستِ درجه‌بندی‌شده — خودِ رأی را این فایل نمی‌سازد.

    info = {"graded", "major_highs", "major_lows", "minor_highs", "minor_lows",
            "undecided", "dropped_minor", "enough", "reason", "atr_x", "floor_pct"}
    وقتی `enough` صادق نیست، فراخوان نباید جهتِ پیش‌فرض بسازد: داورِ System 1 با
    همان فهرستِ کوتاه `na` می‌دهد (یا fallbackِ اعلام‌شدۀِ recent-window).
    """
    majors = [x for x in graded if x.get("major") is True]
    h = [x for x in majors if x["kind"] == "high"]
    l = [x for x in majors if x["kind"] == "low"]
    enough = len(h) >= 2 and len(l) >= 2
    reason = None
    if graded and not enough:
        reason = ("تنها %d سقف و %d کفِ ماژور از %d پیوت (آستانه %s×ATR)"
                  % (len(h), len(l), len(graded), MAJOR_LEG_ATR_X))
    return majors, {
        "graded": len(graded),
        "major_highs": len(h),
        "major_lows": len(l),
        "minor_highs": len([x for x in graded if x["kind"] == "high" and x.get("major") is False]),
        "minor_lows": len([x for x in graded if x["kind"] == "low" and x.get("major") is False]),
        "undecided": len([x for x in graded if x.get("major") is None]),
        "dropped_minor": len(graded) - len(majors),
        "enough": enough,
        "reason": reason,
        "atr_x": MAJOR_LEG_ATR_X,
        "floor_pct": MAJOR_LEG_FLOOR_PCT,
    }


def select(swings, series, **kw):
    """grade + summarize در یکِ فراخوانی (برایِ مصرف‌کننده‌هایی که فهرستِ کامل را نمی‌خواهند)."""
    return summarize(grade(swings, series, **kw))


def forming(series, graded, k=3):
    """سقف/کفِ در حالِ شکل‌گیری — اطلاعِ موقت، جدا از پیوت‌هایِ قطعی.

    بعد ازِ آخرینِ پیوتِ تأییدشده تا آخرینِ کندلِ بسته، یکِ پا در جریان است. تا
    پنجره‌اش کامل نشود (k کندلِ بعدازِ خودش) **پیوت نیست**، پس درِ فهرستِ داوری
    نمی‌نشیند؛ اما کاربر باید بداند موتورِ ساختار روی چه چیزی هنوز نظرِ قطعی ندارد.
    نگاه‌به‌آینده ندارد: فقطِ کندل‌هایِ موجود تا همین لحظه خوانده می‌شود.
    """
    n = len(series)
    if n == 0:
        return None
    last_idx = max((int(x["idx"]) for x in graded), default=-1)
    start = last_idx + 1
    if k < 0:
        k = 0
    tail = series[start:]
    if not tail:
        return None
    hi_i = max(range(len(tail)), key=lambda j: _f(tail[j].get("high")) or 0.0)
    lo_i = min(range(len(tail)), key=lambda j: _f(tail[j].get("low")) or float("inf"))

    def leg(j):
        c = tail[j]
        idx = start + j
        return {"idx": idx, "time": str(c.get("time") or "")[:10],
                "price": _f(c.get("high")) if j == hi_i else _f(c.get("low")),
                "provisional": True, "confirmed": False,
                "bars_since": n - 1 - idx, "bars_to_confirm": max(0, k - (n - 1 - idx))}

    hi, lo = leg(hi_i), leg(lo_i)
    return {"since_pivot_time": (str(series[last_idx].get("time") or "")[:10]
                                 if last_idx >= 0 else None),
            "bars_since_last_pivot": n - 1 - last_idx if last_idx >= 0 else n,
            "high": hi, "low": lo,
            "note": "پنجرۀ تأیید این دو کامل نشده؛ رأیِ قطعی روی آن‌ها ساخته نمی‌شود"}


def closed_only(series):
    """سریِ ساختار: کندلِ جلسهٔ جاریِ تکمیل‌نشده بیرون می‌ماند.

    چرا: `get_chart_tsetmc`/`get_chart_db` کندلِ امروز را از تابلو تزریق می‌کنند
    (`_watch_live_bar`، نشانهٔ `live_forming`). `_fts_swings` برایِ پیوتِ iام
    پنجرۀِ [i+1, i+k] را می‌خواند، پس برایِ i = n-k-1 آن پنجره تا کندلِ جاری
    می‌رسد — یعنی یکِ تیکِ درون‌جلسه می‌تواند پیوتِ «تأییدشده» بسازد یا ببیند.
    سنجشِ همین دور (`_audit/major_swing_evidence.py`، ۱۲۹ نماد): تکانِ ±۲٪ آخرینِ
    بسته درِ ۳ نماد رأیِ D را عوض کرد، هر سه `up→down`، و هیچ‌یک در جهتِ مخالف.
    """
    return [c for c in series or [] if not (isinstance(c, dict) and c.get("live_forming"))]
