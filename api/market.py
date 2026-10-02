"""Market snapshot, live FTS scan and FTS threshold config.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _count_procs, get_db
from bors_config import DB_PATH, FTS_CONFIG_PATH, FTS_DEFAULTS, FTS_LEGACY_LISTS, FTS_LEGACY_SCALARS, FTS_LIST_KEYS, FTS_STR_KEYS, MARKET_STATUS_PATH
from bors_flags import _ORJ
import market_state
from tape_flags import apply_tape_flags
from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import Response
import json
import numpy as np
import pandas as pd
import sqlite3
import threading
import time


router = APIRouter()


# حالت‌های شناخته‌شدهٔ فیلتر صنعت (پنل تنظیمات کدال). دو مقدارِ اول رفتارِ
# قدیمیِ «رژیم قیمت‌گذاری» اند؛ دو مقدارِ تازه فهرستِ دستیِ کاربر را اعمال
# میکنند — وگرنه یک typo در industry_mode بی‌صدا فیلتر را خاموش می‌کرد.
_FTS_INDUSTRY_MODES = ("Exclude_Mandatory_Pricing", "Rank_Only",
                       "Include_Industries", "Exclude_Industries")


def load_fts_config() -> dict:
    """پیش‌شرط‌ها را میخواند و کلیدهای نسل قدیم را به ساختار v8 مهاجرت میدهد."""
    try:
        with open(FTS_CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    cfg = dict(FTS_DEFAULTS)
    # ۱) نگاشت مستقیم کلیدهای معتبر v8
    # v9.1 رفع باگ: شرط قبلی «k not in FTS_LEGACY_LISTS.values()» بود؛ مقادیر آن
    # دقیقاً mandatory_sectors/free_sectors است، پس لیست صنایع هرگز از فایل
    # خوانده نمی‌شد و «فیلتر صنعت» هیچ‌وقت ذخیره نمی‌شد. کلیدهای قدیمی
    # (bad_sectors/good_sectors) از قبل با «k in FTS_DEFAULTS» رد می‌شوند.
    for k, v in raw.items():
        if k in FTS_DEFAULTS:
            cfg[k] = v
    # ۲) مهاجرت کلیدهای عددی قدیمی (فقط اگر کلید جدید در فایل نباشد)
    for old, new in FTS_LEGACY_SCALARS.items():
        if old in raw and new not in raw:
            try:
                cfg[new] = float(raw[old])
            except (TypeError, ValueError):
                pass
    # ۳) مهاجرت لیست‌های صنایع
    for old, new in FTS_LEGACY_LISTS.items():
        if old in raw and new not in raw:
            cfg[new] = raw[old]
    # ۴) پاک‌سازی نوع
    for k in FTS_LIST_KEYS:
        v = cfg.get(k)
        if isinstance(v, str):
            v = [s.strip() for s in v.replace("،", ",").split(",") if s.strip()]
        cfg[k] = [str(s).strip() for s in (v or []) if str(s).strip()]
    for k, v in list(cfg.items()):
        if k in FTS_STR_KEYS:
            cfg[k] = str(v)
        elif k in FTS_LIST_KEYS:
            continue
        elif isinstance(FTS_DEFAULTS[k], bool):
            cfg[k] = bool(v)
        elif k.endswith("_max") or k.endswith("_years") or k.endswith("_sessions"):
            try:
                cfg[k] = int(float(v))
            except (TypeError, ValueError):
                cfg[k] = FTS_DEFAULTS[k]
        else:
            try:
                cfg[k] = float(v)
            except (TypeError, ValueError):
                cfg[k] = FTS_DEFAULTS[k]
    return cfg

def _market_running():
    """True when at least one test_tsetmc (بازار) process is alive."""
    return _count_procs("test_tsetmc")

@router.get("/api/market/sync-state")
def market_sync_state():
    """جزئیات زنده/آخرین بروزرسانی تابلو بازار (برای پنل جزئیات UI).

    NOTE (v9.7.1 cleanup): this path used to be registered a second time further
    down the module, returning `_market_sync_alive()` (in-process thread) instead
    of `_market_running()` (external test_tsetmc process). Starlette matches the
    first registered route, so that later copy was unreachable and has been
    removed. If the UI should reflect the in-process sync thread rather than a
    standalone syncer process, swap the call below to `_market_sync_alive()` --
    that is a behaviour change, not a no-op.
    """
    try:
        with open(MARKET_STATUS_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    return {"status": "success", "running": _market_running(), "last": d}

@router.get("/api/market")
def get_market(request: Request):
    """تابلو. هیچ‌وقت پایِ بازسازیِ ۱.۴ ثانیه‌ای نمی‌ایستد (بخوان SWR)."""
    cached = _market_from_cache(request, time.time())
    if cached is not None:
        return cached
    return _build_market_response(request)


# ── تازه‌سازیِ پس‌زمینه‌ای (#176) ────────────────────────────────────────
# اندازه‌گیری ۱۴۰۵‑۰۷‑۰۵: هر بار که TTLِ کش می‌پایاند، یکِ مشتری باید ۱٫۴ ثانیه
# برایِ ساختنِ دوبارهٔ بدنه صبر کند (در نشستِ پنج‌ثانیه‌یِ پُرمخاطره این یعنی
# یکی از هر چهار پولینگ دیر می‌رسد). ولی در آن لحظه همان بدنهٔ کهنه هنوز درست
# است: سینکِ پایگاه هر ۹۰ ثانیه یک‌بار چیزی عوض می‌کند، پس کشِ ۲۰ ثانیه‌ای
# تقریباً همیشه دارد چیزی را دوباره می‌سازد که تغییر نکرده. راهِ درست پس
# «صبرِ مشتری» نیست؛ «بدهِ کهنه، بساز در پس‌زمینه» است.
_MARKET_BUILD_LOCK = threading.Lock()
_MARKET_BUILDING = False
# سقفِ کهنه: اگر بازسازیِ پس‌زمینه چند دقیقه است که می‌شکند، «کهنه» دیگر
# بی‌خطر نیست؛ از این لحظه به بعدِ درخواست همگام می‌سازد و همان خطای واقعی
# را بالا می‌فرستد تا صادقانه به UI برسد، نه یک تابلوی زندهٔ مُرده.
_MARKET_STALE_CEILING = 300.0


class _MarketInternalRequest:
    """درخواستِ جعلیِ نخِ پس‌زمینه: بدونِ If-None-Match، تا بازسازیِ واقعی
    انجام شود و etagِ بیرونی مانعش نشود."""
    headers: dict = {}


def _kick_market_rebuild():
    """یک بازسازیِ هم‌زمان، نه بیشتر. قفل هرگز موقعِ ساختن گرفته نمی‌ماند."""
    global _MARKET_BUILDING
    with _MARKET_BUILD_LOCK:
        if _MARKET_BUILDING:
            return
        _MARKET_BUILDING = True

    def _run():
        global _MARKET_BUILDING
        try:
            _build_market_response(_MarketInternalRequest())
        except Exception as _e:
            print(f"[market] background rebuild failed: {_e}")
        finally:
            with _MARKET_BUILD_LOCK:
                _MARKET_BUILDING = False

    threading.Thread(target=_run, daemon=True).start()


_MARKET_SNAP_LOCK = threading.Lock()


def _market_snapshot():
    """بدنه، زمان و etag را به‌صورتِ یک عکسِ یکدست می‌خواند.

    سه کلیدِ جدا در یک دیکشنری این تضمین را نمی‌دهند: اگر نخِ سازنده
    بدنۀ تازه را نوشته باشد ولی etag هنوز کهنه باشد، خواننده بدنۀ تازه را
    با etagِ کهنه می‌سنجد و به مشتریِ دارندهٔ همان etagِ کهنه ۳۰۴ می‌دهد —
    یعنی کاربر «تازه شد» را می‌شنود ولی همان عددِ قدیمی را نگه می‌دارد.
    """
    with _MARKET_SNAP_LOCK:
        return MARKET_CACHE.get("body"), MARKET_CACHE.get("t", 0), MARKET_CACHE.get("etag", "")


def _market_store(body, etag, when):
    with _MARKET_SNAP_LOCK:
        MARKET_CACHE["body"] = body
        MARKET_CACHE["etag"] = etag
        MARKET_CACHE["t"] = when


def _market_clear():
    with _MARKET_SNAP_LOCK:
        MARKET_CACHE.clear()
    # آینهٔ دلتا هم باید بسوزد: بدنه‌ای که نبودنِ آن را به کلاینت می‌گوییم
    # نمی‌تواند منبعِ «ردیف‌هایِ تغییریافته» بماند.
    try:
        _delta_clear()
    except NameError:
        pass


def warm_market_cache():
    """تابلو را بی‌درنگ یک‌بار می‌سازد تا در کش بنشیند.

    دو جا لازم است: پایانِ سینک (داده عوض شده و کشِ پیشین بی‌ارزش است) و
    پس از بالا آمدنِ سرور (پیش از آنکه نخستین پنجره باز شود). اگر ساختن
    شکست، کش را خالی می‌کند — «ساختنِ ناموفق» هرگز نباید با دادهٔ کهنهٔ
    مقابلهتِ کاربر پاسخ داده شود؛ درخواستِ بعدی همگام می‌سازد و خطا را
    صادقانه به بالا می‌فرستد.
    """
    try:
        _build_market_response(_MarketInternalRequest())
        return True
    except Exception as _e:
        print(f"[market] warm failed: {_e}")
        _market_clear()
        return False


def _market_from_cache(request: Request, now: float):
    """پاسخ از کش؛ None یعنی کشی نیست یا آن‌قدر کهنه است که باید همین‌جا
    همگام ساخته شود (و اگر ساختن شکست، خطا صادقانه به بالا برود)."""
    body, built_at, etag = _market_snapshot()
    if body is None:
        return None
    age = now - built_at
    if age > _MARKET_STALE_CEILING:
        return None
    fresh = age < MARKET_CACHE_TTL
    if not fresh:
        _kick_market_rebuild()
    if request.headers.get("if-none-match") == etag and etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(content=body, media_type="application/json",
                    headers={"Cache-Control": "max-age=15",
                             "X-Cache": "HIT" if fresh else "STALE", "ETag": etag})


# ════════════════════════════════════════════════════════════════════════════
# پنجره‌هایِ روزانۀ تابلو — یک‌بار در روز، نه یک‌بار در هر تیک (v1.0.56)
# ════════════════════════════════════════════════════════════════════════════
# سنجشِ همین هفته رویِ بانکِ نصبی (tools/rebuild_cost_probe.py، چک‌سامِ
# ستون‌به‌ستونِ دو مسیر یکسان، ۵۳۶۰ ردیف): کوئری ۰٫۶۷۴ ثانیه، بی‌این دو پنجره
# ۰٫۰۶۲ ثانیه. دلیلِ افتِ این‌همه، خودِ داده نیست: پنجرۀ نمایشِ ۳۰ روزه و
# پنجرۀ شصت‌نشستِ [ih] به تیکِ زنده وابسته‌اند، درحالی‌که تیک فقط ستون‌هایِ
# *همان نشست* را در daily_prices/market_watch بازنویسی می‌کند و هر دو پنجره
# «نشست‌هایِ پیشین» را می‌خوانند.
#
# چرا جدول و نه کشِ pandas: get_db() هر درخواست اتصالِ تازه‌ای می‌سازد، پس
# جدولِ موقتِ آن اتصال با بازسازیِ بعدی زنده نمی‌ماند.
#
# چرا بی‌اعتباری با «شمارش» درست است: تنها چیزی که پنجره را تغییر می‌دهد
# ورودِ ردیفِ *قدیمی* است — انتشارِ ردیفِ قیمتِ دیروز (price_history)،
# نهایهٔ نشستِ قبلی (daily_prices)، یا سینکِ [ih] (tape_history). هر سه
# شمارششان تکان می‌خورد. MAX(rowid) رویِ daily_prices عمداً در کلید نیست:
# تیک با INSERT OR REPLACE ردیفِ امروز را جابه‌جا می‌کند و کلید را هر ۵ ثانیه
# عوض می‌کرد، یعنی کش بی‌اثر. ردیفِ امروز درِ پنجره هم نیست (d_even < iso).
_HIST_V_SQL = """
WITH iso AS (SELECT MAX(d_even) AS d FROM market_watch),
-- `spine` فهرستِ ۶۰ نشستِ آخرِ بازار است و تنها کارش بستنِ *سقفِ*
            -- پنجرۀِ ستون‌هایِ نمایش است. درِ خودِ TSETMC آرایۀ [ih] برایِ *هر*
            -- نشستِ تقویمی ردیف دارد و نشستِ بی‌معامله volume=0 و
            -- PriceMin=PriceMax=0 می‌گیرد؛ بانکِ ردیف‌محورِ ما آن ردیف‌هایِ صفر
            -- را ندارد، پس پنجرۀ «سی ردیفِ آخر» برایِ نمادی که بیست روز تعطیل
            -- بوده به تیرماه می‌رسد و مبناء را شش برابرِ عددِ فایل می‌کند
            -- (۱۴۰۵-۰۷-۰۵: بيوتيكح — مرجع ۵۶٬۲۶۴، ردیف‌محور ۳۴۲٬۲۲۸). درمانش
            -- شمارشِ نشست نبود، خودِ ردیف‌هایِ صفر بود: `tape_history` پایین.
            spine AS MATERIALIZED (
                SELECT dt, ROW_NUMBER() OVER (ORDER BY dt DESC) AS srn
                FROM (SELECT date AS dt FROM price_history
                      WHERE date < (SELECT printf('%04d-%02d-%02d', d/10000,
                                                   (d/100)%100, d%100) FROM iso)
                      GROUP BY date ORDER BY date DESC LIMIT 60)
            ),
            -- پنجره از پیش بر ۶۰ نشستِ آخر بسته می‌شود؛ هیچ‌یک از
            -- مصرف‌کننده‌هایِ پایین فراتر از آن را نمی‌خواهند و بی‌این سقف
            -- همین کوئری رویِ ۵۰۲ روزنۀِ بانک هشت ثانیه طول می‌کشید.
            hist AS MATERIALIZED (
                SELECT symbol, dt,
                       MAX(high) AS high, MAX(low) AS low, MAX(volume) AS volume
                FROM (
                    SELECT i.l_val18 AS symbol, h.date AS dt,
                           h.high, h.low, h.volume
                    FROM price_history h
                    JOIN instruments i ON i.l_val18 = h.symbol
                    WHERE h.date >= (SELECT MIN(dt) FROM spine)
                      AND h.date < (SELECT printf('%04d-%02d-%02d', d/10000,
                                                  (d/100)%100, d%100) FROM iso)
                    UNION ALL
                    SELECT i.l_val18,
                           printf('%04d-%02d-%02d', d.d_even/10000,
                                  (d.d_even/100)%100, d.d_even%100),
                           d.price_max, d.price_min, d.q_tot_tran
                    FROM daily_prices d
                    JOIN instruments i ON i.ins_code = d.ins_code
                    WHERE d.d_even < (SELECT d FROM iso)
                      AND printf('%04d-%02d-%02d', d.d_even/10000,
                                 (d.d_even/100)%100, d.d_even%100)
                          >= (SELECT MIN(dt) FROM spine)
                )
                GROUP BY symbol, dt
            ),
            rk AS (
                SELECT symbol, high, low, volume,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY dt DESC) AS rn
                FROM hist
            ),
            v AS (
                SELECT symbol,
                       AVG(CASE WHEN rn <= 30 THEN volume END) AS month_avg_vol,
                       MAX(CASE WHEN rn = 1 THEN volume END) AS prev_day_vol,
                       MIN(CASE WHEN rn <= 29 AND low > 0 THEN low END) AS min30_low,
                       MAX(CASE WHEN rn <= 30 THEN high END) AS max30_high,
                       MAX(CASE WHEN rn = 1 THEN volume END) AS d1_vol
                FROM rk WHERE rn <= 60
                GROUP BY symbol
            )
