"""Price history series and the screener scan endpoint.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _num, get_db
from .market import load_fts_config
from .chart import _fts_analyze_symbol
from fastapi import APIRouter
import pandas as pd


router = APIRouter()


@router.get("/api/history/{symbol}")
def get_history(symbol: str):
    conn = get_db()
    try:
        query = """
            SELECT date, open, high, low, close, volume
            FROM price_history WHERE symbol = ? ORDER BY date ASC
        """
        df = pd.read_sql_query(query, conn, params=(symbol,))
        if df.empty:
            return {"status": "empty", "candles": [], "volumes": []}

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        # پاکسازی OHLC: NULL/صفر → حذف (کندل با 0 نمودار را خراب میکند و NaN در JSON خطا میدهد)
        df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")
        df = df[(df["close"] > 0) & (df["high"] > 0)]
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
        rows = fts_engine.bulk_scan(conn, cfg=cfg)

        # نام کامل + نوع ابزار از instruments (bulk_scan فقط نماد برمی‌گرداند)
        names, boards = {}, {}
        for l18, l30 in conn.execute("SELECT l_val18, l_val30 FROM instruments"):
            k = fts_engine.norm_fa(l18)
            if k and k not in names:
                names[k] = l30 or l18
        for r in rows:
            r["name"] = names.get(fts_engine.norm_fa(r["symbol"]), r["symbol"])
            r["growth_pass"] = r["rev_growth"] is not None and r["rev_growth"] >= cfg["growth_min"]
            r["eps_data_gap"] = bool(r.get("eps_data_gap"))

        # واچ‌لیست: حداکثر watchlist_max سهمِ غیرمردود، مرتب بر اساس امتیاز
        cap = int(cfg.get("watchlist_max", 50) or 50)
        eligible = [r for r in rows if not r["excluded"]]
        for i, r in enumerate(eligible):
            r["watchlist"] = i < cap
        for r in rows:
            r.setdefault("watchlist", False)

        # پیش‌شرط همت (اختیاری) — خارج از پنج محور، فقط علامت می‌خورد
        floor = _num(cfg.get("mcap_min_hmt", 0)) * 1e12
        if floor > 0:
            for r in rows:
                if r["mcap"] < floor:
                    r["excluded"] = True
                    r["exclusion_reasons"] = (r["exclusion_reasons"] + " · " if
                                              r["exclusion_reasons"] else "") + "ارزش بازار زیر حد"

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

        return {"status": "success", "count": len(rows), "data": rows,
                "thresholds": cfg, "max_score": 5}
    finally:
        conn.close()
