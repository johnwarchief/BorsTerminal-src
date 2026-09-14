#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confidence_engine.py — موتور «تایید سه‌گانه» (تکنیکال / تابلو / بنیاد).

فلسفه: یک نماد زمانی قابل اعتماد است که سه ستون مستقل همزمان تاییدش کنند:

  ۱) conf_tech  — ساختار قیمت از `price_history` (روند، موقعیت در بازه، حجم)
  ۲) conf_tape  — پول بازیگران از `client_type` + `daily_prices` + `market_watch`
  ۳) conf_fund  — پنج شاخص FTS از `fts_engine` (بازاستفاده، نه بازنویسی)

این فایل عمداً سه چیز را انجام نمی‌دهد:
  * هیچ جدولی نمی‌سازد و چیزی ذخیره نمی‌کند — خروجی‌ها محاسبی‌اند و با هر sync
    عوض می‌شوند؛ماندنشان در دیتابیس یعنی دادهٔ کهنهٔ «درست‌نما».
  * هیچ route ای ثبت نمی‌کند و به HTTP وابسته نیست (مثل fts_engine.py).
  * ستون FTS را دوباره پیاده نمی‌کند؛ fts_engine تنها منبع حقیقت بنیادی است.

حالت «بی‌داده» (nodata) از «مردود» (fail) جداست. دلیلش داده‌های واقعی همین
market.db است: price_history برای ۲۵۱۵ نماد وجود دارد ولی فقط ۸۶۸تای آن ≥۶۰
کندل دارند، و daily_prices کلاً ۹ نشست دارد. اگر «داده نیست» همان «رد» حساب
شد، نمادهای سالم بی‌دلیل حذف می‌شدند — همان کلاس خطایی که در m141_map با
«نماد در نقشه نیست → مشمول نمی‌شود» جلویش گرفته شده.

منابع داده و محدودیت‌های واقعی‌شان (راستی‌آزمایی روی market.db v9.7.2):
  price_history.symbol  ==  instruments.l_val18  (نه l_val30، نه نوشتار فارسی)
  daily_prices          : فقط ۹ نشست  → مبنای حجم، «تمام نشست‌های قبلیِ موجود»
                          است نه ۳۰ روزه (۳۰ روزه در این بانک ساختنی نیست)
  client_type           : ۳۴۸۰ نماد، ۲۲۱۲ نماد در تازه‌ترین نشست
  date skew             : price_history تا ۲۰۲۶-۰۹-۰۱ و client_type تا ۲۰۲۶۰۹۰۸
                          → هر ستون `asof` خودش را برمی‌گرداند؛ همزمان فرض نشود.
"""
from __future__ import annotations

import math
import sqlite3
from typing import Optional

# norm_fa تنها راه امن مقایسهٔ نام‌های این بانک است (ی عربی/فارسی، کاف، نیم‌فاصله).
# import در سطح ماژول نهاده می‌شود چون fts_engine وابستگی شبکه/HTTP ندارد.
import fts_engine


# ============================================================ آستانه‌ها
# جدا از FTS_DEFAULTS است (آستانه‌های بنیادی در fts_thresholds.json می‌مانند).
# cfg دلخواه هر فراخواننده بر این پیش‌فرض‌ها سوار می‌شود.
CONF_DEFAULTS = {
    # ---- ستون تکنیکال ----
    "tech_min_bars": 40,        # کمتر از این → nodata (میانگین ۵۰ کندله ساختنی نیست)
    "tech_ma_fast": 20,
    "tech_ma_slow": 50,
    "tech_pos_window": 30,      # بازهٔ سنجش «کجا از دامنهٔ ۳۰ روزه ایستاده‌ایم»
    "tech_pos_min": 0.60,       # ≥۶۰٪ دامنه = نزدیک سقف، نه کف
    "tech_vol_recent": 3,       # میانگین حجم N کندل اخیر
    "tech_vol_base": 20,        # در برابر میانگین N کندل پیشین
    "tech_vol_mult": 1.10,      # ≥۱۰٪ انبساط حجم
    "tech_need": 2,             # از ۳ زیرسنجش
    # ---- ستون تابلوخوانی ----
    "tape_inst_ratio": 1.5,     # قدرت خرید حقوقی ÷ قدرت فروش حقوقی (همان f_jet)
    "tape_vol_mult": 2.0,       # حجم امروز ÷ مبنای نشست‌های قبلی
    "tape_min_trades": 30,      # حداقل تعداد معاملات (زیر آن حجم قابل‌اتکا نیست)
    "tape_lookback": 5,         # پنجرهٔ روند حقوقی
    "tape_need": 2,             # از ۳ زیرسنجش
    # ---- ستون بنیادی ----
    "fund_min_score": 4,        # امتیاز FTS لازم (۴ از ۵ = همان STRONG)
    # ---- داوری نهایی ----
    "min_coverage": 2,          # با کمتر از ۲ ستونِ دارای داده، رأی داده نمی‌شود
    # ================================================== v9.7.4 هشدار منعطف
    # دروازهٔ هفتگی دیگر «وتو» نیست؛ فقط وضعیت را از pass به warn می‌برد.
    # reason‌های واقعی برای اینکه هیچ سهمی از دید کاربر حذف نشود (خط قرمز).
    "tech_weekly_ma": 52,       # MA52 روی کندل هفتگی (بستهٔ هفتگی، نه ۵۲ روز)
    "tech_weekly_rsi": 7,       # RSI دورهٔ ۷ هفتگی — اشباع فروش
    "tech_weekly_rsi_oversold": 30.0,
    "tech_daily_ma_long": 100,  # MA100 روزانه
    "tech_stop_ma": 14,         # MA14 — مبنای حد ضرر نوسان‌گیر
    "tech_stop_below_pct": 0.05,   # ۵٪ زیر آخرین کف ماژور
    "tech_low_window": 20,      # پنجرهٔ یافتن کف ماژور
    "tech_weekly_fetch": 300,   # کندل خام لازم برای ساختن ۵۲ هفته
    "tech_pullback_band": 0.03,    # پولبک: بسته بالای MA20 و نه دورتر از ۳٪
    "tech_fib_lo": 0.5, "tech_fib_hi": 0.68,   # محدودهٔ طلایی فیبوناچی
    "tech_heavy_vol_mult": 2.0,    # حجم سنگین روی شکست باکس رنج
    "tech_rsi_daily": 14,       # RSI روزانه برای واگرایی
    "tech_div_back": 20,        # فاصلهٔ مقایسهٔ دو سقف در واگرایی
    # ---- پایهٔ تابلوخوانی (فقط گزارش، نه گیت) ----
    "tape_clock_pct": 1.0,      # الگوی ساعت: (آخرین-پایانی)/پایانی ≥ +۱٪
    "tape_suspicious_vol_mult": 3.0,   # حجم مشکوک ≥ ۳× میانگین
}

PILLAR_LABELS = {"tech": "تکنیکال", "tape": "تابلوخوانی", "fund": "بنیادی"}


def _f(v, default: float = 0.0) -> float:
    """تبدیل امن به float — همان محافظتِ fts_engine._f در برابر None/''/str."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _per(part: float, whole: float) -> Optional[float]:
    """تقسیم امن → None یعنی «قابل محاسبه نبود» (نه صفر). مخرج صفر/منفی رد می‌شود."""
    if whole is None or whole <= 0:
        return None
    return part / whole


PILLAR_STATES = ("pass", "warn", "fail", "nodata")