SELECT * FROM v
"""

_HIST_FV_SQL = """
WITH -- ── پنجرۀ [ih]، عینِ منبعِ خودِ سایت ─────────────────────────────
            -- `tape_history` را سینک از `GetClosingPriceDailyAllInst` می‌سازد —
            -- همان درخواستی که فیلترنویسِ tsetmc.com آرایۀ [ih] را از آن می‌سازد:
            -- شصت نشستِ آخرِ **هر نماد**، با ردیفِ صفر برایِ نشستِ بی‌معامله.
            -- بنابراین `srn` (جایگاهِ ردیف درِ آرایۀِ خودِ نماد) دقیقاً همان [k]ِ
            -- فایل است و `[ih][k] ↔ srn = k+1` بی‌هیچ تقریبی برقرار است.
            -- پیش از این جدول، پنجره از ردیف‌هایِ معامله‌شدهٔ بانک ساخته می‌شد و
            -- عمرِ نماد را با شمارِ ردیفِ او می‌شمرد؛ نمادِ کهنۀِ کم‌معامله (خگلپا:
            -- ۶۰ نشستِ سایت، ۱۸ ردیفِ بانک) پشتِ درِ «کمتر از ۳۰ نشست» می‌ماند و
            -- دو فیلترِ حجمی بی‌دلیل خاموش می‌شد.
            th AS MATERIALIZED (
                SELECT ins_code,
                       ROW_NUMBER() OVER (PARTITION BY ins_code ORDER BY d_even DESC) AS srn,
                       price_min, price_max, q_tot_tran5j AS volume
                FROM tape_history
            ),
            fv AS (
                SELECT ins_code,
                       -- Σ[ih][0..29].QTotTran5J — نشستِ بی‌معامله صفر دارد و
                       -- صفر درِ SUM همان چیزی است که سایت می‌بیند.
                       SUM(CASE WHEN srn <= 30 THEN volume END) AS prior30_vol,
                       -- عمرِ نماد از دیدِ سایت. فایل [ih][29] و [ih][59] را صریح
                       -- می‌خواهد؛ اگر آرایه آن‌قدر ردیف نداشته باشد خودِ
                       -- ExecFilter استثنا می‌دهد و ردیف بیرون می‌افتد — پس
                       -- «کم از سی» یعنی «نسنج»، نه «بر تعدادِ موجود تقسیم کن».
                       MAX(srn) AS hist_sessions,
                       -- کمینۀ [ih][0..28].PriceMin. نشستی که PriceMin=0 دارد
                       -- (بی‌معامله) کمینه را صفر می‌کند و `MinPriceOfMonth() != 0`
                       -- درِ فایل ردیف را می‌اندازد (نفيس2 و رشدي كيان2 همین‌جا).
                       CASE WHEN COUNT(CASE WHEN srn <= 29 THEN 1 END) < 29 THEN 0
                            ELSE MIN(CASE WHEN srn <= 29 THEN price_min END) END AS min_low_29,
                       -- پلکانِ هشت‌نقطه‌ای: [ih][k].PriceMax = نشستِ (k+1)امِ آخر
                       MAX(CASE WHEN srn = 3  THEN price_max END) AS h2_max,
                       MAX(CASE WHEN srn = 6  THEN price_max END) AS h5_max,
                       MAX(CASE WHEN srn = 10 THEN price_max END) AS h9_max,
                       MAX(CASE WHEN srn = 20 THEN price_max END) AS h19_max,
                       MAX(CASE WHEN srn = 30 THEN price_max END) AS h29_max,
                       MAX(CASE WHEN srn = 40 THEN price_max END) AS h39_max,
                       MAX(CASE WHEN srn = 50 THEN price_max END) AS h49_max,
                       MAX(CASE WHEN srn = 60 THEN price_max END) AS h59_max
                FROM th WHERE srn <= 60
                GROUP BY ins_code
            )
