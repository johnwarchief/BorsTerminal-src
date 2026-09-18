"""Candle history, key levels, calendar/MA events, chart-db and patterns.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from bors_config import DB_PATH, MA_WINDOWS, _CAL_CACHE_PATH, _cal_cache
from ._core import sym_pred
from fastapi import APIRouter
from fastapi import Query
import datetime
import json
import math
import os
import sqlite3
import time


router = APIRouter()


CDN_OFFLINE_UNTIL = 0.0

@router.get("/api/chart/{symbol}")
def get_chart_tsetmc(symbol: str):
    """نمودار کامل از CDN TSETMC: OHLCV روزانه + رویدادهای تعدیل عملکردی (ادجاست) با فال‌بک خودکار به دیتابیس محلی."""
    import time as _t
    global CDN_OFFLINE_UNTIL
    _cached = CHART_CACHE.get(symbol)
    if _cached and (_t.time() - _cached[0]) < CHART_CACHE_TTL:
        return _cached[1]
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
                    "count": len(cands),
                    "fts": db_res.get("fts"),
                }
                CHART_CACHE[symbol] = (_t.time(), res)
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
        candles, volumes = [], []
        all_rows = []  # همهٔ ردیف‌های خام (حتی روزهای بدون معامله H=L=0 که کندل نمی‌شوند)
        lines = r.text.splitlines()
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
                # آخرین معامله؛ اگر ستون نبود یا صفر بود به پایانی برمی‌گردد
                last = float(p[i_last]) if (len(p) > i_last and p[i_last]) else 0.0
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
                all_rows.append({"time": dt, "base": base, "close": c})

            if hi <= 0 or c <= 0 or o <= 0 or lo <= 0:
                continue
            if last <= 0:
                last = c          # <LAST> معتبر نبود → پایانی جانشین می‌شود
            # LAST-CLAMP FIX (2026-09-09): «آخرین معامله» قیمتِ معاملاتی است و
            # ریاضیاتاً باید داخل [low, high] باشد. اگر CDN مقدار معیوب داد (همان
            # گونه که برای FIRST در v8.7 FIX-1b می‌داد)، clamp می‌شود تا سریِ
            # «آخرین قیمت» در نمای خطی بیرون از سایهٔ کندل خط نکشد.
            last = min(max(last, lo), hi)
            candles.append({"time": dt, "open": o, "high": hi, "low": lo,
                            "close": c, "last": last})
            volumes.append({"time": dt, "value": v, "color": "#10b981" if c >= o else "#f43f5e"})
        # ۲) رویدادهای تعدیل — v8.7 FIX-2 (رویکرد FIX C): فقط از گسست «قیمت پایه» در همین CSV.
        #    قیمت پایهٔ هر روز (ستون <OPEN>) ذاتاً پایانیِ آخرین روز معاملاتی است؛ تنها در روز
        #    اجرای افزایش سرمایه / تقسیم / سود نقدی عمداً جابه‌جا می‌شود. پس:
        #        رویداد  ⇔  base(day) != close(prev trading day)
        #        ratio   =  base(day) / close(prev trading day)
        #    این روش هم تقسیم و هم سود نقدی را می‌گیرد (هر دو قیمت پایه را می‌کوبند) و برخلاف
        #    GetPriceAdjustList، تاریخ «روز اجرای واقعی» را می‌دهد نه تاریخ وقوع مصوبه.
        #    چرا APF از محاسبهٔ فاکتور حذف شد (آمار خساپا/فولاد، فایل r12.txt):
        #      (الف) جابه‌جایی تاریخ: ۱۲ رویداد APF خساپا → ۷ مورد بی‌ارتباط، تا ۴۳ روز خطا
        #          (فولاد: ۱۵ مورد جابه‌جا، بدترین ۱۳۱ روز).
        #      (ب) ناقص است: رویدادهای ۲۰۰۳–۲۰۰۸ و ۲۰۲۵ را ندارد.
        #      (ج) ترکیبش با gap-detectorِ پایین، همان رویداد را دوباره می‌شمرد (۲۰ رویداد
        #          در برابر ۹ تغییر واقعی قیمت پایه) و پرش‌های واقعی بازار را پاک می‌کرد.
        #    gap-detector ساختگی (close ratio < 0.8) کامل حذف شد: آن پرش‌های ۲۰۰۳–۲۰۰۸
        #    ریزش واقعی بازار بودند، نه تقسیم — و «روز تحریف» (تغییر فاکتور بدون تغییر پایه)
        #    می‌ساختند: ۸ روز در خساپا، ۱ روز در فولاد.
        adj_events = []
        asc = sorted((x for x in all_rows if x["close"] > 0 and x["base"] > 0),
                     key=lambda x: x["time"])
        prev = None
        for row in asc:
            if prev:
                ratio = row["base"] / prev["close"]
                # آستانه دوتایی: هم ≥ یک واحد قیمت، هم > ADJ_TOL نسبی — تا گردکردنِ عددِ
                # قیمت، رویداد جعلی نسازد و در عین حال کوچک‌ترین تقسیم واقعی هم حذف نشود.
                if abs(row["base"] - prev["close"]) >= 1.0 and abs(ratio - 1.0) > ADJ_TOL:
                    adj_events.append({"date": row["time"], "ratio": round(ratio, 6)})
            prev = row
        adj_events.sort(key=lambda e: e["date"])
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

        result = {
            "status": "success",
            "candles": candles,
            "volumes": volumes,
            "factors": factors,
            "adjustEvents": adj_events,
            "adjustSource": "base-price-discontinuity",   # v8.7 FIX-2 (دیگر APF+gap-detector نیست)
            "count": len(candles),
        }
        CHART_CACHE[symbol] = (time.time(), result)
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
    _cached = KEY_LEVELS_CACHE.get(symbol)
    if _cached and (_t.time() - _cached[0]) < KEY_LEVELS_TTL:
        return _cached[1]
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        _pred, _params = sym_pred("symbol", symbol)
        _raw = conn.execute(
            "SELECT symbol, date, open, high, low, close, volume FROM price_history "
            "WHERE %s ORDER BY date DESC, volume DESC LIMIT 250" % _pred,
            _params).fetchall()
        _seen, rows = set(), []
        for r in _raw:            # حذف تکراریِ روز (نمادِ دو-املا): پرحجم‌تر می‌ماند
            if r[1] in _seen:
                continue
            _seen.add(r[1])
            rows.append({"date": r[1], "open": r[2], "high": r[3], "low": r[4],
                         "close": r[5], "volume": r[6]})
        conn.close()
        rows.reverse()  # صعودی
        if len(rows) < 60:
            return {"status": "ok", "symbol": symbol, "levels": [], "blocks": [],
                    "count": 0, "message": "تاریخچهٔ کافی نیست (< 60 روز)"}
        result = _key_levels_from_history(rows)
        result.update({"status": "ok", "symbol": symbol,
                       "message": f"{len(rows)} روز آخر"})
        KEY_LEVELS_CACHE[symbol] = (time.time(), result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

def _cal_events_for(symbol):
    """رویدادهای نماد از static/calendar/cache.json (کش با mtime)."""
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
    _norm = lambda s: str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()
    want = _norm(symbol)
    out, seen = [], set()
    _tg = __import__("calendar").timegm
    for ev in _cal_cache["events"]:
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
    ck = f"{symbol}|{days}"
    _cached = MA_CACHE.get(ck)
    if _cached and (_t.time() - _cached[0]) < MA_TTL:
        return _cached[1]
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        _pred, _params = sym_pred("symbol", symbol)
        _raw = conn.execute(
            "SELECT date, close, volume FROM price_history WHERE %s "
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
        closes = [(r[0], float(r[1])) for r in rows if r[1] is not None]
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
                "SELECT date, open, high, low, close, volume FROM price_history "
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
            # v9.7: price_history ستون «آخرین معامله» ندارد (فقط OHLCV)؛ پس last
            # روی همان close می‌نشیند و گمراه‌کننده نیست — مسیر واقعیِ last،
            # /api/chart (CSV تکمیل‌شده با <LAST>) است.
            candles = [{"time": r[0], "open": float(r[1]), "high": float(r[2]),
                        "low": float(r[3]), "close": float(r[4]),
                        "last": float(r[4]),
                        "volume": float(r[5] or 0)} for r in rows]
        finally:
            conn.close()

        # ---- تزریق کندل امروز از market_watch (دادهٔ زندهٔ تابلوخوانی) ----
        today = datetime.date.today().strftime("%Y-%m-%d")
        last_db_date = candles[-1]["time"] if candles else ""
        live_injected = False
        live_error = None
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
                    "SELECT m.price_first, m.price_max, m.price_min, m.p_closing, m.q_tot_tran, i.l_val18, m.p_last "
                    "FROM instruments i LEFT JOIN market_watch m ON i.ins_code = m.ins_code "
                    "WHERE %s OR %s ORDER BY m.d_even DESC LIMIT 1" % (_p18, _p30),
                    (*_a18, *_a30)).fetchone()
            finally:
                conn.close()
            if row and row[3] and float(row[3]) > 0:   # p_closing موجود و معتبر
                p_first, p_max, p_min, p_close, vol = (
                    float(row[0] or 0), float(row[1] or 0), float(row[2] or 0),
                    float(row[3]), float(row[4] or 0))
                p_last = float(row[6] or 0) if len(row) > 6 else 0.0   # v9.7
                # افت‌به‌روی امن: تابلو ممکن است در میانهٔ روز هنوز high/low را پر نکرده باشد
                o_l = p_first if p_first > 0 else p_close
                h_l = p_max if p_max > 0 else max(o_l, p_close)
                l_l = p_min if p_min > 0 else min(o_l, p_close)
                h_l = max(h_l, o_l, p_close)          # high باید بالای بدنه باشد
                l_l = min(l_l, o_l, p_close) if l_l > 0 else min(o_l, p_close)
                bar = {"time": today, "open": o_l, "high": h_l, "low": l_l,
                       "close": p_close, "volume": vol,
                       # v9.7: «آخرین معامله» زنده از market_watch.p_last
                       "last": p_last if p_last > 0 else p_close}
                if last_db_date < today:
                    candles.append(bar)
                    live_injected = True
                elif candles and candles[-1]["time"] == today:
                    # جایگزینی با دادهٔ زندهٔ تازه‌تر
                    candles[-1] = bar
                    live_injected = True
            elif row:
                live_error = "no_valid_p_closing"
        except Exception as e:
            # v8.7 FIX-4: خطا دیگر خاموش نیست — در پاسخ منعکس می‌شود تا در لاگ/دیباگ دیده شود
            live_error = f"{type(e).__name__}: {e}"

        # ---- v10 FTS: technical methodology payload (same candles) ----
        # Pure compute wrapper; failures must never break the chart contract,
        # so "fts" degrades to None. See _fts_analyze_candles.
        fts_payload = None
        try:
            fts_payload = _fts_analyze_candles(symbol, candles)
        except Exception:
            fts_payload = None

        vols = [{"time": c["time"], "value": c.get("volume", 0),
                 "color": "#10b981" if c.get("close", 0) >= c.get("open", 0) else "#f43f5e"} for c in candles]
        facts = [{"time": c["time"], "factor": 1.0} for c in candles]

        return {"status": "success", "symbol": symbol, "count": len(candles),
                "candles": candles, "volumes": vols, "factors": facts,
                "adjustEvents": [], "adjustSource": "local-db",
                "liveInjected": live_injected,
                "liveError": live_error,
                "adjustment": adjustment,
                "fts": fts_payload}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/patterns/{symbol}")
def get_patterns(symbol: str):
    """نقاط [time, price] الگوها برای KLineChart.createOverlay — بدون drift.

    خروجی: support/resistance (خط افقی از swing levels)، trendlines (خط از دو pivot)،
    breakout zone (آستانهٔ آخرین رنج) — همه با timestamp میلی‌ثانیه (ظهر UTC؛ فرمت overlay v10).
    """
    import time as _t
    cached = PATTERNS_CACHE.get(symbol)
    if cached and (_t.time() - cached[0]) < KEY_LEVELS_TTL:
        return cached[1]
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        _pred, _params = sym_pred("symbol", symbol)
        _raw = conn.execute(
            "SELECT symbol, date, open, high, low, close, volume FROM price_history "
            "WHERE %s ORDER BY date DESC, volume DESC LIMIT 250" % _pred,
            _params).fetchall()
        _seen, rows = set(), []
        for r in _raw:            # حذف تکراریِ روز (نمادِ دو-املا): پرحجم‌تر می‌ماند
            if r[1] in _seen:
                continue
            _seen.add(r[1])
            rows.append({"date": r[1], "open": r[2], "high": r[3], "low": r[4],
                         "close": r[5], "volume": r[6]})
        conn.close()
        rows.reverse()
        if len(rows) < 60:
            return {"status": "ok", "symbol": symbol, "overlays": [], "count": 0,
                    "message": "تاریخچه کافی نیست"}
        # FIX v7.2: سطحها باید در فضای تعدیلشده باشند (chart با factor رسم میکند) — وگرنه Y-mismatch
        evs = _adjust_events_for(symbol, rows)
        for r in rows:
            f = 1.0
            for e in evs:
                if e["date"] > r["date"]:
                    f *= e["ratio"]
            r["high"] *= f; r["low"] *= f; r["close"] *= f
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
        PATTERNS_CACHE[symbol] = (_t.time(), result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

CHART_CACHE = {}   # {symbol: (fetch_time, json_data)}

ADJ_TOL = 0.001

CHART_CACHE_TTL = 3600.0

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

_FTS_SWING_K = 3          # نیم‌پنجرهٔ پیوت (fractal) روی روزانه
_FTS_EQUAL_TOL = 0.005    # اختلاف ≤ ۰.۵٪ دو پیوت = «مساوی» (ساختار رنج/تخت)
_FTS_ENTRY_LOOKBACK = 60  # سقف مرجع تریگر ورود (شکست ماکسِ ۶۰ کندل قبل)


def _fts_resample(candles, bucket="W"):
    """تجمیع کندل روزانه به هفتگی/ماهانه — ورودی روند چند-تایم‌فریمی FTS.

    candles: لیست دیکشنری با کلیدهای time ('YYYY-MM-DD'), open, high, low, close, volume
             (همان ساختار candles در get_chart_db؛ مرتب صعودی).
    bucket:  'W' → هفتهٔ ISO  |  'M' → ماه میلادی.
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
            iso = d.isocalendar()
            key = f"{iso[0]}-W{int(iso[1]):02d}"
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
        if hi >= max(win_l_h) and hi >= max(win_r_h):
            out.append({"idx": i, "price": float(hi), "kind": "high"})
        if lo <= min(win_l_l) and lo <= min(win_r_l):
            out.append({"idx": i, "price": float(lo), "kind": "low"})
    return out