def _pillar(key: str, state: str, score: int = 0, max_score: int = 3,
            reasons=None, detail=None, asof=None) -> dict:
    """ساختار یکنواخت خروجیِ هر سه ستون.

    state ∈ {"pass", "warn", "fail", "nodata"}؛ `pass` فقط وقتی True است که state=='pass'.

    «warn» در v9.7.4 اضافه شد و جایگزین وتوی سخت است: یعنی ستون تأیید نکرده،
    ولی سهم را دور هم نمی‌اندازد. به همین دلیل `pass` عمداً فقط به
    state=='pass' برمی‌گردد — warn هرگز در شمارشِ conf_count نمی‌آید، پس
    ارتقای یک ستون به warn رأی نهایی را آن‌قدرها که باید نرم نمی‌کند.

    ValueError روی state ناشناخته: حالت پنجمِ بی‌نام یعنی یکی از ستون‌ها چیزی
    می‌سازد که UI و تست‌ها نمی‌شناسند؛ بی‌صدا رد کردنش یعنی یک وضعیتِ
    بی‌رنگِ خاکستری روی صفحه که کاربر معنایش را نمی‌داند.
    """
    if state not in PILLAR_STATES:
        raise ValueError("unknown pillar state %r for %r" % (state, key))
    reasons = list(reasons or [])
    return {
        "key": key,
        "label": PILLAR_LABELS.get(key, key),
        "state": state,
        "pass": state == "pass",
        "warn": state == "warn",
        "nodata": state == "nodata",
        "score": int(score),
        "max": int(max_score),
        "reasons": reasons,
        "detail": detail or {},
        "asof": asof,
    }


# ============================================ نرمال‌سازی کلید و resolve نماد
def norm(s) -> str:
    """همان norm_fa است — اینجا فقط یک نام کوتاه برای خوانایی فراخوان‌ها."""
    return fts_engine.norm_fa(s)


def symbol_index(conn: sqlite3.Connection) -> dict:
    """یک‌کوئری: هر نامِ قابل‌تطبیق → {ins_code, l_val18, sector, total_shares}.

    چرا این‌شکل: کلید اصلی price_history همان `instruments.l_val18` است (نوشتار
    خام TSETMC، اغلب با ي/ك عربی)، ولی کاربر و بقیهٔ مسیرها ممکن است l_val30 یا
    نوشتار فارسی بدهند. اگر مستقیم `symbol = ?` بزنیم، نمادهای عربی‌نویسی بی‌صدا
    «پیدا نمی‌شوند» — دقیقاً همان باگی که dev/fts_m141_parity_v97.py روی ۲۲۴ نماد
    گرفت و قفلش کرد. پس هر دو نام، زیر norm() ثبت می‌شوند.

    بازگشت: {"map": {norm_key: row}, "total_mcap_rials": float}
    """
    rows = conn.execute(
        "SELECT ins_code, l_val18, l_val30, sector_name, total_shares "
        "FROM instruments").fetchall()
    m = {}
    # دو پاس: نخست همهٔ l_val18 (نماد)، سپس l_val30 (نام شرکت). اگر در یک پاس
    # می‌شد، نام شرکتِ یک نماد می‌توانست با نمادِ نمادِ دیگری تصادم کند و بستهٔ
    # ترتیفِ ردیف‌ها، آن نام بر نماد غلبه می‌کرد. نماد همیشه اولویت دارد.
    for pas in (0, 1):
        for ins_code, l18, l30, sector, shares in rows:
            name = (l18, l30)[pas]
            if not name:
                continue
            m.setdefault(norm(name), {
                "ins_code": ins_code, "l_val18": l18 or "",
                "sector": sector or "سایر", "total_shares": _f(shares)})
    total = _f(conn.execute(
        "SELECT SUM(p_closing * total_shares) FROM market_watch").fetchone()[0])
    return {"map": m, "total_mcap_rials": total}


def resolve(index: dict, symbol: str) -> Optional[dict]:
    """نام کاربر → رکورد {ins_code, l_val18, sector, total_shares} یا None."""
    return (index.get("map") or {}).get(norm(symbol))


def tape_rows(conn: sqlite3.Connection, lookback: int = 5) -> dict:
    """آخرین `lookback` نشست client_type → {ins_code: [row, ...]} (تازه‌ترین اول).

    تک‌کوئری کل‌بازاری؛ build_ctx یک‌بار می‌سازد تا حلقهٔ نماد‌به‌نماد به N+1
    نیفتد (همان قراردادی که m141_map/avg_trade_value_hmt رعایت می‌کنند).
    """
    sess = [r[0] for r in conn.execute(
        "SELECT DISTINCT d_even FROM client_type ORDER BY d_even DESC LIMIT ?",
        (max(int(lookback), 1),))]
    if not sess:
        return {}
    ph = ",".join("?" * len(sess))
    rows = conn.execute(
        "SELECT ins_code, d_even, buy_i_vol, buy_count_i, sell_i_vol, sell_count_i, "
        "buy_n_vol, sell_n_vol FROM client_type WHERE d_even IN (%s) "
        "ORDER BY ins_code, d_even DESC" % ph, sess).fetchall()
    out: dict = {}
    for r in rows:
        out.setdefault(r[0], []).append({
            "d_even": r[1],
            "buy_i_vol": _f(r[2]), "buy_count_i": _f(r[3]),
            "sell_i_vol": _f(r[4]), "sell_count_i": _f(r[5]),
            "buy_n_vol": _f(r[6]), "sell_n_vol": _f(r[7]),
        })
    return out


def daily_map(conn: sqlite3.Connection, sessions: int = 12) -> dict:
    """نگاشت حجم/قیمت روزانه → {ins_code: [ {d_even, vol, close, change}, ... ]}.

    تازه‌ترین در ابتدا. `sessions` سقفِ نشست‌های recent است (daily_prices در این
    بانک فقط ۹ نشست دارد، پس سقف ۱۲ عملاً «همه» است).

    مبنای حجم از «همهٔ نشست‌ها به‌جز آخرین» ساخته می‌شود؛ یعنی مبنای today-ناپیوسته.
    این عمدی است: اگر امروز داخل مبنای خودش باشد، رشد حجم همیشه به سمت یک خنثی
    کشیده می‌شود و آستانهٔ `tape_vol_mult` بی‌معنی می‌گردد.
    """
    sess = [r[0] for r in conn.execute(
        "SELECT DISTINCT d_even FROM daily_prices ORDER BY d_even DESC LIMIT ?",
        (max(int(sessions), 2),))]
    if not sess:
        return {}
    ph = ",".join("?" * len(sess))
    rows = conn.execute(
        "SELECT ins_code, d_even, q_tot_tran, p_closing, price_change "
        "FROM daily_prices WHERE d_even IN (%s) "
        "ORDER BY ins_code, d_even DESC" % ph, sess).fetchall()
    out: dict = {}
    for ins_code, d_even, vol, close, change in rows:
        out.setdefault(ins_code, []).append({
            "d_even": d_even, "vol": _f(vol),
            "close": _f(close), "change": _f(change),
        })
    return out


def watch_map(conn: sqlite3.Connection) -> dict:
    """اسنپ‌شات آخرین روز market_watch → {ins_code: {z_tot_tran, p_last, ...}}.

    market_watch تنها یک ردیف به‌ازای ins_code دارد (کلید اصلی = ins_code)، پس
    این نقشه «فقط امروز» را می‌دهد و نمی‌تواند جانشین تاریخچهٔ daily_prices شود.
    """
    rows = conn.execute(
        "SELECT ins_code, d_even, p_closing, p_last, z_tot_tran, price_change "
        "FROM market_watch").fetchall()
    return {r[0]: {"d_even": r[1], "p_closing": _f(r[2]), "p_last": _f(r[3]),
                   "z_tot_tran": _f(r[4]), "price_change": _f(r[5])}
            for r in rows}