SELECT * FROM fv
"""

_HIST_LOCK = threading.Lock()

# تاریخِ نشستِ جاری به قالبِ `price_history.date`. سینکِ کندل از تابلو همین
# نشست را درِ همان جدول می‌نویسد و هر ۹۰ ثانیه بازنویسی‌اش می‌کند، پس هر اجزایِ
# امضا که این ردیف‌ها را ببیند، کش را بی‌دلیل می‌سوزاند.
_LIVE_DT = ("(SELECT printf('%04d-%02d-%02d', d/10000, (d/100)%100, d%100)"
            " FROM (SELECT MAX(d_even) AS d FROM market_watch))")


def _history_signature(conn):
    """امضایِ بی‌اعتباریِ دو پنجره — شمارشِ ردیف کافی نیست.

    سینکِ `[ih]` و نهایهٔ نشستِ قبلی می‌توانند همان ردیف‌ها را *مقدارِ تازه*
    بدهند (UPDATE و INSERT OR REPLACE رویِ کلیدِ موجود)، و در آن حالت نه
    COUNT تکان می‌خورد نه هیچ‌یکِ شمارنده‌هایِ کلِ جدول. بی‌جمعِ مقداری، پنج
    فیلترِ حجمی تا نشستِ بعدی با [ih]ِ دیروز حساب می‌کردند.
    هزینهٔ اندازه‌گیری‌شده رویِ بانکِ نصبی: price_history ۶۱٫۲ms،
    tape_history ۱۱٫۱ms، daily_prices ۵٫۰ms — در برابرِ ۱٫۵ ثانیه که هر بازسازی
    هزینه دارد.

    هر سه منبعِ ردیفِ *نشستِ جاری* را کنار می‌گذارند: `daily_prices` با
    `d_even < iso` و `price_history` با «کل منهای امروز»، چون سینکِ کندل از
    تابلو ردیفِ همین امروز را می‌نویسد و با هر تیک بازنویسی‌اش می‌کند — پیش از
    این، همان بازنویسی امضا را عوض می‌کرد و پنجره هر چند دقیقه از نو ساخته
    می‌شد (سنجشِ ۱۴۰۵-۰۷-۰۸: ۲۳ بازسازیِ ۱٫۵ ثانیه‌ای در سه ساعتِ نخستِ نشست).
    `MAX(rowid)` هم عمداً در کلید نیست: ردیفِ جدیدِ امروز آن را بالا می‌برد، و
    بازنویسیِ بی‌تغییریِ یک نشستِ پیشین (حذفِ همسان و درجِ همسان) پنجره را
    عوض نمی‌کند که ارزشِ بازسازی داشته باشد.
    """
    row = conn.execute(
        "SELECT (SELECT MAX(d_even) FROM market_watch),"
        "       (SELECT COUNT(*) FROM price_history)"
        "         - (SELECT COUNT(*) FROM price_history WHERE date = " + _LIVE_DT + "),"
        "       (SELECT COALESCE(SUM(close) + SUM(high) + SUM(low) + SUM(volume), 0)"
        "          FROM price_history)"
        "         - (SELECT COALESCE(SUM(close) + SUM(high) + SUM(low) + SUM(volume), 0)"
        "            FROM price_history WHERE date = " + _LIVE_DT + "),"
        "       (SELECT COUNT(*) FROM daily_prices"
        "         WHERE d_even < (SELECT MAX(d_even) FROM market_watch)),"
        "       (SELECT SUM(p_closing) + SUM(q_tot_tran) FROM daily_prices"
        "         WHERE d_even < (SELECT MAX(d_even) FROM market_watch)),"
        "       (SELECT COUNT(*) FROM tape_history),"
        "       (SELECT SUM(price_max) + SUM(price_min) + SUM(q_tot_tran5j) FROM tape_history)"
    ).fetchone()
    try:
        tape_ok = conn.execute(
            "SELECT COALESCE(newest_d_even, 0) FROM tape_history_state WHERE id = 1"
        ).fetchone()[0]
    except Exception:
        # بانکِ بدونِ جدولِ وضعیت (نسخهٔ قدیمیِ baseline): «همیشه بساز» بی‌خطا.
        tape_ok = -1
    return tuple(row) + (tape_ok,)


def _rebuild_history_windows(conn):
    """ساختنِ دو جدول، با درِ «صفرِ بی‌دلیل».

    جدولِ پنجره اگر بی‌دلیل صفر بسازد، جدولِ قبلی جای خود می‌ماند: پنج فیلترِ
    حجمی بی‌این ستون‌ها خاموش می‌شوند و «صفر» با «نبودنِ داده» یکی به‌نظر
    می‌رسد. ولی صفر *با دلیل* مجاز است: بانکِ تازه‌نصب که tape_history ندارد
    باید پنجرۀ [ih] خالی بدهد، نه خطا — همان چیزی که کوئریِ تکپیسّه هم
    می‌داد (LEFT JOIN رویِ fvِ خالی ⇒ ستون‌ها NULL).
    """
    for table, sql, source in (("board_hist_v", _HIST_V_SQL, "price_history"),
                               ("board_hist_fv", _HIST_FV_SQL, "tape_history")):
        n_src = conn.execute(f"SELECT COUNT(*) FROM {source}").fetchone()[0]
        tmp = table + "_new"
        conn.execute(f"DROP TABLE IF EXISTS {tmp}")
        conn.execute(f"CREATE TABLE {tmp} AS {sql}")
        n = conn.execute(f"SELECT COUNT(*) FROM {tmp}").fetchone()[0]
        if n == 0 and n_src > 0:
            conn.execute(f"DROP TABLE {tmp}")
            raise RuntimeError(f"history window {table} built zero rows "
                               f"while {source} has {n_src}")
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
    conn.commit()


def ensure_board_history(conn):
    """دو پنجره باید پیش از کوئریِ تابلو موجود و به‌روز باشند."""
    global _HIST_CACHE_KEY
    sig = _history_signature(conn)
    with _HIST_LOCK:
        have = _HIST_CACHE_KEY[0] == sig
        if have:
            try:
                n = conn.execute("SELECT COUNT(*) FROM board_hist_v").fetchone()[0]
                m = conn.execute("SELECT COUNT(*) FROM board_hist_fv").fetchone()[0]
                have = n > 0 and m > 0
            except Exception:
                have = False          # جدول نیست (بانک عوض شده) → بساز
        if have:
            return False
        t0 = time.time()
        _rebuild_history_windows(conn)
        _HIST_CACHE_KEY = (sig,)
        # سطرِ بی‌ساعت درِ لاگِ نصبی قابلِ زمان‌بندی نیست و بی‌آن نمی‌شد فهمید
        # کش چند بار درِ نشست می‌سوزد (قیدِ v1.0.55: هر سطر با ساعت شروع شود).
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [market] history windows "
              f"rebuilt in {time.time() - t0:.2f}s (sig={sig})")
        return True


_HIST_CACHE_KEY = (None,)


# ════════════════════════════════════════════════════════════════════════════
# لایۀ «حالتِ داغ» — SQLite بیرون از مسیرِ خواندنِ زنده (کار #73)
# ════════════════════════════════════════════════════════════════════════════
# اندازه‌گیری ۱۴۰۵-۰۷-۱۱ رویِ کپیِ بانکِ کاری (_audit/payload_probe.py):
#   بازسازیِ کامل ۳۸۱–۳۹۵ms = ۹۹ms کوئریِ بی‌اعتباریِ پنجره‌ها
#                    + ۹۵ms کوئریِ تابلو + ~۱۵۰ms مشتقات + ۳۵ms to_dict + ۱۲ms JSON
# و هر پنج ثانیه یک‌بار، حتی وقتی هیچ عددی عوض نشده بود. دو تا از آن چهار
# مرحله فقط «خواندنِ بانک» بودند؛ حال آنکه تنها نویسدۀ درونِ نشست خودِ تیک است
# و خودش می‌داند چه چیزی نوشته. پس:
#   * بدنهٔ خامِ تابلو (joinِ ایستا) در RAM نگه داشته می‌شود و فقط وقتی
#     سینکِ کامل/پنجره‌ها/تاریخِ نشست عوض شده از SQLite خوانده می‌شود؛
#   * ستون‌هایِ زنده رویِ همان قاب از `market_state` می‌نشینند — همان
#     مقدارهایی که رویِ دیسک رفته‌اند، پس RAM هیچ‌وقت جلوتر از بانک نیست؛
#   * متای «زمان تابلو» از ضربانِ خودِ سیکل می‌آید، نه از یک کوئری.
# مسیرِ SQLite دست‌نخورده می‌ماند و گاردِ `dev/market_hot_state_v1077.py`
# بدنۀ هر دو مسیر را ستون‌به‌ستون می‌سنجد.
_STATIC_LOCK = threading.Lock()
# {"key": (sync_count, session_day, static_rev, hist_key), "df": قابِ ایستا}
_STATIC_FRAME: dict = {"key": None, "df": None}
# کوئریِ امضا ~۹۹ms است؛ بی‌از‌نو‌سازیِ پنجره‌ها این هزینه در هر بازسازیِ
# پنج‌ثانیه‌ای صرفِ هیچ می‌شود. سقفِ زمانیِ اطمینان (ثانیه): اگر نویسنده‌ای
# شمارنده را بالا نبرد، حداکثر یک‌دقیقه بعد خودمان بانک را می‌بینیم.
_HIST_CHECK_S = 60.0
_HIST_CHECKED_AT = 0.0

# ستون‌هایِ تابلو که «همین نشست» را از market_watch می‌گیرند و تیکِ زنده‌شان را
# عوض می‌کند. کلید = نامِ ستون درِ قاب، مقدار = نامِ ستون درِ `MW_COLS`.
_LIVE_FROM_WATCH = {
    "d_even": "d_even", "p_closing": "p_closing", "p_last": "p_last",
    "q_tot_tran": "q_tot_tran", "q_tot_cap": "q_tot_cap", "z_tot_tran": "z_tot_tran",
    "price_change": "price_change", "price_yesterday": "price_yesterday",
    "pe": "pe", "eps": "eps", "p_max": "price_max", "p_min": "price_min",
    "tmin": "allowed_min", "tmax": "allowed_max",
    "buy_q_vol": "buy_q_vol", "buy_q_val": "buy_q_val", "buy_q_cnt": "buy_q_cnt",
    "sell_q_vol": "sell_q_vol", "sell_q_val": "sell_q_val", "sell_q_cnt": "sell_q_cnt",
    "buy_q1_vol": "buy_q1_vol", "buy_q1_px": "buy_q1_px", "buy_q1_cnt": "buy_q1_cnt",
    "sell_q1_vol": "sell_q1_vol", "sell_q1_px": "sell_q1_px",
}


def _static_key():
    return (market_state.sync_count(), market_state.session_day(),
            market_state.static_rev())


def _reset_board_cache() -> None:
    """همهٔ قاب‌هایِ RAM را بی‌اعتبار می‌کند — درِ بوت، پایانِ سینک، و تست.

    سه چیز جدا سوختنی است: قابِ ایستا، کلیدِ پنجره‌ها (که `_HIST_CACHE_KEY`
    نگه می‌دارد) و ویرایشِ قاب. اگر فقط بدنۀ /api/market بسوزد و قابِ ایستا
    بماند، بازسازیِ بعدی دلتایِ *همان قابِ کهنه* را می‌گذارد و عددِ یک نشستِ
    پیشین زیرِ تاریخِ جدید می‌نشیند.
    """
    global _FRAME_REV, _HIST_CHECKED_AT
    with _STATIC_LOCK:
        _STATIC_FRAME["df"] = None
        _STATIC_FRAME["key"] = None
        _HIST_CHECKED_AT = 0.0
    _FRAME_REV = market_state.revision()


def _board_query_frame(conn):
    """قابِ ایستایِ تابلو از SQLite، ایندکس‌شده بر `ins_code`.

    ستون‌هایِ زنده هم همین‌جا از بانک می‌آیند (تازۀ آخرین نوشتن) و بعد رویِ
    همان‌ها overlay می‌نشیند؛ پس «قابِ ایستا» دقیقاً همان چیزی است که کوئریِ
    تک‌پیسّهٔ پیش می‌داد.
    """
    global _HIST_CHECKED_AT
    ensure_board_history(conn)
    _HIST_CHECKED_AT = time.time()
    df = pd.read_sql_query(_BOARD_SQL, conn)
    df = df.drop_duplicates(subset="ins_code", keep="first").set_index("ins_code")
    last_deven = df["d_even"].max() if len(df) else None
    df["is_live"] = (df["d_even"] == last_deven) if last_deven is not None else True
    with _STATIC_LOCK:
        _STATIC_FRAME["df"] = df
        _STATIC_FRAME["key"] = _static_key() + (_HIST_CACHE_KEY,)
    return df


def _live_overlay(df, codes):
    """ستون‌هایِ زندۀ `codes` را از حالتِ داغ رویِ کپیِ قاب می‌گذارد.

    `codes` = هرچه از آخرینِ ساختنِ قاب نوشته شده. ردیفِ کامل از `_FULL`
    می‌آید و patch (نوشتنِ پس از بستن که صف‌ها را نمی‌نویسد) رویِ همان می‌نشیند
    — همان تفکیکی که درِ `market_state.commit` بین INSERT و UPDATE بود، پس
    تابلوی RAM دقیقاً محتوایِ market_watch را می‌بیند.
    """
    if not codes:
        return df
    import test_tsetmc as _T
    idx = [_T.MW_COLS.index(name) for name in _LIVE_FROM_WATCH.values()]
    live_cols = list(_LIVE_FROM_WATCH)
    dfcols = [c for c in live_cols if c in df.index or c in df.columns]
    dfcols = [c for c in dfcols if c in df.columns]
    full, patch = market_state.live_rows(codes)
    pos = df.index
    if full:
        rows, kept = [], []
        for code, r in full.items():
            if code not in pos:
                continue
            rows.append([r[i] if i < len(r) else None for i in idx])
            kept.append(code)
        if rows:
            df.update(pd.DataFrame(rows, index=kept, columns=live_cols)[dfcols])
    if patch:
        rows, kept, names = [], [], []
        for code, p in patch.items():
            if code not in pos or code in kept:
                continue
            rows.append([p.get(_LIVE_FROM_WATCH[c]) for c in live_cols])
            kept.append(code)
        if rows:
            pf = pd.DataFrame(rows, index=kept, columns=live_cols)
            pf = pf[[c for c in dfcols if pf[c].notna().any()]]
            df.update(pf)
    return df


def _board_frame(conn, frame_rev):
    """قابِ کاریِ این بازسازی: کشِ ایستا + دلتایِ زنده، یا SQLite اگر کش نیست.

    تنها شرطِ خواندنِ SQLite تغییرِ لایۀ ایستاست (سینکِ کامل، روزِ نشست،
    شمارندۀ ایستا، یا پنجره‌هایِ تاریخ) و یکِ سقفِ زمانیِ اطمینان برایِ
    نویسدۀ ناشناخته. بی‌آن‌ها کوئریِ تابلو و کوئریِ امضا هر دو رد می‌شوند —
    یعنی صفرِ SQLite در مسیرِ زنده.
    """
    global _FRAME_REV
    key = _static_key() + (_HIST_CACHE_KEY,)
    with _STATIC_LOCK:
        cached = _STATIC_FRAME["df"]
        same = _STATIC_FRAME["key"] == key and cached is not None
    if same and (time.time() - _HIST_CHECKED_AT) < _HIST_CHECK_S:
        df = cached.copy()
    else:
        df = _board_query_frame(conn)
        frame_rev = _FRAME_REV = market_state.revision()
    df = _live_overlay(df, market_state.overlay_codes(frame_rev))
    return df, frame_rev



_FRAME_REV = 0


# ════════════════════════════════════════════════════════════════════════════
# بدنۀ کوچک‌تر — و آینه‌ای که دلتا از آن می‌خواند
# ════════════════════════════════════════════════════════════════════════════
# سنجش ۱۴۰۵-۰۷-۱۱ (_audit/payload_probe.py رویِ کپیِ بانکِ کاری): بدنه ۷٫۵۵MB،
# ۷۲ کلید در هر ردیف، و ۱۵٪ مقدارها null. inventoryِ frontend/src (گزارشِ #73)
# نشان داد ۲۵ کلید هیچ‌جا خوانده نمی‌شوند؛ schemaیِ zod همه را `.nullish()`
# می‌خواهد، پس **نیامدنِ کلید بی‌خطاست** و ۴۵٪ از بدن می‌کاهد
# (۷٫۵۵MB → ۴٫۱۵MB، gzip ۹۱۳KB → ۵۶۴KB).
#
# چرا بی‌حدسِ «به‌درد نمی‌خورد» سرِ route نگه داشته می‌شوند: این ستون‌ها درِ
# بانک و درِ کوئری هستند و سازندۀ تابلو همان‌ها را می‌خواند؛ فقط سریال‌سازی
# از فرستادنِ آن‌ها دست می‌کشد. اگر روزی UI بخواهد، یک سطر از همین فهرست
# برمی‌گردد — نه یک migration.
_DROP_FIELDS = frozenset((
    "eps", "price_max", "price_min", "p_max", "p_min",          # دوباره‌نویسِ p_max/p_min
    "buy_n_vol", "sell_n_vol",                                   # صفِ حقوقی/حقیقی درِ تابلو خوانده نمی‌شود
    "buy_q_vol", "buy_q_val", "buy_q_cnt",
    "sell_q_vol", "sell_q_val", "sell_q_cnt",
    "buy_q1_px", "sell_q1_vol", "sell_q1_px",
    "prev_day_vol", "d1_vol", "max30_high",
    "tmax", "vol_trend", "sell_power_i", "suspicious_vol",       # میانگینِ ماه فرستاده می‌شود: typeِ فرانت آن را اعلام می‌کند

    "d_even", "resistance_59", "dist_min30_pct",
))


def _clean(v):
    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
        return None
    return v


def _slim_records(df):
    """ردیف‌ها بی‌کلیدهایِ بی‌خواننده و بی‌null — و `ins_code` به‌عنوان کلید."""
    out = []
    for rec in df.reset_index().to_dict(orient="records"):
        r = {}
        for k, v in rec.items():
            if k in _DROP_FIELDS:
                continue
            v = _clean(v)
            if v is None:
                continue
            r[k] = v
        out.append(r)
    return out


def _board_meta(conn):
    """تاریخ/ساعتِ تابلو. درِ حالتِ داغ از ضربانِ سیکل، بی‌کوئری."""
    day = market_state.session_day()
    at = market_state.last_cycle_at()
    if day and at:
        return {"d_even": int(day), "h_even": int(market_state.max_h_even() or 0),
                "last_sync": at}
    try:
        _r = conn.execute(
            "SELECT d_even, MAX(h_even), MAX(fetched_at) FROM market_watch "
            "WHERE d_even = (SELECT MAX(d_even) FROM market_watch)").fetchone()
        if _r:
            return {"d_even": int(_r[0] or 0), "h_even": int(_r[1] or 0), "last_sync": _r[2]}
    except Exception:
        pass
    return {"d_even": None, "h_even": None, "last_sync": None}


def _encode_board(payload):
    import hashlib
    if _ORJ:
        import orjson
        body = orjson.dumps(payload)
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return body, '"' + hashlib.md5(body).hexdigest()[:16] + '"'


# آینهٔ دلتا: ردیف‌هایِ سریال‌سازی‌شدهٔ آخرینِ بازسازی، keyed بر ins_code، به‌همراه
# ویرایشی که *پیش از* ساختن خوانده شده بود. بی‌آن «rev = بعد از ساخت» می‌شد و
# نوشتن‌هایِ وسطِ ساخت از چشمِ کلاینت پنهان می‌ماند.
_DELTA_LOCK = threading.Lock()
_DELTA: dict = {"by_code": {}, "meta": {}, "counts": {}, "rev": -1, "ready": False}


def _mirror(records, meta, counts, rev):
    with _DELTA_LOCK:
        _DELTA["by_code"] = {r["ins_code"]: r for r in records if r.get("ins_code")}
        _DELTA["meta"] = meta
        _DELTA["counts"] = counts
        _DELTA["rev"] = rev
        _DELTA["ready"] = True


def _mirror_snapshot():
    with _DELTA_LOCK:
        return (dict(_DELTA["by_code"]), dict(_DELTA["meta"]), dict(_DELTA["counts"]),
                _DELTA["rev"], _DELTA["ready"])


def _delta_clear():
    with _DELTA_LOCK:
        _DELTA["by_code"] = {}
        _DELTA["ready"] = False
        _DELTA["rev"] = -1


# کوئریِ تابلو — دو پنجره، دو مصرف — و این تفکیک قبلاً یکی از منبع‌هایِ اختلاف بود:
#   tape_history — آرایۀِ [ih] عینِ سایت. درِ پنج فیلترِ فایل
#       (مبناءِ حجم، کفِ بیست‌ونُه نشست، پلکانِ مقاومت) از این است.
#   hist (اتحادِ price_history و daily_prices) — فقط ستون‌هایِ *نمایش*
#       (میانگین ماه، حجمِ دیروز، کمینه/بیشینۀِ ۳۰ روزه). این ردیف‌ها
#       روزهایی‌اند که نماد *معامله شده*:
#         price_history — ردیف‌هایِ *منتشرشده* (GetClosingPriceDailyListCSV
#             و بک‌فیلِ GetInstrmentsHistoryInDay).
#         daily_prices  — اسنپ‌شاتِ زندۀِ تابلو، برایِ روزهایی که هنوز
#             ردیفِ انتشاریافته نداریم؛ «امروزِ بی‌نهایه» را عمداً بیرون
#             می‌گذارد، چون ستونِ نمایش هم نباید نیم‌بها از حجمِ
#             نشستِ تمام‌نشده بسازد (اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵: خكمك با
#             شمارفتنِ امروز نسبتِ ۰٫۹۹ می‌شد و مردود، مرجعِ TSETMC ۱٫۰۶).
# روزهایِ همپوشان با GROUP BY رویِ (نماد،تاریخ) یک‌بار شمرده می‌شوند.
_BOARD_SQL = """
            WITH iso AS (
                SELECT d,
                       printf('%04d-%02d-%02d', d/10000, (d/100)%100, d%100) AS dt
                FROM (SELECT MAX(d_even) AS d FROM market_watch)
            ),
            -- `v` حالا یک جدولِ materialized است؛ متنِ پنجره دست‌نخورده به