def _fts_classify_trend(swings, tol=_FTS_EQUAL_TOL):
    """طبقه‌بندی روند بر پایهٔ ساختار سقف/کف (هستهٔ متدولوژی FTS صفحهٔ ۲).

    دو سقف پیوت و دو کف پیوتِ آخر مقایسه می‌شوند:
        HH + HL → 'up'        (سقف بالاتر و کف بالاتر)
        LH + LL → 'down'      (سقف پایین‌تر و کف پایین‌تر)
        غیر آن  → 'range'     (هر اختلاف ≤ tol = ساختار «مساوی»/تخت)
    خروجی: {'trend', 'hh', 'hl', 'last_high', 'prev_high', 'last_low', 'prev_low'}
    تایم‌فریم با کمتر از دو پیوت کامل → trend='na' (غربگر/UI باید نال‌پذیر باشد).
    """
    highs = [s for s in swings if s["kind"] == "high"][-2:]
    lows = [s for s in swings if s["kind"] == "low"][-2:]
    base = {"trend": "na", "hh": None, "hl": None,
            "last_high": None, "prev_high": None, "last_low": None, "prev_low": None}
    if len(highs) < 2 or len(lows) < 2:
        return base
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
    return {"trend": trend, "hh": hh, "hl": hl,
            "last_high": round(h1, 2), "prev_high": round(h2, 2),
            "last_low": round(l1, 2), "prev_low": round(l2, 2)}


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


