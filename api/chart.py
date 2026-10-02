"""Candle history, key levels, calendar/MA events, chart-db and patterns.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from bors_config import DB_PATH, MA_WINDOWS, _CAL_CACHE_PATH, _cal_cache
from tape_flags import JET_LADDER
import candle_contract
import price_basis
from ._core import get_user_db, sym_pred
from fastapi import APIRouter
from fastapi import Query
import datetime
import json
import math
import os
import sqlite3
import threading
import time


router = APIRouter()


CDN_OFFLINE_UNTIL = 0.0


def _parse_tsetmc_csv(text):
    """CSV روزانهٔ TSETMC → (candles, volumes, all_rows). خالص: بدون شبکه و دیتابیس.

    `all_rows` همهٔ روزهایی است که پایه و پایانیِ معتبر دارند — حتی روزهای بدون
    معامله (H=L=۰) که کندل نمی‌شوند؛ تشخیصِ تعدیل به آن‌ها نیاز دارد.
    """
    candles, volumes, all_rows = [], [], []
    lines = text.splitlines()
    # v9.7: ایندکس ستون‌ها از خودِ هدر خوانده میشود، نه عدد ثابت.
    # هدر رسمی TSETMC:
    #  <TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,
    #  <VOL>,<OPENINT>,<PER>,<OPEN>,<LAST>
    # <LAST> = «قیمت آخرین معامله» — در ۹۰٪ روزها با <CLOSE> (قیمت پایانی)
    # متفاوت است (خساپا: ۳۶۱۴ ردیف از ۳۹۹۹). تا پیش از v9.7 این ستون
    # نادیده گرفته می‌شد و «آخرین قیمت» همان پایانی را نشان می‌داد.
    _hdr = {}
    if lines and lines[0].strip().startswith('<'):
        _hdr = {nm.strip().upper(): i for i, nm in enumerate(lines[0].split(','))}
    i_last = _hdr.get('<LAST>', 11)
    for ln in lines[1:]:
        if not ln.strip():
            continue
        p = [x.strip() for x in ln.split(",")]
        if len(p) < 11:
            continue
        try:
            d = p[1]
            dt = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            first = float(p[2] or 0)   # <FIRST> = اولین معاملهٔ روز
            hi = float(p[3]); lo = float(p[4]); c = float(p[5])
            base = float(p[10] or 0)   # <OPEN>  = «قیمت پایه» (= پایانی دیروز، یا پس از تعدیل)
            v = float(p[7]) if p[7] else 0
        except (ValueError, IndexError):
            continue
        # v8.7 FIX-1: بدنهٔ کندل = «اولین معامله» (ستون ۲). ستون <OPEN> که قبلاً استفاده
        # می‌شد قیمت «پایه» است نه یک قیمت معاملاتی؛ همیشه ≈ پایانی دیروز بود در نتیجه
        # (الف) هیچ گپ معاملاتی روی چارت دیده نمی‌شد (۹۹.۸٪ کندل‌ها open==closeِ دیروز)
        # و (ب) در ~۴۹٪ روزها open بیرون بازهٔ [low, high] می‌افتاد (وضعیت هندسی ناممکن).
        # اگر روزی FIRST صفر/خالی بود (روز بدون معامله) به قیمت پایه و سپس به پایانی برمی‌گردد.
        # v8.7 FIX-1b: در روزهای کمیاب که CDN ستون <FIRST> را صفر می‌دهد ولی معامله
        # رخ داده (خساپا ۲۰۲۱-۱۲-۰۸: پایه=۱۷۵۶ در برابر H=L=C=۱۸۲۵)، پایه می‌تواند
        # بیرون بازه بیفتد و کندلِ ناممکن بسازد؛ پس داخل [low, high] clamp می‌شود.
        o = first if first > 0 else (min(max(base, lo), hi) if base > 0 else c)
        if c > 0 and base > 0:
            all_rows.append({"time": dt, "base": base, "close": c, "vol": v})

        if hi <= 0 or c <= 0 or o <= 0 or lo <= 0:
            continue
        # ترمیمِ هندسه: خودِ CSV در درصدِ قابل‌توجهی از ردیف‌های تاریخی، پایانی
        # (یا اولین‌معامله) بیرونِ [کمینه، بیشینه] می‌دهد — نمونهٔ فولاد
        # ۲۰۰-۱۲-۲۲: H=L=۱۹۷۳ در برابر C=۱۹۱۷؛ آمارِ ۱۴۰ نماد: اخابر ۶۹۴ ردیف
        # (۱۸٪)، اميد ۳۹۲ (۲۰٪)، البرز ۵۲۲، خودرو ۴۱۵). از آنجا که <CLOSE> به
        # پایهٔ روزِ بعد زنجیر می‌شود (base(t+1)==close(t))، پایانی معتبر است و
        # سایه نقص دارد؛ پس سایه را گِشاد می‌کنیم نه اینکه پایانی را خُرد کنیم.
        # همان قاعده‌ای که مسیرِ کندلِ زندهٔ get_chart_db از قبل رعایت می‌کند.
        # تنها قاعدۀ هندسه (Step 4): سایه گِشاد می‌شود، هیچ قیمتِ منتشرشده خُرد نمی‌شود
        hi, lo = candle_contract.widen(o, hi, lo, c)
        # v10.7.0 (کارِ #73 قدمِ ۳): «آخرین» دیگر به پایانی fallback نمی‌کند و دیگر
        # clamp نمی‌شود. دو جعلِ قبلی همان چیزی بود که قرارداد §۱-ث شرطِ ۳ بست:
        #   (الف) `last = c` وقتی ستون خالی است ⇒ مصرف‌کننده عددِ پایانی را با نامِ
        #       «آخرین» می‌خواند؛ حالا None می‌ماند و price_basis صریح اعلام می‌کند.
        #   (ب) clamp داخلِ [low, high] ⇒ قیمتِ منتخب بی‌صدا جابه‌جا می‌شد. حالا سایه
        #       گِشاد می‌شود (همان قاعدۀ candle_from_row) و تعدادش درِ متادیتا می‌آید.
        last = float(p[i_last]) if (len(p) > i_last and p[i_last]) else None
        candles.append({"time": dt, "open": o, "high": hi, "low": lo,
                        "close": c, "last": last})
        volumes.append({"time": dt, "value": v, "color": "#10b981" if c >= o else "#f43f5e"})
    return candles, volumes, all_rows


def _adjust_events_from_rows(all_rows):
    """(adj_events, anchored) — تعدیل از دو نشانۀ خامِ CSV، به‌علاوهٔ درِ لنگر.

    نشانۀ (ی) — گسستِ «قیمت پایه»: `base(t) != close(t-1)`. رفتارِ همیشگیِ برنامه.

    نشانۀ (ب) — بازنویسیِ «قیمت پایانی» روی سطرِ بی‌معامله: روزِ توقفِ معامله با
    VOL=0 درِ CSV منتشر می‌شود و TSETMC تعدیل را بعضی نمادها **داخلِ ستونِ پایانیِ
    همان سطر** می‌گذارد، بی‌آنکه پایه جابه‌جا شود. سنجشِ مستقیم (کارِ #73، قدمِ ۶،
    `_audit/adjust_zero_volume_probe.py`):

        وبملت  ۲۰۱۲-۰۲-۰۴  VOL=0  CLOSE=2242  BASE=2242
        وبملت  ۲۰۱۲-۰۲-۰۵  VOL=0  CLOSE=1793  BASE=2242   ← ۱۷۹۳/۲۲۴۲ = ۰٫۷۹۹۷۳
        وبملت  ۲۰۱۲-۰۲-۰۶  VOL=۱۵٬۱۸۷٬۵۸۰  CLOSE=1736  BASE=1793   ← پایه می‌خواند

    درِ این الگو (ی) هیچ‌وقت آتش نمی‌زند (پایۀ ۰۲-۰۶ == پایانیِ ۰۲-۰۵) و زنجیرِ تعدیل
    شش رویدادِ ۱۳۹۰–۱۳۹۳ وبملت را کامل از دست می‌داد — مقیاسِ تاریخِ قبل از آن تا
    ۳٫۸ برابر با رهاورد فرق می‌کرد. نسبتِ (ب) با معکوسِ گامِ پلکانِ رهاورد می‌خواند
    (۱/۰٫۷۹۹۷۳ = ۱٫۲۵۰۴ در برابرِ ۱٫۲۵۰۴۱۸ِ اندازه‌گیری‌شدۀ آن‌ها).

    دو نشانۀ روزِ یکی درِ دوازده نماد سنجیده‌شده صفر بار دیده شد (پس جمع‌شدنشان
    ضریب را دو‌بار نمی‌کند)، و با درِ لنگرِ زیر هم می‌خورند.

    درِ لنگر چرا لازم است: گسستِ پایه تنها وقتی نشانهٔ تعدیل است که پایهٔ هر روز
    «خودِ پایانیِ دیروز» باشد. در سهام این برقرار است (۹۹٪+ روزها دقیقاً برابر)، ولی
    صندوق‌هایی که قیمت پایه‌شان را بازارگردان/NAV می‌گذارد هر روز گسست دارند و
    شمارشگر، تعدیلِ جعلی می‌سازد (اعتماد4: ۹۰۰، آبادا3: ۱٬۲۳۱، آسود2: ۳۴۲ «تعدیل»).
    رویدادِ جعلی بدتر از نبودِ رویداد است: فاکتورِ تجمعی‌اش کل تاریخِ گذشته را
    مقیاس می‌کند و چارت را می‌شکند. پس در آن حالت هیچ رویدادی نمی‌دهیم.
    """
    asc = sorted((x for x in all_rows if x["close"] > 0 and x["base"] > 0),
                 key=lambda x: x["time"])
    _anch = _pairs = 0
    prev = None
    for row in asc:
        if prev and prev["close"] > 0:
            _pairs += 1
            if row["base"] == prev["close"]:
                _anch += 1
        prev = row
    # با نمونهٔ کم داوری نمی‌کنیم: بی‌شواهد، رفتارِ پیشین (گسست = تعدیل) محترم می‌ماند.
    anchored = not (_pairs >= 20 and _anch / _pairs < ANCHOR_MIN)
    if not anchored:
        return [], False
    by_date = {}
    prev = None
    for row in asc:
        if prev:
            ratio = row["base"] / prev["close"]
            # آستانه دوتایی: هم ≥ یک واحد قیمت، هم > ADJ_TOL نسبی — تا گردکردنِ عددِ
            # قیمت، رویداد جعلی نسازد و در عین حال کوچک‌ترین تقسیم واقعی هم حذف نشود.
            if abs(row["base"] - prev["close"]) >= 1.0 and abs(ratio - 1.0) > ADJ_TOL:
                by_date.setdefault(row["time"], {"date": row["time"], "ratio": round(ratio, 6)})
        if row.get("vol") == 0.0:
            r2 = row["close"] / row["base"]
            if abs(r2 - 1.0) > ADJ_TOL:
                by_date.setdefault(row["time"], {"date": row["time"], "ratio": round(r2, 6)})
        prev = row
    adj_events = sorted(by_date.values(), key=lambda e: e["date"])
    return adj_events, True


def _d_even_to_date(d_even):
    """20260928 (int/str) → '2026-09-28'؛ بی‌اعتبار → None."""
    s = str(d_even or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def _watch_live_bar(symbol, after_date):
    """(bar, error) — کندلِ جلسهٔ جاری از market_watch، با تاریخِ خودِ جلسه.

    تاریخ از `d_evenِ` ردیف خوانده می‌شود، نه از `date.today()`. پیش از این،
    همان ردیفِ جلسهٔ *دیروز* با برچسبِ «امروز» می‌چسبید: فولاد بامداد ۱۴۰۵/۷/۸
    (پیش از بازگشایی) کندلی به نام ۲۰۲۶-۰۹-۲۹ گرفت با O=H=L=C=۳۴۲۰ و حجمِ صفر،
    درست کنارِ کندلِ واقعیِ ۰۹-۲۸ که پایانی‌اش همان ۳۴۲۰ بود. آن کندلِ شبح هم
    مقیاسِ عمودی را جابه‌جا می‌کند و هم سطل‌هایِ تجمیعِ هفتگی را یک‌خانه می‌کِشَد،
    پس «عددِ کندلِ پنجم» بی‌هیچ معاملۀ‌ای عوض می‌شد.

    `after_date` آخرین روزِ سریِ موجود است؛ فقط جلسه‌ای که **جدیدتر** از آن است
    تزریق می‌شود — یعنی واقعاً هنوز کندلش در تاریخچه نیست.
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        try:
            # v8.7 FIX-4: نام ستون‌ها با اسکیمای واقعی market_watch تطبیق داده شد
            # (p_open/p_max/p_min وجود نداشتند → OperationalError هر بار توسط
            #  exceptِ خاموش بلعیده می‌شد و کندل زندهٔ امروز هرگز تزریق نمی‌شد).
            #  price_first = اولین معامله (هم‌خانمان با FIX-1)، p_closing = پایانی.
            _p18, _a18 = sym_pred("i.l_val18", symbol)
            _p30, _a30 = sym_pred("i.l_val30", symbol)
            row = conn.execute(
                "SELECT m.price_first, m.price_max, m.price_min, m.p_closing, m.q_tot_tran, "
                "       m.d_even, m.p_last "
                "FROM instruments i LEFT JOIN market_watch m ON i.ins_code = m.ins_code "
                "WHERE (%s OR %s) AND m.p_closing > 0 ORDER BY m.d_even DESC LIMIT 1" % (_p18, _p30),
                (*_a18, *_a30)).fetchone()
        finally:
            conn.close()
    except Exception as e:
        # v8.7 FIX-4: خطا دیگر خاموش نیست — در پاسخ منعکس می‌شود تا در لاگ/دیباگ دیده شود
        return None, f"{type(e).__name__}: {e}"
    if not row:
        return None, None
    session_date = _d_even_to_date(row[5])
    if not session_date or (after_date and session_date <= after_date):
        return None, None
    p_first, p_max, p_min, p_close, vol = (
        float(row[0] or 0), float(row[1] or 0), float(row[2] or 0),
        float(row[3] or 0), float(row[4] or 0))
    p_last = float(row[6] or 0)                       # v9.7
    vol = float(row[4] or 0)
    # «قیمت پایانی» ردیفِ تابلو پیش از بازگشایی هم پر است (قیمتِ پایهٔ امروز =
    # پایانیِ دیروز)، ولی حجمِ صفر یعنی هنوز هیچ معامله‌ای نشده — همان چیزی که
    # باید از کندل ساخته نشود. اثباتِ زنده (اپِ نصبی، ۱۴۰۵-۰۷-۰۷ ساعتِ ۰۷:۵۰):
    # d_even=20260929 با q_tot_tran=0 و پایانیِ ۳۴۲۰.
    if vol <= 0:
        return None, None
    # افت‌به‌روی امن: تابلو ممکن است در میانهٔ روز هنوز high/low را پر نکرده باشد
    o_l = p_first if p_first > 0 else p_close
    h_l, l_l = candle_contract.widen(o_l, p_max, p_min, p_close)
    return ({"time": session_date, "open": o_l, "high": h_l, "low": l_l,
             "close": p_close, "volume": vol,
             # «آخرین معامله» زنده از market_watch.p_last؛ بی‌fallback به پایانی
             # (کارِ #73 قدمِ ۳، شرطِ ۳ قرارداد). p_last نبود ⇒ None، و price_basis
             # خودش اعلام می‌کند که این سری last ندارد.
             "last": p_last if p_last > 0 else None}), None


HISTORY_REPAIR_MIN_GAP = 900.0   # هر نماد، دست‌کم هر ۱۵ دقیقه یک‌بار تازه می‌شود

_HISTORY_REPAIR_AT = {}          # symbol → monotonicِ آخرین تلاش
_HISTORY_REPAIR_LOCK = threading.Lock()


def _history_repair_due(last_date, target_date, symbol, now=None):
    """آیا تاریخچۀ محلیِ این نماد واقعاً به تازگی نیاز دارد؟ (خالص، بی‌کش)

    دو شرط: (۱) `target_date` (امروزِ تقویمی) از آخرین روزِ سروشده تازه‌تر باشد —
    یعنی شکافِ واقعی، نه فقط عمقِ کم؛ و (۲) از آخرین تلاشِ همان نماد
    `HISTORY_REPAIR_MIN_GAP` گذشته باشد. (۲) با ساعتِ تزریق‌شونده اندازه گرفته
    می‌شود تا گاردِ آفلاین همان مسیر را ثابتِ قدم بداند.
    """
    if not last_date or not target_date or target_date <= last_date:
        return False
    import time as _t
    _now = _t.monotonic() if now is None else now
    return (_now - _HISTORY_REPAIR_AT.get(symbol, -1e12)) >= HISTORY_REPAIR_MIN_GAP