def watch_one(conn: sqlite3.Connection, ins_code: str) -> dict:
    """market_watch یک نماد — جایگزین تک‌کوئریِ watch_map برای مسیر بی‌ctx.

    چرا لازم است: بی‌این، فراخوانیِ تکیِ conf_fund (مثلاً از یک endpoint آینده)
    mcap را صفر حساب می‌کرد و شاخص ۴ FTS (فروش÷ارزش بازار) بی‌صدا می‌سوخت —
    یعنی همان «خطای داده‌ای که در لاگ دیده نمی‌شود».
    """
    row = conn.execute(
        "SELECT d_even, p_closing, p_last, z_tot_tran, price_change "
        "FROM market_watch WHERE ins_code=?", (ins_code,)).fetchone()
    if not row:
        return {}
    return {"d_even": row[0], "p_closing": _f(row[1]), "p_last": _f(row[2]),
            "z_tot_tran": _f(row[3]), "price_change": _f(row[4])}


def build_ctx(conn: sqlite3.Connection, cfg: dict = None) -> dict:
    """ساختِ یک‌بارهٔ نقشه‌های کل‌بازاری برای فراخوانی‌های پیدرپی.

    بدون ctx، هر conf_tape یک کوئریِ کل‌بازار می‌زند؛ برای ماتریس ۲۰نمادی این
    فاجعه است. با ctx، هر نقشه یک‌بار ساخته می‌شود (قرارداد ضدِN+1ِ fts_engine).
    """
    cfg = dict(CONF_DEFAULTS, **(cfg or {}))
    idx = symbol_index(conn)
    return {
        "cfg": cfg,
        "index": idx,
        "total_mcap_rials": idx["total_mcap_rials"],
        "tape": tape_rows(conn, int(cfg["tape_lookback"])),
        "daily": daily_map(conn),
        "watch": watch_map(conn),
        "sessions": fts_engine.market_sessions(conn),
        # تزریق نقشه‌های بنیادی: scan_symbol خودش این‌ها را تک‌کوئری می‌سازد،
        # ولی در حلقهٔ نماد‌به‌نماد به N+1 تبدیل می‌شوند. اینجا یک‌بار ساخته
        # و از مسیر m141_hit / avg_trade_val تزریق می‌شوند.
        "m141": fts_engine.m141_map(conn),
        "liq": fts_engine.avg_trade_value_hmt(conn),
    }


# ====================================================== کمک‌حساب‌های مشترک
def _cfg(ctx: dict = None, cfg: dict = None) -> dict:
    """ادغام سه‌لایه: پیش‌فرض ← cfgِ ctx ← cfgِ فراخواننده."""
    base = dict((ctx or {}).get("cfg") or CONF_DEFAULTS)
    base.update(cfg or {})
    return base


def _index(conn: sqlite3.Connection, ctx: dict = None) -> dict:
    return (ctx or {}).get("index") or symbol_index(conn)


def _sma(vals: list, n: int) -> Optional[float]:
    """میانگین N مقدار اول؛ داده کمتر از n → None (نه صفر)."""
    if n <= 0 or len(vals) < n:
        return None
    return sum(vals[:n]) / float(n)


def _mean(vals: list) -> Optional[float]:
    return (sum(vals) / float(len(vals))) if vals else None


def _x(v) -> str:
    """قالب ضریب برای متن: None → «-»."""
    return "-" if v is None else "%.2fx" % v


def _bars(conn: sqlite3.Connection, symbol: str, entry: dict = None,
          limit: int = 120):
    """کندل‌های price_history (تازه‌ترین اول).

    v9.7.3: قبلاً دو «تلاش» جدا با `symbol = ?` خام می‌زد (اول l_val18، بعد
    رشتهٔ ورودی). این همان باگ نوشتار مختلط بود: اگر price_history آن نماد را
    با «ي/ك» عربی نگه داشته باشد و هیچ‌کدام از آن دو رشته عربی نباشد، صفر ردیف
    برمی‌گشت و ستون تکنیکال «بی‌داده» می‌شد — یعنی رندر شدنِ «رند ندارد» برای
    سهمی که ۲۵۰ کندل دارد. حالا هر دو نام به symbol_aliases می‌روند و با یک
    کوئریِ ایندکسی (symbol IN) خوانده می‌شوند.

    قاعدهٔ حذف تکراری (date، symbol): price_history کلید PRIMARY KEY‌اش
    (symbol, date) است، پس یک شرکتِ دو-املا می‌تواند همان روز را دوبار داشته
    باشد. ادغام بی‌حذف‌تکراری یعنی شمردن دوبارهٔ یک کندل در میانگین/حجم.
    ترتیب SELECT هم `volume DESC` پس از `date DESC` می‌آید تا در تساویِ روز،
    رکورد پرحجم‌تر بماند و خروجی بین اجراها عوض نشود.
    """
    cands = []
    for k in (((entry or {}).get("l_val18")), symbol):
        if k and k not in cands:
            cands.append(k)
    al = []
    for k in cands:
        for a in fts_engine.symbol_aliases(k):
            if a not in al:
                al.append(a)
    if not al:
        return [], None
    rows = conn.execute(
        "SELECT date, close, high, low, volume FROM price_history "
        "WHERE symbol IN (%s) ORDER BY date DESC, volume DESC LIMIT ?"
        % ",".join("?" * len(al)), (*al, int(limit))).fetchall()
    seen, uniq = set(), []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        uniq.append(r)
    return (uniq, cands[0]) if uniq else ([], None)


from datetime import date as _date


# ============================ دروازهٔ نرم هفتگی (v9.7.4 — جانشین وتوی سخت)
def _week_key(iso: str):
    """کلید هفته از 'YYYY-MM-DD' → (سال ایزو, هفته) یا None برای تاریخ خراب."""
    try:
        return _date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10])).isocalendar()[:2]
    except (TypeError, ValueError):
        return None


def _weekly_closes(rows) -> list:
    """کندل‌های روزانه (تازه‌ترین اول) → بسته‌های هفتگی، تازه‌ترین اول.

    چرا «اولین ردیفِ هر هفته» درست است: ردیف‌ها نزولی‌اند، پس نخستین بار که یک
    هفته دیده می‌شود آن ردیف آخرین روز معاملاتیِ همان هفته است — یعنی close هفتگی.
    """
    out, seen = [], set()
    for r in rows:
        key = _week_key(str(r[0])[:10])
        if key is None or key in seen:
            continue
        seen.add(key)
        out.append(_f(r[1]))
    return out


def _rsi(closes, period: int):
    """RSI وایلدر روی سریِ بسته‌ها (تازه‌ترین اول) → آخرین مقدار، یا None.

    سری عمداً معکوس می‌شود: فرمول وایلدر روی ترتیبِ زمانیِ صعودی تعریف شده و
    اشتباه گرفتنِ جهت، RSI را به ۱۰۰−RSI تبدیل می‌کند (باگی ساکت و مخرب).
    """
    period = int(period)
    if period < 2 or len(closes) < period + 1:
        return None
    ser = [_f(x) for x in reversed(list(closes))]
    avg_g = avg_l = None
    for i in range(1, len(ser)):
        ch = ser[i] - ser[i - 1]
        g, l = (ch if ch > 0 else 0.0), (-ch if ch < 0 else 0.0)
        if i <= period:
            avg_g = (avg_g or 0.0) + g / period
            avg_l = (avg_l or 0.0) + l / period
        else:
            avg_g = (avg_g * (period - 1) + g) / period
            avg_l = (avg_l * (period - 1) + l) / period
    if avg_l is None:
        return None
    if avg_l <= 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + (avg_g / avg_l))