def _fts_fib_zones(candles, swings):
    """کمربندهای فیبوناچی در مقیاس لگاریتمی — متدولوژی FTS صفحهٔ ۲.

    چرا لگاریتم؟ در سهام‌های حرصیِ تالار شفاف، حرکت ×۴ و اصلاح ۵۰٪ آن در مقیاس
    خطی «کف» درست نمی‌دهد؛ نسبت اصلاح باید روی لگاریتم قیمت سنجیده شود
    (ret = ln(low) / ln(high) در ادبیات فیبو-لگاریتمی).

    بازهٔ اندازه‌گیری: آخرین سقف پیوت مهم ← پایین‌ترین کفِ «پس از آن سقف»
    (اگر کفی بعد از سقف نبود، پایین‌ترین کف کل بازه). خروجی دو کمربند:
        zone_33_40: ورود پس از «ادامهٔ روند» (کمربند کم‌عمق)
        zone_618_70: کمربند طلایی — منطقهٔ ورود اصلاحی کلاسیک FTS
    هر کمربند: {'lo', 'hi', 'in_zone'} — in_zone = قیمت پایانیِ آخر داخل کمربند.
    """
    highs = [s for s in swings if s["kind"] == "high"]
    if not highs:
        return None
    top = max(highs, key=lambda s: s["idx"])["price"]
    after = [c["low"] for c in candles
             if c["high"] <= top or True]      # کل بازه؛ فیلتر زمانی پایین‌تر
    hi_idx = max(range(len(candles)), key=lambda i: candles[i]["high"])
    lows_after = [c["low"] for c in candles[hi_idx:]] or after
    bot = min(lows_after) if lows_after else min(c["low"] for c in candles)
    if top <= 0 or bot <= 0 or top <= bot:
        return None
    ln_top, ln_bot = math.log(top), math.log(bot)

    def _band(p1, p2):
        lo_p = math.exp(ln_top + (ln_bot - ln_top) * p2)   # p2 بزرگ‌تر → قیمت پایین‌تر
        hi_p = math.exp(ln_top + (ln_bot - ln_top) * p1)
        return lo_p, hi_p

    z1_lo, z1_hi = _band(0.33, 0.40)
    z2_lo, z2_hi = _band(0.618, 0.70)
    last = float(candles[-1]["close"]) if candles else 0.0
    return {
        "retrace_base_high": round(top, 2), "retrace_base_low": round(bot, 2),
        "zone_33_40": {"lo": round(z1_lo, 2), "hi": round(z1_hi, 2),
                       "in_zone": bool(z1_lo <= last <= z1_hi)},
        "zone_618_70": {"lo": round(z2_lo, 2), "hi": round(z2_hi, 2),
                        "in_zone": bool(z2_lo <= last <= z2_hi)},
    }