--        `board_hist_v` منتقل شده (refresh در @ensure_board_history).
            v AS MATERIALIZED (SELECT * FROM board_hist_v),
            -- `fv` هم مثلِ `v`: پنجرۀ [ih] یک‌بار در روز ساخته می‌شود.
            fv AS MATERIALIZED (SELECT * FROM board_hist_fv),
            ctm AS (
                SELECT ins_code, MAX(d_even) AS d FROM client_type
                WHERE d_even <= (SELECT d FROM iso)
                GROUP BY ins_code
            )
            SELECT m.ins_code, i.l_val18 AS symbol, i.l_val30 AS name,
                   COALESCE(NULLIF(i.sector_name, ''), 'سایر') AS sector_name,
                   m.p_closing, m.p_last, m.q_tot_tran, m.z_tot_tran, m.price_yesterday,
                   m.q_tot_cap, m.price_change, m.d_even,
                   m.pe, m.eps, b.board AS board, m.price_max AS p_max, m.price_min AS p_min,
                   COALESCE(ct.buy_i_vol, 0)  AS buy_i_vol,
                   COALESCE(ct.buy_n_vol, 0)  AS buy_n_vol,
                   COALESCE(ct.sell_i_vol, 0) AS sell_i_vol,
                   COALESCE(ct.sell_n_vol, 0) AS sell_n_vol,
                   COALESCE(ct.buy_count_i, 0)  AS buy_count_i,
                   COALESCE(ct.sell_count_i, 0) AS sell_count_i,
                   -- تابلویِ ۵ مظنه: در بانک هست ولی هرگز به UI نمی‌رسید، پس
                   -- ویجتِ «عمق بازار» چاره‌ای نداشت جز ساختنِ عدد.
                   m.buy_q_vol, m.buy_q_val, m.buy_q_cnt,
                   m.sell_q_vol, m.sell_q_val, m.sell_q_cnt,
                   m.buy_q1_vol, m.buy_q1_px, m.sell_q1_vol, m.sell_q1_px,
                   m.buy_q1_cnt,
                   -- (tmin)/(tmax) درِ فیلترنویس = آستانۀ مجاز، نه کفِ نشست؛
                   -- خودِ ExecFilter آن‌ها را به element.pMin/pMax بدل می‌کند.
                   m.allowed_min AS tmin, m.allowed_max AS tmax,
                   v.month_avg_vol, v.prev_day_vol,
                   v.min30_low, v.max30_high, v.d1_vol,
                   fv.h2_max, fv.h5_max, fv.h9_max, fv.h19_max, fv.h29_max,
                   fv.h39_max, fv.h49_max, fv.h59_max,
                   fv.prior30_vol, fv.min_low_29, fv.hist_sessions
            FROM market_watch m
            JOIN instruments i ON i.ins_code = m.ins_code
            LEFT JOIN boards b ON b.ins_code = m.ins_code
            LEFT JOIN ctm ON ctm.ins_code = m.ins_code
            LEFT JOIN client_type ct ON ct.ins_code = m.ins_code AND ct.d_even = ctm.d
            LEFT JOIN v ON v.symbol = i.l_val18
            LEFT JOIN fv ON fv.ins_code = m.ins_code
            WHERE m.ins_code IS NOT NULL
            ORDER BY m.d_even DESC, i.l_val18 ASC