def _schedule_history_repair(symbol, last_date, target_date):
    """تاریخچۀ *همین یک نماد* را در پس‌زمینه تازه می‌کند.

    چرا: وقتی CDN نمی‌رسد، نمودار به `price_history` می‌افتد و آنجا بعضی نمادها
    هفته‌ها عقب‌اند (اندازۀ ۱۴۰۵-۰۷-۰۷ روی بانکِ کاری: ۴٬۸۳۷ نماد از ۵٬۷۱۷ از
    تازه‌ترین روزِ خودِ جدول عقب‌تر بودند). نشان‌دادنِ منبع تنها نیمیِ کار است؛
    نیمۀ دیگر این است که دیدِ بعدی کامل باشد.
    ایمنی (ریسکِ داوری‌شدۀ پایلوت ۰٫۸): یک نماد، نه کل بازار؛ هر نماد دست‌کم
    ۱۵ دقیقه یک‌بار (علامت‌گذاری درونِ همان قفل، پس دو درخواستِ هم‌زمان یکی را
    دوباره نمی‌فرستند)؛ پاسخِ چارت را هرگز نگه نمی‌دارد؛ و از همان
    `fetch_price_history` می‌گذرد که خودش min_interval و سقفِ ۴۲۹ دارد.
    """
    with _HISTORY_REPAIR_LOCK:
        if not _history_repair_due(last_date, target_date, symbol):
            return False
        _HISTORY_REPAIR_AT[symbol] = time.monotonic()

    def _run():
        try:
            import test_tsetmc
            test_tsetmc.fetch_price_history(symbol)
        except Exception:
            # بهترینِ تلاش: نشد، دیدِ بعدی دوباره امتحان می‌کند
            pass
    threading.Thread(target=_run, daemon=True, name="hist-repair").start()
    return True


def _attach_live_bar(symbol, res):
    """کندلِ جلسهٔ جاری را به پاسخِ /api/chart اضافه می‌کند — بی‌نوشتن در کش.

    تا پیش از این فقط /api/chart-db کندلِ زنده می‌ساخت، پس همان نماد در دو
    اندپوینت دو «آخرین کندل» متفاوت داشت. این تابع روی *نسخه* کار می‌کند تا
    شیءِ کش‌شده دست‌نخورده بماند و کندلِ زنده هر بار تازه بچسبد (وگرنه یک
    کندلِ نیم‌کار تا یک ساعت در CHART_CACHE_TTL قفل می‌شد).
    """
    candles = res.get("candles") or []
    if not candles:
        return price_basis.resolve_payload(res)
    newest = max(c["time"] for c in candles)   # ترتیبِ آرایه به خودِ سری واگذار است
    bar, err = _watch_live_bar(symbol, newest)
    if bar is None:
        return price_basis.resolve_payload(dict(res, liveError=err) if err else res)
    # /api/chart نزولی می‌دهد (تازه‌به‌قدیم) و مسیرِ محلی صعودی — کندلِ تازه باید
    # در همان سمتی بنشیند که سری بزرگ می‌شود، نه همیشه در خانۀ صفر.
    at = len(candles) if candles[-1]["time"] > candles[0]["time"] else 0
    out = dict(res)
    cands = list(candles); cands.insert(at, bar)
    out["candles"] = cands
    vols = list(res.get("volumes") or [])
    vols.insert(min(at, len(vols)), {"time": bar["time"], "value": bar.get("volume", 0),
                                     "color": "#10b981" if bar["close"] >= bar["open"] else "#f43f5e"})
    out["volumes"] = vols
    facts = list(res.get("factors") or [])
    facts.insert(min(at, len(facts)), {"time": bar["time"], "factor": 1.0})   # تازه‌ترین خام
    out["factors"] = facts
    out["count"] = len(cands)
    out["liveInjected"] = True
    # تنها نقطۀ انتخابِ مبنایِ قیمت درِ این مسیر (کارِ #73 قدمِ ۳): کندلِ زنده هم
    # داخلِ سری است، پس یکِ تصمیمِ مبنایی برایِ کلِ سری اینجا گرفته می‌شود — نه یکی
    # برایِ تاریخچه و یکی برایِ امروز.
    return price_basis.resolve_payload(out)


@router.get("/api/chart/{symbol}")
def get_chart_tsetmc(symbol: str):
    """نمودار کامل از CDN TSETMC: OHLCV روزانه + رویدادهای تعدیل عملکردی (ادجاست) با فال‌بک خودکار به دیتابیس محلی."""
    import time as _t
    global CDN_OFFLINE_UNTIL
    _cached = CHART_CACHE.get(symbol)
    if _cached and (_t.time() - _cached[0]) < _cached[2]:
        return _attach_live_bar(symbol, _cached[1])
    import requests as _rq
    from urllib.parse import quote

    def _fallback_local():
        try:
            db_res = get_chart_db(symbol)
            if db_res.get("status") == "success" and db_res.get("candles"):
                cands = db_res["candles"]
                vols = db_res.get("volumes") or [
                    {"time": c["time"], "value": c.get("volume", 0),
                     "color": "#10b981" if c.get("close", 0) >= c.get("open", 0) else "#f43f5e"}
                    for c in cands
                ]
                res = {
                    "status": "success",
                    "symbol": symbol,
                    "candles": cands,
                    "volumes": vols,
                    "factors": db_res.get("factors") or [{"time": c["time"], "factor": 1.0} for c in cands],
                    "adjustEvents": db_res.get("adjustEvents") or [],
                    "adjustSource": "local-db-fallback",
                    # فرانت با این پرچم «منبعِ جایگزین» را روی چارت می‌نویسد:
                    # سریِ محلی هم کوتاه‌تر است و هم بی‌رویدادِ تعدیل، پس هر
                    # جابه‌جاییِ اعدادِ محور باید برای کاربر توضیح داشته باشد.
                    "degraded": True,
                    "count": len(cands),
                    "fts": db_res.get("fts"),
                }
                # شکافِ تاریخچه را بی‌صدا نگه نمی‌داریم: اگر سریِ محلی حتی
                # امروزِ تقویمی را هم ندارد، نشستِ تازه‌ای جا افتاده و همین یک
                # نماد در پس‌زمینه تازه می‌شود تا دیدِ بعدی کامل باشد.
                res["historyRepairScheduled"] = _schedule_history_repair(
                    symbol, cands[-1]["time"], datetime.date.today().strftime("%Y-%m-%d"))
                CHART_CACHE[symbol] = (_t.time(), res, CHART_FALLBACK_TTL)
                return res
        except Exception:
            pass
        return None

    # اگر CDN اخیراً قطع/تایم‌اوت بوده، بلافاصله از دیتابیس محلی لود کن تا کاربر معطل نشود
    if _t.time() < CDN_OFFLINE_UNTIL:
        fb = _fallback_local()
        if fb:
            return fb

    try:
        # نرمال‌سازی کاراکترهای عربی/فارسی ('ك'→'ک'، 'ي'→'ی'، 'ى'→'ی') چون DB ممکن است عربی ذخیره کند
        _norm = lambda s: str(s).translate(str.maketrans({'ك': 'ک', 'ي': 'ی', 'ى': 'ی', 'ك': 'ک'}))
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        # DETERMINISM FIX (2026-09-09): نمادهای بازانتشار‌یافته (مانند «حيان072» که
        # دو ins_code دارد — سری قدیمی و سری جدید) با LIMIT 1 بدون ORDER BY هر بار
        # ردیفِ دلخواهِ SQLite را می‌گرفتند → در دو اجرا، نمودارِ یک اوراقِ «دیگر»
        # با همان نام سرو می‌شد. اکنون newest-first: ردیفِ به‌روزتر (ابزارِ فعلیِ
        # بازار) به‌صورت قطعی انتخاب می‌شود.
        _pred, _params = sym_pred("l_val18", symbol)
        ins = conn.execute(
            f"SELECT ins_code FROM instruments WHERE {_pred} ORDER BY updated_at DESC LIMIT 1", _params
        ).fetchone()
        if not ins:
            try:
                import fts_engine
                norm_s = fts_engine.norm_fa(symbol)
            except Exception:
                norm_s = symbol
            ins = conn.execute(
                "SELECT ins_code FROM instruments WHERE REPLACE(REPLACE(REPLACE(l_val18, 'ك', 'ک'), 'ي', 'ی'), 'ى', 'ی') = ? ORDER BY updated_at DESC LIMIT 1",
                (norm_s,)
            ).fetchone()
        conn.close()
        if not ins:
            fb = _fallback_local()
            if fb:
                return fb
            return {"status": "error", "message": "نماد در تابلوی بازار یافت نشد (ممکن است خیلی جدید باشد و هنوز در بروزرسانی تابلو قرار نگرفته؛ دکمهٔ «بروزرسانی تابلو» را بزنید و دوباره تلاش کنید)"}
        ins_code = ins[0]
        hdr = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        # ۱) تاریخچهٔ روزانه — از ۱۳۸۰ (با سرکوب ریترای و تایم‌اوت اتصال ۱.۵ ثانیه‌ای)
        try:
            sess = _rq.Session()
            sess.mount("https://", _rq.adapters.HTTPAdapter(max_retries=0))
            r = sess.get(
                f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/19900101",
                headers=hdr, timeout=(1.5, 3.0),
            )
        except Exception:
            CDN_OFFLINE_UNTIL = _t.time() + 120.0  # مدار قطع شد — تا ۲ دقیقه مستقیم از دیتابیس محلی بخوان
            fb = _fallback_local()
            if fb:
                return fb
            raise

        if r.status_code != 200 or not r.text or len(r.text.strip()) < 20:
            fb = _fallback_local()
            if fb:
                return fb
            return {"status": "error", "message": f"CSV HTTP {r.status_code}"}
        candles, volumes, all_rows = _parse_tsetmc_csv(r.text)
        # رویدادهای تعدیل: گسستِ «قیمت پایه» در همین CSV، به‌علاوهٔ درِ لنگر. منطق و
        # دلیلِ حذفِ APF/gap-detector در _adjust_events_from_rows مستند است.
        adj_events, anchored = _adjust_events_from_rows(all_rows)
        adjust_source = ("base-price-discontinuity" if adj_events
                         else "base-not-anchored" if not anchored
                         else "no-adjustment-event")
        # ۳) فاکتور تعدیل (back-adjustment، مقیاس روز آخر):
        #        factor(t) = ∏ ratio  برای همهٔ رویدادهایی که date > t
        #    → آخرین کندل دقیقاً خام می‌ماند (factor=1)، قیمت‌های قدیمی‌تر کوچک‌تر، و هیچ
        #      پرش مصنوعی ساخته نمی‌شود چون فاکتور فقط در همان روزِ تغییر پایه جابه‌جا می‌شود.
        #    v8.7: یک پیمایش معکوس O(n+m) به‌جای حلقهٔ تو‌در‌توی n×m (۵۲۸۸×۲۰) قبلی؛ round هم
        #    از ۶ رقم به ۱۰ رقم (فاکتور قدیمی‌ترین کندل به ~۱e-4 می‌رسد و با ۶ رقم دقتش می‌مرد).
        ev_dates = [e["date"] for e in adj_events]
        ev_ratios = [e["ratio"] for e in adj_events]
        factors = [None] * len(candles)
        # ترتیب‌مستقل: CSV امروز نزولی است (تازه‌به‌قدیم) ولی نباید به آن اعتماد کرد؛
        # ایندکس‌ها را یک‌بار صعودی مرتب می‌کنیم و از جدیدترین به قدیمی‌ترین می‌رویم.
        order = sorted(range(len(candles)), key=lambda i: candles[i]["time"])
        f = 1.0
        j = len(ev_dates) - 1
        for i in reversed(order):
            t = candles[i]["time"]
            while j >= 0 and ev_dates[j] > t:
                f *= ev_ratios[j]
                j -= 1
            factors[i] = {"time": t, "factor": round(f, 10)}

        # صفر کندل ≠ موفق. اوراق/نمادهای منقضی CSV خالی می‌دهند؛ قبلاً
        # status=success با count=0 برمی‌گشت و چارت بی‌توضیح خالی می‌ماند.
        if not candles:
            fb = _fallback_local()
            if fb:
                return fb
            return {"status": "error",
                    "message": "هیچ کندلِ معاملاتی برای این نماد منتشر نشده است "
                               "(اوراقِ منقضی یا نمادی که هرگز معامله نشده)."}
        result = {
            "status": "success",
            "candles": candles,
            "volumes": volumes,
            "factors": factors,
            "adjustEvents": adj_events,
            "adjustSource": adjust_source,   # v8.7 FIX-2 (دیگر APF+gap-detector نیست)
            "count": len(candles),
        }
        CHART_CACHE[symbol] = (time.time(), result, CHART_CACHE_TTL)
        return _attach_live_bar(symbol, result)
    except Exception as e:
        fb = _fallback_local()
        if fb:
            return fb
        return {"status": "error", "message": str(e)}

def _swing_extremes(rows, k=3, min_strength=2):
    """Swing highs/lows با rolling extremes:
    نقطهٔ i اگر max/min (در پنجرهٔ [i-k, i+k]) باشد و تعداد تکرارش ≥ min_strength.
    خروجی: [(idx, price, strength, kind)] — kind: 'high'|'low'"""
    n = len(rows)
    out = []
    if n < 2 * k + 1:
        return out
    for i in range(k, n - k):
        win_hi = rows[i - k: i + k + 1]
        win_lo = rows[i - k: i + k + 1]
        r = rows[i]
        # سقف/کف واقعی پنجره — و باید خودش maximum/minimum باشد
        hi = max(x["high"] for x in win_hi)
        lo = min(x["low"] for x in win_lo)
        cnt_hi = sum(1 for x in win_hi if abs(x["high"] - r["high"]) <= r["high"] * 0.005)
        cnt_lo = sum(1 for x in win_lo if abs(x["low"] - r["low"]) <= r["low"] * 0.005)
        if r["high"] >= hi * 0.995 and cnt_hi >= min_strength:
            out.append({"idx": i, "price": r["high"], "strength": cnt_hi, "kind": "high"})
        elif r["low"] <= lo * 1.005 and cnt_lo >= min_strength:
            out.append({"idx": i, "price": r["low"], "strength": cnt_lo, "kind": "low"})
    return out

def _merge_levels(ext, merge_pct=0.008, keep=10):
    """ادغام پیکهای نزدیک (در بازهٔ merge_pct) → سطحهای متمایز؛ نزولی، keep تا."""
    if not ext:
        return []
    ext = sorted(ext, key=lambda e: e["price"])
    merged = []
    for e in ext:
        if merged and abs(e["price"] - merged[-1]["price"]) / merged[-1]["price"] <= merge_pct:
            # نزدیک → قویتر برنده
            if e["strength"] > merged[-1]["strength"]:
                merged[-1] = e
            continue
        merged.append(e)
    # نگهداشتن keep تا آخرین سطح (نزدیکترین به قیمت فعلی)
    merged.sort(key=lambda e: e["idx"], reverse=True)
    return merged[:keep]

def _order_blocks(rows, ext, lookback=2, vol_mult=1.5, keep=3):
    """Demand/Supply Order Blocks ساده:
    Demand: آخرین کندل نزولیای که کفش ≈ swing low است و حجمش ≥ vol_mult× میانگین
    Supply: آخرین کندل صعودیای که سقفش ≈ swing high است و حجمش ≥ vol_mult× میانگین
    مستطیل = [کمترین low، بیشترین high] در بازهٔ lookback کندل قبل/بعد."""
    if not rows or not ext:
        return []
    avg_vol = sum(r["volume"] for r in rows) / max(1, len(rows))
    out = []
    off = sorted(ext, key=lambda e: e["idx"], reverse=True)
    used_idx = set()
    for e in off:
        if len(out) >= keep * 2 or e["idx"] in used_idx:
            break
        i = e["idx"]
        body = rows[i]
        w = rows[max(0, i - lookback): min(len(rows), i + lookback + 1)]
        if body["volume"] < avg_vol * vol_mult:
            continue
        if e["kind"] == "high" and body["close"] >= body["open"]:
            # Supply: سقف swing + کندل صعودی در آن
            top = max(x["high"] for x in w)
            bot = min(x["low"] for x in w)
            out.append({"type": "supply", "time_start": rows[max(0, i - lookback)]["date"],
                        "time_end": rows[min(len(rows) - 1, i + lookback)]["date"],
                        "top": top, "bottom": bot, "strength": e["strength"]})
            used_idx.add(e["idx"])
        elif e["kind"] == "low" and body["close"] <= body["open"]:
            # Demand: کف swing + کندل نزولی در آن
            top = max(x["high"] for x in w)
            bot = min(x["low"] for x in w)
            out.append({"type": "demand", "time_start": rows[max(0, i - lookback)]["date"],
                        "time_end": rows[min(len(rows) - 1, i + lookback)]["date"],
                        "top": top, "bottom": bot, "strength": e["strength"]})
            used_idx.add(e["idx"])
    return out[:keep]