def _fts_jet_setup(candles, lookback=_FTS_ENTRY_LOOKBACK):
    """ستاپ جت (Jet) — ورود شکست صعودی با تأیید پایانی روزانه.

    مقاومت مرجع = max(high) در پنجرهٔ lookback کندلی «پیش از» کندل آخر؛
    اگر آن مقاومت ≈ بیشینهٔ کل تاریخچه → پرچم ath هم روشن است (شکست سقف تاریخی).
    تریگر: پایانیِ امروزِ (کندل آخر) بالای آن مقاومت، با بدنهٔ صعودی
    (close > open تا کندل‌های شمشِ بالای مقاومتِ بدون تعهد تریگر نشوند).
    خروجی: {'active', 'resistance', 'ath', 'close', 'pct_above_res'}.
    """
    if len(candles) < lookback + 2:
        return {"active": False, "resistance": None, "ath": False,
                "close": None, "pct_above_res": None}
    window = candles[-lookback - 1:-1]
    res = max(c["high"] for c in window)
    ath_res = max(c["high"] for c in candles[:-1])
    last = candles[-1]
    active = (last["close"] > res) and (last["close"] >= last["open"])
    return {"active": bool(active), "resistance": round(res, 2),
            "ath": bool(abs(res - ath_res) / ath_res < 0.002 if ath_res else False),
            "close": round(float(last["close"]), 2),
            "pct_above_res": round((last["close"] - res) / res * 100.0, 2) if res else None}