def _weekly_gate(rows, c: dict) -> dict:
    """MA52 هفتگی + RSI7 هفتگی + MA100 روزانه → فقط هشدار، هرگز رد نیست.

    `weak` تنها وقتی True است که «داده باشد و صعودی نباشد». کمبود داده weak نیست:
    ۵۲ هفته ≈ ۲۶۰ نشست است و نمادهای جدیدالورود آن را ندارند؛ اگر بی‌داده را ضعیف
    بشماریم هر سهم تازه‌وارد بی‌دلیل برچسب هشدار می‌گیرد.
    """
    wc = _weekly_closes(rows)
    need = int(c["tech_weekly_ma"])
    out = {"w_bars": len(wc), "ma52": None, "rsi7": None, "oversold": None,
           "bullish": None, "weak": None, "ma100": None}
    if len(wc) >= need and wc[0] > 0:
        ma = sum(wc[:need]) / float(need)
        out["ma52"] = ma
        out["bullish"] = bool(wc[0] > ma)
        out["weak"] = not out["bullish"]
        r = _rsi(wc, int(c["tech_weekly_rsi"]))
        out["rsi7"] = r
        if r is not None:
            out["oversold"] = bool(r <= _f(c["tech_weekly_rsi_oversold"], 30.0))
    out["ma100"] = _sma([_f(r[1]) for r in rows], int(c["tech_daily_ma_long"]))
    return out


def _choch(highs, closes):
    """CHoCH: پس از یک سقفِ پایین‌تر، بستهٔ فعلی همان سقف را می‌شکند.

    None یعنی پیوتِ کافی نبود (نه «نداشت»). فقط گزارش می‌شود؛ در رأی نقشی ندارد.
    """
    if len(highs) < 12 or not closes:
        return None
    piv = []
    for i in range(1, min(len(highs) - 1, 40)):
        if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]:
            piv.append(highs[i])
        if len(piv) >= 2:
            break
    if len(piv) < 2:
        return None
    newest, prev = piv[0], piv[1]
    if newest >= prev:          # سقف پایین‌تر نداشته‌ایم → ساختار نزولی نبوده
        return None
    return bool(closes[0] > newest)


def _bearish_div(closes, highs, c: dict):
    """واگرایی نزولی RSI: سقف قیمتی بالاتر، ولی RSIِ همان لحظه پایین‌تر."""
    period, back = int(c["tech_rsi_daily"]), int(c["tech_div_back"])
    if len(closes) < back * 3 or len(highs) < back * 3:
        return None
    r_now, r_then = _rsi(closes, period), _rsi(closes[back:], period)
    if r_now is None or r_then is None:
        return None
    prior = highs[back:back * 3]
    return bool(prior and closes[0] >= max(prior) and r_now < r_then)


def _daily_setups(closes, highs, lows, vols, c: dict) -> dict:
    """ستاپ‌های روزانهٔ FTS: breakout / pullback / fibonacci / CHoCH.

    همه پرچم اطلاعاتی‌اند، نه گیت. نسخهٔ سختِ این شرط‌ها در v9.7.3 باعث شد
    سهم‌های نوسان‌گیری از لیست حذف شوند؛ اینجا فقط «هست یا نیست» گزارش می‌شود.
    """
    s, n = {}, len(closes)
    if n >= 21:
        s["breakout"] = bool(closes[0] > max(highs[1:21]))
        base = _mean(vols[1:21])
        s["heavy_volume"] = bool(
            base and base > 0 and vols[0] / base >= _f(c["tech_heavy_vol_mult"], 2.0))
    ma20 = _sma(closes, 20)
    if ma20 and closes[0]:
        s["pullback"] = bool(ma20 < closes[0] <= ma20 * (1.0 + _f(c["tech_pullback_band"], 0.03)))
    if n >= 60:
        hi, lo = max(highs[:60]), min(lows[:60])
        if hi > lo > 0:
            retr = (hi - closes[0]) / (hi - lo)
            s["fibonacci"] = bool(_f(c["tech_fib_lo"], 0.5) <= retr <= _f(c["tech_fib_hi"], 0.68))
    s["choch"] = _choch(highs, closes)
    s["bearish_div"] = _bearish_div(closes, highs, c)
    return s


