"""آزمایشگاهِ تاریخیِ سیگنال‌های تکنیکال FTS — بدونِ اطلاعاتِ آینده در دیتکت.

چرا این فایل هست: تا پیش از این هیچ راهی نبود برای گفتنِ «این قاعده کار
می‌کند یا نه». `_fts_setup_history` مارکر می‌ساخت ولی هیچ‌کس نمی‌سنید آن
مارکرها چند بار درست بوده‌اند. این harness همان را اندازه می‌گیرد:

  ۱) پنلِ واقعی از `price_history` (فقط‌خواندنی) — بدونِ شبکه، بدونِ CDN.
  ۲) نقطه‌به‌زمان: در بار i دیتکتور **فقط** candles[:i+1] را می‌بیند. پیوتی
     حساب می‌شود که `confirm_idx <= i` باشد (پیوتِ k-فاصله دقیقاً k کندل بعد
     تأیید می‌شود — همان چیزی که `_fts_swings` در لحظهٔ خودش نمی‌داند). کندل
     هفتگی هم فقط از اولینِ روزِ هفتهٔ بعد در دسترس است.
  ۳) داوریِ نتیجه با first-touch bracket رویِ کندل‌هایِ **بعد** (فقط برای
     امتیازدهی، هرگز برایِ دیتکت): ورود در openِ بارِ بعد، +TP یا −SL.
  ۴) معیارِ مرجع: نرخِ پایهٔ همان bracket رویِ **همهٔ بارها**. سیگنالی که
     برنده‌اش از نرخِ پایه بهتر نباشد، سیگنال نیست.
  ۵) حساسیتِ پارامتر: هر variant با سه bracket اجرا می‌شود؛ اگر ترتیبِ
     variantها با bracket عوض شود، آن variant شکننده است و انتخاب نمی‌شود.

اجرا:
  PYTHONIOENCODING=utf-8 py -3.14 tools/fts_signal_lab.py --signals jet,choch,hunt,dbl,fib
  PYTHONIOENCODING=utf-8 py -3.14 tools/fts_signal_lab.py --min-bars 260 --limit-symbols 0
خروجی: `_audit/fts_lab_<signals>.json` (معیارها + نمونۀ خطاها برای تحلیل).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import statistics
import sys
from bisect import bisect_right

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "market.db")

# آستانه‌های ثابتِ دیتکت (از api/chart.py گرفته شده‌اند — اینجا کپی‌اند چون
# harness باید حتی اگر موتور عوض شد، مبنای ثابتی برای مقایسه داشته باشد).
K_DAILY = 3            # `_fts_swings(series, k=3)`
EQUAL_TOL = 0.005      # `_FTS_EQUAL_TOL`
JET_LADDER = (2, 5, 9, 19, 29, 39, 49, 59)
# شکافِ مشکوک به تجزیه/افزایشِ سرمایه: `price_history` تعدیل **نشده** است، پس
# یک افتِ یک‌روزۀ بزرگ می‌تواند «شکستِ کف»ِ جعلی بسازد. چنین باری نه سیگنال
# می‌گیرد نه در نرخِ پایه شمرده می‌شود (و شمارشش گزارش می‌شود).
GAP_SUSPECT = 0.25

BRACKETS = ((0.08, 0.05, 20), (0.12, 0.06, 40), (0.05, 0.04, 10))


# ═══════════════════════════════════════════════════════════════════════════
#  پنل
# ═══════════════════════════════════════════════════════════════════════════
def load_panel(min_bars: int = 260, limit_symbols: int = 0) -> dict:
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    q = ("SELECT symbol, date, open, high, low, close, volume FROM price_history "
         "WHERE symbol IN (SELECT symbol FROM price_history GROUP BY symbol "
         "HAVING COUNT(*) >= ?) ORDER BY symbol, date")
    rows = con.execute(q, (min_bars,)).fetchall()
    con.close()
    panel, cur, buf = {}, None, []
    for sym, d, o, h, l, c, v in rows:
        if sym != cur:
            if cur and len(buf) >= min_bars:
                panel[cur] = _series(buf)
            cur, buf = sym, []
        buf.append((d, o, h, l, c, v))
    if cur and len(buf) >= min_bars:
        panel[cur] = _series(buf)
    if limit_symbols and len(panel) > limit_symbols:
        # نمونه‌برداریِ پایدار (نه first-N): نمادهایِ پرتعدادِ یکسان در هر اجرا
        keys = sorted(panel)[:limit_symbols * 3:3][:limit_symbols]
        panel = {k: panel[k] for k in keys}
    return panel


def _series(buf) -> dict:
    o = np.array([float(r[1] or 0) for r in buf])
    h = np.array([float(r[2] or 0) for r in buf])
    l = np.array([float(r[3] or 0) for r in buf])
    c = np.array([float(r[4] or 0) for r in buf])
    v = np.array([float(r[5] or 0) for r in buf])
    dates = [str(r[0])[:10] for r in buf]
    n = len(dates)
    ok = (o > 0) & (h > 0) & (l > 0) & (c > 0)
    gap = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if c[i - 1] > 0 and (c[i] / c[i - 1] - 1.0) <= -GAP_SUSPECT:
            gap[i] = True
    # پیوت‌های fractal با اندیسِ تأیید (پیوتِ p فقط از بار p+k قابل دیدن است)
    highs, lows = [], []
    for i in range(K_DAILY, n - K_DAILY):
        wl = slice(i - K_DAILY, i)
        wr = slice(i + 1, i + K_DAILY + 1)
        if h[i] >= h[wl].max() and h[i] >= h[wr].max():
            highs.append((i, float(h[i]), i + K_DAILY))
        if l[i] <= l[wl].min() and l[i] <= l[wr].min():
            lows.append((i, float(l[i]), i + K_DAILY))
    # کندل هفتگی (شنبه‌محور) + اندیسِ «بسته‌شدن»
    wk = []
    key = None
    for i, d in enumerate(dates):
        k = _sat_key(d)
        if k != key:
            wk.append({"start": i, "end": i, "o": float(o[i]), "h": float(h[i]),
                       "l": float(l[i]), "c": float(c[i])})
            key = k
        else:
            w = wk[-1]
            w["end"] = i
            w["h"] = max(w["h"], float(h[i]))
            w["l"] = min(w["l"], float(l[i]))
            w["c"] = float(c[i])
    for j, w in enumerate(wk):
        w["avail"] = wk[j + 1]["start"] if j + 1 < len(wk) else n + 1
    return {"dates": dates, "o": o, "h": h, "l": l, "c": c, "v": v, "ok": ok,
            "gap": gap, "highs": highs, "lows": lows, "wk": wk, "n": n}


def _sat_key(iso: str) -> str:
    import datetime as dt
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso[:7]
    return (d - dt.timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def pivots_upto(items, i):
    """پیوت‌هایی که تا بار i تأیید شده‌اند (items: (idx, price, confirm_idx))."""
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid][2] <= i:
            lo = mid + 1
        else:
            hi = mid
    return items[:lo]


def weekly_upto(wk, i):
    lo, hi = 0, len(wk)
    while lo < hi:
        mid = (lo + hi) // 2
        if wk[mid]["avail"] <= i:
            lo = mid + 1
        else:
            hi = mid
    return wk[:lo]


# ═══════════════════════════════════════════════════════════════════════════
#  ساختارِ مشترک: پیوت‌هایِ اخیر + روند
# ═══════════════════════════════════════════════════════════════════════════
def recent_pivots(S, i, lookback=250):
    hs = pivots_upto(S["highs"], i)
    ls = pivots_upto(S["lows"], i)
    lo_i = max(0, i - lookback)
    hs = [x for x in hs if x[0] >= lo_i]
    ls = [x for x in ls if x[0] >= lo_i]
    return hs, ls


def trend_dir(hs, ls, tol=EQUAL_TOL):
    """همان قاعدۀ `_fts_classify_trend`: دو سقف و دو کفِ آخر."""
    if len(hs) < 2 or len(ls) < 2:
        return "na"
    hh = hs[-1][1] > hs[-2][1] * (1 + tol)
    lh = hs[-1][1] < hs[-2][1] * (1 - tol)
    hl = ls[-1][1] > ls[-2][1] * (1 + tol)
    ll = ls[-1][1] < ls[-2][1] * (1 - tol)
    if hh and hl:
        return "up"
    if lh and ll:
        return "down"
    return "range"


# ═══════════════════════════════════════════════════════════════════════════
#  variantهای دیتکت — امضایِ مشترک: fn(S, i) → None | False | dict
#    None  یعنی «داده برای قضاوت نیست» (هرگز به False تبدیل نمی‌شود)
#    False یعنی صریحاً فعال نیست
#    dict  یعنی فعال؛ {"level":…, "why":…}
# ═══════════════════════════════════════════════════════════════════════════
def _body_up(S, i):
    return S["c"][i] >= S["o"][i]


def jet_ladder(S, i):
    """جتِ امروز: close > max(high در فاصله‌هایِ پلکان) + بدنه صعودی."""
    if i < 1 + max(JET_LADDER):
        return None
    res = max(S["h"][i - 1 - k] for k in JET_LADDER)
    if S["c"][i] > res and _body_up(S, i):
        return {"level": float(res)}
    return False


def _static_resistance(S, i, band=0.02, min_touches=2, lookback=250):
    """مقاومتِ **استاتیک** جزوه (ص۲۷): خوشۀ سقف‌هایِ چسبانِ افقی، بی‌قیدِ ۶۰ روزه.

    سقف‌ها را در پنجره جمع می‌کنیم، خوشه‌ای با ≥min_touches لمس و پهنای ≤band
    می‌خواهیم، و **بعد از** آخرینِ لمسِ آن خوشه قیمت پایین‌تر رفته باشد (وگرنه
    خوشه همان «در حال شکسته شدن» است نه مقاومتِ ایستاده).
    """
    lo_i = max(0, i - lookback)
    hs = [x for x in pivots_upto(S["highs"], i) if x[0] >= lo_i and x[0] < i]
    if len(hs) < min_touches:
        return None
    best = None
    for a in range(len(hs)):
        cluster = [hs[a]]
        for b in range(a + 1, len(hs)):
            if hs[b][1] <= hs[a][1] * (1 + band):
                cluster.append(hs[b])
        if len(cluster) < min_touches:
            continue
        lvl = max(x[1] for x in cluster)
        last_touch = max(x[0] for x in cluster)
        if last_touch >= i - 1:
            continue
        if best is None or len(cluster) > best[1]:
            best = (lvl, len(cluster), last_touch)
    if best is None:
        return None
    return {"level": float(best[0]), "touches": best[1], "last_touch": best[2]}


def jet_static(S, i):
    """عبور از مقاومتِ استاتیک (بدونِ شرطِ تثبیت)."""
    r = _static_resistance(S, i)
    if r is None:
        return None
    if S["c"][i] > r["level"] and _body_up(S, i):
        return r
    return False


def jet_static_confirm(S, i, days=2, eps=0.0):
    """عبور + **کندلِ تثبیت** (جزوه ص۲۷): `days` نشستِ متوالی بالای سطح."""
    r = _static_resistance(S, i)
    if r is None:
        return None
    lvl = r["level"] * (1 + eps)
    if S["c"][i] <= lvl or not _body_up(S, i):
        return False
    for j in range(1, days):
        if i - j < 0 or S["c"][i - j] <= lvl:
            return False
    return r


def jet_ath(S, i):
    """عبور از سقفِ تاریخیِ واقعی (بالاترین highِ کلِ پیش از امروز)."""
    if i < 60:
        return None
    res = float(S["h"][:i].max())
    if S["c"][i] > res and _body_up(S, i):
        return {"level": res}
    return False


def choch_now(S, i, margin=0.003, days=1):
    """CHoCHِ امروز: شکستِ آخرین پیوتِ مخالفِ جهتِ غالب (کدِ فعلی با days=1)."""
    hs, ls = recent_pivots(S, i)
    if not hs or not ls:
        return None
    up = ls[-1][0] > hs[-1][0]
    if up:
        lvl = ls[-1][1]
        for j in range(days):
            k = i - j
            if k < 0 or S["c"][k] >= lvl * (1 - margin):
                return False
        return {"level": float(lvl), "dir": "bear"}
    lvl = hs[-1][1]
    for j in range(days):
        k = i - j
        if k < 0 or S["c"][k] <= lvl * (1 + margin):
            return False
    return {"level": float(lvl), "dir": "bull"}


def hunt_channel(S, i, tol=0.005, need=3, lookback=250):
    """نقطه‌زنیِ امروز: کفِ دایامتریکِ کانالِ سقف‌ها (کدِ فعلی)."""
    hs, ls = recent_pivots(S, i, lookback)
    if len(hs) < 2 or not ls or i < 10:
        return None
    h2, h1 = hs[-2], hs[-1]
    if h1[0] - h2[0] < 3:
        return None
    slope = (h1[1] - h2[1]) / (h1[0] - h2[0])
    inside = [x for x in ls if h2[0] < x[0] <= h1[0]]
    anchor = min(inside, key=lambda x: x[1]) if inside else min(ls, key=lambda x: x[1])
    floor_at = lambda j: anchor[1] + slope * (j - anchor[0])
    touches = sum(1 for j in range(anchor[0], i + 1) if S["l"][j] <= floor_at(j) * (1 + tol))
    if touches >= need and S["l"][i] <= floor_at(i) * (1 + tol):
        return {"level": float(floor_at(i)), "touches": touches}
    return False


def hunt_two_lows(S, i, equal=0.03, lookback=250):
    """نقطه‌زنیِ جزوه (ص۲۷): «معمولاً دو کف مساوی می‌سازد؛ از آن دو کف یک خط».

    خطِ عبوری از دو کفِ پیوتِ اخیر (شیبِ آزاد، نه موازیِ سقف)؛ لمس = lowِ کندل
    روی/زیرِ خط. شرطِ روند نزولیِ غالب (جزوه: «در روندهای نزولی اتفاق می‌افتد»).
    """
    hs, ls = recent_pivots(S, i, lookback)
    if len(ls) < 2 or i < 10:
        return None
    a, b = ls[-2], ls[-1]
    if b[0] - a[0] < 5:
        return None
    slope = (b[1] - a[1]) / (b[0] - a[0])
    line = lambda j: a[1] + slope * (j - a[0])
    if trend_dir(hs, ls) == "up":
        return False
    near = sum(1 for j in range(a[0], i + 1) if S["l"][j] <= line(j) * (1 + 0.01))
    if near >= 2 and S["l"][i] <= line(i) * (1 + equal):
        return {"level": float(line(i)), "touches": near}
    return False


def hunt_flat_lows(S, i, equal=0.02, lookback=250):
    """خوانشِ تحت‌اللفظیِ «دو کف مساوی»: خطِ **افقی** از دو کفِ چسبان."""
    hs, ls = recent_pivots(S, i, lookback)
    if len(ls) < 2 or i < 10:
        return None
    a, b = ls[-2], ls[-1]
    if b[0] - a[0] < 5 or abs(a[1] - b[1]) / max(a[1], b[1]) > equal:
        return False
    lvl = min(a[1], b[1])
    if trend_dir(hs, ls) == "up":
        return False
    if S["l"][i] <= lvl * (1 + 0.005) and S["c"][i] > S["o"][i]:
        return {"level": float(lvl)}
    return False


def dbl_neck(S, i, equal=0.015, days=1):
    """دابل‌باتم: دو کف مساوی + یقه؛ تریگر = بسته‌شدنِ بالای یقه (با `days` تأیید)."""
    hs, ls = recent_pivots(S, i)
    if len(ls) < 2:
        return None
    a, b = ls[-2], ls[-1]
    if abs(a[1] - b[1]) / max(a[1], b[1]) > equal:
        return False
    necks = [x[1] for x in hs if a[0] < x[0] < b[0]]
    if not necks:
        return False
    neck = max(necks)
    for j in range(days):
        if i - j < 0 or S["c"][i - j] <= neck:
            return False
    return {"level": float(neck)}


def fib_zone(S, i, zone=(0.33, 0.40), log=True, lookback=250):
    """قیمت داخلِ باندهایِ فیبوی موجِ اخیر (مقیاس log — ص۹ جزوه)."""
    hs, ls = recent_pivots(S, i, lookback)
    if not hs or not ls:
        return None
    if hs[-1][0] > ls[-1][0]:
        bot, top = ls[-1], hs[-1]
    else:
        top, bot = hs[-1], ls[-1]
    if top[0] == bot[0] or top[1] <= bot[1]:
        return None
    lo_i, hi_i = min(bot[0], top[0]), max(bot[0], top[0])
    hh = float(S["h"][lo_i:hi_i + 1].max())
    ll = float(S["l"][lo_i:hi_i + 1].min())
    if hh <= ll:
        return None
    up = hs[-1][0] > ls[-1][0]
    if log:
        span = math.log(hh) - math.log(ll)
        at = lambda r: math.exp(math.log(hh) - span * r) if up else \
            math.exp(math.log(ll) + span * r)
    else:
        span = hh - ll
        at = lambda r: hh - span * r if up else ll + span * r
    lo_p, hi_p = sorted((at(zone[0]), at(zone[1])))
    c = float(S["c"][i])
    if lo_p <= c <= hi_p and _body_up(S, i):
        return {"level": (lo_p + hi_p) / 2.0, "lo": lo_p, "hi": hi_p}
    return False


def jet_ladder_nofilter(S, i, days_back=None):
    """نردبانِ فعلی **بدونِ** شرطِ بدنهٔ صعودی — آیا «کندل تثبیت» چیزی اضافه می‌کند؟"""
    need = 1 + max(JET_LADDER)
    if i < need:
        return None
    res = max(S["h"][i - 1 - k] for k in JET_LADDER)
    if S["c"][i] > res:
        return {"level": float(res)}
    return False


def jet_ladder_confirm(S, i, days=2):
    """نردبان + `days` بستهٔ متوالی بالای سطح (تثبیتِ جزوه روی قاعدۀ فعلی)."""
    need = 1 + max(JET_LADDER) + days
    if i < need:
        return None
    res = max(S["h"][i - 1 - k] for k in JET_LADDER)
    if S["c"][i] <= res or not _body_up(S, i):
        return False
    for j in range(1, days):
        if S["c"][i - j] <= res:
            return False
    return {"level": float(res)}


def jet_ceiling(S, i, win=120, skip=6):
    """سقفِ افقیِ واقعی: بالاترین highِ `win` نشستِ اخیر (بدون `skip` نشستِ آخر).

    تفاوتش با نردبان: نردبان فقط هشت نقطۀِ ثابت را می‌بیند؛ این «سقفِ ایستاده»
    را می‌خواهد که کلِ پنجره بالای سر قیمت بوده باشد.
    """
    if i < win + skip:
        return None
    res = float(S["h"][i - win:i - skip].max())
    if S["c"][i] > res and _body_up(S, i):
        return {"level": res}
    return False


def jet_ladder_3day_window(S, i, window=3):
    """جزوه ص۲۷: «تا ۳ روز مهلت ورود». آتش = شکستِ نردبان **در یکی از** `window`
    نشستِ آخر و بستهٔ امروز بالای همان سطح."""
    need = 1 + max(JET_LADDER) + window
    if i < need:
        return None
    for d in range(window):
        j = i - d
        res = max(S["h"][j - 1 - k] for k in JET_LADDER)
        if S["c"][j] > res and all(S["c"][x] > res for x in range(j, i + 1)):
            if d == 0:
                return {"level": float(res), "age": 0}
            return {"level": float(res), "age": d}
    return False


def jet_static_confirm_days(S, i, win=120, skip=6, days=2):
    """سقفِ استاتیک + `days` بستهٔ متوالی بالای آن (تثبیتِ جزوۀ ص۲۷)."""
    if i < win + skip + days:
        return None
    res = float(S["h"][i - win:i - skip].max())
    if S["c"][i] <= res or not _body_up(S, i):
        return False
    for j in range(1, days):
        if S["c"][i - j] <= res:
            return False
    return {"level": res}


def _weekly_trend(S, i, lookback_weeks=30):
    """روندِ هفتگی از پیوت‌هایِ کندل‌هایِ هفتۀ **بسته‌شده** تا بار i."""
    wk = weekly_upto(S["wk"], i)
    if len(wk) < 12:
        return "na"
    seg = wk[-lookback_weeks:]
    hs, ls = [], []
    k = 2
    for j in range(k, len(seg) - k):
        win_l = seg[j - k:j]
        win_r = seg[j + 1:j + k + 1]
        if seg[j]["h"] >= max(x["h"] for x in win_l + win_r):
            hs.append((j, seg[j]["h"]))
        if seg[j]["l"] <= min(x["l"] for x in win_l + win_r):
            ls.append((j, seg[j]["l"]))
    return trend_dir(hs, ls)


def fib_gated(S, i, zone=(0.618, 0.70), log=True, need_weekly="up"):
    """باندِ فیبو **در چارچوبِ ماتریس** (ص۸ جزوه): هفتۀ صعودی + روزانۀ نزولی.

    فیبوی بی‌گیتِ دورِ اول edge نداشت چون در هر وضعیتی «داخلِ باند بودن» را سیگنال
    می‌گرفت؛ جزوه آن را فقط رویِ هفتۀ صعودی مجاز می‌داند (وگرنه وتوی صریح است).
    """
    if need_weekly and _weekly_trend(S, i) != need_weekly:
        return False
    return fib_zone(S, i, zone, log)


def hunt_bounce(S, i, need=3, lookback=250):
    """لمسِ کف + **ریباند**: همان لمس، ولی کندلِ امروز باید سبز و بالای کفِ خط باشد.

    جزوه می‌گوید «وقتی قیمت به این خط برسد سیگنال خرید» — رسیدنِ تنها کافی نیست،
    بازگشتِ همان کندل همان چیزی است که «کف سوم جذاب است» را معنادار می‌کند.
    """
    r = hunt_channel(S, i, need=need, lookback=lookback)
    if r is None:
        return None
    if r is False:
        return False
    lvl = r["level"]
    if S["c"][i] > S["o"][i] and S["c"][i] > lvl and S["l"][i] <= lvl * 1.01:
        return r
    return False


VARIANTS = {
    "jet": {
        "ladder_current": jet_ladder,
        "ladder_confirm2": lambda S, i: jet_ladder_confirm(S, i, 2),
        "ladder_confirm3": lambda S, i: jet_ladder_confirm(S, i, 3),
        "static_ceiling_120": jet_ceiling,
        "static_ceil_confirm2": lambda S, i: jet_static_confirm_days(S, i, days=2),
        "static_ceil_confirm3": lambda S, i: jet_static_confirm_days(S, i, days=3),
        "static_ceiling_60": lambda S, i: jet_ceiling(S, i, win=60, skip=4),
        "static_ceiling_250": lambda S, i: jet_ceiling(S, i, win=250, skip=6),
    },
    "choch": {
        "current_1d": lambda S, i: choch_now(S, i, days=1),
        "confirm_2d": lambda S, i: choch_now(S, i, days=2),
        "confirm_2d_margin1": lambda S, i: choch_now(S, i, margin=0.01, days=2),
        "confirm_3d": lambda S, i: choch_now(S, i, days=3),
    },
    "hunt": {
        "channel_current": hunt_channel,
        "channel_bounce": hunt_bounce,
        "channel_bounce_4": lambda S, i: hunt_bounce(S, i, need=4),
        "two_lows_line": hunt_two_lows,
        "two_lows_bounce": lambda S, i: (hunt_two_lows(S, i) or False) if (
            S["c"][i] > S["o"][i]) else False,
        "flat_lows": hunt_flat_lows,
    },
    "dbl": {
        "current": lambda S, i: dbl_neck(S, i, days=1),
        "confirm_2d": lambda S, i: dbl_neck(S, i, days=2),
    },
    "fib": {
        "ungated_618_70_log": lambda S, i: fib_zone(S, i, (0.618, 0.70), log=True),
        "ungated_33_40_log": lambda S, i: fib_zone(S, i, (0.33, 0.40), log=True),
        "weekly_up_618_70_log": lambda S, i: fib_gated(S, i, (0.618, 0.70), True),
        "weekly_up_33_40_log": lambda S, i: fib_gated(S, i, (0.33, 0.40), True),
        "weekly_up_618_70_linear": lambda S, i: fib_gated(S, i, (0.618, 0.70), False),
        "weekly_up_not_daily_up": lambda S, i: (
            fib_gated(S, i, (0.618, 0.70), True)
            if trend_dir(*recent_pivots(S, i)) != "up" else False),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  داوریِ نتیجه (first-touch) — فقط برایِ امتیازدهی
# ═══════════════════════════════════════════════════════════════════════════
def resolve(S, i, tp, sl, horizon):
    """نتیجۀ خریدِ در openِ بار i+1، با bracketِ +tp/−sl در سقفِ horizon.

    خروج: 'win' | 'loss' | 'open' (به هیچ کف نرسید) و بازدهِ بسته‌شدن.
    اگر در یک کندل هم tp و هم sl بخورد ⇒ **loss** (محافظه‌کارانه).
    """
    e = i + 1
    if e >= S["n"]:
        return "open", 0.0, 0
    entry = float(S["o"][e])
    if entry <= 0:
        return "open", 0.0, 0
    stop = entry * (1 - sl)
    take = entry * (1 + tp)
    last = min(e + horizon, S["n"] - 1)
    for j in range(e, last + 1):
        if S["l"][j] <= stop:
            return "loss", -sl, j - e
        if S["h"][j] >= take:
            return "win", tp, j - e
    return "open", float(S["c"][last]) / entry - 1.0, last - e


def regime(S, i, win=60):
    if i < win:
        return "na"
    a = float(S["c"][i - win])
    if a <= 0:
        return "na"
    r = float(S["c"][i]) / a - 1.0
    if r > 0.08:
        return "bull"
    if r < -0.08:
        return "bear"
    return "range"


# ═══════════════════════════════════════════════════════════════════════════
#  اجرا
# ═══════════════════════════════════════════════════════════════════════════
def run(panel, signal, bracket_idx=0, warmup=70, sample_every=1, mode="event",
        cooldown=5, folds=0):
    """mode=event ⇒ فقط **اولینِ** باری که شرط true می‌شود (تریگر)، و تا
    `cooldown` بارِ بعدی دوبار آتش نمی‌گیرد. mode=state ⇒ هر باری که شرط برقرار
    است (برای مقایسۀ «وضعیتِ فعال» با «رویدادِ ورود»).

    `folds` ⇒ walk-forward: بازۀ زمانیِ پنل به N قطعهٔ متوالی تقسیم می‌شود و
    دقتِ هر variant در هر قطعه جدا گزارش می‌شود (پایداریِ پارامتر، نه فقط میانگین).
    قطعه‌بندی رویِ **تاریخ** است، پس هر قطعه نمونه‌ای بیرونِ نمونهٔ قطعهٔ دیگر است.

    بدونِ event، دقتِ یک شکستِ ماندگار با «چند روز بالای سطح مانده» قاطی می‌شود
    و مقایسهٔ variantها بی‌معنی است.
    """
    tp, sl, hz = BRACKETS[bracket_idx]
    variants = VARIANTS[signal]
    agg = {k: {"fires": 0, "win": 0, "loss": 0, "open": 0, "ret": [], "bars": [],
               "regime": {}, "symbols": set(), "examples": [], "pending": 0,
               "false": 0, "folds": {}} for k in variants}
    # مرزهایِ قطعه‌ها از تقویمِ کلِ پنل (بی‌look-ahead: تقسیمِ زمانی است، نه انتخابِ داده)
    fold_edges = []
    if folds and folds > 1:
        alldates = sorted({str(d) for S in panel.values() for d in S["dates"]})
        if len(alldates) >= folds:
            step = len(alldates) / float(folds)
            fold_edges = [alldates[int(round(step * (k + 1))) - 1]
                          for k in range(folds - 1)]

    def fold_of(date_str):
        if not fold_edges:
            return None
        return sum(1 for e in fold_edges if date_str > e)
    base = {"n": 0, "win": 0, "loss": 0, "open": 0, "ret": []}
    bars_total = 0
    for sym, S in panel.items():
        prev = {k: (-999, False) for k in variants}   # (آخرین barِ true, was_true)
        for i in range(warmup, S["n"] - 1, sample_every):
            if S["gap"][i] or not S["ok"][i]:
                continue
            bars_total += 1
            if True:   # نرخِ پایه برای هر bracket لازم است (دورِ اول اشتباه فقط b0 حساب می‌شد)
                r0, ret0, _ = resolve(S, i, tp, sl, hz)
                base["n"] += 1
                base[r0 if r0 != "open" else "open"] += 1
                base["ret"].append(ret0)
            for name, fn in variants.items():
                try:
                    hit = fn(S, i)
                except Exception:
                    continue
                if hit is None:
                    agg[name]["pending"] += 1
                    continue
                if hit is False:
                    agg[name]["false"] += 1
                if mode == "event":
                    last_i, was = prev[name]
                    if was and (i - last_i) <= cooldown:
                        continue
                    if hit is False:
                        prev[name] = (i, False)
                        continue
                    prev[name] = (i, True)
                elif hit is False:
                    continue
                a = agg[name]
                a["fires"] += 1
                a["symbols"].add(sym)
                r, ret, nb = resolve(S, i, tp, sl, hz)
                a[r if r != "open" else "open"] += 1
                a["ret"].append(ret)
                a["bars"].append(nb)
                # تفکیکِ regime/fold رویِ «نشستۀ بسته» است (win+loss)، وگرنه با
                # «open» مخلوط می‌شود و با precisionِ ستون اصلی قابلِ مقایسه نیست
                # (اشتباهِ دورِ اول؛ درِ همین دور اصلاح شد).
                if r != "open":
                    rg = regime(S, i)
                    d = a["regime"].setdefault(rg, [0, 0])
                    d[0] += 1
                    if r == "win":
                        d[1] += 1
                fd = fold_of(str(S["dates"][i])[:10])
                if fd is not None and r != "open":
                    g = a["folds"].setdefault(fd, [0, 0])
                    g[0] += 1
                    if r == "win":
                        g[1] += 1
                if len(a["examples"]) < 12 and r == "loss":
                    a["examples"].append({"symbol": sym, "date": S["dates"][i],
                                          "level": hit.get("level"), "ret": round(ret, 4)})
    out = {"bracket": {"tp": tp, "sl": sl, "horizon": hz},
           "bars_evaluated": bars_total, "symbols": len(panel),
           "base_rate": {
               "n": base["n"],
               "win": (base["win"] / base["n"]) if base["n"] else None,
               "loss": (base["loss"] / base["n"]) if base["n"] else None,
               "open": (base["open"] / base["n"]) if base["n"] else None,
               "mean_ret": statistics.fmean(base["ret"]) if base["ret"] else None},
           "variants": {}}
    for name, a in agg.items():
        f = a["fires"]
        closed = a["win"] + a["loss"]
        out["variants"][name] = {
            "fires": f,
            "fires_per_1000_bars": round(1000.0 * f / bars_total, 3) if bars_total else 0,
            "win": a["win"], "loss": a["loss"], "open": a["open"],
            "pending_bars": a["pending"], "false_bars": a["false"],
            "precision": round(a["win"] / closed, 4) if closed else None,
            "expectancy": round(statistics.fmean(a["ret"]), 5) if a["ret"] else None,
            "median_bars_to_resolve": statistics.median(a["bars"]) if a["bars"] else None,
            "coverage_symbols": len(a["symbols"]),
            "by_regime": {k: {"n": v[0], "win": round(v[1] / v[0], 4)}
                          for k, v in sorted(a["regime"].items())},
            # walk-forward: دقت در هر قطعهٔ زمانی + بدترین قطعه (پارامتر شکننده
            # میانگینِ خوب دارد و دامنهٔ wide؛ این دو ستون همان را لو می‌دهند)
            "by_fold": {k: {"closed": v[0], "win": round(v[1] / v[0], 4)}
                        for k, v in sorted(a["folds"].items())},
            "fold_precision": [round(v[1] / v[0], 4) for _k, v in sorted(a["folds"].items())
                               if v[0] >= 20],
            "fold_min": min((v[1] / v[0] for v in a["folds"].values() if v[0] >= 20), default=None),
            "fp_examples": a["examples"],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="jet")
    ap.add_argument("--min-bars", type=int, default=260)
    ap.add_argument("--limit-symbols", type=int, default=0)
    ap.add_argument("--bracket", type=int, default=0)
    ap.add_argument("--sample-every", type=int, default=1)
    ap.add_argument("--mode", default="event", choices=("event", "state"))
    ap.add_argument("--cooldown", type=int, default=5)
    ap.add_argument("--folds", type=int, default=0,
                    help="walk-forward: N قطعهٔ زمانیِ متوالی (۰ = خاموش)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    panel = load_panel(args.min_bars, args.limit_symbols)
    print("پنل: %d نماد | %d کندل" % (len(panel), sum(S["n"] for S in panel.values())))
    allres = {}
    for sig in [s.strip() for s in args.signals.split(",") if s.strip()]:
        if sig not in VARIANTS:
            print("نامعلوم:", sig)
            continue
        r = run(panel, sig, args.bracket, sample_every=args.sample_every,
                mode=args.mode, cooldown=args.cooldown, folds=args.folds)
        r["folds"] = args.folds
        r["mode"] = args.mode
        r["cooldown"] = args.cooldown
        allres[sig] = r
        print("\n══ %s | %s | bracket %s | نرخ پایه win=%.3f" %
              (sig, args.mode, r["bracket"], (r["base_rate"]["win"] or 0)))

        # ستونِ walk-forward: spreadِ دقت بین قطعه‌ها (شکنندگیِ پارامتر)
        hdr = "  %-24s %7s %8s %8s %9s %8s" % (
            "variant", "fires", "win/1k", "precision", "expect", "cover")
        if args.folds > 1:
            hdr += "  %-18s" % "fold precision"
        print(hdr)
        for name, m in sorted(r["variants"].items(),
                              key=lambda kv: -(kv[1]["precision"] or 0)):
            line = "  %-24s %7d %8.2f %9s %8s %8s" % (
                name, m["fires"], m["fires_per_1000_bars"],
                ("%.3f" % m["precision"]) if m["precision"] is not None else "-",
                ("%.4f" % m["expectancy"]) if m["expectancy"] is not None else "-",
                m["coverage_symbols"])
            if args.folds > 1:
                fp = m.get("fold_precision") or []
                spread = ("%.3f…%.3f" % (min(fp), max(fp))) if len(fp) > 1 else "-"
                line += "  %-18s" % spread
            print(line)

    path = args.out or os.path.join(ROOT, "_audit", "fts_lab_%s_b%d_%s.json" %
                                    (args.signals.replace(",", "+"), args.bracket, args.mode))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(allres, f, ensure_ascii=False, indent=1)
    print("\nنوشته شد:", path)


if __name__ == "__main__":
    main()
