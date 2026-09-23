"""Price history series and the screener scan endpoint.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _num, get_db, sym_pred
from .market import load_fts_config
from .chart import _fts_analyze_symbol
from fastapi import APIRouter
import pandas as pd
import os
import json
from bors_config import DB_PATH, WORK_DIR

import time

# کشِ هوشمندِ پاسخ اسکنر — با کش روی دیسک برای جلوگیری از فریز شدن سرور در استارت‌آپ.
# داده‌های بنیادی کدال دیر به دیر تغییر می‌کنند؛ پس TTL را ۱۲ ساعت (۴۳۲۰۰ ثانیه) می‌گذاریم.
# اسکریپت آپدیت کدال در صورت نیاز این کش را باطل می‌کند.
_SCREENER_CACHE = {"cfg_hash": None, "payload": None, "ts": 0.0}
_SCREENER_CACHE_TTL = 43200.0  # ۱۲ ساعت
# کش باید داخلِ WORK_DIR (محلِ نوشتنی) باشد: کنارِ EXE در حالتِ پرتابیل،
# وگرنه %LOCALAPPDATA%\BorsTerminal_Ultimate\data. نوشتنِ کنارِ مسیرِ نصب
# (Program Files) با «Permission denied» شکست می‌خورد و در هر استارت‌آپ خطا
# لاگ می‌شد و کشِ دیسک عملاً از کار می‌افتاد.
CACHE_FILE = os.path.join(WORK_DIR, ".screener_cache.json")

def invalidate_screener_cache():
    """باطل‌کردن دستی کش اسکرینر (مثلاً هنگام سینک و رفرش کدال).

    هر دو کش را باطل می‌کند: RAM/دیسکِ payload، و جدولِ مادی‌شدهٔ fts_results
    (تسک ۱۹). هر دو از همان منبع (سینک کدال/تابلو) تغذیه میشوند، پس سینکِ
    تازه هر دو را کثیف می‌کند. fts_results با DELETE پاک می‌شود تا دفعهٔ بعد
    دوباره از sync_fts_results پر شود.
    """
    _SCREENER_CACHE["payload"] = None
    _SCREENER_CACHE["ts"] = 0.0
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except OSError:
            pass
    try:
        import fts_engine as _fe
        _conn = get_db()
        try:
            _fe.invalidate_fts_results(_conn)
        finally:
            _conn.close()
    except Exception:
        pass


router = APIRouter()


def warm_screener_cache():
    """گرم‌کردنِ کشِ پاسخِ اسکنر در پس‌زمینه (اولین بارگذاریِ تبِ بنیادی سریع شود؛
    اجرای single-source روی ۸۶۵ نماد بارِ سرد ~۲۷s است)."""
    try:
        get_screener()
        print("[screener] cache warmed")
    except Exception as e:  # pragma: no cover
        print(f"[screener] warm-up failed: {e}")


@router.get("/api/history/{symbol}")
def get_history(symbol: str):
    conn = get_db()
    try:
        # تطبیق چند-نویشتاری (ك/ي عربی ↔ ک/ی فارسی): ورودیِ کاربر/واچلیست
        # ممکن است فارسی باشد ولی DB همان نماد را عربی نگه داشته باشد —
        # بدون این، `WHERE symbol = ?` صفر ردیف می‌دهد و تاریخچه خالی می‌ماند.
        _pred, _params = sym_pred("symbol", symbol)
        query = """
            SELECT date, open, high, low, close, volume
            FROM price_history WHERE %s ORDER BY date ASC
        """ % _pred
        df = pd.read_sql_query(query, conn, params=_params)
        if df.empty:
            return {"status": "empty", "candles": [], "volumes": []}

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        # پاکسازی OHLC: NULL/صفر → حذف (کندل با 0 نمودار را خراب میکند و NaN در JSON خطا میدهد)
        df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")
        df = df[(df["close"] > 0) & (df["high"] > 0)]
        # حذف تکراریِ روز: کلید price_history = (symbol,date)، پس یک شرکتِ
        # دو-املا می‌تواند همان روز را دو بار بدهد؛ رکورد پرحجم‌تر می‌ماند.
        df = df.sort_values(["date", "volume"], ascending=[True, False]) \
               .drop_duplicates("date", keep="first")
        df["volume"] = df["volume"].fillna(0)

        # v7.3 برداری‌سازی: iterrows حذف — list-comprehension روی آنپی آرایه (~۲۰x سریعتر)
        times = df["date"].dt.strftime("%Y-%m-%d")
        opens = df["open"].astype(float).tolist()
        highs = df["high"].astype(float).tolist()
        lows = df["low"].astype(float).tolist()
        closes = df["close"].astype(float).tolist()
        vols = df["volume"].astype(float).tolist()
        up_c, dn_c = "rgba(34, 197, 94, 0.4)", "rgba(239, 68, 68, 0.4)"
        candles = [{"time": t, "open": o, "high": h, "low": l, "close": c}
                   for t, o, h, l, c in zip(times, opens, highs, lows, closes)]
        volumes = [{"time": t, "value": v, "color": up_c if c >= o else dn_c}
                   for t, v, o, c in zip(times, vols, opens, closes)]
        return {"status": "success", "candles": candles, "volumes": volumes}
    finally:
        conn.close()

@router.get("/api/screener")
def get_screener():
    """جدول بنیادی کدال — غربالگری ۵ شاخص FTS (v8).

    در v7.3 این endpoint امتیاز را روی مقیاس ۰..۷ و با معیارهای خارج از ۵ محور
    می‌بست (ROE>15، mcap>1e13، شمارش دوبارهٔ رشد فروش، P/S به‌جای فروش÷ارزش بازار،
    «سودآوری مستمر» بر پایهٔ net_profit به‌جای EPS سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی).
    اکنون امتیاز دقیقاً تعداد پنج محور است (۰..۵) و نمادهای تعلیق/بیمه/دستوری
    با پرچم excluded علامت می‌خورند.
    """
    conn = get_db()
    try:
        import fts_engine
        cfg = load_fts_config()
        cfg_hash = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
        now = time.time()
        
        # 1. Check RAM cache
        if (
            _SCREENER_CACHE["payload"] is not None
            and _SCREENER_CACHE.get("cfg_hash") == cfg_hash
            and (now - _SCREENER_CACHE.get("ts", 0.0)) < _SCREENER_CACHE_TTL
        ):
            return _SCREENER_CACHE["payload"]
            
        # 2. Check Disk cache
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    disk_cache = json.load(f)
                if disk_cache.get("cfg_hash") == cfg_hash and (now - disk_cache.get("ts", 0.0)) < _SCREENER_CACHE_TTL:
                    _SCREENER_CACHE["payload"] = disk_cache["payload"]
                    _SCREENER_CACHE["cfg_hash"] = disk_cache["cfg_hash"]
                    _SCREENER_CACHE["ts"] = disk_cache["ts"]
                    print("[screener] loaded from disk cache")
                    return disk_cache["payload"]
            except Exception as e:
                print(f"[screener] Failed to load disk cache: {e}")
        
        print("[screener] cache miss, running heavy bulk scan...")
        rows = fts_engine.bulk_scan(conn, cfg=cfg)

        # نام کامل + نوع ابزار از instruments (bulk_scan فقط نماد برمی‌گرداند)
        names, boards = {}, {}
        for l18, l30 in conn.execute("SELECT l_val18, l_val30 FROM instruments"):
            k = fts_engine.norm_fa(l18)
            if k and k not in names:
                names[k] = l30 or l18
        for r in rows:
            r["name"] = names.get(fts_engine.norm_fa(r["symbol"]), r["symbol"])
            r["eps_data_gap"] = bool(r.get("eps_data_gap"))
            # سند v2.1: اگر سطرهای سالانهٔ اسکنر کافی نبود، همان نردبانِ EPSِ
            # مسیر جزئیات صدا زده می‌شود تا شاخص ۲ بین اسکرینر و /api/fundamental
            # واگرا نشود (ریشهٔ گزارش کاربر: «بدون داده» برای نمادهایی که داده دارند).
            if r["eps_data_gap"]:
                try:
                    from .fundamental import _eps_track_blended
                    _tr = _eps_track_blended(conn, r["symbol"], years=3) or {}
                    _ser = _tr.get("eps_series")
                    if _ser:
                        r["eps_series"] = _ser
                        r["eps_last"] = _ser[-1]
                        r["eps_data_gap"] = bool(_tr.get("data_gap"))
                        r["eps_years_available"] = len([v for v in _ser if v is not None])
                        if isinstance(_tr.get("pass"), bool):
                            r["i2_pass"] = _tr["pass"]
                except Exception:
                    pass

        # ---- v10: یکسان‌سازی امتیاز/پرچم اسکرینر با کارت جزئیات (منبع واحد حقیقت) ----
        # قاعدهٔ v10 (بالای api/fundamental.py): هیچ مسیرِ خواندنی — کارت،
        # واچلیست، اسکرینر، خروجی و UI — حق ندارد ارزش بازار را دوباره بسازد
        # (p_closing × total_shares). عدد یک‌بار از ستونِ رسمیِ تابلو می‌آید و
        # امتیاز/پرچمِ اسکرینر هم دقیقاً با همان evaluate_v10 کارت محاسبه می‌شود
        # تا شاخص‌ها بین /api/screener و /api/fundamental واگرا نشوند.
        try:
            from .fundamental import (
                evaluate_v10, board_total_market_cap,
                ensure_market_cap_schema, _has_mcap_col,
            )
        except Exception:
            evaluate_v10 = None
        if evaluate_v10 is not None:
            if not _has_mcap_col(conn, "market_watch"):
                ensure_market_cap_schema(conn)
            mcap_official = {}
            for _l18, _mc in conn.execute(
                    "SELECT i.l_val18, m.market_cap FROM instruments i "
                    "JOIN market_watch m ON m.ins_code = i.ins_code"):
                _k = fts_engine.norm_fa(_l18)
                if _k and _k not in mcap_official:
                    mcap_official[_k] = _num(_mc)
            total_mcap, _mcap_src = board_total_market_cap(conn)
            _m141m = fts_engine.m141_map(conn)
            _liqm = fts_engine.avg_trade_value_hmt(conn)
            cname_of = {}
            for _sym, _cn in conn.execute(
                    "SELECT symbol, company_name FROM financial_statements "
                    "ORDER BY period_end DESC"):
                _k = fts_engine.norm_fa(_sym)
                if _k and _k not in cname_of:
                    cname_of[_k] = _cn or ""

            # تسک ۱۹ — مادی‌سازی: یک SELECT از fts_results به‌جای ~۲۵۰۰ فراخوانیِ
            # evaluate_v10. قراردادِ fallback (تصمیم ۴): جدول غایب/خالی، یا
            # cfg_hash ناهم‌خوان → _mat برمی‌گردد و مسیرِ زندهٔ زیر اجرا می‌شود،
            # یعنی یک DB قدیمی/خالی دقیقاً همان رفتارِ قبلی را دارد.
            _mat = None
            try:
                _mat = fts_engine.fts_results_bulk(conn, cfg_hash=cfg_hash)
            except Exception:
                _mat = None
            if _mat is not None:
                print("[screener] fts_results hit — %d نماد مادی‌شده (یک SELECT)"
                      % len(_mat))
            else:
                print("[screener] fts_results miss — محاسبهٔ زندهٔ evaluate_v10")

            for r in rows:
                key = r.get("symbol_norm") or fts_engine.norm_fa(r["symbol"])
                res = None
                if _mat is not None:
                    # مسیرِ مادی: همان خروجی که sync_fts_results با همین cfg_hash
                    # نوشته. نمادی که در جدول نیست → None → fallback به زنده.
                    res = _mat.get(key)
                if res is None:
                    res = evaluate_v10(conn, key, mcap_official.get(key, 0.0),
                                       total_mcap, r.get("sector_name", ""),
                                       cfg=cfg, company_name=cname_of.get(key, ""),
                                       m141_map=_m141m, liq_map=_liqm)
                p = res["passes"]
                r["score"] = res["score"]
                r["primary_score"] = res.get("primary_score", 0)
                r["i1_pass"] = p["1_growth"]
                r["i2_pass"] = p["2_eps_trend"]
                r["i3_pass"] = p["3_gross_margin"]
                r["i4_pass"] = p["4_sales_to_mcap"]
                r["i5_pass"] = p["5_industry"]
                r["i1a_pass"] = p.get("1a_monetary_growth")
                r["i1b_pass"] = p.get("1b_volume_growth")
                r["i4a_pass"] = p.get("4a_sales_to_mcap")
                r["i4b_pass"] = p.get("4b_profit_potential")
                r["excluded"] = res["excluded"]
                r["exclusion_reasons"] = " · ".join(res["exclusion_reasons"])
                r["verdict"] = res["verdict"]
                r["pricing_mode"] = res.get("pricing_mode")
                r["panel_industry"] = (res.get("profile") or {}).get("kind")
                # v10 (منبعِ واحدِ حقیقت): ستون‌های «مقدار»ِ جدول هم باید از همان
                # مسیرِ کارت بیایند، نه سالانه‌سازیِ legacy مسیر bulk_scan. بدونِ
                # این، «۴ پتانسیل»ِ جدول (فروش ۳ماهه×۴) با potential_pctِ کارت
                # (تجمیعی × ۱۲÷م) واگرا می‌شد — شاهد: شملی جدول ۳۳٫۲٪ در برابر کارت
                # ۶۱٫۳٪؛ ۵۲۳ ردیف از ۸۶۵ ناهم‌خوان بودند. امتیاز/پرچم دست‌نخورده است.
                _ind = res.get("indicators") or {}
                _g1 = ((_ind.get("1") or {}).get("monetary") or {})
                _g3 = _ind.get("3") or {}
                _v4 = _ind.get("4") or {}
                _an4 = _v4.get("annual") or {}
                r["rev_growth"] = _g1.get("monetary_pct")
                r["gross_margin"] = _g3.get("margin_pct")
                r["sales_to_mcap"] = _v4.get("sales_to_mcap")
                r["profit_potential_pct"] = _v4.get("potential_pct")
                r["annual_sales_bt"] = (_v4.get("annual_sales_bt")
                                         if _v4.get("annual_sales_bt") is not None
                                         else _an4.get("annual_sales_bt"))
                r["annualize_months"] = _an4.get("months_used")
            # رتبه‌بندی: اول سه محورِ بلاکر (جزوه ص ۶)، بعد امتیازِ پنج‌تایی
            rows.sort(key=lambda r: (r["excluded"], -int(r.get("primary_score") or 0),
                                     -r["score"],
                                     -_num(r.get("mcap")), r["symbol"]))

        # واچ‌لیست: حداکثر watchlist_max سهمِ غیرمردود، مرتب بر اساس امتیاز
        cap = int(cfg.get("watchlist_max", 50) or 50)
        eligible = [r for r in rows if not r["excluded"]]
        for i, r in enumerate(eligible):
            r["watchlist"] = i < cap
        for r in rows:
            r.setdefault("watchlist", False)

        # ---- v10: FTS technical methodology columns (tech_*) ----
        # Only watchlist rows are enriched (cap <= watchlist_max): the full
        # bulk_scan universe (~2500 symbols) would make the endpoint minutes
        # slow, and the frontend preset badges only need the top scan rows.
        # Per-symbol try/except: one bad symbol must not kill the scan.
        for r in rows:
            if not r.get("watchlist"):
                continue
            raw = str(r.get("symbol") or "")
            norm = raw.translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"}))
            fts = None
            try:
                fts = _fts_analyze_symbol(norm or raw)
            except Exception:
                fts = None
            f = (fts or {}).get("fts") or {}
            tr = f.get("trend") or {}
            ex = f.get("exit_engine") or {}
            fib = f.get("fib") or {}
            r["tech_trend_d"] = (tr.get("D") or {}).get("trend")
            r["tech_trend_w"] = (tr.get("W") or {}).get("trend")
            r["tech_trend_m"] = (tr.get("M") or {}).get("trend")
            r["tech_alignment"] = tr.get("alignment")
            r["tech_jet"] = bool((f.get("jet") or {}).get("active"))
            r["tech_choch_bull"] = bool((f.get("choch") or {}).get("bullish"))
            r["tech_choch_bear"] = bool((f.get("choch") or {}).get("bearish"))
            r["tech_double_bottom"] = bool((f.get("double_bottom") or {}).get("active"))
            r["tech_range_break"] = bool((f.get("range_box") or {}).get("active"))
            if ((fib.get("zone_33_40") or {}).get("in_zone")):
                r["tech_fib_zone"] = "33-40"
            elif ((fib.get("zone_618_70") or {}).get("in_zone")):
                r["tech_fib_zone"] = "61.8-70"
            else:
                r["tech_fib_zone"] = None
            r["tech_exit_verdict"] = ex.get("verdict")
            r["tech_exit_signals"] = ex.get("signals") or []
            mat = tr.get("matrix") or {}
            r["tech_matrix_decision"] = mat.get("decision")
            r["tech_matrix_setup"] = mat.get("setup")
            r["tech_matrix_desc"] = mat.get("desc")
            hg = f.get("hourglass") or {}
            r["tech_hourglass_active"] = bool(hg.get("active"))
            r["tech_hourglass_action"] = hg.get("action")

        # ---- وتوی روند هفتگی (چارت ۳: هم نزولی و هم خنثی ⇒ reject) ----
        # داورِ انحصاری همین وتو `trend.matrix.decision` در api/chart.py است — همان
        # چیزی که جدول بنیادی و نوارِ بج‌ها قرمز می‌کنند (useScreener.ts:69).
        # پیش از این وتو فقط *نمایش* داده می‌شد و سهمِ وتو‌شده جای واچ‌لیستِ خود
        # را نگه می‌داشت. «بی‌داده» وتو نیست: decision == UNKNOWN (کمتر از دو پیوت
        # کاملِ هفتگی) واچ‌لیست را نمی‌سوزاند.
        # نکتهٔ دانستن: تحلیل تکنیکال فقط روی حداکثر `watchlist_max` ردیفِ اول
        # انجام می‌شود (هر ردیف یک fetchِ کاملِ تاریخچه است، نه یک کوئری)؛ پس
        # ردیفِ وتوشده با ردیفِ رتبهٔ بعدی پر نمی‌شود و واچ‌لیست می‌تواند کوتاه‌تر
        # از سقف بماند — این همان انقباضِ عمدیِ قیف است، نه باگ.
        for r in rows:
            if not r.get("watchlist"):
                continue
            if r.get("tech_matrix_decision") == "REJECT":
                r["watchlist"] = False
                r["weekly_veto"] = True
                why = ("وتوی هفتگی — روند نزولی" if r.get("tech_trend_w") == "down"
                       else "وتوی هفتگی — روند خنثی")
                r["exclusion_reasons"] = " · ".join(
                    [x for x in (str(r.get("exclusion_reasons") or "").strip(), why) if x])
            else:
                r["weekly_veto"] = False

        payload = {"status": "success", "count": len(rows), "data": rows,
                   "thresholds": cfg, "max_score": 5}
        _SCREENER_CACHE["cfg_hash"] = cfg_hash
        _SCREENER_CACHE["payload"] = payload
        _SCREENER_CACHE["ts"] = now
        
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"cfg_hash": cfg_hash, "payload": payload, "ts": now}, f, ensure_ascii=False)
            print("[screener] saved to disk cache")
        except Exception as e:
            print(f"[screener] Failed to save disk cache: {e}")
            
        return payload
    finally:
        conn.close()