def _fts_choch(candles, swings):
    """CHoCH (Change of Character) — شکست قطعیِ آخرین پیوتِ مخالف روند.

    روند فعلی از ساختار خوانده می‌شود:
      • در روند صعودی: CHoCH نزولی وقتی پایانیِ امروز زیر آخرین کف پیوتِ بالاتر
        (last_low) بسته شود — اولین نشانهٔ تغییر کاراکتر ساختار.
      • در روند نزولی: CHoCH صعودی وقتی پایانی امروز بالای آخرین سقف پیوتِ پایین‌تر
        (last_high) بسته شود — نشانهٔ برگشت صعودی (معیار ورود FTS روی نمادهای
        فرسوده‌شده).
      • در رنج/نا: شکست هر سمتِ آخرین سقف/کف پیوت گزارش می‌شود ولی «قطعی»
        نیست (label 'range-break').
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
    خروجی: {'touches', 'floor_price', 'active', 'floor_idx'}.
    """
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    out = {"touches": 0, "floor_price": None, "active": False, "floor_idx": None}
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
               active=touches >= 3, floor_idx=anchor_low["idx"])
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
    major_low = min(float(c["low"]) for c in candles[-20:])
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
    خروجی: {'third_peak', 'double_top', 'hs_break', 'neckline', 'level'}.
    """
    out = {"third_peak": False, "double_top": False, "hs_break": False,
           "neckline": None, "level": None}
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
            "D": _fts_classify_trend(swings_d),
            "W": _fts_classify_trend(_fts_swings(w, k=2)),
            "M": _fts_classify_trend(_fts_swings(m, k=2)),
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
    elif tW in ("range", "na"):
        out["trend"]["matrix"] = {
            "decision": "REJECT",
            "setup": "NONE",
            "desc": "تایم هفتگی خنثی/نامشخص — عدم ورود طبق چارت درختی FTS",
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
        else:
            out["trend"]["matrix"] = {
                "decision": "PERMITTED",
                "setup": "SWING_DOUBLE_BOTTOM_OR_RANGE",
                "desc": "هفتگی صعودی + روزانه خنثی: ستاپ کف دوقلو یا خرید در کف باکس رنج؛ نوسان‌گیری زیر ۳ ماه",
            }

    # استراتژی ساعت شنی پیشرفته FTS طبق بخش ۵ سند رسمی FTS v2.1
    closes_w = [float(c["close"]) for c in w] if w else []
    if len(closes_w) >= 15:
        period_ma = min(52, len(closes_w))
        ma52_w = _fts_ma(closes_w, period_ma)
        rsi5_w = _fts_rsi(closes_w, 5)
        last_cw = closes_w[-1]
        last_ma52 = ma52_w[-1] if ma52_w else None
        last_rsi5 = rsi5_w[-1] if rsi5_w else None
        is_hg_active = bool(last_ma52 and last_cw < last_ma52 and (last_rsi5 is not None and last_rsi5 <= 30.0))
        out["hourglass"] = {
            "active": is_hg_active,
            "weekly_close": round(last_cw, 2),
            "ma52": round(last_ma52, 2) if last_ma52 else None,
            "weekly_rsi5": round(last_rsi5, 1) if last_rsi5 is not None else None,
            "action": "ACCELERATE_BUY_2X_4X" if is_hg_active else "NORMAL",
            "desc": "اهرم شتاب‌دهنده ساعت شنی فعال: قیمت هفتگی زیر MA52 و RSI هفتگی اشباع فروش (خرید ۲ تا ۴ برابری)" if is_hg_active else "شرایط ساعت شنی برقرار نیست",
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
    return out


def _fts_analyze_symbol(symbol, entry_hint=None):
    """Cached single-symbol FTS payload for /api/fts/{symbol} and badges.

    Cache key = symbol + last daily close: intra-day live-candle churn
    recomputes freely, but repeated calls with unchanged closes (the common
    case for the badge strip polling the same symbol) are served from cache.
    TTL guards against a static close with drifting intraday fields.
    """
    import time as _t
    now = _t.time()
    try:
        db = get_chart_db(symbol, adjustment=3)
        candles = db.get("candles") or []
    except Exception as e:
        return {"status": "error", "symbol": symbol, "message": str(e)}
    if not candles:
        return {"status": "empty", "symbol": symbol, "fts": None}
    last_close = candles[-1].get("close")
    key = f"{symbol}|{last_close}"
    cached = FTS_ANALYSIS_CACHE.get(key)
    if cached and (now - cached[0]) < FTS_ANALYSIS_TTL:
        return cached[1]
    try:
        fts = _fts_analyze_candles(symbol, candles, entry_hint=entry_hint)
    except Exception as e:
        return {"status": "error", "symbol": symbol, "message": str(e)}
    result = {"status": "success", "symbol": symbol, "fts": fts}
    if len(FTS_ANALYSIS_CACHE) > FTS_ANALYSIS_CACHE_MAX:
        FTS_ANALYSIS_CACHE.clear()
    FTS_ANALYSIS_CACHE[key] = (now, result)
    return result


@router.get("/api/fts/{symbol}")
def get_fts(symbol: str):
    """Light analysis-only payload for the tech-view badge strip.

    Same FTS engine as the embedded chart payload; separate endpoint so the
    UI can refresh badges without refetching full candle history.
    """
    return _fts_analyze_symbol(symbol)

# __FTS_APPEND__
