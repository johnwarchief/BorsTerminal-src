"""Market snapshot, live FTS scan and FTS threshold config.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _count_procs, get_db
from bors_config import DB_PATH, FTS_CONFIG_PATH, FTS_DEFAULTS, FTS_LEGACY_LISTS, FTS_LEGACY_SCALARS, FTS_LIST_KEYS, FTS_STR_KEYS, MARKET_STATUS_PATH
from bors_flags import _ORJ
from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import Response
import json
import numpy as np
import pandas as pd
import sqlite3


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
    import time as _t
    now = _t.time()
    hit = MARKET_CACHE.get("body")
    if hit and (now - MARKET_CACHE.get("t", 0)) < MARKET_CACHE_TTL:
        inm = request.headers.get("if-none-match")
        if inm and inm == MARKET_CACHE.get("etag"):
            return Response(status_code=304)
        return Response(content=hit, media_type="application/json",
                        headers={"Cache-Control": "max-age=15", "X-Cache": "HIT",
                                 "ETag": MARKET_CACHE.get("etag", "")})
    conn = get_db()
    try:
        # Left join for 30-session Avg Volume (سوال suspicious volume) + prev-day volume
        # rn <= 30 => آخرین ۳۰ جلسه (بدون ردیفهای قدیمیتر)؛ rn=1 => آخرین روز (پایه روند حجم)
        query = """
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
                   v.month_avg_vol, v.prev_day_vol,
                   v.h1_max, v.h5_max, v.h9_max, v.h19_max, v.h29_max,
                   v.h39_max, v.h49_max, v.h59_max,
                   v.min30_low, v.max30_high, v.d1_vol
            FROM market_watch m
            JOIN instruments i ON i.ins_code = m.ins_code
            LEFT JOIN boards b ON b.ins_code = m.ins_code
            LEFT JOIN (SELECT ins_code, MAX(d_even) AS d FROM client_type GROUP BY ins_code) ctm
                 ON ctm.ins_code = m.ins_code
            LEFT JOIN client_type ct ON ct.ins_code = m.ins_code AND ct.d_even = ctm.d
            LEFT JOIN (
                SELECT symbol,
                       AVG(volume) AS month_avg_vol,
                       MAX(CASE WHEN rn = 1 THEN volume END) AS prev_day_vol,
                       -- فیلترهای TSETMC: [ih][k].PriceMax / PriceMin
                       MAX(CASE WHEN rn = 1 THEN high END) AS h1_max,
                       MAX(CASE WHEN rn = 5 THEN high END) AS h5_max,
                       MAX(CASE WHEN rn = 9 THEN high END) AS h9_max,
                       MAX(CASE WHEN rn = 19 THEN high END) AS h19_max,
                       MAX(CASE WHEN rn = 29 THEN high END) AS h29_max,
                       MAX(CASE WHEN rn = 39 THEN high END) AS h39_max,
                       MAX(CASE WHEN rn = 49 THEN high END) AS h49_max,
                       MAX(CASE WHEN rn = 59 THEN high END) AS h59_max,
                       MIN(low) AS min30_low,
                       MAX(high) AS max30_high,
                       MAX(CASE WHEN rn = 1 THEN volume END) AS d1_vol
                FROM (
                    SELECT symbol, volume, high, low,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                    FROM price_history
                ) WHERE rn <= 60
                GROUP BY symbol
            ) v ON v.symbol = i.l_val18
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

        buy_per_i = df["buy_i_vol"] / df["buy_count_i"].replace(0, 1)
        sell_per_i = df["sell_i_vol"] / df["sell_count_i"].replace(0, 1)
        # cap 10x: وقتی فروش حقیقی صفر است، نسبت بینهایت میشود — سقف ۱۰ منطقی است
        df["buyer_power"] = (buy_per_i / sell_per_i.replace(0, 1)).round(2).fillna(1.0).clip(upper=10.0)
        # قدرت خالص خریدار/فروشنده (حجم به ازای هر معامله) — برای ستون مقایسهای
        df["buy_power_i"] = buy_per_i.round(0).fillna(0)
        df["sell_power_i"] = sell_per_i.round(0).fillna(0)

        # ---------- حجم مشکوک: tvol >= 2.5 * month_avg_vol (DivByZero/Null-safe) ----------
        mav = df["month_avg_vol"].where(df["month_avg_vol"] > 0)   # <=0/NaN → NaN
        df["vol_ratio"] = (df["tvol"] / mav).round(1)              # NaN where no history
        df["suspicious_vol"] = (df["vol_ratio"] >= 3.0)            # NaN → False

        # ---------- روند حجم: tvol vs آخرین روز معاملاتی (day-over-day, Null-safe) ----------
        pdv = df["prev_day_vol"].where(df["prev_day_vol"] > 0)     # <=0/NaN → NaN
        df["vol_dod"] = (df["tvol"] / pdv).round(2)                # NaN where no prev day
        df["vol_trend"] = np.where(df["vol_dod"].isna(), None,
                           np.where(df["vol_dod"] >= 1.10, "up",
                           np.where(df["vol_dod"] <= 0.90, "down", "flat")))

        # ============================================================
        # فیلترهای TSETMC (جایگزین فیلترهای قبلی تابلوخوانی)
        # متغیرها: pl=پایانی، pc=آخرین معامله، plp=درصد تغییر، tmin=کف روز،
        #          tvol=حجم، tno=تعداد معاملات، zd1/qd1=دیروز، [ih][k]=تاریخچه
        # ============================================================
        V = lambda s: df[s].astype(float)
        df["f_roobi"] = (np.isclose(V("p_closing"), V("p_min"), atol=0.5) & (V("prev_day_vol") > 1) & (V("percent_change") < -1) & (V("z_tot_tran") > 100)).fillna(False)
        # حجم مشکوک: tvol > 3*avg30 و tno > 50
        df["f_susp"] = ((V("tvol") > 3 * (df["month_avg_vol"].where(df["month_avg_vol"] > 0))) & (V("z_tot_tran") > 50)).fillna(False)
        # الگوی ساعت FTS: آخرین معامله حداقل ۱٪ بالاتر از قیمت پایانی (plp - pcp >= 1.0)
        df["f_clock"] = ((V("p_last") >= V("p_closing") * 1.01) & (V("tvol") > (df["month_avg_vol"].where(df["month_avg_vol"] > 0))) & (V("z_tot_tran") > 30)).fillna(False)
        # فیلتر جت FTS: tvol > 3*avg30 و قدرت خریدار حقیقی >= 1.5*فروشنده و آخرین معامله بالای پایانی و شکست سقف‌ها
        buy_pow = V("buy_i_vol") / V("buy_count_i").replace(0, 1)
        sell_pow = V("sell_i_vol") / V("sell_count_i").replace(0, 1)
        jet_hist_ok = True
        for k in (5, 9, 19, 29, 39, 49, 59):
            jet_hist_ok = jet_hist_ok & (df[f"h{k}_max"].isna() | (df[f"h{k}_max"] < V("p_closing")))
        df["f_jet"] = ((V("tvol") > 3 * (df["month_avg_vol"].where(df["month_avg_vol"] > 0)))
                       & (buy_pow >= 1.5 * sell_pow)
                       & (V("p_last") >= V("p_closing"))
                       & (V("percent_change") > 0)
                       & (V("z_tot_tran") > 100)
                       & jet_hist_ok).fillna(False)
        # نقطه زنی: (pc - min30)/pc*100 < 3 و tvol > 1*avg30 و tno > 5
        min30 = df["min30_low"].where(df["min30_low"] > 0)
        df["dist_min30_pct"] = np.where(V("p_closing") > 0, (V("p_closing") - min30) / V("p_closing") * 100, np.nan)
        df["f_noqteh"] = ((df["dist_min30_pct"] < 3) & (V("tvol") > (df["month_avg_vol"].where(df["month_avg_vol"] > 0))) & (V("z_tot_tran") > 5)).fillna(False)

        # Fail-safe: NaN/Inf → 0 (JSON safety)؛ سپس NaN حجمی → واقعاً null
        # (تا sort و نمایش «حجم مشکوک» درست بماند).
        # نکته: ستونهای حجمی از نسخهٔ خام بازیابی میشوند چون fillna(0)
        # روی object-column (vol_trend) None را به 0 تبدیل میکند.
        _vr = df["vol_ratio"].copy()
        _vd = df["vol_dod"].copy()
        _vt = df["vol_trend"].copy()
        _filters_tbl = {k: df[k].copy() for k in ("f_roobi", "f_susp", "f_clock", "f_jet", "f_noqteh")}
        _dist = df["dist_min30_pct"].copy()
        df = df.replace([np.inf, -np.inf], 0).fillna(0)
        df["vol_ratio"] = _vr   # NaN باقی میماند → _clean → null
        df["vol_dod"] = _vd
        df["vol_trend"] = _vt   # None سرجایش میماند
        for _k, _s in _filters_tbl.items():
            df[_k] = _s.fillna(False)
        df["dist_min30_pct"] = _dist

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
            _r = conn.execute(
                "SELECT d_even, h_even, fetched_at FROM market_watch "
                "ORDER BY fetched_at DESC LIMIT 1").fetchone()
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
        MARKET_CACHE["body"] = body
        MARKET_CACHE["t"] = now
        MARKET_CACHE["etag"] = etag
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
MARKET_CACHE_TTL = 20.0   # ثانیه — دادهٔ تابلو هر ۳۰ثانیه سینک میشود، ۲۰ کافی است
