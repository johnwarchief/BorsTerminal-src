"""Market snapshot, live FTS scan and FTS threshold config.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _count_procs, get_db
from bors_config import DB_PATH, FTS_CONFIG_PATH, FTS_DEFAULTS, FTS_LEGACY_LISTS, FTS_LEGACY_SCALARS, FTS_LIST_KEYS, FTS_STR_KEYS, MARKET_STATUS_PATH
from bors_flags import _ORJ
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


def _build_market_response(request: Request):
    import time as _t
    now = _t.time()
    conn = get_db()
    try:
        # پنجرۀ تاریخچه از **اتحادِ** دو جدول ساخته می‌شود، نه از price_history
        # به‌تنهایی. دلیلِ اندازه‌گیری‌شده: price_history فقط برایِ نمادهایی
        # نوشته می‌شود که یک‌بار در چارت باز شده باشند، و حجمِ انبوه‌اش در
        # ۱۴۰۵/۰۶/۰۱ (۲۰۲۶-۰۸-۲۳) مانده است. نتیجه پیش از این: «میانگین حجمِ
        # ۳۰ روزه» و «سقفِ دیروز» برایِ صدها نماد یک‌ماهه کهنه، و برایِ ۴٬۲۰۰
        # نماد کلاً غایب — یعنی فیلترهایِ حجمیِ تابلو رویِ دادهٔ تاریخ‌گذشته
        # یا رویِ هیچ کار می‌کردند. daily_prices هر نشستِ کاملِ بازار را دارد.
        # روزهایِ همپوشان (دو جدول همزمان یک نشست را دارند) با GROUP BY روی
        # (نماد،تاریخ) یک‌بار شمرده می‌شوند و نشستِ جاریِ تابلو بیرون می‌ماند،
        # تا rn=1 واقعاً «نشستِ پیش» باشد.
        query = """
            WITH iso AS (
                SELECT d,
                       printf('%04d-%02d-%02d', d/10000, (d/100)%100, d%100) AS dt
                FROM (SELECT MAX(d_even) AS d FROM market_watch)
            ),
            hist AS (
                SELECT symbol, dt,
                       MAX(high) AS high, MAX(low) AS low, MAX(volume) AS volume,
                       MAX(tran) AS tran
                FROM (
                    SELECT i.l_val18 AS symbol, h.date AS dt,
                           h.high, h.low, h.volume, NULL AS tran
                    FROM price_history h
                    JOIN instruments i ON i.l_val18 = h.symbol
                    WHERE h.date < (SELECT dt FROM iso)
                    UNION ALL
                    SELECT i.l_val18,
                           printf('%04d-%02d-%02d', d.d_even/10000,
                                  (d.d_even/100)%100, d.d_even%100),
                           d.price_max, d.price_min, d.q_tot_tran, d.z_tot_tran
                    FROM daily_prices d
                    JOIN instruments i ON i.ins_code = d.ins_code
                    WHERE d.d_even < (SELECT d FROM iso)
                )
                GROUP BY symbol, dt
            ),
            rk AS (
                SELECT symbol, high, low, volume, tran,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY dt DESC) AS rn
                FROM hist
            ),
            v AS (
                SELECT symbol,
                       AVG(CASE WHEN rn <= 30 THEN volume END) AS month_avg_vol,
                       MAX(CASE WHEN rn = 1 THEN volume END) AS prev_day_vol,
                       -- فیلترهای TSETMC: [ih][k].PriceMax — سقفِ تک‌روزیِ
                       -- kِمین نشستِ پیش. پلکانِ جت به [ih][2] نیاز دارد.
                       MAX(CASE WHEN rn = 1 THEN high END) AS h1_max,
                       MAX(CASE WHEN rn = 2 THEN high END) AS h2_max,
                       MAX(CASE WHEN rn = 5 THEN high END) AS h5_max,
                       MAX(CASE WHEN rn = 9 THEN high END) AS h9_max,
                       MAX(CASE WHEN rn = 19 THEN high END) AS h19_max,
                       MAX(CASE WHEN rn = 29 THEN high END) AS h29_max,
                       MAX(CASE WHEN rn = 39 THEN high END) AS h39_max,
                       MAX(CASE WHEN rn = 49 THEN high END) AS h49_max,
                       MAX(CASE WHEN rn = 59 THEN high END) AS h59_max,
                       -- کفِ ۳۰ روزهٔ جزوه: [ih][0..28].PriceMin
                       -- نشستِ بدونِ معامله high/low را صفر می‌نویسد؛ صفر در
                       -- MIN *سمّ* است (کفِ جعلیِ صفر → نقطه‌زنی رد) برعکسِ MAX
                       -- که صفر را خودکار نادیده می‌گیرد. پس هر دو کف > 0 می‌خواهند.
                       MIN(CASE WHEN rn <= 29 AND low > 0 THEN low END) AS min30_low,
                       MAX(CASE WHEN rn <= 29 THEN high END) AS max30_high,
                       MAX(CASE WHEN rn = 1 THEN volume END) AS d1_vol,
                       -- ── ورودی‌هایِ «عینِ فرمولِ فایل» ──────────────────────
                       -- Σ[ih][0..29].QTotTran5J = امروز + ۲۹ نشستِ پیش. فایل
                       -- همیشه بر ۳۰ ثابت تقسیم می‌کند؛ `month_avg_vol` میانگینِ
                       -- واقعیِ نشست‌هایِ موجود است. هر دو می‌مانند: اولی فقط
                       -- قیدهایِ حجمیِ پنج فیلتر را می‌سنجد، دومی ستونِ
                       -- «نسبت حجم ماه» را (دو مبنایِ متفاوت، دو مصرفِ متفاوت).
                       SUM(CASE WHEN rn <= 29 THEN volume END) AS prior29_vol,
                       -- کمینۀِ [ih][1..28] — «امروز» جدا افزوده می‌شود تا
                       -- حلقۀِ JS (`for n=1; n<29`) عیناً بازسازی شود.
                       MIN(CASE WHEN rn <= 28 AND low > 0 THEN low END)   AS min_low_28,
                       -- qd1 = تعدادِ معاملاتِ نشستِ پیش (قیدِ چهارمِ کف‌روبی).
                       -- تا پیش از افزودنِ ستونش به daily_prices هیچ مقدارِ
                       -- واقعیِ ندارد؛ صفرِ جعلی نمی‌سازیم.
                       MAX(CASE WHEN rn = 1 THEN tran END)    AS prev_day_tran,
                       -- چند نشستِ پیش واقعاً وجود دارد؟ نمادی که ۳۰ نشست
                       -- ندارد مبنایِ «تقسیم بر ۳۰»اش جعلی کوچک می‌شود.
                       COUNT(CASE WHEN rn <= 29 THEN volume END) AS prior29_n
                FROM rk WHERE rn <= 60
                GROUP BY symbol
            ),
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
                   v.month_avg_vol, v.prev_day_vol,
                   v.h1_max, v.h2_max, v.h5_max, v.h9_max, v.h19_max, v.h29_max,
                   v.h39_max, v.h49_max, v.h59_max,
                   v.min30_low, v.max30_high, v.d1_vol,
                   v.prior29_vol, v.min_low_28, v.prev_day_tran, v.prior29_n
            FROM market_watch m
            JOIN instruments i ON i.ins_code = m.ins_code
            LEFT JOIN boards b ON b.ins_code = m.ins_code
            LEFT JOIN ctm ON ctm.ins_code = m.ins_code
            LEFT JOIN client_type ct ON ct.ins_code = m.ins_code AND ct.d_even = ctm.d
            LEFT JOIN v ON v.symbol = i.l_val18
            WHERE m.ins_code IS NOT NULL
            ORDER BY m.d_even DESC, i.l_val18 ASC
        """
        df = pd.read_sql_query(query, conn)
        last_deven = df["d_even"].max() if "d_even" in df.columns and len(df) else None
        # نمادهای خارج از تابلو (دEVEN قدیمی) با اولویت آخر — ولی هنوز قابل نمایشاند
        df["is_live"] = (df["d_even"] == last_deven) if last_deven else True

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
        # متغیرها: pl=آخرین معامله، pc=قیمت پایانی، plp=درصد تغییر، tmin=کف روز،
        #          tvol=حجم، tno=تعداد معاملات، zd1=حجم نشست پیش، [ih][k]=تاریخچه
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
        # ستون‌هایِ تاریخچه هم باید بازیابی شوند: «سقفِ ۵۹ نشستِ پیش» اگر
        # موجود نباشد باید null بماند. اگر صفر شود، فیلترِ جت آن را «سقفِ
        # صفر» می‌بیند و ردیف را قبول می‌کند — همان حلقهٔ خاموشی که ۶۷۱ ردیف
        # را جت می‌زد.
        _KEEP_NULL = ("vol_ratio", "vol_dod", "vol_trend", "dist_min30_pct",
                      "month_avg_vol", "prev_day_vol", "d1_vol",
                      "prior29_vol", "min_low_28", "prev_day_tran", "percent_last",
                      "vol_ratio_file", "prior29_n",
                      "buyer_power", "buy_power_i", "sell_power_i",
                      "buyer_power_raw", "resistance_59",
                      "h1_max", "h2_max", "h5_max", "h9_max", "h19_max",
                      "h29_max", "h39_max", "h49_max", "h59_max",
                      "min30_low", "max30_high")
        _kept = {k: df[k].copy() for k in _KEEP_NULL if k in df.columns}
        _filters_tbl = {k: df[k].copy() for k in ("f_roobi", "f_susp", "f_clock", "f_jet", "f_noqteh")}
        df = df.replace([np.inf, -np.inf], 0).fillna(0)
        for _k, _s in _kept.items():
            df[_k] = _s          # NaN باقی می‌ماند → _clean → null
        for _k, _s in _filters_tbl.items():
            df[_k] = _s.fillna(False)

        records = df.to_dict(orient="records")

        def _clean(v):
            if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
                return None
            return v

        for rec in records:
            for k in list(rec.keys()):
                rec[k] = _clean(rec[k])
        # meta: تاریخ/زمان معاملات برای نمایش شمسی (دادهٔ تابلو متعلق به کدام روز است)
        meta = {"d_even": None, "h_even": None, "last_sync": None}
        try:
            # «زمان تابلو» یعنی آخرین چاپِ نشست، نه h_evenِ یک ردیفِ اتفاقی:
            # ردیفِ برگزیده با ORDER BY fetched_at، ساعتِ معاملهٔ همان نماد است
            # (امروز ۰۶:۱۰:۴۶ داد، در حالی که تابلو ۱۲:۵۸ بسته بود).
            _r = conn.execute(
                "SELECT d_even, MAX(h_even), MAX(fetched_at) FROM market_watch "
                "WHERE d_even = (SELECT MAX(d_even) FROM market_watch)").fetchone()
            if _r:
                meta = {"d_even": int(_r[0] or 0), "h_even": int(_r[1] or 0), "last_sync": _r[2]}
        except Exception:
            pass
        payload = {"status": "success", "count": len(df), "data": records, "meta": meta,
                   "live_count": int(df["is_live"].sum()) if "is_live" in df.columns else len(df),
                   "fossil_count": int((~df["is_live"]).sum()) if "is_live" in df.columns else 0}
        import hashlib, json as _json
        if _ORJ:
            import orjson
            body = orjson.dumps(payload)
        else:
            body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
        etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'
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