def _key_levels_from_history(rows):
    """محاسبهٔ سطوح کلیدی + بلاکهای Demand/Supply از دهات تاریخچه.
    FIX: فقط ۳ مقاومت + ۳ حمایت برتر (قویترینها) — نه ۱۰ سطح که چارت را شلوغ میکند."""
    if not rows:
        return {"levels": [], "blocks": [], "count": 0}
    ext = _swing_extremes(rows)
    merged = _merge_levels(ext)
    if not merged:
        return {"levels": [], "blocks": [], "count": 0}
    # تفکیک حمایت/مقاومت و هرکدام ۳ تای قویتر (strength بیشتر، بعد idx اخیر)
    res = sorted([e for e in merged if e["kind"] == "high"],
                 key=lambda e: (e["strength"], e["idx"]), reverse=True)[:3]
    sup = sorted([e for e in merged if e["kind"] == "low"],
                 key=lambda e: (e["strength"], e["idx"]), reverse=True)[:3]
    levels = []
    for e in sorted(res + sup, key=lambda e: e["idx"], reverse=True):
        levels.append({"price": round(e["price"], 0), "strength": e["strength"],
                       "kind": e["kind"], "date": rows[e["idx"]]["date"]})
    blocks = _order_blocks(rows, ext)
    return {"levels": levels, "blocks": blocks, "count": len(levels) + len(blocks)}