def _stop_refs(closes, lows, c: dict) -> dict:
    """مراجع حد ضرر — Phase 3 (کارتابل پورتفوی) همین‌ها را مصرف می‌کند.

    نوسان‌گیر: «۵٪ زیر آخرین کف ماژور» یا «کسرِ کندل پایانی زیر MA14». هر دو اینجا
    محاسبه می‌شوند تا پورتفوی تصمیمِ دوباره‌سازی‌شده نگیرد و هر دو مسیر قابل تست بماند.
    """
    ma14 = _sma(closes, int(c["tech_stop_ma"]))
    win, rl = int(c["tech_low_window"]), None
    half = max(int(c["tech_div_back"]) // 4, 3)
    for i in range(1, min(len(lows) - 1, win * 3)):
        seg = lows[max(i - half, 0):i + half + 1]
        # «<= min» تنها کافی نیست: روی سریِ صافِ ۱۰۰،۱۰۰،... هر ردیفی کفِ محلی
        # خودش است و کفِ جعلیِ جلسهٔ اول گزارش می‌شود. پس باید واقعاً پایین‌تر باشد.
        if lows[i] <= min(seg) and lows[i] < max(seg):
            rl = lows[i]
            break
    return {"ma14": ma14, "rising_low": rl,
            "swing_stop": None if rl is None else rl * (1.0 - _f(c["tech_stop_below_pct"], 0.05))}


# ============================================ ستون ۱: تکنیکال (price_history)
def conf_tech(conn: sqlite3.Connection, symbol: str, ctx: dict = None,
              cfg: dict = None) -> dict:
    """روند + موقعیت در دامنه + انبساط حجم؛ ۲ از ۳ زیرسنجش لازم است.

    هر زیرسنجش می‌تواند None (بی‌داده) برگرداند و آن‌وقت در مخرج شمارش نمی‌آید:
    روی نمادی با ۴۵ کندل، میانگین ۵۰ روزه ساختنی نیست ولی موقعیت در دامنهٔ
    ۳۰ روزه همچنان معنا دارد.

    لایهٔ v9.7.4 *روی* همان امتیازِ روزانه می‌نشیند (دروازهٔ نرم هفتگی + ستاپ‌ها)،
    پس هیچ ادعای پیشینی دربارهٔ score/reason های روزانه نمی‌شکند، جز جایی که state
    از pass به warn می‌رود — که همان خواستهٔ اصلی است: وتو حذف شود، هشدار بماند.
    """
    c = _cfg(ctx, cfg)
    entry = resolve(_index(conn, ctx), symbol)
    need_bars = int(c["tech_min_bars"])
    rows, _used = _bars(conn, symbol, entry,
                        limit=max(need_bars * 3, int(c["tech_weekly_fetch"])))
    n = len(rows)
    asof = rows[0][0] if rows else None
    if n < need_bars:
        return _pillar("tech", "nodata",
                       reasons=["کندل کافی نیست (%d < %d)" % (n, need_bars)],
                       detail={"bars": n}, asof=asof)

    closes = [_f(r[1]) for r in rows]
    fast, slow = int(c["tech_ma_fast"]), int(c["tech_ma_slow"])
    ma_f, ma_s = _sma(closes, fast), _sma(closes, slow)
    trend = None if (ma_f is None or ma_s is None) else bool(closes[0] > ma_f > ma_s)

    w = min(int(c["tech_pos_window"]), n)
    hi = max(_f(r[2]) for r in rows[:w])
    lo = min(_f(r[3]) for r in rows[:w])
    pos = None if hi <= lo else (closes[0] - lo) / (hi - lo)
    pos_ok = None if pos is None else bool(pos >= _f(c["tech_pos_min"], 0.6))

    rn = max(int(c["tech_vol_recent"]), 1)
    bn = min(int(c["tech_vol_base"]), max(n - rn, 0))
    vols = [_f(r[4]) for r in rows]
    vol_ratio, vol_ok = None, None
    if bn >= 5:
        rec, base = _mean(vols[:rn]), _mean(vols[rn:rn + bn])
        if rec is not None and base and base > 0:
            vol_ratio = rec / base
            vol_ok = bool(vol_ratio >= _f(c["tech_vol_mult"], 1.1))

    checks = {"trend": trend, "range_position": pos_ok, "volume": vol_ok}
    decided = [v for v in checks.values() if v is not None]
    if not decided:
        return _pillar("tech", "nodata", reasons=["هیچ زیرسنجش قابل‌محاسبه نبود"],
                       detail={"bars": n}, asof=asof)
    score = sum(1 for v in decided if v)

    if trend is None:
        r_trend = "روند: کندل برای %dMA کم است" % slow
    elif trend:
        r_trend = "روند صعودی (بسته > %dMA > %dMA)" % (fast, slow)
    else:
        r_trend = "روند صعودی نیست"
    if pos is None:
        r_pos = "دامنهٔ قابل‌محاسبه نبود"
    elif pos_ok:
        r_pos = "نزدیک سقف دامنهٔ %d روزه (%.0f%%)" % (w, pos * 100)
    else:
        r_pos = "کف/میانهٔ دامنهٔ %d روزه (%.0f%%)" % (w, pos * 100)
    if vol_ratio is None:
        r_vol = "مبنای حجم کمتر از ۵ نشست"
    elif vol_ok:
        r_vol = "انبساط حجم %s مبنای %d روزه" % (_x(vol_ratio), bn)
    else:
        r_vol = "حجم منقبض (%s)" % _x(vol_ratio)

    need = min(int(c["tech_need"]), len(decided))
    state = "pass" if score >= need else "fail"

    # ---- دروازهٔ نرم هفتگی (v9.7.4، سیاست v9.7.5) ----
    # warn فقط وقتی صادر می‌شود که «ستاپ روزانه برقرار است ولی روند هفتگی ضعیف».
    # اگر ستاپ روزانه کلاً fail باشد، وضعیت همان fail می‌ماند (قرمز) — ضعف هفتگی
    # نمی‌تواند یک ستاپ خراب را «کهربایی» کند، وگرنه کاربرِ داشبورد نمی‌فهمد کدام
    # سهم واقعاً شرایط خرید دارد و کدام فقط «بدتر از آن است که رد شود».
    # دلیل ضعف هفتگی در هر دو حالت در reasons می‌ماند (پنهان نمی‌شود).
    gates = _weekly_gate(rows, c)
    highs, lows = [_f(r[2]) for r in rows], [_f(r[3]) for r in rows]
    reasons = [r_trend, r_pos, r_vol]
    if gates["weak"] is True:
        if state == "pass":
            state = "warn"
            reasons.insert(0, "⚠️ روند هفتگی ضعیف (بستهٔ آخر زیر MA%d هفتگی)"
                           % int(c["tech_weekly_ma"]))
        else:
            reasons.append("روند هفتگی هم ضعیف است (بستهٔ آخر زیر MA%d هفتگی)"
                           % int(c["tech_weekly_ma"]))
    elif gates["oversold"] is True:
        reasons.insert(0, "⚠️ RSI هفتگی در اشباع فروش (%.0f)" % gates["rsi7"])
    if gates["ma100"] and closes[0] and closes[0] < gates["ma100"]:
        reasons.append("بستهٔ آخر زیر MA%d روزانه" % int(c["tech_daily_ma_long"]))

    setups = _daily_setups(closes, highs, lows, vols, c)
    if setups.get("bearish_div"):
        reasons.insert(0, "⚠️ واگرایی نزولی RSI")

    return _pillar("tech", state, score=score, max_score=len(decided),
                   reasons=reasons, asof=asof,
                   detail={"bars": n, "close": closes[0], "ma_fast": ma_f,
                           "ma_slow": ma_s, "range_pos": pos, "vol_ratio": vol_ratio,
                           "checks": checks, "need": need,
                           "weekly": gates, "setups": setups,
                           "stop_refs": _stop_refs(closes, lows, c)})


# ========================================= ستون ۲: تابلوخوانی (client_type)
def conf_tape(conn: sqlite3.Connection, symbol: str, ctx: dict = None,
              cfg: dict = None) -> dict:
    """پول حقوقی + انبساط حجم + پذیرش قیمت؛ ۲ از ۳ زیرسنجش لازم است.

    تعاریف از فیلترهای زندهٔ app.py گرفته شده‌اند (f_jet: قدرت خرید حقوقی
    ≥ ۱٫۵ × قدرت فروش حقوقی؛ f_clock: حجم > مبنای ۳۰ روزه و تعداد معامله > ۳۰)
    ولی فقط با داده‌های موجود در market.db — ستون‌هایی مثل month_avg_vol و
    min30_low که API-محورند و در بانک نیست اینجا استفاده نمی‌شوند.
    """
    c = _cfg(ctx, cfg)
    # ctx باید کامل باشد (ساختهٔ build_ctx). ctxِ نیمه، ستون‌ها را بی‌صدا
    # «بدون داده» می‌کرد؛ پس ناقص را دور می‌اندازیم و یک‌بار خودمان می‌سازیم.
    need_maps = ("index", "tape", "daily", "watch")
    x = ctx if ctx and all(k in ctx for k in need_maps) else build_ctx(conn)
    entry = resolve(x["index"], symbol)
    ins = (entry or {}).get("ins_code")
    if not ins:
        return _pillar("tape", "nodata", reasons=["نماد در instruments پیدا نشد"])

    tape = x["tape"].get(ins) or []
    daily = x["daily"].get(ins) or []
    watch = x["watch"].get(ins) or {}
    if not tape:
        return _pillar("tape", "nodata", reasons=["ردیف حقوقی در client_type نیست"],
                       asof=(daily[0]["d_even"] if daily else None))

    # دروازهٔ اعتبار: بدون تعداد معاملهٔ معنادار، حجم قابل‌اتکا نیست (همان f_clock)
    trades = _f(watch.get("z_tot_tran"))
    if trades and trades < _f(c["tape_min_trades"], 30):
        return _pillar("tape", "nodata",
                       reasons=["تعداد معاملات %d < %d — حجم قابل‌اتکا نیست"
                                % (int(trades), int(c["tape_min_trades"]))],
                       asof=watch.get("d_even"), detail={"trades": trades})

    t0 = tape[0]
    inst_net = t0["buy_i_vol"] - t0["sell_i_vol"]
    if t0["buy_i_vol"] + t0["sell_i_vol"] <= 0:
        return _pillar("tape", "nodata",
                       reasons=["هیچ فعالیت حقوقی در پنجرهٔ %d نشست نیست"
                                % len(tape)], asof=t0["d_even"])

    # قدرت = حجم به‌ازای هر معامله (buy_pow / sell_pow در app.py)
    buy_pow = _per(t0["buy_i_vol"], t0["buy_count_i"])
    sell_pow = _per(t0["sell_i_vol"], t0["sell_count_i"])
    pow_ratio = (buy_pow / sell_pow) if (buy_pow and sell_pow and sell_pow > 0) else None
    accum = None if pow_ratio is None else bool(
        inst_net > 0 and pow_ratio >= _f(c["tape_inst_ratio"], 1.5))

    # انبساط حجم: آخرین نشست در برابر مبنای نشست‌های پیشین
    vol_ratio, vol_ok = None, None
    if len(daily) >= 2:
        base = _mean([d["vol"] for d in daily[1:]])
        if base and base > 0:
            vol_ratio = daily[0]["vol"] / base
            vol_ok = bool(vol_ratio >= _f(c["tape_vol_mult"], 2.0))

    # پذیرش قیمت: تغییر مثبت و بستن در یا بالای آخرین معامله
    change = _f(watch.get("price_change")) if watch else (daily[0]["change"] if daily else None)
    p_closing = _f(watch.get("p_closing")) if watch else (daily[0]["close"] if daily else 0.0)
    p_last = _f(watch.get("p_last")) if watch else 0.0
    accept = None if change is None or p_closing <= 0 else bool(
        change > 0 and (p_last <= 0 or p_closing >= p_last))

    # ---- الگوی ساعت (v9.7.4): اختلاف آخرین و پایانی ≥ +۱٪ ----
    # عمداً به `checks` اضافه نشد تا امتیاز و مخرجِ سه‌گانهٔ v9.7.3 دست‌نخورده بماند؛
    # اینجا نشانهٔ هشدار است، نه چهارمین زیرسنجش. صفرِ بی‌داده با None فرق دارد:
    # p_last در نشست بسته‌شده معمولاً صفر است و «صفر» یعنی داده نیست، نه «کاهش».
    lf_pct = None
    if p_closing > 0 and p_last > 0:
        lf_pct = (p_last - p_closing) * 100.0 / p_closing
    clock = None if lf_pct is None else bool(lf_pct >= _f(c["tape_clock_pct"], 1.0))
    vol_suspect = None if vol_ratio is None else bool(
        vol_ratio >= _f(c["tape_suspicious_vol_mult"], 3.0))

    checks = {"accumulation": accum, "volume": vol_ok, "price_accept": accept}
    decided = [v for v in checks.values() if v is not None]
    if not decided:
        return _pillar("tape", "nodata", reasons=["زیرسنجش قابل‌محاسبه نبود"],
                       asof=t0["d_even"])
    score = sum(1 for v in decided if v)

    if accum is None:
        r_a = "قدرت حقوقی قابل‌محاسبه نبود (تعداد معامله صفر)"
    elif accum:
        r_a = "خرید خالص حقوقی %s، قدرت %s فروش" % ("{:+,.0f}".format(inst_net), _x(pow_ratio))
    else:
        r_a = "حقوقی انباشت نمی‌کند (خالص %s، قدرت %s)" % ("{:+,.0f}".format(inst_net), _x(pow_ratio))
    r_v = ("مبنای حجم بی‌معنا (نشست قبلی نیست)" if vol_ratio is None
           else "انبساط حجم %s مبنای %d نشست" % (_x(vol_ratio), max(len(daily) - 1, 0))
           if vol_ok else "حجم رشد نکرده (%s)" % _x(vol_ratio))
    r_p = ("پذیرش قیمت (تغییر %s)" % ("{:+,.0f}".format(change)) if accept
           else "بدون تغییر مثبت (تغییر %s)" % ("{:+,.0f}".format(change) if change is not None else "-"))
    need = min(int(c["tape_need"]), len(decided))
    state = "pass" if score >= need else "fail"
    reasons = [r_a, r_v, r_p]
    if clock:
        reasons.append("⚠️ الگوی ساعت: اختلاف آخرین و پایانی %+.2f%%" % lf_pct)
        if state == "fail":
            state = "warn"          # ستارهٔ صف ⇒ هشدار، نه حذف از لیست
    if vol_suspect:
        reasons.append("⚠️ حجم مشکوک %s مبنای نشست‌های پیش" % _x(vol_ratio))
        if state == "fail":
            state = "warn"
    return _pillar("tape", state, score=score,
                   max_score=len(decided), reasons=reasons, asof=t0["d_even"],
                   detail={"inst_net": inst_net, "buy_pow": buy_pow, "sell_pow": sell_pow,
                           "pow_ratio": pow_ratio, "vol_ratio": vol_ratio, "accept": accept,
                           "last_vs_closing_pct": lf_pct, "clock": clock,
                           "vol_suspect": vol_suspect,
                           "trades": trades, "sessions": len(tape),
                           "inst_days_pos": sum(1 for t in tape if t["buy_i_vol"] > t["sell_i_vol"]),
                           "checks": checks, "need": need})


# ================================= ستون ۳: بنیادی (بازاستفاده از fts_engine)
def _fund_has_data(d: dict) -> bool:
    """آیا واقعاً دادهٔ عددی بنیادی وجود دارد، یا فقط اسکنر «پاس نشد» داده؟

    دام واقعی: fts_engine برای نمادِ بی‌صورت‌مالی، `eps_trend` را به‌صورت dict
    برمی‌گرداند (با years_available=0 و data_gap=True) در حالی که growth/
    gross_margin/sales_to_mcap را None می‌کند. اگر «dict بودنِ eps_trend» را نشانهٔ
    داده بدانیم، هر رشتهٔ بی‌ربطِ واردشده امتیاز ۱ از ۵ می‌گیرد (فقط شاخص صنعت
    «خنثی» است و پاس می‌شود) و ستون بنیادی «مردود» اعلام می‌کند — درحالی‌که
    پاسخ درست «نظر نمی‌دهم» است. پس شاخص صنعت را دلیلِ داده نمی‌دانیم.
    """
    for k in ("growth", "gross_margin", "sales_to_mcap"):
        if d.get(k) is not None:
            return True
    e = d.get("eps_trend") or {}
    if isinstance(e, dict) and not e.get("data_gap"):
        if _f(e.get("years_available")) > 0 or (e.get("eps_series") or []):
            return True
    return False


def fund_from_bulk(row: dict) -> dict:
    """رکورد `fts_engine.bulk_scan` → همان شکل `scan_symbol` که ستون بنیادی می‌خورد.

    چرا لازم است: scan_symbol به‌ازای هر نماد ~۲۴ کوئری می‌زند (۱۹تایش روی
    financial_statements)؛ bulk_scan همان پنج شاخص را برای کل بازار با چند
    کوئری تک‌گذر می‌سازد. برای ماتریسِ تایید سه‌گانه، مسیر درستِ ضدِN+1 همین است.

    دو ستون که bulk_scan ندارد، اینجا ساخته می‌شود: `passes` (از i1..i5) و
    `verdict`. فرمول verdict از scan_symbol الگوبرداری شده و گارد
    dev/confidence_engine_v973.py هم‌ارزی دو مسیر را روی نماد زنده می‌سنجد؛
    یعنی اگر روزی آستانه‌ها عوض شود، این‌جا بی‌صدا از قضا در نمی‌رود.
    """
    passes = {"1_growth": bool(row.get("i1_pass")),
              "2_eps_trend": bool(row.get("i2_pass")),
              "3_gross_margin": bool(row.get("i3_pass")),
              "4_sales_to_mcap": bool(row.get("i4_pass")),
              "5_industry": bool(row.get("i5_pass"))}
    reasons = row.get("exclusion_reasons") or ""
    if isinstance(reasons, str):
        reasons = [x.strip() for x in reasons.split("·") if x.strip()]
    excluded = bool(row.get("excluded")) or bool(reasons)
    score = int(_f(row.get("score")))
    series = row.get("eps_series")
    eps = None
    if series or not row.get("eps_data_gap"):
        eps = {"eps_series": series or [], "data_gap": bool(row.get("eps_data_gap")),
               "years_available": len(series or []), "pass": bool(row.get("i2_pass"))}
    # دامِ خودِ fts_engine: bulk_scan وقتی هیچ گزارش ماهانه‌ای نیست (`annualize_months=0`)
    # مقدار sales_to_mcap را 0.0 می‌گذارد، ولی scan_symbol همان‌جا None می‌دهد.
    # صفرِ بی‌داده باعث می‌شد ستون بنیادی «مردود» بگوید جایی که حقِ پاسخ
    # «نظر نمی‌دهم» است (دو نماد زنده این را نشان داد). پس صفر را فقط وقتی
    # می‌پذیریم که واقعاً فروش سالانهٔ Annualized ساخته شده باشد.
    months = int(_f(row.get("annualize_months")))
    s2m_raw = row.get("sales_to_mcap")
    s2m = None if (s2m_raw is None or months <= 0) else {"ratio": s2m_raw}
    return {
        "symbol": row.get("symbol"), "sector": row.get("sector_name") or "",
        "pricing_mode": row.get("pricing_mode"), "market_cap_rials": _f(row.get("mcap")),
        "score": score, "passes": passes, "excluded": excluded,
        "exclusion_reasons": list(reasons), "m141": bool(row.get("m141")),
        "avg_trade_val_hmt": row.get("avg_trade_val_hmt"),
        "detail": {
            "growth": None if row.get("rev_growth") is None else {"growth": row.get("rev_growth")},
            "eps_trend": eps,
            "gross_margin": None if row.get("gross_margin") is None else {"margin": row.get("gross_margin")},
            "sales_to_mcap": s2m,
            "profit_potential": None if row.get("profit_potential_pct") is None
            else {"potential_pct": row.get("profit_potential_pct")},
        },
        "verdict": ("EXCLUDED" if excluded else
                    "STRONG" if score >= 4 else "WATCH" if score >= 3 else "REJECT"),
        "_from_bulk": True,
    }


class FundMap(dict):
    """نگاشت norm(symbol) → رکورد bulk_scan، به‌همراه مرزِ پوشش دادهٔ بنیادی.

    `.covered` مهم‌تر از خودِ نگاشت است: نبودنِ یک نماد در bulk_scan تنها وقتی
    یعنی «صورت مالی ندارد» که در financial_statements/monthly_sales هم نباشد.
    bulk_scan فقط نمادهای دارای صورت‌مالی ۱۲ماهه را می‌شمارد، ولی scan_symbol
    می‌تواند رشد فروش را از گزارش ماهانهٔ نمادی بدون صورت‌مالی سالانه هم بسازد؛
    پس بدون `.covered`، آن نمادها بی‌صدا «بی‌داده» می‌شدند.
    """

    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.covered = set(self.keys())


def fund_map(conn: sqlite3.Connection, cfg: dict = None) -> FundMap:
    """ماتریس بنیادی کل‌بازار با یک گذر bulk_scan (جایِ N فراخوانی scan_symbol)."""
    fm = FundMap()
    for r in fts_engine.bulk_scan(conn, cfg=cfg or {}):
        fm[norm(r.get("symbol") or "")] = r
    covered = set(fm.keys())
    for tbl in ("financial_statements", "monthly_sales"):
        for (v,) in conn.execute("SELECT DISTINCT symbol FROM %s" % tbl):
            covered.add(norm(v or ""))
    fm.covered = covered
    return fm


def conf_fund(conn: sqlite3.Connection, symbol: str, ctx: dict = None,
              cfg: dict = None, fts: dict = None, fts_cfg: dict = None) -> dict:
    """آرایهٔ بنیادی = همان نتیجهٔ fts_engine.scan_symbol، بدون بازنویسی منطق.

    دو نکته که بی‌آن‌ها غلط از آب در می‌آید:

    ۱) نماد حل‌شده (`l_val18`) به fts_engine داده می‌شود، نه رشتهٔ ورودی کاربر.
       از v9.7.3 این دیگر «شرط کافی» نیست و فقط دقتِ اضافه است: fts_engine خودِ
       کوئری‌هایش را با symbol_aliases می‌زند، پس هر دو نوشتار پیدا می‌شوند.
       (پیش از آن، `symbol = ?` خام رشتهٔ فارسی را در financial_statementsِ
       عربی‌نویسی بی‌صدا صفر ردیف می‌کرد و هر پنج شاخص None می‌شدند.)

    ۲) نقشه‌های m141/liq از ctx تزریق می‌شوند تا در ماتریسِ چند‌نمادی N+1 نشود
       (بی‌ctx هم درست است، فقط scan_symbol خودشان را یک‌بار می‌سازد).

    `fts` از بیرون قابل تزریق است تا فراخواننده‌ای که نتایج bulk_scan را از پیش
    دارد همان‌ها را پاس بدهد و اصلاً کوئری نزند.
    """
    c = _cfg(ctx, cfg)
    x = ctx or {}
    idx = x.get("index") or symbol_index(conn)
    entry = resolve(idx, symbol)
    db_symbol = (entry or {}).get("l_val18") or symbol
    ins = (entry or {}).get("ins_code")
    watch = ((x.get("watch") or {}).get(ins) if x.get("watch")
             else watch_one(conn, ins)) if ins else None
    watch = watch or {}
    mcap = _f(watch.get("p_closing")) * _f((entry or {}).get("total_shares"))
    sector = (entry or {}).get("sector") or "سایر"
    total_mcap = _f(x.get("total_mcap_rials") or idx.get("total_mcap_rials"))
    key = norm(db_symbol)

    if fts is None:
        # اگر ctx نقشهٔ m141 را ساخته، bool تزریق می‌شود تا در ماتریس چند‌نمادی
        # یک کوئریِ کل‌بازار به‌ازای نماد (N+1) زده نشود؛ نمادِ غایب از m141
        # مشمول نیست، دقیقاً همان چیزی که bulk_scan نتیجه می‌گیرد.
        m141 = None if not x.get("m141") else bool(x["m141"].get(key, False))
        # liq عمداً `.get(key)` است نه `.get(key, 0.0)`: همان قرارداد bulk_scan.
        # صفرِ جعلی وقتی min_trade_val روشن باشد «نقدشوندگی کمتر از آستانه» تولید
        # می‌کند در حالی که None یعنی «نمی‌دانم» و فیلتر را رد می‌کند. برای نمادی
        # که در نقشه نیست، scan_symbol یک‌بار خودش محاسبه می‌کند (کوئریِ ~۳۵ms)؛
        # این هزینهٔ آگاهانهٔ حفظ هم‌ارزی با /api/fts/{symbol} است، نه باگ.
        liq = None if not x.get("liq") else x["liq"].get(key)

        # دو املا، یک نماد: در همین market.db جدول financial_statements برخی نمادها
        # را با ي عربی و برخی را با ی فارسی ذخیره کرده (۲۱ گروهِ تکراری اندازه‌گیری
        # شده روی market.db v9.7.2). ریشهٔ باگ در v9.7.3 داخل fts_engine درست شد
        # (symbol_aliases)، پس این حلقه دیگر «تلاش برای پیدا کردن داده» نیست؛
        # فقط وقتی دومین فراخوانی می‌شود که l_val18 واقعاً نامِ دیگری باشد.
        cands = []
        for k in (symbol, db_symbol):
            if k and k not in cands:
                cands.append(k)
        for cand in cands:
            fts = fts_engine.scan_symbol(
                conn, cand, mcap, total_mcap, sector, cfg=fts_cfg or {},
                _sessions=x.get("sessions"), m141_hit=m141,
                avg_trade_val=liq)
            if _fund_has_data(fts.get("detail") or {}):
                break

    if "i1_pass" in fts:        # رکوردِ bulk_scan → به شکل scan_symbol درمی‌آید
        fts = fund_from_bulk(fts)
    d = fts.get("detail") or {}
    passes = fts.get("passes") or {}
    score = int(_f(fts.get("score")))
    if not _fund_has_data(d):
        return _pillar("fund", "nodata",
                       reasons=["صورت مالی/گزارش ماهانه‌ای برای این نماد نیست"],
                       detail={"score": score, "verdict": fts.get("verdict"),
                               "db_symbol": db_symbol})

    if fts.get("excluded"):
        # v9.7.4: حذف خودکار FTS دیگر وتو نیست — فقط warn. سهم در لیست می‌ماند و
        # کاربر خودش تصمیم می‌گیرد؛ متنِ دلیل هم عیناً به conf_reasons می‌رود.
        return _pillar("fund", "warn", score=score, max_score=5,
                       reasons=["⚠️ ماده ۱۴۱ / زیان‌ده — حذف نشد، فقط هشدار: " + " · ".join(
                           fts.get("exclusion_reasons") or [])],
                       detail={"score": score, "verdict": "EXCLUDED",
                               "warn_only": True,
                               "pricing_mode": fts.get("pricing_mode"),
                               "passes": passes, "db_symbol": db_symbol})

    need_score = int(c["fund_min_score"])
    hit = [k for k, v in passes.items() if v]
    miss = [k for k, v in passes.items() if not v]
    reasons = ["امتیاز %d از ۵ (لازم ≥ %d)" % (score, need_score)]
    if hit:
        reasons.append("موفق: " + "، ".join(hit))
    if miss:
        reasons.append("رد: " + "، ".join(miss))
    return _pillar("fund", "pass" if score >= need_score else "fail",
                   score=score, max_score=5, reasons=reasons,
                   detail={"score": score, "verdict": fts.get("verdict"),
                           "pricing_mode": fts.get("pricing_mode"), "passes": passes,
                           "m141": fts.get("m141"),
                           "avg_trade_val_hmt": fts.get("avg_trade_val_hmt"),
                           "market_cap_rials": mcap, "db_symbol": db_symbol})


# ==================================================== ترکیب سه‌گانه
PILLAR_ORDER = ("tech", "tape", "fund")
CALCULATORS = {"tech": conf_tech, "tape": conf_tape}


def triple(conn: sqlite3.Connection, symbol: str, ctx: dict = None,
           cfg: dict = None, pillars: dict = None, fts: dict = None,
           fts_cfg: dict = None) -> dict:
    """تایید سه‌گانهٔ یک نماد → conf_tech / conf_tape / conf_fund + داوری.

    داوری سه‌حالته است، نه دودویی: «بی‌داده» رأی نمی‌دهد. اگر پوشش داده زیر
    `min_coverage` باشد verdict = INSUFFICIENT می‌شود، نه رد؛ یعنی سیستم ادعا
    نمی‌کند نمادی بد است، فقط می‌گوید نظر نمی‌دهد.
    """
    c = _cfg(ctx, cfg)
    given = pillars or {}
    res = {}
    for k in PILLAR_ORDER:
        if given.get(k) is not None:
            res[k] = dict(given[k])
        elif k == "fund":
            res[k] = conf_fund(conn, symbol, ctx=ctx, cfg=c, fts=fts, fts_cfg=fts_cfg)
        else:
            res[k] = CALCULATORS[k](conn, symbol, ctx=ctx, cfg=c)

    passing = [k for k in PILLAR_ORDER if res[k].get("state") == "pass"]
    with_data = [k for k in PILLAR_ORDER if res[k].get("state") != "nodata"]
    missing = [k for k in PILLAR_ORDER if res[k].get("state") == "nodata"]
    warns = [k for k in PILLAR_ORDER if res[k].get("state") == "warn"]

    # ---- v9.7.4: وتوی بنیادی حذف شد (رویکرد هشدار منعطف) ----
    # نمادی که FTS آن را «حذف خودکار» می‌کرد دیگر VETOED نمی‌خورد و از لیست بیرون
    # نمی‌رود؛ فقط warn است و دلیلش در conf_reasons می‌آید. چرا اصرار بر این تغییر:
    # وتوی سخت، سهم‌های برگشتیِ ماده ۱۴۱ را از دید کاربر پنهان می‌کرد — همان‌هایی
    # که صفحهٔ ۲ متدولوژی FTS شکارشان می‌کند. داوری با کاربر است، نه موتور.
    warn_reasons = []
    for k in warns:
        for txt in (res[k].get("reasons") or []):
            if isinstance(txt, str) and txt.startswith("⚠"):
                warn_reasons.append("%s: %s" % (PILLAR_LABELS[k], txt))

    if len(with_data) < int(c["min_coverage"]):
        verdict = "INSUFFICIENT"
    elif len(passing) == len(PILLAR_ORDER):
        verdict = "CONFIRMED"
    elif len(passing) >= 2:
        verdict = "PROBABLE"
    elif warns:
        verdict = "WATCH"          # جانشین VETOED — هشدار، بدون حذف
    else:
        verdict = "WEAK"

    notes = []
    if warn_reasons:
        notes.append("هشدارها — " + " | ".join(warn_reasons)[:220])
    if missing:
        notes.append("بدون داده: " + "، ".join(PILLAR_LABELS[k] for k in missing))

    return {
        "symbol": symbol,
        "db_symbol": (res["fund"].get("detail") or {}).get("db_symbol"),
        "conf_tech": res["tech"].get("state") == "pass",
        "conf_tape": res["tape"].get("state") == "pass",
        "conf_fund": res["fund"].get("state") == "pass",
        "states": {k: res[k].get("state") for k in PILLAR_ORDER},
        "conf_count": len(passing),
        "coverage": len(with_data),
        "verdict": verdict,
        "warns": warns,
        "conf_reasons": warn_reasons,
        "passing": passing,
        "missing": missing,
        "notes": notes,
        "asof": {k: res[k].get("asof") for k in PILLAR_ORDER},
        "pillars": res,
    }


def triple_many(conn: sqlite3.Connection, symbols, ctx: dict = None,
                cfg: dict = None, fts_cfg: dict = None,
                fund_rows=None) -> list:
    """ماتریس تایید چند نماد؛ نقشه‌های کل‌بازار یک‌بار ساخته می‌شوند (ضدِN+1).

    `fund_rows` = خروجی `fts_engine.bulk_scan(conn)` (یا دیکشنریِ نماد→رکورد).
    اگر داده شود، ستون بنیادی از همان ردیف‌های آماده خوانده می‌شود و هیچ کوئریِ
    تک‌نمادی FTS زده نمی‌شود؛ اگر نشود، هر نماد با scan_symbol محاسبه می‌شود
    (درست ولی ~۲۴ کوئری به‌ازای نماد). برای >چند نماد، fund_rows را بدهید.
    """
    x = ctx or build_ctx(conn)
    fmap = covered = None
    if fund_rows is not None:
        rows = fund_rows.values() if isinstance(fund_rows, dict) else fund_rows
        fmap = {norm(r.get("symbol") or ""): r for r in rows}
        covered = getattr(fund_rows, "covered", None)
    out = []
    for s in symbols:
        fts = fmap.get(norm(s)) if fmap is not None else None
        key = norm(s)
        if fts is None and fmap is not None:
            alt = (resolve(x["index"], s) or {}).get("l_val18") or ""
            key = norm(alt) or key
            fts = fmap.get(key)
        if fts is None and covered is not None and key not in covered:
            # نه در bulk_scan و نه در financial_statements/monthly_sales:
            # بی‌دادهٔ قطعی است، پس ۲۴ کوئریِ scan_symbol بی‌مصرف می‌ماند.
            fts = {"symbol": s, "score": 0, "passes": {}, "excluded": False,
                   "exclusion_reasons": [], "detail": {}, "verdict": "REJECT"}
        out.append(triple(conn, s, ctx=x, cfg=cfg, fts_cfg=fts_cfg, fts=fts))
    return out