"""


def _build_market_response(request: Request):
    """تابلو. قابِ ایستا از RAM، دلتا از حالتِ داغ؛ SQLite فقط درِ بی‌اعتباری."""
    now = time.time()
    # ویرایش **پیش از** ساختن خوانده می‌شود: نوشتن‌هایِ وسطِ این ۳۰۰ میلی‌ثانیه
    # در بدنۀ پیش رو نیستند، پس آینه باید بگوید «این بدنۀ rev است»، نه revِ
    # لحظۀ آخر — وگرنه دلتا همان ردیف‌هایِ تازه را «بی‌تغییری» گزارش می‌کند.
    built_rev = market_state.revision()
    conn = get_db()
    try:
        df, frame_rev = _board_frame(conn, _FRAME_REV)

        # ---------- cast حجم به float؛ NULL/NaN → 0 ----------
        df["tvol"] = pd.to_numeric(df["q_tot_tran"], errors="coerce").astype(float).fillna(0.0)
        df["month_avg_vol"] = pd.to_numeric(df["month_avg_vol"], errors="coerce").astype(float)
        df["prev_day_vol"] = pd.to_numeric(df["prev_day_vol"], errors="coerce").astype(float)

        # ---------- درصد تغییر ----------
        # TSETMC برای نمادهای حق‌تقدم/اختیار (پیشوند ض/ط) و نمادهای تازه‌لیست‌شده
        # price_yesterday را برابر ۱ می‌فرستد — این یک مقدار نگهبان است، نه
        # قیمت واقعیِ دیروز. تقسیم بر ۱ درصد‌های بی‌معنی مثل +۴٬۱۹۵٬۶۰۰٪
        # می‌سازد (تأییدشده: این نمادها هیچ ردیفی در price_history ندارند).
        # شرطِ قدیمیِ «> ۰» این حالت را نمی‌گرفت.
        _py = pd.to_numeric(df["price_yesterday"], errors="coerce")
        # قیمت دیروزِ معتبر: بزرگ‌تر از ۱ است (کفِ قانونیِ تابلو) و منطقی‌تر
        # از قیمت پایانیِ امروز — اگر قیمت دیروز نامعتبر باشد اما خودِ
        # price_change معتبر باشد، از همان نسبتِ رسمیِ TSETMC استفاده می‌کنیم.
        _pc = pd.to_numeric(df["p_closing"], errors="coerce")
        _chg = pd.to_numeric(df["price_change"], errors="coerce")
        py_ok = _py.where(_py > 1.0)
        pct_from_close = ((_pc - py_ok) / py_ok * 100).round(2)
        # fallback: price_change / price_yesterday (نسبت رسمی TSETMC)
        pct_from_change = (_chg / py_ok * 100).round(2)
        df["percent_change"] = pct_from_close.where(pct_from_close.notna(), pct_from_change)
        # هرچه هنوز NaN ماند یعنی قیمت دیروزِ معتبری وجود ندارد → نمایش نمی‌شود
        df["percent_change"] = df["percent_change"].where(df["percent_change"].notna(), None)
        # دفاعِ نهایی: درصدِ غیرممکن (بزرگ‌تر از بازهٔ مجازِ تابلو) را مخفی کن
        _pct = pd.to_numeric(df["percent_change"], errors="coerce")
        df["percent_change"] = np.where(_pct.abs() <= 100.0, df["percent_change"], None)

        # «٪ آخرین» (آخرین به نسبتِ دیروز) — تریدرزآرنا و TSETMC این را کنارِ
        # «٪ پایانی» می‌گذارند؛ الگویِ ساعت و جت با همین عدد معنا می‌شوند.
        _pl = pd.to_numeric(df["p_last"], errors="coerce")
        pct_last = ((_pl - py_ok) / py_ok * 100).round(2)
        pct_last = pct_last.where(pct_last.abs() <= 100.0)
        df["percent_last"] = pct_last.where(pct_last.notna(), None)

        _bc = pd.to_numeric(df["buy_count_i"], errors="coerce")
        _sc = pd.to_numeric(df["sell_count_i"], errors="coerce")
        # مخرجِ صفر = «هیچ معاملۀِ حقیقی در آن سمت نبوده» → عدد نیست، نه بی‌نهایت
        # و نه ۱٫۰۰ِ بی‌طرف. پیش از این fillna(1.0) همان را «قدرت خریدار ۱٫۰۰»
        # نشان می‌داد؛ یعنی برایِ نمادی که هیچ خریدارِ حقیقی‌ای نداشت، داوریِ
        # جعلیِ «متعادل». فیلترها از buyer_power_raw (همین NaNِ صادق) می‌خوانند.
        buy_per_i = df["buy_i_vol"] / _bc.where(_bc > 0)
        sell_per_i = df["sell_i_vol"] / _sc.where(_sc > 0)
        df["buyer_power"] = (buy_per_i / sell_per_i).round(2).clip(upper=10.0)
        # قدرت خالص خریدار/فروشنده (حجم به ازای هر معامله) — برای ستون مقایسهای
        df["buy_power_i"] = buy_per_i.round(0)
        df["sell_power_i"] = sell_per_i.round(0)

        # ---------- روند حجم: tvol vs آخرین روز معاملاتی (day-over-day, Null-safe) ----------
        pdv = df["prev_day_vol"].where(df["prev_day_vol"] > 0)     # <=0/NaN → NaN
        df["vol_dod"] = (df["tvol"] / pdv).round(2)                # NaN where no prev day
        df["vol_trend"] = np.where(df["vol_dod"].isna(), None,
                           np.where(df["vol_dod"] >= 1.10, "up",
                           np.where(df["vol_dod"] <= 0.90, "down", "flat")))

        # ============================================================
        # پنج فیلترِ تابلو — عینِ فرمول‌هایِ جزوه، در tape_flags.apply_tape_flags
        # (اینجا دیگر چیزی محاسبه نمی‌شود؛ تنها نتیجه رویِ ستون‌هایِ نمایشی
        #  اعمال می‌گردد تا تابلو و نشان‌هایِ ستونی یک عدد ببینند.)
        # متغیرها (از ExecFilterِ خودِ tsetmc.com): pl=pdv، pc=pcl، plp=درصدِ آخرین
        # نسبت به دیروز، tmin=آستانۀ مجاز پایین (allowed_min)، tvol/qtj=حجم،
        # tno/ztt=تعداد، zd1=تعدادِ سفارشِ سطرِ اولِ خرید، qd1=حجمِ همان سطر،
        # [ih][k]=kِمین روزنۀِ منتشرشده (نه امروز، تا پیش از نهایه).
        # ============================================================
        flags = apply_tape_flags(df)
        df["vol_ratio"] = flags["vol_ratio"].round(1)      # نمایش با همان دقتِ قبل
        df["vol_ratio_file"] = flags["vol_ratio_file"].round(2)  # قیدِ حجمیِ پنج فیلتر (Σ[ih][0..29]÷۳۰)
        df["buyer_power_raw"] = flags["buyer_power_raw"]   # بی‌سقف، برای فیلترِ جت
        df["resistance_59"] = flags["resistance_59"]
        df["dist_min30_pct"] = flags["dist_min30_pct"]
        df["suspicious_vol"] = flags["f_susp"]             # «ستونِ مشکوک» همان حجمِ ۳× است
        for _k in ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh"):
            df[_k] = flags[_k]

        # Fail-safe: NaN/Inf → 0 (JSON safety)؛ سپس NaN حجمی → واقعاً null
        # (تا sort و نمایش «حجم مشکوک» درست بماند).
        # نکته: ستونهای حجمی از نسخهٔ خام بازیابی میشوند چون fillna(0)
        # روی object-column (vol_trend) None را به 0 تبدیل میکند.
        #
        # «سقفِ ۵۹ نشستِ پیش» اگر موجود نباشد باید null بماند تا فرانت‌اند آن را
        # «صفر» یا «حدس» نخواند. (پلکانِ خالی درِ خودِ فیلتر صفر می‌شود، ولی
        # `hist_sessions` می‌گوید نماد آن‌قدر سابقه دارد یا نه — همان تفکیکی که
        # ExecFilter با try/catch می‌کند.)
        # `percent_change` هم همین‌جاست: سایت برایِ نمادهایِ اختیار و حق‌تقدم
        # «قیمتِ دیروز» را ۱ می‌فرستد (نگهبان)، پس درصد هیچ‌وقت سنجیده نمی‌شود؛
        # با fillna(0) آن ردیف‌ها «تغییر٪ ۰٫۰۰» می‌گرفتند، یعنی «بدونِ تغییر»
        # درحالی‌که چیزی اندازه گرفته نشده بود (شاهدِ ۱۴۰۵-۰۷-۰۷: ۸۹۳ ردیف).
        _KEEP_NULL = ("vol_ratio", "vol_dod", "vol_trend", "dist_min30_pct",
                      "month_avg_vol", "prev_day_vol", "d1_vol",
                      "prior30_vol", "min_low_29", "percent_last", "percent_change",
                      "vol_ratio_file", "hist_sessions", "tmin", "tmax", "buy_q1_cnt",
                      "buyer_power", "buy_power_i", "sell_power_i",
                      "buyer_power_raw", "resistance_59",
                      "h2_max", "h5_max", "h9_max", "h19_max",
                      "h29_max", "h39_max", "h49_max", "h59_max",
                      "min30_low", "max30_high")
        _kept = {k: df[k].copy() for k in _KEEP_NULL if k in df.columns}
        _filters_tbl = {k: df[k].copy() for k in ("f_roobi", "f_susp", "f_clock", "f_jet", "f_noqteh")}
        df = df.replace([np.inf, -np.inf], 0).fillna(0)
        for _k, _s in _kept.items():
            df[_k] = _s          # NaN باقی می‌ماند → _clean → null
        for _k, _s in _filters_tbl.items():
            df[_k] = _s.fillna(False)

        records = _slim_records(df)
        counts = {"count": len(df),
                  "live_count": int(df["is_live"].sum()) if "is_live" in df.columns else len(df),
                  "fossil_count": int((~df["is_live"]).sum()) if "is_live" in df.columns else 0}
        meta = _board_meta(conn)
        payload = dict(status="success", rev=built_rev, data=records,
                   meta=meta, **counts)
        body, etag = _encode_board(payload)
        # آینهٔ دلتا: همان ردیف‌هایِ سریال‌سازی‌شده، keyed بر ins_code، به‌همراه
        # ویرایشی که برایِ آن ساخته شده‌اند. `/api/market/delta` از همین آینه
        # می‌فهمد «از ویرایشِ N تا چه نمادهایی تکان خورده» و همان ردیف‌ها را
        # می‌فرستد — بی‌JSONِ ۴ مگابایتیِ هر پنج ثانیه.
        _mirror(records, meta, counts, built_rev)
        _market_store(body, etag, now)
        # #175: دوازدهمِ ثانیه یک‌بار TTL می‌پایان و بدنه از نو ساخته می‌شود، ولی
        # سینک هر ~۳۰ ثانیه یک‌بار چیزی عوض می‌کند — یعنی بیشترِ آن بدنه‌ها
        # عیناً همان چیزی‌اند که کلاینت دارد. etagِ تازه را با If-None-Match
        # بسنج؛ برابر بود صفر بایت برگردان (۷٫۳ مگابایتِ decompress + JSON.parse
        # + zod رویِ دستگاهِ کاربر، و ۹۷۶ کیلوبایتِ gzip رویِ سیم، با این دو خط
        # حذف می‌شود). سنجش رویِ md5ِ خودِ بدنه است، نه زمانِ کش — پس «۳۰۴» هیچ‌وقت
        # دادهٔ کهنه نمی‌تواند باشد.
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "X-Cache": "MISS-304"})
        return Response(content=body, media_type="application/json",
                        headers={"Cache-Control": "max-age=15", "X-Cache": "MISS", "ETag": etag})
    finally:
        conn.close()

@router.get("/api/market/delta")
def get_market_delta(since: int = -1):
    """فقط ردیف‌هایی که از ویرایشِ `since` تکان خورده‌اند.

    پولینگِ پنج‌ثانیه‌ایِ تابلو رویِ localhost هم هزینه دارد: بدنهٔ کامل
    ۴٫۱۵ مگابایت (۵۶۴KB gzip) است و رویِ دستگاهِ کاربر decompress + JSON.parse +
    zodِ ۵٬۴۵۱ شیء را می‌خواهد. حال آنکه در یک سیکلِ پنج‌ثانیه‌ای معمولاً چند
    صد نماد عوض می‌شود، نه پنج‌هزار.

    سه پاسخ ممکن است و هیچ‌کدام «حدسِ ناقص» نیست:
      • `unchanged` — آینه همان ویرایشِ کلاینت است ⇒ صفر ردیف، صفر parse.
      • `delta`     — ردیف‌هایِ تغییریافته در (since, mirror_rev].
      • `full`      — ژورنال به `since` نمی‌رسد، یا آینه از کلاینت عقب‌تر است،
                      یا ردیفی در آینه نیست ⇒ کلاینت `/api/market` کامل را
                      می‌گیرد. هیچ‌وقت دلتایِ نصفه از نبودِ داده ساخته نمی‌شود.

    آینه فقط تا `mirror_rev` را دیده است؛ نوشتن‌هایِ بعد از آن در بدنۀ فعلی
    نیستند، پس بازهٔ پاسخ `since < r <= mirror_rev` است و اگر revision جلو
    افتاده باشد، rebuildِ پس‌زمینه را خودمان محرک می‌کنیم.
    """
    by_code, meta, counts, mirror_rev, ready = _mirror_snapshot()
    cur = market_state.revision()
    if not ready or mirror_rev < 0:
        _kick_market_rebuild()
        return _ORJ_JSON({"status": "full", "rev": cur, "reason": "no-cache"})
    if since == mirror_rev and since == cur:
        return _ORJ_JSON({"status": "unchanged", "rev": mirror_rev, "meta": meta, **counts})
    if since > mirror_rev or not (0 <= since <= cur):
        return _ORJ_JSON({"status": "full", "rev": mirror_rev, "reason": "stale-client"})
    codes = market_state.codes_between(since, mirror_rev)
    if codes is None:
        if cur > mirror_rev:
            _kick_market_rebuild()
        return _ORJ_JSON({"status": "full", "rev": mirror_rev, "reason": "journal-gap"})
    rows = [by_code[c] for c in codes if c in by_code]
    if len(rows) != len(codes):
        # نمادی که در آینه نیست (از تابلو رفته یا تازه آمده): دلتا صادق نیست.
        return _ORJ_JSON({"status": "full", "rev": mirror_rev, "reason": "missing-rows"})
    if cur > mirror_rev:
        _kick_market_rebuild()
    return _ORJ_JSON({"status": "delta", "rev": mirror_rev, "rows": rows,
                      "meta": meta, **counts})


def _ORJ_JSON(payload) -> Response:
    """JSONِ فشرده‌تر از defaultِ FastAPI؛ همان orjsonِ مسیرِ اصلی."""
    body, _ = _encode_board(payload)
    return Response(content=body, media_type="application/json",
                    headers={"Cache-Control": "no-store"})


@router.get("/api/live-stats")
def live_stats():
    """شمارنده‌هایِ حالتِ داغ — برایِ اینکه «چه‌قدر واقعاً عوض شد» دیده شود.

    بی‌این endpoint ادعاهایِ «دلتا نوشتن‌ها را یک‌دهم کرد» فقط حرف می‌ماند؛
    چرخۀ benchmarkِ کار #73 همین اعداد را قبل/بعد مقابله می‌کند.
    """
    from .market import _STATIC_FRAME
    s = market_state.stats()
    s["board_cache"] = bool(_STATIC_FRAME.get("df") is not None)
    s["board_rows"] = int(len(_STATIC_FRAME["df"])) if _STATIC_FRAME.get("df") is not None else 0
    s["delta_mirror_rows"] = len(_mirror_snapshot()[0])
    s["subscribed"] = sorted(market_state.subscriptions())
    return {"status": "success", "data": s}


@router.post("/api/orderbook/watch")
def orderbook_watch(payload: dict = None):
    """«این پنجره عمقِ این نماد را نگاه می‌کند» — اشتراکِ حالتِ داغ.

    عمقِ پنج‌سطحی هزینهٔ *شبکه* جدا ندارد: blDs در همان یک درخواستِ تابلو
    (withBestLimits=true) می‌آید. چیزی که اشتراک می‌سنجد دو چیز است: ریتمِ
    پولینگِ سایدبار (که تا پیش از این بی‌اعتبار به نشست، هر ۳۰ ثانیه می‌زد)
    و هر کارِ افزونۀ درون‌جلسه‌ای که در آینده فقط برایِ نمادهایِ دیده‌شده
    انجام می‌شود. نوشتنِ `order_book` دست‌نخورده مانده: حذفِ ردیف‌هایِ
    غیرمشترک یعنی نمادی که کاربر دیر باز می‌کند «بی‌داده» ببیند — آن تصمیمِ
    مالک است، نه حدسِ من.
    """
    code = str((payload or {}).get("ins_code") or "").strip()
    if not code:
        return {"status": "error", "message": "ins_code لازم است"}
    market_state.subscribe_orderbook(code)
    return {"status": "success", "subscribed": sorted(market_state.subscriptions())}


@router.get("/api/fts")
def get_fts_scan(limit: int = 0):
    """اسکن کامل ۵ شاخص FTS روی همهٔ نمادهای FS-دار — مرتب بر اساس score."""
    try:
        import fts_engine
        _cfg = load_fts_config()
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            results = fts_engine.scan_all(conn, limit=limit, cfg=_cfg)
        finally:
            conn.close()
        return {"status": "success", "count": len(results), "data": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/fts/config")
def get_fts_config():
    return {"status": "success", "config": load_fts_config()}


@router.get("/api/price-basis")
def get_price_basis():
    """مبنایِ قیمتِ منتخبِ کاربر — سمتِ سرور، نه فرانت (کارِ #73 قدمِ ۳).

    تنها نقطۀ خواندن این مقدار `price_basis.py` است و تنها نقطۀ نوشتنش همین endpoint؛
    چارت/غربگر/کارتِ FTS همه از یکِ تصمیم تغذیه می‌شوند تا عددِ چارت با عددِ غربگر
    نجنگد (شکلِ نقضِ آن درِ #66 بود).
    """
    import price_basis
    return {"status": "success", **price_basis.describe()}


@router.post("/api/price-basis")
def set_price_basis(payload: dict = None):
    """`{"basis": "last"}` یا `{"basis": "closing"}`؛ هر چیزِ دیگر مردود است.

    لنگرِ زنجیرِ تعدیل با این عوض نمی‌شود و اینجا هم تنظیم نمی‌شود: همیشه CLOSING
    (§۱-ث قرارداد؛ سنجشِ §۱-پ: بردنِ لنگر به last درِ ۹۲٪ نمادها لنگر را می‌شکند).
    """
    import price_basis
    val = (payload or {}).get("basis") or (payload or {}).get("priceBasis")
    return price_basis.set_basis(val)

@router.post("/api/fts/config")
def set_fts_config(payload: dict = None):
    """ذخیرهٔ پیش‌شرط‌های ۵ شاخص (از پنل تنظیمات کدال).

    v8: نوع‌سنجی بر پایهٔ FTS_DEFAULTS — `industry_mode` رشته است و نباید به float
    تبدیل شود؛ لیست صنایع با نام‌های جدید mandatory_sectors/free_sectors میآید و
    نام‌های قدیمی (bad_sectors/good_sectors) هم پذیرفته میشود (backward compat).

    v10: هر عددِ منفی مردود است (آستانهٔ منفی معنا ندارد و بی‌صدا «همه چیز قبول»
    می‌سازد) و `industry_mode` فقط یکی از چهار مقدارِ شناخته‌شده را می‌پذیرد.
    خطاها پیش از نوشتنِ فایل جمع میشوند و با نامِ فیلد برمی‌گردند، تا پنل
    همان فیلد را قرمز کند — نه اینکه عددِ غلط روی دیسک برود و بعداً بی‌سبب
    جدول عوض شود.
    """
    if not payload:
        return {"status": "error", "message": "بدون داده"}
    aliases = {"bad_sectors": "mandatory_sectors", "good_sectors": "free_sectors"}
    cfg = dict(FTS_DEFAULTS)
    errors = {}
    for key, v in payload.items():
        k = aliases.get(key, key)
        if k not in FTS_DEFAULTS:
            continue
        if k in FTS_LIST_KEYS:
            if isinstance(v, str):
                v = [s.strip() for s in v.replace("،", ",").split(",") if s.strip()]
            cfg[k] = [str(s).strip() for s in (v or []) if str(s).strip()]
        elif k in FTS_STR_KEYS:
            cfg[k] = str(v)
        elif isinstance(FTS_DEFAULTS[k], bool):
            cfg[k] = bool(v)
        elif k.endswith("_max") or k.endswith("_years") or k.endswith("_sessions"):
            try:
                cfg[k] = int(float(v))
            except (TypeError, ValueError):
                errors[k] = "عددِ معتبر نیست"
                continue
            if cfg[k] < 0:
                errors[k] = "مقدار منفی مجاز نیست"
        else:
            try:
                cfg[k] = float(v)
            except (TypeError, ValueError):
                errors[k] = "عددِ معتبر نیست"
                continue
            if cfg[k] < 0:
                errors[k] = "مقدار منفی مجاز نیست"
    if str(cfg.get("industry_mode") or "").strip() not in _FTS_INDUSTRY_MODES:
        errors["industry_mode"] = "حالتِ شناخته‌شده‌ای نیست"
    for k, lo, hi in (("watchlist_max", 1, 500), ("eps_years", 1, 12),
                      ("v10_eps_years", 1, 12),
                      ("suspended_max_stale_sessions", 1, 20)):
        if k in cfg and isinstance(cfg[k], int) and not (lo <= cfg[k] <= hi):
            errors[k] = "باید بین %d و %d باشد" % (lo, hi)
    if errors:
        return {"status": "error", "message": "برخی مقادیر معتبر نیستند",
                "errors": errors, "config": None}
    try:
        with open(FTS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return {"status": "success", "config": cfg}
    except Exception as e:
        return {"status": "error", "message": str(e)[:160]}

MARKET_CACHE = {}   # {"t": ts, "body": bytes, "etag": str}
MARKET_CACHE_TTL = 60.0
# این عدد دیگر «تازگی» را تعیین نمی‌کند: پایانِ هر سینک خودِ کش را از نو می‌سازد
# (warm_market_cache در api/_sync_market). اینجا فقط تورِ امنیتی است برای نوشتنِ
# بیرونِ این پروسه. اندازه‌گیری با ۲۰ و پولینگِ پنج‌ثانیه‌ای: ۹ بازسازیِ ۱.۴
# ثانیه‌ای در ۳ دقیقه = هفت‌درصدِ یک هسته، روی داده‌ای که هر ۹۰ ثانیه بیشتر عوض
# نمی‌شود. با ۶۰: سه بازسازی.