@router.get("/api/chart/{symbol}/key-levels")
def get_key_levels(symbol: str):
    """سطوح کلیدی (Swing High/Low) + بلوکهای تقاضا/عرضه — از تاریخچهٔ قیمت DB (price_history)."""
    import time as _t
    # کلید باید مبنایِ قیمت را هم داشته باشد: این سه کش رویِ سریِ **پس ازِ
    # `price_basis`** حساب می‌شوند، و `set_basis` هیچ کشی را پاک نمی‌کند — با کلیدِ
    # بدونِ مبنای، پس ازِ عوض‌کردنِ setting تا ۱۵ دقیقه MA/سطوح/الگو رویِ مبنایِ
    # قبلی می‌ماندند (شرطِ ۱ِ §۱-ث).
    _ck_levels = f"{symbol}|{price_basis.current()}"
    _cached = KEY_LEVELS_CACHE.get(_ck_levels)
    if _cached and (_t.time() - _cached[0]) < KEY_LEVELS_TTL:
        return _cached[1]
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        _pred, _params = sym_pred("symbol", symbol)
        _raw = conn.execute(
            "SELECT symbol, date, open, high, low, close, volume, last FROM price_history "
            "WHERE %s ORDER BY date DESC, volume DESC LIMIT 250" % _pred,
            _params).fetchall()
        _seen, rows = set(), []
        for r in _raw:            # حذف تکراریِ روز (نمادِ دو-املا): پرحجم‌تر می‌ماند
            if r[1] in _seen:
                continue
            _seen.add(r[1])
            rows.append({"date": r[1], "open": r[2], "high": r[3], "low": r[4],
                         "close": r[5], "volume": r[6], "last": r[7]})
        conn.close()
        rows.reverse()  # صعودی
        # سطوح کلیدی رویِ همان مبنایی رسم می‌شوند که چارت نشان می‌دهد (§۱-ث شرطِ ۱):
        # پیش از این این endpoint خامِ پایانی را می‌خواند و «مقاومت» با عددِ چارت نمی‌خواند.
        price_basis.apply_basis(rows)
        if len(rows) < 60:
            return {"status": "ok", "symbol": symbol, "levels": [], "blocks": [],
                    "count": 0, "message": "تاریخچهٔ کافی نیست (< 60 روز)"}
        result = _key_levels_from_history(rows)
        result.update({"status": "ok", "symbol": symbol,
                       "message": f"{len(rows)} روز آخر"})
        KEY_LEVELS_CACHE[_ck_levels] = (time.time(), result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/order-book/{symbol}")
def get_order_book(symbol: str):
    """پنج خطِ واقعیِ صفِ خرید و فروشِ یک نماد — از blDsِ همان نشست.

    جمعِ پنج خط و «خطِ اول» در ستون‌هایِ خودِ market_watch بودند و برایِ
    پنلِ پنج‌سطحی کافی نیستند؛ تک‌تکِ سطرها در جدولِ order_book می‌نشینند.
    بی‌داده یعنی `no_data` با فهرستِ خالی، نه پنج سطرِ صفر — صفِ تهی با
    صفی که تابلو آن را نفرستاده دو چیزند و سایدبار باید فرقشان را بگوید.
    جمع‌ها هم از همان ستون‌هایِ market_watch خوانده می‌شوند تا پنل عددِ
    دیگری جزِ تابلو نسازد.
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        _pred, _params = sym_pred("l_val18", symbol)
        ins = conn.execute(
            f"SELECT ins_code FROM instruments WHERE {_pred}"
            " ORDER BY updated_at DESC LIMIT 1", _params).fetchone()
        row = None
        if ins:
            try:
                row = conn.execute(
                    "SELECT b.book_txt, b.d_even, b.h_even, b.updated_at,"
                    " m.buy_q_vol, m.buy_q_cnt, m.sell_q_vol, m.sell_q_cnt"
                    " FROM order_book b"
                    " LEFT JOIN market_watch m ON m.ins_code = b.ins_code"
                    " WHERE b.ins_code = ?", (ins["ins_code"],)).fetchone()
            except sqlite3.OperationalError:
                row = None          # بانکی که هنوز همگام نشده: جدولِ عمق نیست
        conn.close()
        if not row or not row["book_txt"]:
            return {"status": "no_data", "symbol": symbol, "levels": [],
                    "message": "عمقِ پنج‌سطحی این نماد ذخیره نشده — بعد از"
                               " نخستین همگام‌سازیِ تابلو می‌آید"}
        levels = [{"buy_px": ln[0], "buy_vol": ln[1], "buy_cnt": ln[2],
                   "sell_px": ln[3], "sell_vol": ln[4], "sell_cnt": ln[5]}
                  for ln in json.loads(row["book_txt"]) if isinstance(ln, list)]
        return {"status": "ok", "symbol": symbol, "levels": levels,
                "session": {"d_even": row["d_even"], "h_even": row["h_even"],
                            "updated_at": row["updated_at"]},
                "totals": {"buy_vol": row["buy_q_vol"], "buy_cnt": row["buy_q_cnt"],
                           "sell_vol": row["sell_q_vol"], "sell_cnt": row["sell_q_cnt"]}}
    except Exception as e:
        return {"status": "error", "symbol": symbol, "levels": [],
                "message": str(e)}


def _cal_classify(title, tid):
    """تکرار حداقلِ منطق calendarService.js سمت سرور (دسته برای رنگ/آیکون مارکر)."""
    import re as _re
    t = str(title or "").replace("\u200c", "").replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
    if _re.search("لغو|عدم برگزاری|به تعویق|تغییر زمان|انتقال مجمع|موافقت با تغییر", t):
        return "assemblyChange"
    if tid == 1:
        return "assembly"
    if tid == 2:
        return "assemblyExtra"
    if tid == 3:
        return "dividend"
    if _re.search("افزایش\\s*سرمایه", t):
        return "capitalIncrease"
    if _re.search("عرضه\\s*اولیه|عرضه\\s*در\\s*بازار", t):
        return "ipo"
    if _re.search("سررسید|اخزا|صکوک|اوراق", t):
        return "bondMaturity"
    return "other"

def _cal_cache_events():
    """رویدادهای خام از static/calendar/cache.json — با بیعه‌سازیِ mtime."""
    try:
        mtime = os.path.getmtime(_CAL_CACHE_PATH)
    except Exception:
        return []
    if mtime != _cal_cache["mtime"]:
        try:
            with open(_CAL_CACHE_PATH, encoding="utf-8") as f:
                _cal_cache["events"] = (json.load(f) or {}).get("events") or []
            _cal_cache["mtime"] = mtime
        except Exception:
            return []
    return _cal_cache["events"]


def _cal_events_for(symbol):
    """رویدادهای نماد از static/calendar/cache.json (کش با mtime)."""
    _norm = lambda s: str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()
    want = _norm(symbol)
    out, seen = [], set()
    _tg = __import__("calendar").timegm
    for ev in _cal_cache_events():
        if _norm(ev.get("asset_symbol_trade")) != want:
            continue
        try:
            dt = datetime.datetime.fromisoformat(str(ev.get("date_time")))
        except Exception:
            continue
        title = str(ev.get("event_title") or "")[:140]
        key = (dt.date().isoformat(), title)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "date": dt.date().isoformat(),
            # مبنای کندل: ظهر UTC — هم‌قرارداد rvDateToTs در فرانت
            "ts": int(_tg((dt.year, dt.month, dt.day, 12, 0, 0, 0, 0, 0))) * 1000,
            "title": title,
            "cat": _cal_classify(title, int(ev.get("event_type_id") or 0)),
        })
    out.sort(key=lambda x: x["ts"])
    return out

_ASSEMBLY_FAMILY = ("assembly", "assemblyExtra", "assemblyChange")
# مجمعِ «قطعی»: رویدادی که واقعاً تاریخِ توقفِ نماد را می‌سازد. لغو/تعویق/انتقال
# (assemblyChange) تاریخِ معتبری به دست نمی‌دهد، پس وتو نمی‌سازد — فقط برچسبِ
# صادقانهٔ تغییر. وتو روی تاریخِ نامعلوم، وتوی ساختگی است.
_ASSEMBLY_CONFIRMED = ("assembly", "assemblyExtra")
# افقِ «مجمعِ نزدیک» (روز) — یک منبع برای هر سه مصرفِ پایتون: برچسبِ ردیف‌های جدول
# (`/api/calendar/upcoming`)، وتوی اسکرینر، و مقدارِ پیش‌فرضِ `upcoming_assemblies`.
# باید با `ASSEMBLY_NEAR_DAYS` در
# frontend/src/features/fundamental/lib/assemblyEvent.ts یکی بماند، وگرنه ردیفی
# برچسبِ «مجمع نزدیک» می‌خورد ولی وتو نمی‌شود (یا برعکس). گاردِ برابری:
# dev/test_calendar_v92.py بخش ۴ — عدد از خودِ دو فایل خوانده می‌شود، نه کپی.
ASSEMBLY_NEAR_DAYS = 14


def _clamp_days(days) -> int:
    """افقِ درخواستی را در [۱, ۹۰] نگه می‌دارد — مقدارِ نامعتبر ⇒ پیش‌فرض."""
    try:
        return max(1, min(int(days), 90))
    except (TypeError, ValueError):
        return ASSEMBLY_NEAR_DAYS


def _upcoming_by(cats, days: int, title_re=None) -> dict:
    """نزدیک‌ترین رویدادِ پیش‌روی هر نماد در میانِ دسته‌هایِ خواستۀ `cats`.

    یک تابع برای دو مصرف: خانوادۀ مجمع (برچسب + وتو) و «افزایشِ سرمایه» (فقط
    برچسب — رأیِ pilot: این رویداد وتو نمی‌سازد). افقِ هر دو یکی است، وگرنه
    ردیفی برچسب می‌گیرد ولی وتو نمی‌شود. خطا ⇒ {}.

    `title_re` برایِ «افزایشِ سرمایه» است: عنوانِ یک اطلاعیه می‌تواند هم‌زمان
    «دعوت به مجمع فوق‌العاده» و «افزایش سرمایه» باشد و آن‌وقت `cat` تنها یکی از
    دو را می‌گوید (مجمع، چون رأیِ وتو به آن گره خورده است). پس برچسبِ دوم با
    خودِ عنوان سنجیده می‌شود تا آن یکی را نبَد.
    """
    days = _clamp_days(days)
    _norm = lambda s: str(s or "").translate(
        str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()
    # لنگرِ افقِ تقویم، نه مُهرِ کندل. dev/live_bar_session_date_v1059.py هر
    # «امروزِ ساعتِ سیستم» را در این فایل کندلِ مهرشده می‌شمارد، پس نامِ متغیر
    # عمداً `today` نیست.
    as_of = datetime.date.today()
    horizon = as_of + datetime.timedelta(days=days)
    best: dict = {}
    for ev in _cal_cache_events():
        title = str(ev.get("event_title") or "")
        cat = _cal_classify(title, int(ev.get("event_type_id") or 0))
        if cats is not None and cat not in cats:
            continue
        if title_re is not None and not title_re.search(
                title.replace("‌", "").replace("ي", "ی").replace("ك", "ک")):
            continue
        try:
            d = datetime.datetime.fromisoformat(str(ev.get("date_time"))).date()
        except Exception:
            continue
        if d < as_of or d > horizon:
            continue
        sym = _norm(ev.get("asset_symbol_trade"))
        if not sym:
            continue
        cur = best.get(sym)
        # نزدیک‌ترینِ پیش‌رو؛ در تساویِ تاریخ، لغو/تعویق برنده است تا تاریخِ
        # مجمعِ باطل‌شده به کاربر نشان داده نشود.
        if cur is None or d < datetime.date.fromisoformat(cur["date"]) or (
            d == datetime.date.fromisoformat(cur["date"]) and cat == "assemblyChange"
            and cur["cat"] != "assemblyChange"
        ):
            best[sym] = {"symbol": sym, "date": d.isoformat(), "cat": cat,
                         "title": title[:140]}
    return best


def upcoming_assemblies(days: int = ASSEMBLY_NEAR_DAYS) -> dict:
    """نزدیک‌ترین رویدادِ خانوادهٔ مجمع برای هر نماد در افقِ `days` روز.

    یک منبع برای دو مصرف: اندپوینتِ `/api/calendar/upcoming` (برچسبِ ردیف‌های
    جدولِ بنیادی) و وتوی مجمع در `/api/screener`. هر دو باید یک افق و یک قاعدهٔ
    تساوی داشته باشند، وگرنه برچسب یک چیز می‌گوید و وتو چیزِ دیگر.
    هزینه: یک بار خواندنِ کشِ `static/calendar/cache.json`، نه کوئری به‌ازایِ ردیف.
    خروجی: {نمادِ نرمال‌شده: {"symbol", "date", "cat", "title"}} — خطا ⇒ {} .
    """
    return _upcoming_by(_ASSEMBLY_FAMILY, days)


# «افزایش سرمایه» با فاصله یا بدونِ آن، با ي/ك عربی — همان کلیدواژه‌ای که
# dev/calendar_fetcher.py در جستجویش استفاده می‌کند (فاصله‌زدایی‌شده).
_CAP_RE = __import__("re").compile("افزايش\\s*سرمايه|افزایش\\s*سرمایه|افزایشسرمايه|افزايشسرمايه")


def upcoming_capital_increases(days: int = ASSEMBLY_NEAR_DAYS) -> dict:
    """«افزایش سرمایه»هایِ پیش‌رو — برچسبِ هشدار، بی‌هیچ حکمی (رأیِ pilot #53).

    عنوان‌محور است نه دسته‌محور: واکشی‌کننده دسته‌هایِ دیگر را `event_type_id=0`
    می‌گذارد («فرانت با کلیدواژه دسته‌بندی می‌کند» — static/calendar/README.md)،
    و یک اطلاعیه می‌تواند هم «دعوت به مجمع فوق‌العاده» باشد هم «افزایش سرمایه».
    آن‌جا `cat` مجمع می‌ماند تا وتو نَبَد، و این فهرست هم همان ردیف را می‌گیرد.
    """
    return _upcoming_by(None, days, title_re=_CAP_RE)



@router.get("/api/calendar/upcoming")
def get_calendar_upcoming(days: int = Query(ASSEMBLY_NEAR_DAYS)):
    """مجمع‌های پیش‌روی همهٔ نمادها در یک درخواست — برای برچسبِ ردیف‌های جدول.

    `/api/calendar/{symbol}` نمادی است؛ اگر این مسیر بعد از آن تعریف می‌شد،
    «upcoming» به‌عنوان نامِ نماد مطابق می‌شد و پاسخ خالی می‌داد.
    """
    try:
        span = _clamp_days(days)
        best = upcoming_assemblies(span)
        cap = upcoming_capital_increases(span)
        return {"status": "ok", "days": span,
                "count": len(best), "items": sorted(best.values(), key=lambda x: x["date"]),
                "capital_count": len(cap),
                "capital": sorted(cap.values(), key=lambda x: x["date"])}
    except Exception as e:
        return {"status": "error", "message": str(e), "items": [], "capital": []}


@router.get("/api/calendar/{symbol}")
def get_calendar_events(symbol: str):
    """رویدادهای تقویم کدال نماد (مجمع/تقسیم سود/افزایش سرمایه/…) — سبک، بدون سری قیمت."""
    try:
        events = _cal_events_for(symbol)
        return {"status": "ok", "symbol": symbol,
                "count": len(events), "events": events}
    except Exception as e:
        return {"status": "error", "symbol": symbol,
                "message": str(e), "events": []}


@router.get("/api/ma/{symbol}")
def get_ma_events(symbol: str, days: int = Query(730)):
    """میانگینهای متحرک (۵/۲۰/۵۰/۱۲۰) از price_history + رویدادهای تقویم نماد."""
    import time as _t
    days = max(120, min(int(days or 730), 2000))
    ck = f"{symbol}|{days}|{price_basis.current()}"
    _cached = MA_CACHE.get(ck)
    if _cached and (_t.time() - _cached[0]) < MA_TTL:
        return _cached[1]
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        _pred, _params = sym_pred("symbol", symbol)
        _raw = conn.execute(
            "SELECT date, close, volume, last FROM price_history WHERE %s "
            "ORDER BY date DESC, volume DESC LIMIT ?" % _pred,
            (*_params, days)).fetchall()
        conn.close()
        _seen, rows = set(), []
        for r in _raw:            # حذف تکراریِ روز (نمادِ دو-املا): پرحجم‌تر می‌ماند
            if r[0] in _seen:
                continue
            _seen.add(r[0])
            rows.append(r)
        rows.reverse()  # صعودی
        # مبنایِ MA همان مبنایِ چارت است (قدمِ ۳): سری از price_basis می‌گذرد، پس
        # ma{w} و کندل‌هایِ چارت هرگز دو جوابِ متفاوت برایِ یکِ روز نمی‌دهند.
        _ma_rows = [{"time": r[0], "close": r[1], "last": r[3]} for r in rows]
        price_basis.apply_basis(_ma_rows)
        closes = [(c["time"], float(c["close"])) for c in _ma_rows if c["close"] is not None]
        ma = {}
        for w in MA_WINDOWS:
            ser, acc = [], 0.0
            for i, (d, c) in enumerate(closes):
                acc += c
                if i >= w:
                    acc -= closes[i - w][1]
                ser.append([d, round(acc / (i + 1), 2) if i >= w - 1 else None])
            ma[f"ma{w}"] = ser
        result = {"status": "ok", "symbol": symbol, "periods": MA_WINDOWS,
                  "ma": ma, "events": _cal_events_for(symbol), "bars": len(closes)}
        MA_CACHE[ck] = (_t.time(), result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _adjust_events_for(symbol, rows):
    """رویدادهای تعدیل — از همان منطق /api/chart (APF + gap-detection) reuse میشود."""
    try:
        import test_tsetmc  # noqa — نه لازم؛ فقط اگر importError
    except Exception:
        pass
    try:
        j = get_chart_tsetmc(symbol)
        return j.get("adjustEvents") or []
    except Exception:
        return []

@router.get("/api/chart-db/{symbol}")
def get_chart_db(symbol: str, adjustment: int = 3):
    """(v7.3.2 — Hybrid Data Fusion) تمام تاریخچه از price_history + تزریق کندل امروز از تابلوخوانی.

    - تاریخچه کامل (بدون limit) — اندیکاتورها به عمق نیاز دارند
    - کندل امروز (اگر در price_history نیست یا کهنه است) از market_watch زنده تزریق میشود
    - adjustment: 0=خام، 3=عملکردی (فقط برای فرانت که factor را اعمال میکند؛ اینجا raw میفرستیم)
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            _pred, _params = sym_pred("symbol", symbol)
            _raw = conn.execute(
                "SELECT date, open, high, low, close, volume, last, value FROM price_history "
                "WHERE %s ORDER BY date DESC, volume DESC" % _pred, _params).fetchall()
            # حذف تکراریِ روز: کلید price_history = (symbol,date)؛ نمادِ دو-املا
            # می‌تواند همان روز را در دو نوشتار داشته باشد — پرحجم‌تر می‌ماند.
            _seen, rows = set(), []
            for r in _raw:
                if r[0] in _seen:
                    continue
                _seen.add(r[0])
                rows.append(r)
            rows.reverse()          # صعودی (قرارداد پیشین: ORDER BY date ASC)
            # `close` = «قیمت پایانی» و `last` = «آخرین قیمت»؛ این دو ستونِ جدا‌اند و
            # جعلِ `last := close` حذف شده (docs/CANDLE-CONTRACT.md §۱-ث شرطِ ۳). ردیفی
            # که منبعش «آخرین» نداشته (مثلاً GetInstrmentsHistoryInDay) صریح null
            # می‌رود، تا مصرف‌کننده بتواند «نداریم» را تشخیص دهد، نه اینکه عددِ پایانی
            # را با نامِ «آخرین» بخورد.
            candles = [{"time": r[0], "open": float(r[1]), "high": float(r[2]),
                        "low": float(r[3]), "close": float(r[4]),
                        "last": float(r[6]) if r[6] is not None else None,
                        "value": float(r[7]) if r[7] is not None else None,
                        "volume": float(r[5] or 0)} for r in rows]
        finally:
            conn.close()

        # ---- تزریق کندلِ جلسهٔ جاری از market_watch (دادهٔ زندهٔ تابلوخوانی) ----
        # تاریخِ کندل را خودِ جلسه (d_even) می‌دهد، نه ساعتِ سیستم — دلیلش در
        # _watch_live_bar مستند است. سریِ اینجا صعودی است، پس آخرینِ لیست تازه‌ترین.
        last_db_date = candles[-1]["time"] if candles else ""
        bar, live_error = _watch_live_bar(symbol, last_db_date)
        live_injected = bar is not None
        if live_injected:
            candles.append(bar)

        # ---- v10 FTS: technical methodology payload (same candles) ----
        # Pure compute wrapper; failures must never break the chart contract,
        # so "fts" degrades to None. See _fts_analyze_candles.
        fts_payload = None
        try:
            # نسخه‌کپی به موتور داده می‌شود: `apply_basis()` کندل‌ها را در‌جا تغییر
            # می‌دهد و موتورِ FTS درِ این قدم **عمداً** رویِ همان مبنایِ پایانیِ خام
            # می‌ماند (کارِ FTS Pattern Engine درِ #73 معوق است؛ ببینید
            # docs/CANDLE-CONTRACT.md §۱-ث). کپی، نشتِ مبنایِ منتخب به آرایۀ موتور را
            # تضمین می‌کند، نه فقط قرائتِ پیش از تغییر.
            fts_payload = _fts_analyze_candles(symbol, [dict(c) for c in candles])
        except Exception:
            fts_payload = None

        vols = [{"time": c["time"], "value": c.get("volume", 0),
                 "color": "#10b981" if c.get("close", 0) >= c.get("open", 0) else "#f43f5e"} for c in candles]
        facts = [{"time": c["time"], "factor": 1.0} for c in candles]

        return price_basis.resolve_payload(
            {"status": "success", "symbol": symbol, "count": len(candles),
             "candles": candles, "volumes": vols, "factors": facts,
             "adjustEvents": [], "adjustSource": "local-db",
             "liveInjected": live_injected,
             "liveError": live_error,
             "adjustment": adjustment,
             "fts": fts_payload})
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/patterns/{symbol}")
def get_patterns(symbol: str):
    """نقاط [time, price] الگوها برای KLineChart.createOverlay — بدون drift.

    خروجی: support/resistance (خط افقی از swing levels)، trendlines (خط از دو pivot)،
    breakout zone (آستانهٔ آخرین رنج) — همه با timestamp میلی‌ثانیه (ظهر UTC؛ فرمت overlay v10).
    """
    import time as _t
    _ck_pat = f"{symbol}|{price_basis.current()}"
    cached = PATTERNS_CACHE.get(_ck_pat)
    if cached and (_t.time() - cached[0]) < KEY_LEVELS_TTL:
        return cached[1]
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        _pred, _params = sym_pred("symbol", symbol)
        _raw = conn.execute(
            "SELECT symbol, date, open, high, low, close, volume, last FROM price_history "
            "WHERE %s ORDER BY date DESC, volume DESC LIMIT 250" % _pred,
            _params).fetchall()
        _seen, rows = set(), []
        for r in _raw:            # حذف تکراریِ روز (نمادِ دو-املا): پرحجم‌تر می‌ماند
            if r[1] in _seen:
                continue
            _seen.add(r[1])
            rows.append({"date": r[1], "open": r[2], "high": r[3], "low": r[4],
                         "close": r[5], "volume": r[6], "last": r[7]})
        conn.close()
        rows.reverse()
        if len(rows) < 60:
            return {"status": "ok", "symbol": symbol, "overlays": [], "count": 0,
                    "message": "تاریخچه کافی نیست"}
        # FIX v7.2: سطحها باید در فضای تعدیلشده باشند (chart با factor رسم میکند) — وگرنه Y-mismatch
        evs = _adjust_events_for(symbol, rows)
        # مبنایِ قیمت پیش از ضربِ فاکتور انتخاب می‌شود (تنها نقطۀ انتخاب؛ §۱-ث شرطِ ۱)،
        # و سپس هر سه نگارۀ قیمتی همان کندل ضریب می‌گیرند تا `closing` (لنگر) و `last`
        # درِ پاسخ با `close` (منتخب) در یک فضایِ مقیاس باشند.
        price_basis.apply_basis(rows)
        for r in rows:
            f = 1.0
            for e in evs:
                if e["date"] > r["date"]:
                    f *= e["ratio"]
            for _k in ("high", "low", "close", "closing", "last", "high_raw", "low_raw"):
                if r.get(_k) is not None:
                    r[_k] = r[_k] * f
        ext = _swing_extremes(rows, k=3, min_strength=2)
        levels = _merge_levels(ext, keep=6)
        # v8.7 FIX-3: خروجی باید میلی‌ثانیه باشد (سند KLineChart v10) — قبلاً ثانیه بود و
        # نقاط overlay قبل از اولین کندل می‌افتادند. +43200 → ظهر UTC تا خوانش تقویمی
        # در هر منطقهٔ زمانی همان روز بماند.
        ts_of = lambda d: (int(__import__("calendar").timegm(
            __import__("datetime").datetime.strptime(d, "%Y-%m-%d").timetuple())) + 43200) * 1000
        overlays = []
        # S/R خط افقی — دو نقطه (اول/آخر) برای کشش کامل
        for lv in levels:
            overlays.append({
                "name": "horizontalStraightLine", "kind": "sr",
                "points": [{"timestamp": ts_of(rows[0]["date"]), "value": lv["price"]}],
                "styles": {"line": {"style": "dashed", "size": 1,
                                     "color": "#f59e0b" if lv["kind"] == "high" else "#38bdf8"}},
                "meta": {"strength": lv["strength"], "kind": lv["kind"]},
            })
        # Trendline: دو pivot high آخر → خط روند نزولی/صعودی سقف؛ دو pivot low → کف
        highs = [e for e in ext if e["kind"] == "high"][-2:]
        lows = [e for e in ext if e["kind"] == "low"][-2:]
        for pts, kind, color in ((highs, "trend-high", "#ef4444"), (lows, "trend-low", "#22c55e")):
            if len(pts) == 2:
                overlays.append({
                    "name": "trendLine", "kind": kind,
                    "points": [{"timestamp": ts_of(rows[p["idx"]]["date"]), "value": p["price"]}
                               for p in pts],
                    "styles": {"line": {"color": color, "size": 2}},
                })
        # Breakout zone: مستطیل از آخرین رنج تراکم (min/max ۲۰ کندل آخر)
        last20 = rows[-20:]
        hi = max(r["high"] for r in last20)
        lo = min(r["low"] for r in last20)
        overlays.append({
            "name": "rect", "kind": "breakout-zone",
            "points": [{"timestamp": ts_of(last20[0]["date"]), "value": hi},
                       {"timestamp": ts_of(last20[-1]["date"]), "value": lo}],
            "styles": {"color": "#2962ff"},
        })
        result = {"status": "ok", "symbol": symbol, "overlays": overlays, "count": len(overlays)}
        PATTERNS_CACHE[_ck_pat] = (_t.time(), result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

CHART_CACHE = {}   # {symbol: (fetch_time, json_data)}

ADJ_TOL = 0.001

# کمینهٔ کسرِ روزهایی که «قیمت پایه = قیمت پایانیِ دیروز» تا گسستِ پایه بتواند نشانهٔ
# تعدیل شمردل شود. پایین‌تر از این، پایه لنگرِ پایانیِ دیروز نیست (صندوق‌هایی که
# بازارگردان/NAV قیمت پایه را می‌گذارند) و شمارشگر، تعدیلِ جعلی می‌سازد.
ANCHOR_MIN = 0.9

CHART_CACHE_TTL = 3600.0
# پاسخِ CDN یک ساعت می‌مانَد؛ اما فال‌بکِ محلی نه. دلیلش اندازه‌گیری است، نه
# احتیاط: یک لحظه‌ی قطعیِ دو‌ثانیه‌ای CDN کافی بود که کل چارت و تحلیل FTS رویِ
# همان تعدادِ کمِ ردیفِ محلی قفل شود (شاهد: فولاد ۳۵۵ در برابر ۴٬۲۳۲، و
# `/api/fts` با basis=local-db تا یک ساعت). با این سقف، هر بیست ثانیه یک‌بار CDN
# دوباره امتحان می‌شود.
# نکته (۱۴۰۵-۰۷-۱۱): «۳۵۵ کندلِ دو سالِ اخیر» وصفِ **عمقِ بانکِ امروز** است، نه
# سقفِ برنامه — هرسِ ۷۳۰روزه درِ test_tsetmc حذف شد و عمق با --backfill-history
# پر می‌شود؛ تا آن اجرا، همین کم‌عمقی دلیلِ ماندنِ TTLِ کوتاه است.
CHART_FALLBACK_TTL = 20.0

KEY_LEVELS_CACHE = {}
KEY_LEVELS_TTL = 300  # ۵ دقیقه — محاسبه گران نیست ولی دوباره پول نشود

MA_CACHE = {}
MA_TTL = 900  # ۱۵ دقیقه

PATTERNS_CACHE = {}

# ============================================================================
# v10.0 — FTS Technical Methodology (متدولوژی فنی FTS)
# ----------------------------------------------------------------------------
# مرجع: docs/FTS-7-Phase-Progress.md («صفحهٔ ۲ متدولوژی») + تصمیم مصوب این جلسه.
# این بخش «موتور خالص» است (بدون I/O) تا سه مسیر reuse کنند:
#     • get_chart_db        → کلید «fts» در همان پاسخ چارت (بدون شکستن قرارداد قدیمی)
#     • /api/fts/{symbol}   → پیلود سبک فقط-تحلیل برای نوار نشان‌ها (badge strip)
#     • api/screener.py     → ستون‌های tech_* برای جدول غربگر
# اجزای متدولوژی:
#   ۱) روند چند-تایم‌فریمی: ساختار HH/HL = صعودی، LH/LL = نزولی، غیر آن = رنج
#      (محاسبهٔ مستقل روی D/W/M + «هم‌راستایی» سه تایم‌فریم)
#   ۲) کمربندهای فیبوناچی در مقیاس لگاریتمی: ۳۳–۴۰٪ و ۶۱.۸–۷۰٪
#   ۳) ستاپ جت: شکست سقف ایستا/ATH با تأیید پایانی روزانه
#   ۴) CHoCH: شکست قطعیِ آخرین پیوتِ مخالف روند
#   ۵) شکار نقطه: لمس‌های کف کانال (۳ تا ۴ لمسِ کف دایامتریک)
#   ۶) دابل‌باتم / جعبهٔ رنج: شکست یقه و سقف جعبه
#   ۷) موتور خروج/حد ضرر چهارلایه → _fts_exit_engine (توضیح کامل بالای همان تابع)
# ============================================================================

_FTS_STALE_BARS = 8         # فاصلهٔ تازه‌ترین پیوتِ تأییدشده تا امروز که «ساختار کهنه» حساب می‌شود
_FTS_STALE_WINDOW = 52      # بازهٔ سنجشِ مستقیمِ روند (همان ۵۲ دورهٔ MA52)
_FTS_STALE_MIN_BARS = 12    # کمینهٔ کندل برای سنجشِ مستقیم؛ کمتر از آن رأی نمی‌دهیم
_FTS_STALE_MOVE_MIN = 0.05  # کمینهٔ جابه‌جاییِ کلِ بازه برای اعلامِ جهت
_FTS_SWING_K = 3          # نیم‌پنجرهٔ پیوت (fractal) روی روزانه
_FTS_EQUAL_TOL = 0.005    # اختلاف ≤ ۰.۵٪ دو پیوت = «مساوی» (ساختار رنج/تخت)
# تریگرِ ورودِ جت دیگر «ماکسِ ۶۰ کندلِ قبل» را نمی‌بیند؛ پلکانِ هشت‌نقطه‌ایِ
# جزوه (JET_LADDER از tape_flags) مرجع است، تا چارت و تابلو یک جواب بدهند.


def _fts_resample(candles, bucket="W"):
    """تجمیع کندل روزانه به هفتگی/ماهانه — ورودی روند چند-تایم‌فریمی FTS.

    candles: لیست دیکشنری با کلیدهای time ('YYYY-MM-DD'), open, high, low, close, volume
             (همان ساختار candles در get_chart_db؛ مرتب صعودی).
    bucket:  'W' → هفتهٔ شنبه‌محور (کلید = تاریخ شنبۀ همان هفته)  |  'M' → ماه میلادی.
    هفتهٔ ISO دوشنبه‌محور است؛ نشستِ ایران شنبه تا چهارشنبه است، پس در ISO سه
    روزِ اولِ هفتهٔ معاملاتی به هفتهٔ قبلی می‌افتادند و کندلِ هفتگیِ موتور با
    کندلِ هفتگیِ چارت (که شنبه‌محور است یکی از همان‌ها را می‌شمارد) یکی نمی‌شد —
    یعنی رأیِ هفتگی و وتوی آن رویِ سبدی از روزها ساخته می‌شد که کاربر نمی‌بیند.
    کندل تجمیعی: open = اولین روز سبد، close = آخرین روز، high/low = max/min سبد،
    حجم = جمع. تاریخ کندل تجمیعی = تاریخ آخرین روز سبد (کندلِ هفته در آخرین روز
    معاملاتی‌اش می‌بندد) — هم‌قرارداد rvAggregate سمت فرانت.
    """
    if not candles:
        return []
    out = {}
    for c in candles:
        t = str(c.get("time") or "")
        if len(t) < 10:
            continue
        try:
            d = datetime.date.fromisoformat(t[:10])
        except ValueError:
            continue
        if bucket == "W":
            key = (d - datetime.timedelta(days=(d.weekday() + 2) % 7)).isoformat()
        else:
            key = t[:7]          # 'YYYY-MM'
        prev = out.get(key)
        if prev is None:
            out[key] = {"time": t[:10], "open": c["open"], "high": c["high"],
                        "low": c["low"], "close": c["close"],
                        "volume": float(c.get("volume") or 0)}
        else:
            prev["high"] = max(prev["high"], c["high"])
            prev["low"] = min(prev["low"], c["low"])
            prev["close"] = c["close"]
            prev["time"] = t[:10]
            prev["volume"] += float(c.get("volume") or 0)
    return [out[k] for k in sorted(out.keys())]

def _fts_swings(series, k=3):
    """پیوت‌های ساختاری (fractal) — مبنای همهٔ تشخیص‌های ساختاری FTS.

    سقف پیوت: high[i] ≥ high هر دو طرف تا k کندل (و اکیداً بزرگ‌تر از یک طرف).
    کف پیوت:  low[i]  ≤ low  هر دو طرف تا k کندل.
    خروجی: [{'idx', 'price', 'kind': 'high'|'low'}] مرتب زمانی. k بزرگ‌تر =
    فقط پیوت‌های «مهم‌تر» (روی ماهانه k=2 می‌گذاریم چون کندل کم داریم).
    """
    n = len(series)
    if n < 2 * k + 2:
        return []
    out = []
    for i in range(k, n - k):
        hi, lo = series[i]["high"], series[i]["low"]
        win_l_h = [series[j]["high"] for j in range(i - k, i)]
        win_r_h = [series[j]["high"] for j in range(i + 1, i + k + 1)]
        win_l_l = [series[j]["low"] for j in range(i - k, i)]
        win_r_l = [series[j]["low"] for j in range(i + 1, i + k + 1)]
        t = str(series[i].get("time") or "")[:10]
        if hi >= max(win_l_h) and hi >= max(win_r_h):
            out.append({"idx": i, "price": float(hi), "kind": "high", "time": t})
        if lo <= min(win_l_l) and lo <= min(win_r_l):
            out.append({"idx": i, "price": float(lo), "kind": "low", "time": t})
    return out


def _fts_recent_window_trend(series, window=_FTS_STALE_WINDOW):
    """روندِ مستقیمِ بازهٔ اخیر — فقط وقتی ساختارِ پیوت کهنه شده است (رأیِ پایلوت: گزینهٔ B).

    پیوت‌های تأییدشده دست‌نخورده می‌مانند؛ اگر تازه‌ترین پیوت قدیمی‌تر از
    `_FTS_STALE_BARS` کندل بود، جهت از روی شیبِ رگرسیونِ خطیِ بستهٔ بازهٔ اخیر و
    جایِ قیمت نسبت به میانگینِ ۵۲ دوره خوانده می‌شود. انگیزه: تأییدِ پیوت سه کندل
    در هر دو طرف می‌خواهد، پس در یک حرکتِ یک‌طرفهٔ طولانی هیچ پیوتی تأیید نمی‌شود و
    موتور روی پیوت‌های ماه‌ها پیش رأی می‌داد — شاهد: کايزد با صعودِ ۱۵۱۴ ← ۳۸۲۰
    «نزولی/خنثی» و REJECT می‌گرفت چون تازه‌ترین پیوتِ تأییدشده‌اش ۴۴ کندل عقب بود.
    جهت فقط وقتی اعلام می‌شود که شیب و جایِ قیمت هم‌داستان باشند؛ وگرنه «رنج».
    """
    closes = [float(c["close"]) for c in series
              if isinstance(c.get("close"), (int, float)) and float(c["close"]) > 0]
    n = len(closes)
    if n < _FTS_STALE_MIN_BARS:
        return None
    w = min(window, n)
    seg = closes[-w:]
    mean_y = sum(seg) / w
    if mean_y <= 0:
        return None
    mean_x = (w - 1) / 2.0
    den = sum((i - mean_x) ** 2 for i in range(w))
    num = sum((i - mean_x) * (seg[i] - mean_y) for i in range(w))
    slope = num / den if den else 0.0
    move = slope * (w - 1) / mean_y           # جابه‌جاییِ کلِ بازه بر حسبِ کسری
    ma_n = min(window, n)
    ma = sum(closes[-ma_n:]) / ma_n
    above = closes[-1] >= ma
    if move >= _FTS_STALE_MOVE_MIN and above:
        trend = "up"
    elif move <= -_FTS_STALE_MOVE_MIN and not above:
        trend = "down"
    else:
        trend = "range"
    return {"trend": trend, "basis": "recent-window", "window": w,
            "move_pct": round(move * 100.0, 1), "ma": round(ma, 2),
            "last_close": round(closes[-1], 2), "above_ma": above}


def _fts_classify_trend(swings, tol=_FTS_EQUAL_TOL, series=None,
                        stale_bars=_FTS_STALE_BARS):
    """طبقه‌بندی روند بر پایهٔ ساختار سقف/کف (هستهٔ متدولوژی FTS صفحهٔ ۲).

    دو سقف پیوت و دو کف پیوتِ آخر مقایسه می‌شوند:
        HH + HL → 'up'        (سقف بالاتر و کف بالاتر)
        LH + LL → 'down'      (سقف پایین‌تر و کف پایین‌تر)
        غیر آن  → 'range'     (هر اختلاف ≤ tol = ساختار «مساوی»/تخت)
    تایم‌فریم با کمتر از دو پیوت کامل → trend='na' (غربگر/UI باید نال‌پذیر باشد).

    اگر `series` داده شود، کهنگیِ ساختار هم سنجیده می‌شود: وقتی تازه‌ترین پیوتِ
    تأییدشده بیش از `stale_bars` کندل عقب است، رأیِ پیوت‌ها مربوط به گذشته است و
    جای خودش را به `_fts_recent_window_trend` می‌دهد (`basis='recent-window'`) —
    وگرنه کايزد‌ها (حرکتِ یک‌طرفهٔ بدون پیوتِ تازه) همیشه «نزولی/خنثی» می‌مانند.
    `basis` و تاریخِ پیوت‌ها در خروجی هست تا ردِ ورود بگوید بر چه مبنایی بوده.
    """
    highs = [s for s in swings if s["kind"] == "high"][-2:]
    lows = [s for s in swings if s["kind"] == "low"][-2:]
    base = {"trend": "na", "hh": None, "hl": None, "basis": "pivots",
            "last_high": None, "prev_high": None, "last_low": None, "prev_low": None,
            "last_high_time": None, "prev_high_time": None,
            "last_low_time": None, "prev_low_time": None,
            "stale_bars": None, "window": None}
    piv = None
    if len(highs) >= 2 and len(lows) >= 2:
        h2, h1 = highs[-2]["price"], highs[-1]["price"]     # h1 = سقف اخیر
        l2, l1 = lows[-2]["price"], lows[-1]["price"]
        hh = h1 > h2 * (1 + tol)
        hl = l1 > l2 * (1 + tol)
        lh = h1 < h2 * (1 - tol)
        ll = l1 < l2 * (1 - tol)
        if hh and hl:
            trend = "up"
        elif lh and ll:
            trend = "down"
        else:
            trend = "range"
        piv = {"trend": trend, "hh": hh, "hl": hl, "basis": "pivots",
               "last_high": round(h1, 2), "prev_high": round(h2, 2),
               "last_low": round(l1, 2), "prev_low": round(l2, 2),
               "last_high_time": highs[-1].get("time"), "prev_high_time": highs[-2].get("time"),
               "last_low_time": lows[-1].get("time"), "prev_low_time": lows[-2].get("time"),
               "stale_bars": None, "window": None}
    if series is None:
        return piv if piv is not None else base
    n = len(series)
    newest = max((s["idx"] for s in swings), default=-1)
    gap = n - 1 - newest
    if piv is not None and gap <= stale_bars:
        return piv
    win = _fts_recent_window_trend(series)
    if win is None:
        return piv if piv is not None else base
    out = dict(win)
    out["stale_bars"] = gap
    out["last_pivot_time"] = series[newest].get("time") if 0 <= newest < n else None
    out["hh"] = None
    out["hl"] = None
    out["last_high"] = None
    out["prev_high"] = None
    out["last_low"] = None
    out["prev_low"] = None
    if piv is not None:
        out["pivots"] = piv
    return out


def _fts_fa(v):
    """رقمِ فارسی — متنِ دلیلِ رد هم باید با اعدادِ فارسی خوانده شود (قاعدهٔ سراسری UI)."""
    if v is None:
        return "—"
    return str(v).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _fts_trend_reason(t):
    """مبنایِ رأیِ روند به فارسی — ردِ ورود باید بگوید با چه عددی قضاوت شده.

    پیش‌تر فقط «تایم هفتگی خنثی» نوشته می‌شد و کاربر راهی نداشت بفهمد کدام دو پیوت
    مقایسه شده‌اند (شاهد: کايزد با ۴۴ کندلِ صعودیِ بی‌پیوت «نزولی» می‌گرفت). تاریخ‌ها
    همان رشته‌هایِ محورِ زمانِ خودِ چارت‌اند تا عددِ متن و عددِ چارت یکی باشد.
    """
    if not isinstance(t, dict):
        return ""
    if t.get("basis") == "recent-window":
        pos = "بالای" if t.get("above_ma") else "زیر"
        txt = (f"مبنا: {_fts_fa(t.get('window'))} کندلِ اخیر، "
               f"{_fts_fa(t.get('move_pct'))}٪ جابه‌جایی، قیمت {pos} میانگینِ ۵۲ دوره")
        stale = t.get("stale_bars")
        if stale is not None:
            txt += f" (تازه‌ترین پیوتِ تأییدشده {_fts_fa(stale)} کندل عقب است)"
        return txt
    if t.get("trend") == "na":
        return "مبنا: کمتر از دو پیوتِ کامل"
    return (f"مبنا: سقف‌ها {_fts_fa(t.get('prev_high_time'))} "
            f"({_fts_fa(t.get('prev_high'))}) ← {_fts_fa(t.get('last_high_time'))} "
            f"({_fts_fa(t.get('last_high'))})، کف‌ها {_fts_fa(t.get('prev_low_time'))} "
            f"({_fts_fa(t.get('prev_low'))}) ← {_fts_fa(t.get('last_low_time'))} "
            f"({_fts_fa(t.get('last_low'))})")


def _fts_ma(closes, period=14):
    """SMA ساده — MA14 مبنای «خروج تعقیبی» لایهٔ ۱ موتور خروج.
    خروجی هم‌طول ورودی؛ تا period-1 → None."""
    out, acc = [], 0.0
    for i, c in enumerate(closes):
        acc += c
        if i >= period:
            acc -= closes[i - period]
        out.append(round(acc / period, 2) if i >= period - 1 else None)
    return out


def _fts_rsi(closes, period=14):
    """RSI وایلدر — مبنای لایهٔ مومنتوم موتور خروج (واگرایی/چرخش اشباع).
    خروجی هم‌طول ورودی؛ تا period → None."""
    if len(closes) < period + 2:
        return [None] * len(closes)
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    ag, al = gains / period, losses / period
    out = [None] * period
    for i in range(period, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(ch, 0.0)) / period
        al = (al * (period - 1) + max(-ch, 0.0)) / period
        out.append(round(100.0 - 100.0 / (1.0 + ag / al), 1) if al > 0 else 100.0)
    return out


def _fts_fib_leg(candles, swings):
    """لنگرِ فیبو: موجِ اخیر، نه کلِ تاریخ و نه پنج کندلِ آخر.

    موج = زنجیرهٔ سقف‌ها/کف‌هایِ ساختاری که هنوز نشکسته‌اند. اگر آخرین پیوتِ
    تأییدشده کف باشد موج صعودیِ جاری است: از همان کف به عقب می‌رویم و تا زمانی
    که پیوتِ قبلی «کفِ پایین‌تر» باشد و از زمان خودش تا امروز هیچ پایانیِ زیرش
    بسته نشود، موج را بلندتر می‌کنیم — یعنی همان زنجیرهٔ HL که `_fts_classify_trend`
    روند صعودی می‌نامد، فقط تا جایی که پایه‌اش واقعاً پا برجا است. سقفِ موج
    بالاترین highِ پس از آن پایه است. برای موج نزولی قرینه: زنجیرهٔ LH.

    چرا این‌همه دقت؟ دو تعریفِ پیشین هر دو خطا بود و هیچ‌وقت قیمت داخل کمربند
    نمی‌افتاد (سنجشِ هشت نماد: in_zone = false در ۸ از ۸):
      • سرور: «سقفِ تک‌روزیِ تمامِ تاریخ ← کفِ بعد از آن» → نمادی که همین هفته
        سقفِ تاریخی زده موجش به چند کندل خلاصه می‌شد (فولاد: ۶٫۶٪ و کمربندِ
        ۱۵ریالی روی قیمتِ ۳۲۶۰)، و نمادی که سقفش ده سال پیش بود موجِ چندساله
        می‌گرفت.
      • چارت: کمینه/بیشینهٔ ۱۰۰ کندلِ آخر → با همان نمودار، کمربندی که هیچ‌وقت
        به کارِ موتورِ جزوه نمی‌آمد.
    جهتِ موج را روندِ ساختاریِ خودِ FTS (`_fts_classify_trend` روی پیوت‌های روزانه)
    می‌گوید، نه «کدام پیوت آخر از همه تازه‌تر است» — چون در یک رشدِ بی‌وقفه آخرین
    پیوتِ سقف سه کندلِ پیش است و آن تعریف، موجِ صعودی را نزولی می‌خواند.
    خروجی: {'direction', 'start_idx', 'end_idx', 'high', 'low'} یا None.
    """
    n = len(candles)
    if n < 2:
        return None
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    if not highs and not lows:
        hi_idx = max(range(n), key=lambda i: candles[i]["high"])
        return {"direction": "up", "start_idx": 0, "end_idx": n - 1,
                "high": float(candles[hi_idx]["high"]),
                "low": min(float(c["low"]) for c in candles)}
    # «هیچ پایانیِ پس از idx زیرِ قیمت نبسته» — با کمینهٔ پس‌رو، یک‌بار محاسبه
    close = [float(c["close"]) for c in candles]
    suf_min = [0.0] * (n + 1)
    suf_max = [0.0] * (n + 1)
    suf_min[n] = math.inf
    suf_max[n] = -math.inf
    for i in range(n - 1, -1, -1):
        suf_min[i] = min(close[i], suf_min[i + 1])
        suf_max[i] = max(close[i], suf_max[i + 1])

    if not lows:
        up = False
    elif not highs:
        up = True
    else:
        t = _fts_classify_trend(swings, series=candles)["trend"]
        up = True if t == "up" else False if t == "down" else lows[-1]["idx"] >= highs[-1]["idx"]

    if up:
        i = len(lows) - 1
        while i > 0 and lows[i - 1]["price"] < lows[i]["price"] \
                and suf_min[lows[i - 1]["idx"]] >= lows[i - 1]["price"]:
            i -= 1
        base = lows[i]
        idx = base["idx"]
        return {"direction": "up", "start_idx": idx, "end_idx": n - 1,
                "high": max(float(c["high"]) for c in candles[idx:]),
                "low": float(base["price"])}
    i = len(highs) - 1
    while i > 0 and highs[i - 1]["price"] > highs[i]["price"] \
            and suf_max[highs[i - 1]["idx"]] <= highs[i - 1]["price"]:
        i -= 1
    top = highs[i]
    idx = top["idx"]
    return {"direction": "down", "start_idx": idx, "end_idx": n - 1,
            "high": float(top["price"]),
            "low": min(float(c["low"]) for c in candles[idx:])}


# سطوحِ فعالِ ابزارِ فیبو، عینِ جزوه (صفحهٔ ۲): «تنظیم روی ۰ و ۰.۳۳ و ۰.۴ و
# ۰.۵ و ۰.۶۱۸ و ۰.۷ و ۱ فعال می‌کنیم» — و دو کمربندِ ورود ۳۳–۴۰ و ۶۱.۸–۷۰.
_FTS_FIB_LEVELS = (0.0, 0.33, 0.40, 0.50, 0.618, 0.70, 1.00)
_FTS_FIB_BELTS = (("zone_33_40", 0.33, 0.40), ("zone_618_70", 0.618, 0.70))


def _fts_fib_price(top, bot, ratio):
    """قیمتِ سطحِ p روی مقیاس لگاریتمی، از سقفِ موج به پایین."""
    return math.exp(math.log(top) + (math.log(bot) - math.log(top)) * ratio)


def _fts_fib_retrace(top, bot, ratio, direction):
    """سطحِ اصلاحِ pِ موج، در مقیاس لگاریتمی.

    موجِ صعودی: اصلاح از سقف به پایین است (p=0.۶۱۸ ⇒ ۶۱٫۸٪ از صعود برگشته).
    موجِ نزولی: همان p باید از کف به بالا سنجیده شود؛ وگرنه «کمربندِ ۳۳–۴۰٪»
    رویِ موجِ ریزشی جایی نزدیک سقف می‌افتد — یعنی درست همان‌جا که قیمتِ موج
    از آن شروع کرده، و کاربر به‌جای منطقۀ بازگشت، ابتدای ریزش را می‌بیند.
    """
    if direction == "down":
        return math.exp(math.log(bot) + (math.log(top) - math.log(bot)) * ratio)
    return _fts_fib_price(top, bot, ratio)


def _fts_fib_zones(candles, swings):
    """کمربندها و سطوحِ فیبوناچی در مقیاس لگاریتمی — متدولوژی FTS صفحهٔ ۲.

    چرا لگاریتم؟ در سهام‌های حرصیِ تالار شفاف، حرکت ×۴ و اصلاح ۵۰٪ آن در مقیاس
    خطی «کف» درست نمی‌دهد؛ نسبت اصلاح باید روی لگاریتم قیمت سنجیده شود.

    بازهٔ اندازه‌گیری: موجِ اخیر (`_fts_fib_leg`). خروجی دو کمربندِ ورود به‌علاوهٔ
    تمامِ سطوحِ جزوه و خودِ موج:
        zone_33_40: ورود پس از «ادامهٔ روند» (کمربند کم‌عمق)
        zone_618_70: کمربند طلایی — منطقهٔ ورود اصلاحی کلاسیک FTS
        levels: [{'ratio', 'price'}] برای ۰ تا ۱
        leg:    {'direction','start','end','high','low'} — بازۀ زمانیِ رسم
    هر کمربند: {'lo', 'hi', 'in_zone'} — in_zone = قیمت پایانیِ آخر داخل کمربند.
    """
    leg = _fts_fib_leg(candles, swings)
    if not leg:
        return None
    top, bot = leg["high"], leg["low"]
    if top <= 0 or bot <= 0 or top <= bot:
        return None
    zones = {}
    direction = leg.get("direction") or "up"
    for key, p1, p2 in _FTS_FIB_BELTS:
        # کمربند در جهتِ موج سنجیده می‌شود: صعودی از سقف به پایین، نزولی از کف
        # به بالا. پیش از این هر دو «از سقف به پایین» بودند، پس روی موجِ ریزشی
        # کمربندِ ۳۳–۴۰٪ چسبیده به همان سقفی می‌افتاد که موج از آن شروع کرده
        # بود — منطقۀ بازگشت نه، ابتدایِ ریزش.
        a, b = _fts_fib_retrace(top, bot, p1, direction), _fts_fib_retrace(top, bot, p2, direction)
        hi_p, lo_p = max(a, b), min(a, b)
        last = float(candles[-1]["close"]) if candles else 0.0
        zones[key] = {"lo": round(lo_p, 2), "hi": round(hi_p, 2),
                      "in_zone": bool(lo_p <= last <= hi_p)}
    return {
        "retrace_base_high": round(top, 2), "retrace_base_low": round(bot, 2),
        **zones,
        "levels": [{"ratio": r, "price": round(_fts_fib_retrace(top, bot, r, direction), 2)}
                   for r in _FTS_FIB_LEVELS],
        "leg": {"direction": leg["direction"],
                "start": str(candles[leg["start_idx"]]["time"])[:10],
                "end": str(candles[leg["end_idx"]]["time"])[:10],
                "high": round(top, 2), "low": round(bot, 2)},
    }


def _fts_jet_setup(candles, ladder=JET_LADDER):
    """ستاپ جت (Jet) — شکستِ پلکانِ مقاومتِ جزوه با آخرینِ کندل.

    تعریفِ جزوه: ``[ih][2].PriceMax < pl && [ih][5] < pl && … && [ih][59] < pl``
    یعنی «آخرینِ همین نشست از سقفِ تک‌روزیِ هشتِ نشستِ مشخص بالاتر رفته»،
    نه «بالاترینِ ۶۰ روز». این دو یکی نیستند: سقفِ متحرکِ ۶۰ روزه سخت‌گیرتر
    است و نمادی که دیروز سقفِ ۴۰ روزه‌اش را بشکند ستاپ نمی‌گیرد، در حالی که
    فیلترِ تابلو آن را جت می‌زند. تا پیش از این چارت و تابلو دو جوابِ متفاوت
    به یک سؤال می‌دادند (JET-BREAK)؛ حالا هر دو همین تابع را share می‌کنند.

    کندلِ آخر = نشستِ جاریِ زنده (live-bar)، پس «آخرین کندل مقاومت را شکست»
    همان چیزی است که مالک خواسته. اگر تاریخچه به [ih][59] نرسد صادقاً
    ``reason`` می‌دهد و false برمی‌گرداند — حدس نمی‌زند.
    خروجی: {'active', 'resistance', 'ath', 'close', 'pct_above_res', 'reason'}.
    """
    need = 1 + max(ladder)
    if len(candles) < need:
        return {"active": False, "resistance": None, "ath": False,
                "close": None, "pct_above_res": None,
                "reason": f"تاریخچه به {need} نشست نمی‌رسد (این {len(candles)})"}
    last = candles[-1]
    # [ih][k] = k نشستِ پیش از امروز = candles[-1-k]
    res = max(float(candles[-1 - k]["high"]) for k in ladder)
    ath_res = max(float(c["high"]) for c in candles[:-1])
    close = float(last["close"])
    up_body = close >= float(last["open"])
    active = bool(res > 0 and close > res and up_body)
    return {"active": active, "resistance": round(res, 2),
            "ath": bool(abs(res - ath_res) / ath_res < 0.002 if ath_res else False),
            "close": round(close, 2),
            "pct_above_res": round((close - res) / res * 100.0, 2) if res else None,
            "reason": None if active else (
                "بدنهٔ نزولی: پایانی زیر آخرینِ بازِ همین نشست" if close > res
                else "آخرین هنوز زیر پلکان مقاومت است")}


def _fts_choch(candles, swings):
    """CHoCH (Change of Character) — شکست قطعیِ آخرین پیوتِ مخالف روند.

    روند فعلی از ساختار خوانده می‌شود:
      • در روند صعودی: CHoCH نزولی وقتی پایانیِ امروز زیر آخرین کف پیوتِ بالاتر
        (last_low) بسته شود — اولین نشانهٔ تغییر کاراکتر ساختار.
      • در روند نزولی: CHoCH صعودی وقتی پایانی امروز بالای آخرین سقف پیوتِ پایین‌تر
        (last_high) بسته شود — نشانهٔ برگشت صعودی (معیار ورود FTS روی نمادهای
        فرسوده‌شده).
      • جهتِ غالب از سمتِ پیوتِ اخیر خوانده می‌شود (آخرین پیوتِ زمانی، سقف یا کف)،
        پس در رنج هم همان یک سمت سنجیده می‌شود. شکستِ باکسِ رنج را این تابع
        برچسب نمی‌زند؛ آن کارِ `range_box` است (فرانت از همان جبران می‌کند).
    آستانهٔ «قطعی»: بسته‌شدنِ کامل پایانی (نه فقط wick) + فاصلهٔ ≥ ۰.۳٪ از سطح.
    خروجی: {'bearish', 'bullish', 'level', 'label'}.
    """
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    out = {"bearish": False, "bullish": False, "level": None, "label": None}
    if not highs or not lows or not candles:
        return out
    last = float(candles[-1]["close"])
    last_high = highs[-1]["price"]
    last_low = lows[-1]["price"]
    # جهت غالب = سمتِ پیوتِ اخیر (آخرین پیوتِ زمانی، سقف یا کف)
    trend_up = lows[-1]["idx"] > highs[-1]["idx"]
    decisive = 0.003
    if trend_up:
        if last < last_low * (1 - decisive):
            out.update(bearish=True, level=round(last_low, 2), label="choch_bear")
    else:
        if last > last_high * (1 + decisive):
            out.update(bullish=True, level=round(last_high, 2), label="choch_bull")
    return out


def _fts_point_hunt(candles, swings):
    """شکار نقطه (Point Hunting) — کف دایامتریک کانال با ۳ تا ۴ لمس.

    کانالِ مورد نظر FTS: خط سقف از دو سقف پیوتِ اخیر (چون در فاز توزیع/رنج
    سقف‌ها تخت‌تر عمل می‌کنند) و کف دایامتریک = خط موازیِ همان شیب که از
    پایین‌ترین کفِ بین آن دو سقف می‌گذرد.
    «لمس» = کندلی که low آن ≤ کفِ محاسبه‌شده × ۱.۰۰۵ (تلورانس ۰.۵٪) و پس از
    نقطهٔ لنگرِ کف رخ داده باشد. آستانهٔ فعال‌شدن سیگنال: ≥ ۳ لمس (مصوب: ۳/۴).
    معنای عملیاتی: هر لمس جدیدِ کف در حالت ≥۳، «شکار نقطه» است — خرید در کف
    کانال با حد ضررِ کوتاه زیر همان کف.
    خروجی: {'touches', 'floor_price', 'active', 'floor_idx', 'floor_date'}.

    `floor_date` همان تاریخِ کندلِ لنگر است. چارت نمی‌تواند به `floor_idx`
    تکیه کند: شمارۀِ اندیس درِ آرایۀِ سرور با ردیف‌هایِ دیدۀِ مرورگر یکی نیست
    (بازگشتِ تاریخچه و تعدیل متفاوت‌اند) — نشستنِ نشانگر رویِ کندلِ اشتباه
    بدتر از نبودنش است. تاریخ را که بدهیم، لایهٔ نمایش همان را به timestamp
    تبدیل می‌کند و اگر درِ چارت نبود، بی‌خبر نمی‌کشد؛ نمی‌کارد.
    """
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    out = {"touches": 0, "floor_price": None, "active": False, "floor_idx": None,
           "floor_date": None}
    if len(highs) < 2 or not lows or len(candles) < 10:
        return out
    h2, h1 = highs[-2], highs[-1]
    if h1["idx"] - h2["idx"] < 3:
        return out                                   # کانال بی‌معنی (سقف‌های چسبیده)
    slope = (h1["price"] - h2["price"]) / (h1["idx"] - h2["idx"])
    anchor_low = min((l for l in lows if h2["idx"] < l["idx"] <= h1["idx"]),
                     key=lambda l: l["price"], default=None)
    if anchor_low is None:
        anchor_low = min(lows, key=lambda l: l["price"])
    floor_at = lambda i: anchor_low["price"] + slope * (i - anchor_low["idx"])
    tol = 0.005
    touches = 0
    for i in range(anchor_low["idx"], len(candles)):
        if candles[i]["low"] <= floor_at(i) * (1 + tol):
            touches += 1
    out.update(touches=touches, floor_price=round(floor_at(len(candles) - 1), 2),
               active=touches >= 3, floor_idx=anchor_low["idx"],
               floor_date=str(candles[anchor_low["idx"]]["time"])[:10])
    return out


def _fts_double_bottom(candles, swings):
    """دابل‌باتم + جعبهٔ رنج (Range-Box) — ستاپ برگشتی FTS.

    دابل‌باتم: دو کف پیوتِ آخر با اختلاف ≤ ۱.۵٪ (کف دومِ «مساوی»)، بین آن‌ها یک
    سقف پیوت (یقهٔ دابل‌باتم). تریگر: پایانیِ امروز بالای یقه.
    جعبهٔ رنج: سقف جعبه = ماکسِ high در ۲۰ کندل اخیر منهای کندل آخر، کف جعبه =
    مینِ low همان پنجره. تریگر شکست: پایانیِ امروز بالای سقف جعبه با بدنهٔ صعودی.
    خروجی: {'double_bottom': {'active','neckline','pct_above_neck'},
            'range_box': {'active','top','bottom','pct_above_top'}}.
    """
    lows = [s for s in swings if s["kind"] == "low"]
    highs = [s for s in swings if s["kind"] == "high"]
    dbl = {"active": False, "neckline": None, "pct_above_neck": None}
    if len(lows) >= 2:
        l1, l2 = lows[-2]["price"], lows[-1]["price"]
        equal = abs(l1 - l2) / max(l1, l2) <= 0.015 if l1 and l2 else False
        necks = [h["price"] for h in highs if lows[-2]["idx"] < h["idx"] < lows[-1]["idx"]]
        if equal and necks and candles:
            neck = max(necks)
            last = float(candles[-1]["close"])
            hit = last > neck
            dbl.update(active=bool(hit), neckline=round(neck, 2),
                       pct_above_neck=round((last - neck) / neck * 100.0, 2) if hit else None)
    box = {"active": False, "top": None, "bottom": None, "pct_above_top": None}
    if len(candles) >= 21:
        win = candles[-21:-1]
        top = max(c["high"] for c in win)
        bot = min(c["low"] for c in win)
        last = candles[-1]
        broke = last["close"] > top and last["close"] >= last["open"]
        box.update(active=bool(broke), top=round(top, 2), bottom=round(bot, 2),
                   pct_above_top=round((last["close"] - top) / top * 100.0, 2) if broke else None)
    return {"double_bottom": dbl, "range_box": box}


_FTS_SETUP_LABELS = {"jet": "جت", "choch": "CHoCH", "dbl": "دابل‌باتم"}


def _fts_setup_history(candles, swings, limit=40, ladder=JET_LADDER):
    """ستاپ‌های FTSِ گذشته، به‌تاریخ — با همان قاعده‌ای که پنل امروز می‌دهد.

    چارت تا پیش از این مارکرهایش را با موتورِ دومی و قاعده‌ای جدا می‌ساخت
    («جت» = حجمِ دو برابرِ میانگین، «CHoCH» = سه کندل) و پنلِ «وضعیت FTS» همان
    لحظه چیز دیگری می‌گفت: روی نُه نمادِ اندازه‌گرفته‌شده چارت تا ده برچسبِ
    «تغییر ساختار» می‌زد که هیچ‌یک در موتورِ جزوه وجود نداشت. حالا هر مارکر از
    همین حلقه می‌آید و قاعده‌ها عینِ `_fts_jet_setup`، `_fts_choch` و
    `_fts_double_bottom`اند — همان سه تابعی که وضعیتِ امروزِ پنل را می‌سازند.
    پیوتِ fractal در کندلِ idx+k تأیید می‌شود، پس در کندلِ i فقط پیوت‌هایِ
    idx ≤ i−k دیده می‌شوند — مارکرِ گذشته به آینده نگاه نمی‌کند. رویدادِ
    متوالی یک‌بار ثبت می‌شود (جریانِ چند جتِ پیاپی یک برچسب است، نه ده‌تا).
    کمربندِ ۳۳–۴۰ اینجا مارکر ندارد: سطحِ فعال است، نه واقعه؛ همان‌طور که در
    `fib` و نشانگرِ «داخل کمربند» به پنل می‌رسد.
    خروجی: [{'date','kind','label','price','side'}] مرتب زمانی، حداکثر limit.
    """
    need = 1 + max(ladder)
    n = len(candles)
    if n < need + 1:
        return []
    k = _FTS_SWING_K
    hp = [s for s in swings if s["kind"] == "high"]
    lp = [s for s in swings if s["kind"] == "low"]
    a = b = 0
    last_h = last_l = prev_l = None
    neck = None
    on = {"jet": False, "choch": None, "dbl": False}
    events = []

    def emit(i, kind, price, side):
        events.append({"date": str(candles[i]["time"])[:10], "kind": kind,
                       "label": _FTS_SETUP_LABELS[kind],
                       "price": round(float(price), 2), "side": side})

    for i in range(need - 1, n):
        while a < len(hp) and hp[a]["idx"] <= i - k:
            last_h = hp[a]; a += 1
        new_low = None
        while b < len(lp) and lp[b]["idx"] <= i - k:
            new_low = lp[b]; b += 1

        # دو کفِ مساوی ← یقهٔ منتظر؛ پیوتِ کفِ تازه الگو را همان‌جا بازنشانی می‌کند
        if new_low is not None:
            prev_l, last_l = last_l, new_low
            neck = None
            if prev_l and prev_l["price"] > 0 and last_l["price"] > 0:
                if abs(prev_l["price"] - last_l["price"]) / max(
                        prev_l["price"], last_l["price"]) <= 0.015:
                    necks = [h["price"] for h in hp
                             if prev_l["idx"] < h["idx"] < last_l["idx"]]
                    neck = max(necks) if necks else None

        c = candles[i]
        hi = float(c["high"])
        cl, op = float(c["close"]), float(c["open"])
        up_leg = bool(last_l and (not last_h or last_l["idx"] >= last_h["idx"]))
        # ۱) جت — شکستِ پلکانِ مقاومت با بدنهٔ صعودی، عینِ `_fts_jet_setup`
        res = max(float(candles[i - 1 - j]["high"]) for j in ladder)
        jet = bool(res > 0 and cl > res and cl >= op)
        if jet and not on["jet"]:
            emit(i, "jet", max(hi, res), "above")
        on["jet"] = jet

        # ۲) CHoCH — شکستِ قطعیِ آخرین پیوتِ مخالف، عینِ `_fts_choch`
        if last_h and last_l:
            want = "bear" if up_leg else "bull"
            level = last_l["price"] if up_leg else last_h["price"]
            broke = (cl < level * 0.997) if up_leg else (cl > level * 1.003)
            if broke and on["choch"] != want:
                emit(i, "choch", level, "below" if up_leg else "above")
            on["choch"] = want if broke else None

        # ۳) دابل‌باتم — یقه‌شکستِ دو کفِ مساوی، عینِ `_fts_double_bottom`
        dbl = bool(neck and cl > neck)
        if dbl and not on["dbl"]:
            emit(i, "dbl", neck, "above")
        on["dbl"] = dbl

    return events[-limit:]


def _fts_exit_layer1(candles, entry_hint=None):
    """لایهٔ ۱ موتور خروج — حد ضرر سخت + خروج تعقیبی MA14.

    ▪ حد ضرر سخت (Hard Stop): ۵٪ زیر نقطهٔ ورود، یا ۵٪ زیر «آخرین کفِ مهم»
      (major swing low) — هر کدام که بالاتر است (نزدیک‌ترین محافظ). آخرین کف مهم
      = پایین‌ترین low در ۲۰ کندل اخیر (کفِ «چرخش» اخیر؛ برخلاف پیوت fractal که
      به دلیل پنجرهٔ k کندل تأخیر دارد، این کف همیشه تا دیروز شناخته می‌شود و
      با _stop_refs در confidence_engine.py هم‌خوان است: «swing stop = ۵٪ زیر
      آخرین کف مهم»).
    ▪ خروج تعقیبی (Trailing): «بدنهٔ» کندل روزانه کاملاً زیر MA14 بسته شود —
      یعنی max(open, close) < MA14. شرطِ بدنه (نه wick) باعث می‌شود سکه‌های
      سایه‌دارِ یک‌روزه علامت اشتباه ندهند؛ دو کندل متوالی برای قطعیتِ سیگنال
      لازم است (کندل اول = هشدار، دوم = تأیید خروج).
    خروجی: {'hard_stop', 'stop_basis', 'stop_hit', 'ma14_exit', 'ma14_exit_pending',
            'ma14', 'close'}.
    """
    out = {"hard_stop": None, "stop_basis": None, "stop_hit": False,
           "ma14_exit": False, "ma14_exit_pending": False,
           "ma14": None, "close": None}
    if not candles:
        return out
    last = candles[-1]
    close = float(last["close"])
    out["close"] = round(close, 2)
    # --- حد ضرر سخت ---
    # بیست کندلِ بسته‌شده. کندلِ آخر نشستِ جاریِ زنده است و کمینۀ آن با هر تیک
    # عوض می‌شود؛ پیش از این همین سایهٔ لحظه‌ای حدِ ضرری را که در تابلو، سبد و
    # کارتِ پلن منتشر شده پله‌پله پایین می‌کشید.
    closed = candles[:-1] if len(candles) > 1 else candles
    major_low = min(float(c["low"]) for c in closed[-20:])
    cand = []
    if entry_hint and entry_hint > 0:
        cand.append((entry_hint * 0.95, "entry"))
    cand.append((major_low * 0.95, "swing_low"))
    stop_px, basis = max(cand, key=lambda x: x[0])
    out["hard_stop"] = round(stop_px, 2)
    out["stop_basis"] = basis
    out["stop_hit"] = bool(close < stop_px)
    # --- خروج تعقیبی MA14 ---
    closes = [float(c["close"]) for c in candles]
    ma14 = _fts_ma(closes, 14)
    out["ma14"] = ma14[-1] if ma14 else None
    if out["ma14"] is None:
        return out
    body_top = max(float(last["open"]), close)
    body_below = body_top < out["ma14"]
    prev_below = False
    if len(candles) >= 2 and ma14[-2] is not None:
        p = candles[-2]
        prev_below = max(float(p["open"]), float(p["close"])) < ma14[-2]
    out["ma14_exit"] = bool(body_below and prev_below)   # دو بدنهٔ متوالی زیر MA14
    out["ma14_exit_pending"] = bool(body_below and not prev_below)  # هشدار (کندل اول)
    return out


def _fts_exit_layer2(candles, swings_d):
    """لایهٔ ۲ موتور خروج — خرابی‌های ساختاری.

    ▪ CHoCH نزولی: شکست قطعیِ آخرین کف پیوت در روند صعودی (بالا).</br>
      همان تعریف _fts_choch با جهت صعودی؛ سیگنال رسمی خروج ساختاری FTS —
      کاراکتر روند عوض شده حتی اگر هنوز حد ضرر نخورده باشیم.
    ▪ شکست کف کانال (Channel/Diametric-Floor Breakdown): در ستاپ «شکار نقطه»
      حداقل ۳ لمسِ کف ثبت شده باشد و امروزِ پایانی زیر کفِ دایامتریک بسته شود
      (فاصلهٔ ≥ ۰.۵٪) — یعنی کفی که سه بار خریدار از آن دفاع کرده بود، واگذار شد.
      این خروج «تأییدی» است: تا وقتی لمس ≥ ۳ نباشد، شکستِ یک کفِ بی‌سابقه
      سیگنال نمی‌دهد (همان منطق soft_warnings_v974.py: خرابیِ سطحِ آزموده‌شده).
    خروجی: {'choch_break', 'channel_break', 'level', 'touches'}.
    """
    out = {"choch_break": False, "channel_break": False,
           "level": None, "touches": None}
    if not candles:
        return out
    ch = _fts_choch(candles, swings_d)
    if ch["bearish"]:
        out["choch_break"] = True
        out["level"] = ch["level"]
    ph = _fts_point_hunt(candles, swings_d)
    out["touches"] = ph["touches"]
    floor = ph["floor_price"]
    if ph["active"] and floor and float(candles[-1]["close"]) < floor * 0.995:
        out["channel_break"] = True
        out["level"] = round(floor, 2)
    return out


def _fts_exit_layer3(candles, swings):
    """لایهٔ ۳ موتور خروج — الگوهای برگشتی کلاسیک.

    ▪ هشدار سقف سوم (Third Peak Warning): سه سقف پیوتِ اخیر نتوانند بالای
      همدیگر ببندند (اختلاف ≤ ۱٪ — سقف‌های «تخت»). توزیعِ سه‌مرحله‌ای؛ در
      متدولوژی FTS بعد از سقف سومِ ناموفق، خرید تازه ممنوع و نگهداریِ «پایش‌شده»
      است. این «هشدار» است نه خروج قطعی — مگر با تأیید شکست کف (لایهٔ ۲).
    ▪ دابل‌تاپ: دو سقف پیوتِ آخر با اختلاف ≤ ۱٪ و بین آن‌ها کف پیوت (یقه).
      تریگر خروج: پایانی زیر یقه.
    ▪ سر و شانه (H&S): سه سقف پیوت که میانی بالاترین است (سر) و دو سقف کناری
      در محدودهٔ ۳٪ همدیگر (شانه‌ها). یقه = خط واصل دو کفِ بین سقف‌ها (شیب‌دار
      هم می‌تواند). تریگر خروج: پایانی زیر خط یقه (در هر نقطه از خط، درونِ بازهٔ
      زمانی الگو تا امروز).
    خروجی: {'third_peak', 'double_top', 'hs_break', 'neckline', 'level',
    'third_peak_level'}. سقفِ سومِ تخت یک *ناحیه* است، پس ارتفاعِ همان سه سقف
    (m) هم بیرون می‌رود؛ لایۀ نمایشِ چارت بدونِ این عدد نمی‌تواند باند را
    بکشد و الگو را یا نادیده می‌گرفت یا سرِ خود جایِ سطح را می‌گذاشت (#193).
    """
    out = {"third_peak": False, "double_top": False, "hs_break": False,
           "neckline": None, "level": None, "third_peak_level": None}
    if len(candles) < 15:
        return out
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    last = float(candles[-1]["close"])
    # --- سقف سوم ---
    if len(highs) >= 3:
        h1, h2, h3 = highs[-3]["price"], highs[-2]["price"], highs[-1]["price"]
        m = max(h1, h2, h3)
        if m > 0 and (m - min(h1, h2, h3)) / m <= 0.01:
            out["third_peak"] = True
            out["third_peak_level"] = round(m, 2)
    # --- دابل‌تاپ ---
    if len(highs) >= 2:
        h1, h2 = highs[-2]["price"], highs[-1]["price"]
        m = max(h1, h2)
        twin = m > 0 and (m - min(h1, h2)) / m <= 0.01
        necks = [l["price"] for l in lows if highs[-2]["idx"] < l["idx"] < highs[-1]["idx"]]
        if twin and necks:
            neck = min(necks)
            if last < neck:
                out["double_top"] = True
                out["neckline"] = round(neck, 2)
                out["level"] = round(neck, 2)
    # --- سر و شانه ---
    if len(highs) >= 3 and len(lows) >= 2:
        s1, head, s2 = highs[-3], highs[-2], highs[-1]
        ls1, ls2 = lows[-2], lows[-1]
        between1 = s1["idx"] < ls1["idx"] < head["idx"]
        between2 = head["idx"] < ls2["idx"] < s2["idx"]
        shoulders = abs(s1["price"] - s2["price"]) / max(s1["price"], s2["price"]) <= 0.03
        is_hs = (head["price"] > s1["price"] and head["price"] > s2["price"]
                 and between1 and between2 and shoulders
                 and ls1["idx"] > s1["idx"] and ls2["idx"] < s2["idx"])
        if is_hs:
            # یقه: خط واصل دو کف — مقدار خط در کندل آخر (exterior extropolate)
            span = ls2["idx"] - ls1["idx"]
            if span > 0:
                slope = (ls2["price"] - ls1["price"]) / span
                neck_now = ls1["price"] + slope * (len(candles) - 1 - ls1["idx"])
                if last < neck_now:
                    out["hs_break"] = True
                    out["neckline"] = round(neck_now, 2)
                    out["level"] = round(neck_now, 2)
    return out


def _fts_exit_layer4(candles):
    """لایهٔ ۴ موتور خروج — مومنتوم (RSI).

    ▪ واگرایی نزولی (Bearish Divergence): قیمت سقفِ بالاتر (HH) می‌زند ولی RSI
      سقفِ پایین‌تر (LH). مقایسه روی دو سقف پیوتِ اخیرِ روزانه: RSI در پنجرهٔ
      ±۲ کندلِ هر پیوت بیشینه می‌شود (اوج RSI ممکن است یک‌دو کندل جلو/عقبِ پیوت
      قیمت باشد). واگرایی = هشدار خروج (نه قطعی) — در FTS با کاهش پله‌ای پوزیشن
      همراه است.
    ▪ چرخش اشباع خرید (Overbought Roll-over): RSI روزانه ≥ ۷۰ بوده و اکنون
      «پایان‌یافته به زیر ۶۵» — یعنی از اوجِ اشباع، ۵ واحد واگذاریِ مومنتوم
      رخ داده. سیگنال خروجِ تاکتیکی (سودجمعی) در متدولوژی FTS.
    خروجی: {'rsi_divergence', 'rsi_rollover', 'rsi', 'rsi_prev_peak'}.
    """
    out = {"rsi_divergence": False, "rsi_rollover": False,
           "rsi": None, "rsi_prev_peak": None}
    if len(candles) < 30:
        return out
    closes = [float(c["close"]) for c in candles]
    rsi = _fts_rsi(closes, 14)
    out["rsi"] = rsi[-1]
    swings = _fts_swings(candles, k=_FTS_SWING_K)
    highs = [s for s in swings if s["kind"] == "high"]
    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]

        def _rsi_peak(sw):
            lo = max(0, sw["idx"] - 2)
            hi = min(len(rsi), sw["idx"] + 3)
            vals = [v for v in rsi[lo:hi] if v is not None]
            return max(vals) if vals else None

        r1, r2 = _rsi_peak(h1), _rsi_peak(h2)
        out["rsi_prev_peak"] = r1
        if r1 is not None and r2 is not None:
            # قیمت HH (سقف جدید بالاتر) ولی RSI LH (اوجِ RSI پایین‌تر)
            if h2["price"] > h1["price"] and r2 < r1 - 1.0:   # تلورانس ۱ واحد RSI
                out["rsi_divergence"] = True
    # چرخش اشباع: در ۱۰ کندل اخیر RSI ≥ ۷۰ بوده و اکنون ≤ ۶۵ است
    recent = [v for v in rsi[-10:] if v is not None]
    if recent and out["rsi"] is not None:
        if max(recent) >= 70.0 and out["rsi"] <= 65.0:
            out["rsi_rollover"] = True
    return out


def _fts_exit_engine(candles, entry_hint=None):
    """FTS four-layer exit/stop engine - master assembler.

    Layers (each independently boolean-flagged, layer dict exposed verbatim):
      L1 hard stop + MA14 trailing body-exit  -> _fts_exit_layer1
      L2 structural breaks (CHoCH, channel)   -> _fts_exit_layer2
      L3 reversal patterns (3rd peak, DT, HS) -> _fts_exit_layer3
      L4 momentum (RSI divergence, rollover)  -> _fts_exit_layer4
    Verdict precedence (highest severity first):
      'stop'    - hard stop hit; position must be closed
      'exit'    - confirmed structural/pattern exit (L2 or L3 triggers)
      'caution' - soft warnings only (MA14 pending, divergence, rollover,
                  third peak) - reduce / monitor, do not add
      'hold'    - no exit signal
    Input candles are DAILY OHLCV dicts (same shape as get_chart_db output).
    Output: {'verdict', 'signals': [..], 'l1', 'l2', 'l3', 'l4'}.
    """
    l1 = _fts_exit_layer1(candles, entry_hint=entry_hint)
    swings_d = _fts_swings(candles, k=_FTS_SWING_K)
    l2 = _fts_exit_layer2(candles, swings_d)
    l3 = _fts_exit_layer3(candles, swings_d)
    l4 = _fts_exit_layer4(candles)
    signals = []
    if l1["stop_hit"]:
        signals.append("stop_hard")
    if l1["ma14_exit"]:
        signals.append("ma14_trail")
    if l1["ma14_exit_pending"]:
        signals.append("ma14_watch")
    if l2["choch_break"]:
        signals.append("choch_break")
    if l2["channel_break"]:
        signals.append("channel_break")
    if l3["third_peak"]:
        signals.append("third_peak")
    if l3["double_top"]:
        signals.append("double_top")
    if l3["hs_break"]:
        signals.append("hs_break")
    if l4["rsi_divergence"]:
        signals.append("rsi_divergence")
    if l4["rsi_rollover"]:
        signals.append("rsi_rollover")
    if l1["stop_hit"]:
        verdict = "stop"
    elif l2["choch_break"] or l2["channel_break"] or l3["double_top"] or l3["hs_break"]:
        verdict = "exit"
    elif l1["ma14_exit_pending"] or l4["rsi_divergence"] or l4["rsi_rollover"] or l3["third_peak"]:
        verdict = "caution"
    else:
        verdict = "hold"
    return {"verdict": verdict, "signals": signals,
            "l1": l1, "l2": l2, "l3": l3, "l4": l4}


# ============================================================================
# v10 - single-symbol FTS analysis (payload assembly + endpoint)
# ============================================================================

FTS_ANALYSIS_CACHE = {}          # {key: (ts, payload)}; key = symbol|close
FTS_ANALYSIS_CACHE_MAX = 3000    # size cap (bulk-screener style churn safe)
FTS_ANALYSIS_TTL = 900.0         # seconds; payload recomputed after expiry


def _fts_analyze_candles(symbol, candles, entry_hint=None):
    """Pure-compute FTS analysis for one symbol from its DAILY candles.

    No I/O and no cache writes: safe to call from get_chart_db (its caller
    owns error handling and serialization). `candles` = list of
    {'time','open','high','low','close','volume'} ascending by time.

    Output keys (all optional-safe for the UI, None when insufficient data):
      trend            - {'D','W','M','alignment'} trend dicts (_fts_classify_trend)
      fib              - log-scale 33-40% / 61.8-70% retrace belts or None
      jet              - breakout entry setup {'active','resistance','ath',...}
      choch            - structural break {'bearish','bullish','level','label'}
      point_hunt       - channel-floor touch count {'touches','floor_price',...}
      double_bottom    - {'active','neckline','pct_above_neck'}
      range_box        - {'active','top','bottom','pct_above_top'}
      exit_engine      - four-layer verdict {'verdict','signals','l1'..'l4'}
    """
    swings_d = _fts_swings(candles, k=_FTS_SWING_K)
    w = _fts_resample(candles, "W")
    m = _fts_resample(candles, "M")
    out = {
        "trend": {
            "D": _fts_classify_trend(swings_d, series=candles),
            "W": _fts_classify_trend(_fts_swings(w, k=2), series=w),
            "M": _fts_classify_trend(_fts_swings(m, k=2), series=m),
            "alignment": "na",
        },
        "fib": _fts_fib_zones(candles, swings_d),
        "jet": _fts_jet_setup(candles),
        "choch": _fts_choch(candles, swings_d),
        "point_hunt": _fts_point_hunt(candles, swings_d),
        "double_bottom": {"active": False, "neckline": None, "pct_above_neck": None},
        "range_box": {"active": False, "top": None, "bottom": None, "pct_above_top": None},
        "exit_engine": None,
    }
    # Alignment: all three timeframes agree and are directional.
    tD = out["trend"]["D"]["trend"]
    tW = out["trend"]["W"]["trend"]
    tM = out["trend"]["M"]["trend"]
    if tD != "na" and tD == tW and tW == tM and tD in ("up", "down"):
        out["trend"]["alignment"] = tD

    # ماتریس روند چندزمانه FTS طبق بخش ۲ سند رسمی FTS v2.1
    if tW == "down":
        out["trend"]["matrix"] = {
            "decision": "REJECT",
            "setup": "NONE",
            "desc": "تایم هفتگی نزولی — وتوی کامل و ممنوعیت ورود (طبق چارت درختی FTS)",
        }
    elif tW == "range":
        out["trend"]["matrix"] = {
            "decision": "REJECT",
            "setup": "NONE",
            "desc": "تایم هفتگی خنثی — عدم ورود طبق چارت درختی FTS",
        }
    elif tW == "na":
        # کمبود داده رأی نیست: دو پیوتِ کاملِ هفتگی نداریم (نماد تازه‌وارد یا
        # سابقهٔ کوتاه). قبلاً همین حالت با «خنثی» یک‌جا REJECT می‌شد و سهمِ سالم
        # بی‌دلیل خط قرمز می‌گرفت.
        out["trend"]["matrix"] = {
            "decision": "UNKNOWN",
            "setup": "NONE",
            "desc": "روند هفتگی قابل تشخیص نیست (کمتر از دو پیوت کامل) — نظر داده نمی‌شود",
        }
    elif tW == "up":
        if tD == "up":
            out["trend"]["matrix"] = {
                "decision": "PERMITTED",
                "setup": "JET_OR_PULLBACK_HOLD",
                "desc": "هفتگی صعودی + روزانه صعودی: ستاپ جت یا پولبک؛ نگهداری روندی بدون نوسان‌گیری",
            }
        elif tD == "down":
            out["trend"]["matrix"] = {
                "decision": "PERMITTED",
                "setup": "FIB_CHOCH_STEP_ENTRY",
                "desc": "هفتگی صعودی + روزانه نزولی: ستاپ فیبوناچی لگاریتمی و CHoCH؛ ورود پله‌ای",
            }
        elif tD == "na":
            # «سنجیده نشد» رأی نیست: روزانۀ کم‌سابقه نه صعودی است نه خنثی. پیش از
            # این در همان `else`ی خنثی می‌نشست و «خرید در کف باکس رنج» پیشنهاد
            # می‌داد — پیشنهادِ ستاپ رویِ چیزی که اصلاً اندازه گرفته نشده بود.
            out["trend"]["matrix"] = {
                "decision": "UNKNOWN",
                "setup": "NONE",
                "desc": "هفتگی صعودی + روزانه سنجیده نشده (کمتر از دو پیوت کامل) — نظر داده نمی‌شود",
            }
        else:
            out["trend"]["matrix"] = {
                "decision": "PERMITTED",
                "setup": "SWING_DOUBLE_BOTTOM_OR_RANGE",
                "desc": "هفتگی صعودی + روزانه خنثی: ستاپ کف دوقلو یا خرید در کف باکس رنج؛ نوسان‌گیری زیر ۳ ماه",
            }

    w_reason = _fts_trend_reason(out["trend"]["W"])
    d_reason = _fts_trend_reason(out["trend"]["D"])
    _mx = out["trend"].get("matrix")
    if _mx is not None:
        _mx["basis"] = {"weekly": w_reason, "daily": d_reason}
        if _mx["decision"] in ("REJECT", "UNKNOWN"):
            # دلیلِ همان درزی که رأی را بسته است: وتوی هفتگی دلیلِ هفتگی می‌خواهد،
            # «روزانه سنجیده نشد» دلیلِ روزانه.
            why = w_reason if tW in ("down", "range", "na") else d_reason
            if why:
                _mx["desc"] = f"{_mx['desc']} — {why}"

    # استراتژی ساعت شنی پیشرفته FTS طبق بخش ۵ سند رسمی FTS v2.1
    closes_w = [float(c["close"]) for c in w] if w else []
    if len(closes_w) >= 15:
        rsi5_w = _fts_rsi(closes_w, 5)
        last_cw = closes_w[-1]
        last_rsi5 = rsi5_w[-1] if rsi5_w else None
        # MA52 فقط با پنجاه‌ودو نشستِ هفتگیِ واقعی. پیش از این دوره با
        # «کمترینِ پنجاه‌ودو و طولِ سابقه» ساخته می‌شد و همان عددِ کوتاه‌تر با
        # نامِ ma52 منتشر و در شرطِ «خریدِ ۲ تا ۴ برابری» به کار می‌رفت: نمادی
        # با چهارده هفته، میانگینِ چهارده‌هفته‌اش را زیرِ پا داشت و ساعت شنی
        # روشن می‌شد. عددی که موتور نگفته نباید جایِ عددِ دیگر را بزند.
        ma_ok = len(closes_w) >= 52
        ma52_w = _fts_ma(closes_w, 52) if ma_ok else []
        last_ma52 = ma52_w[-1] if ma52_w else None
        is_hg_active = bool(last_ma52 and last_cw < last_ma52 and (last_rsi5 is not None and last_rsi5 <= 30.0))
        out["hourglass"] = {
            "active": is_hg_active,
            "weekly_close": round(last_cw, 2),
            "ma52": round(last_ma52, 2) if last_ma52 else None,
            "weekly_bars": len(closes_w),
            "weekly_rsi5": round(last_rsi5, 1) if last_rsi5 is not None else None,
            "action": "ACCELERATE_BUY_2X_4X" if is_hg_active else "NORMAL",
            "desc": (
                "اهرم شتاب‌دهنده ساعت شنی فعال: قیمت هفتگی زیر MA52 و RSI هفتگی اشباع فروش (خرید ۲ تا ۴ برابری)"
                if is_hg_active
                else ("MA52 سنجیده نشد (کمتر از ۵۲ کندل هفتگی) — ساعت شنی نظر نمی‌دهد"
                      if not ma_ok else "شرایط ساعت شنی برقرار نیست")
            ),
        }
    else:
        out["hourglass"] = {
            "active": False,
            "weekly_close": None,
            "ma52": None,
            "weekly_rsi5": None,
            "action": "NORMAL",
            "desc": "سابقه هفتگی کمتر از حد نصاب",
        }

    box = _fts_double_bottom(candles, swings_d)
    out["double_bottom"] = box["double_bottom"]
    out["range_box"] = box["range_box"]
    out["exit_engine"] = _fts_exit_engine(candles, entry_hint=entry_hint)
    out["setups"] = _fts_setup_history(candles, swings_d)
    return out


def _basket_entry(symbol):
    """قیمت خریدِ ثبت‌شدهٔ کاربر در سبد — مبنای «٪۵ زیرِ قیمتِ خرید» (جزوه، بند ۵/حد ضررِ تفکیکی).

    از تصمیمات سبد (user.db) خوانده می‌شود و فقط به `/api/fts/{symbol}` داده
    می‌شود؛ غربگر عمداً بی‌آن صدا می‌زند تا حلقۀ ۶۰۰نمادی بانک کاربر را ورق نزند.
    فقط ردیف accept با قیمتِ مثبت؛ غیر آن ⇒ None تا موتور صادقاً به کفِ ساختاری
    برگردد و `stop_basis` همان منشأ را به UI بگوید.
    """
    try:
        conn = get_user_db()
        try:
            row = conn.execute(
                "SELECT price, status FROM selection_decisions WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    if row is None or row["status"] != "accept":
        return None
    try:
        price = float(row["price"])
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _fts_scaled(candles, factors, volumes):
    """کندل‌هایِ صعودیِ ریالیِ تعدیل‌شده — همان سریِ «combined» که چارت می‌رسم.

    مسیرِ CDN کندل‌ها را نزولی می‌دهد و حجم را در آرایه‌ای جدا؛ اینجا هر دو
    یکسان‌سازی می‌شوند تا موتورِ سرور و موتورِ مرورگر یک ورودی داشته باشند.
    گردکردنِ ریال و تقسیمِ حجم بر ضریب، عینِ `applyAdjustmentToCandles` سمت
    فرانت است (به‌جایِ banker's roundingِ پایتون، پایین‌گردِ +۰٫۵).
    """
    fac = {str(x.get("time") or ""): float(x.get("factor") or 1.0)
           for x in (factors or []) if isinstance(x, dict)}
    vol = {str(x.get("time") or ""): float(x.get("value") or 0)
           for x in (volumes or []) if isinstance(x, dict)}

    def r(v):
        return float(math.floor(v + 0.5)) if v >= 0 else v

    out = []
    for c in candles or []:
        t = str(c.get("time") or "")
        if len(t) < 10:
            continue
        k = fac.get(t[:10], 1.0)
        if not k > 0:
            k = 1.0
        o, h, l, cl = (float(c.get(x) or 0) for x in ("open", "high", "low", "close"))
        v = vol.get(t[:10], float(c.get("volume") or 0))
        out.append({"time": t[:10], "open": r(o * k), "high": r(h * k), "low": r(l * k),
                    "close": r(cl * k), "last": r(cl * k), "volume": r(v / k)})
    out.sort(key=lambda c: c["time"])
    return out


def _fts_analysis_series(symbol):
    """سریِ کندلِ تحلیل + برچسبِ مبنا.

    چارت تاریخچۀ کاملِ نماد را از CDN می‌گیرد و ضرایبِ تعدیل را روی آن می‌زند؛
    `price_history` محلی درِ بانکِ امروز کم‌عمق است و میانیِ نمادها ۲۰ نشست (از
    ۲۵۱۸ نماد، ۸۷۲ تا به ۶۰ نشست می‌رسند) — این وصفِ دادۀ موجود است، نه سقفِ
    برنامه: هرسِ ۷۳۰روزه درِ ۱۴۰۵-۰۷-۱۱ لغو شد و عمق با `--backfill-history` پر
    می‌شود. بی‌این هم‌سان‌سازی، نوارِ نشان‌ها و
    پنلِ «وضعیت FTS» برای نمادی که چارتش جت می‌زد می‌گفتند «تاریخچه به ۶۰ نشست
    نمی‌رسد» (شاهد: خودرو ۶ نشست در برابر ۵۲۸۷، تكنار ۶ در برابر ۲۳۲۰) و پلکانِ
    مقاومت را پیش‌از‌تعدیل می‌دادند (شاهد: فولاد ۴۲۱۳ در برابر ۳۴۱۰).
    وقتی CDN قطع است یا پاسخِ معتبری ندارد، صادقاً به بانکِ محلی برمی‌گردد و
    همان را در `analysis_basis` اعلام می‌کند.
    """
    try:
        payload = get_chart_tsetmc(symbol)
    except Exception:
        payload = None
    if isinstance(payload, dict) and payload.get("status") == "success":
        series = _fts_scaled(payload.get("candles") or [],
                             payload.get("factors") or [],
                             payload.get("volumes") or [])
        if len(series) >= 2:
            src = str(payload.get("adjustSource") or "")
            basis = "local-db" if src.startswith("local-db") else "tsetmc-adjusted"
            return series, basis
    db = get_chart_db(symbol)
    return (db.get("candles") or []), "local-db"


def _fts_analyze_symbol(symbol, entry_hint=None):
    """Cached single-symbol FTS payload for /api/fts/{symbol} and badges.

    Cache key = symbol + last daily close + entry hint: the hard stop is
    entry-dependent, so a cached swing-basis payload must never answer an
    `entry` request. Intra-day live-candle churn recomputes freely, but
    repeated calls with unchanged closes (the common case for the badge strip
    polling the same symbol) are served from cache. TTL guards against a
    static close with drifting intraday fields.
    """
    import time as _t
    now = _t.time()
    try:
        candles, basis = _fts_analysis_series(symbol)
    except Exception as e:
        return {"status": "error", "symbol": symbol, "message": str(e)}
    if not candles:
        return {"status": "empty", "symbol": symbol, "fts": None}
    last_close = candles[-1].get("close")
    key = f"{symbol}|{last_close}|{entry_hint}"
    cached = FTS_ANALYSIS_CACHE.get(key)
    if cached and (now - cached[0]) < FTS_ANALYSIS_TTL:
        return cached[1]
    try:
        fts = _fts_analyze_candles(symbol, candles, entry_hint=entry_hint)
    except Exception as e:
        return {"status": "error", "symbol": symbol, "message": str(e)}
    result = {"status": "success", "symbol": symbol, "fts": fts,
              "analysis_basis": basis, "bars": len(candles)}
    if len(FTS_ANALYSIS_CACHE) > FTS_ANALYSIS_CACHE_MAX:
        FTS_ANALYSIS_CACHE.clear()
    FTS_ANALYSIS_CACHE[key] = (now, result)
    return result


@router.get("/api/fts/{symbol}")
def get_fts(symbol: str):
    """Light analysis-only payload for the tech-view badge strip.

    Same FTS engine as the embedded chart payload; separate endpoint so the
    UI can refresh badges without refetching full candle history. The user's
    saved basket price is resolved here (not in the engine) so the hard stop
    can be «۵٪ زیرِ قیمتِ خرید» when the symbol is actually held.
    """
    return _fts_analyze_symbol(symbol, entry_hint=_basket_entry(symbol))

# __FTS_APPEND__
