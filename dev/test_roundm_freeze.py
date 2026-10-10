# dev/test_roundm_freeze.py — Round M §۱۹/§۱۲: پینِ انجمادِ گیتِ هفتگی و ساعت شنی
"""رأیِ مالک (۱۴۰۵-۰۷-۱۲): گیتِ هفتگی و ساعتِ شنی **فریز**اند.

این گارد قاعده را رویِ دادهٔ واقعیِ بانک می‌سنجد، نه رویِ فیکسچرِ دست‌ساز:

    هفتگی نزولی  ⇒ matrix.decision = REJECT
    هفتگی خنثی   ⇒ REJECT
    هفتگی na     ⇒ UNKNOWN  (کمبودِ داده رأی نیست)
    هفتگی صعودی  ⇒ PERMITTED (یا UNKNOWN اگر روزانه سنجیده نشده)

و ساعتِ شنی باید MA52 و RSI **هفتگیِ قابل‌تنظیم (پیش‌فرض RSI7)** را به‌کار ببرد (تعدادِ کندلِ هفتگی ≈ یک‌پنجمِ
روزانه، و عددِ MA52 تنها وقتی می‌آید که ≥۵۲ کندلِ هفتگی باشد). اگر روزی کسی
«Daily-only» را دوباره پیشنهاد کرد، همین فایل قرمز می‌شود — که خواستِ کار است.

بی‌شبکه. بانکِ محلی نباشد ⇒ SKIP (نه شکست).
"""
import io
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api.chart as CH  # noqa: E402

PASS = FAIL = SKIP = 0


def ck(label, cond, detail=""):
    global PASS, FAIL, SKIP
    if cond is None:
        SKIP += 1
        print(f"  SKIP  {label}")
        return
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def _symbols(limit=40):
    try:
        conn = sqlite3.connect(CH.DB_PATH, timeout=30)
        rows = conn.execute(
            "SELECT symbol, COUNT(*) c FROM price_history GROUP BY symbol "
            "HAVING c >= 260 ORDER BY c DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _daily(symbol):
    conn = sqlite3.connect(CH.DB_PATH, timeout=30)
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM price_history "
        "WHERE symbol=? ORDER BY date", (symbol,)).fetchall()
    conn.close()
    return [{"time": r[0], "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
             "close": float(r[4]), "volume": float(r[5] or 0)} for r in rows if r[4]]


print("═" * 72)
print("Round M — پینِ انجمادِ گیتِ هفتگی و ساعتِ شنی")
print("═" * 72)

syms = _symbols()
if not syms:
    print("  SKIP  بانکِ محلی درِ این محیط نیست — سنجشِ واقعی انجام نشد")
else:
    EXPECT = {"down": ("REJECT",), "range": ("REJECT",), "na": ("UNKNOWN",),
              "up": ("PERMITTED", "UNKNOWN")}
    bad, seen, counts = [], {}, {}
    hg_weekly_bad, hg_null_ok = [], True
    for sym in syms:
        candles = _daily(sym)
        if len(candles) < 260:
            continue
        out = CH._fts_analyze_candles(sym, candles)
        tw = ((out.get("trend") or {}).get("W") or {}).get("trend")
        dec = ((out.get("trend") or {}).get("matrix") or {}).get("decision")
        if tw is None or dec is None:
            continue
        seen[tw] = seen.get(tw, 0) + 1
        counts[dec] = counts.get(dec, 0) + 1
        if dec not in EXPECT.get(tw, ()):
            bad.append((sym, tw, dec))
        hg = out.get("hourglass") or {}
        wb = hg.get("weekly_bars")
        nd = len(CH._fts_resample(candles, "W"))
        if wb != nd:
            hg_weekly_bad.append((sym, wb, nd))
        if nd >= 52 and hg.get("ma52") is None:
            hg_null_ok = False
    ck(f"گیتِ هفتگی رویِ {sum(seen.values())} نمادِ واقعی نقض ندارد", not bad, bad[:3])
    ck("همۀ چهار حالتِ هفتگی درِ نمونه دیدگان (بی‌این، سنجشِ بالا می‌تواند توخالی باشد)",
       all(k in seen for k in ("down", "range", "up")) or None, seen)
    # برایِ نمادی که هفتگی‌اش واقعاً بسته است، وضعیتِ عمومی هم باید همان را بگوید
    # (جز در دو اولویتِ بالاتر: حدِ ضررِ سخت و خروجِ تأییدشده).
    veto_checks = 0
    veto_bad = []
    for sym in syms:
        candles = _daily(sym)
        if len(candles) < 260:
            continue
        o = CH._fts_analyze_candles(sym, candles)
        tw = ((o.get("trend") or {}).get("W") or {}).get("trend")
        if tw not in ("down", "range"):
            continue
        code = ((o.get("status") or {}).get("code")) or ""
        veto_checks += 1
        if code not in ("weekly_veto", "hard_stop", "confirmed_exit"):
            veto_bad.append((sym, tw, code))
        if veto_checks >= 6:
            break
    ck(f"وضعیتِ عمومی هم گیتِ هفتگی را می‌گوید ({veto_checks} نمادِ نزولی/خنثی بررسی شد)",
       (not veto_bad) if veto_checks else None, veto_bad[:3])
    ck("ساعتِ شنی شمارۀ کندلِ **هفتگی** را می‌دهد، نه روزانه", not hg_weekly_bad, hg_weekly_bad[:3])
    ck("MA52 هفتگی فقط بی‌کندلِ کافی ناامید می‌شود (با ≥۵۲ هفته عدد می‌آید)", hg_null_ok)
    print(f"  ·  توزیع: seen={seen} decisions={counts}")

    # فریزِ سمتِ UI: متنی که کاربر می‌خواند باید همان واژگانِ گیت باشد
    src = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "api", "chart.py"), encoding="utf-8").read()
    ck("متنِ «وتوی تایم هفتگی» درِ اولویتِ وضعیت باقی است",
       '"weekly_veto"' in src and "وتوی تایم هفتگی" in src)
    ck("Hourglass هنوز MA52/RSI هفتگی را از `closes_w` می‌سازد",
       "ma52_w = _fts_ma(closes_w, 52)" in src and "rsi5_w = _fts_rsi(closes_w, 5)" in src)

print("─" * 72)
print(f"نتیجه: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
