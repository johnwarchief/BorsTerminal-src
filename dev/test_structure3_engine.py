# -*- coding: utf-8 -*-
"""گاردِ قراردادِ موتورِ سوم (api/structure3.py) — مرحلۀ ۲ دورِ تطبیقِ دوم.

مرحلۀ ۲ می‌گوید «ورودی‌ها، خروجی‌ها و وضعیت‌های نامعتبر یا دادهٔ ناکافی را صریح
تعریف کن» و «نتیجهٔ موتور سوم را در رابط از خروجی دو موتور دیگر قابل‌تشخیص نگه
دار». این فایل همان را رویِ دادهٔ کاشته‌شده می‌سنجد (بی‌شبکه، بی‌market.db):

  ۱) چهار حالتِ صریح: success / empty / insufficient / error هرکدام واقعی‌اند.
  ۲) تک‌منبعِ آستانه‌ها: `params` از خودِ `structure_engine3` خوانده می‌شود، نه
     از عددِ written-in-place درِ لایۀ API (کنترلِ منفیِ صریح).
  ۳) ضدِ repaint / بی‌دادهٔ آینده: پیشوندِ سری دقیقاً پیوت‌هایِ تأییدشده‌ای را
     می‌دهد که درِ سریِ کامل `confirm_idx < k` دارند؛ `as_of` هم هیچ نکتی بعد از
     T نمی‌دهد؛ `meta.pending` هرگز درِ `points` نمی‌نشیند.
  ۴) دو شاخۀ آستانه (ATR vs کفِ ۳٪) جدا شمارش می‌شوند -- «سنجیده شد» با
     «بی‌ATR فقط کف» یکی نمی‌شود.
  ۵) مرزِ سه‌موتوره: موتورِ سوم درِ کشِ تحلیلِ FTS هیچ چیزی نمی‌نویسد و
     نسخۀ قواعدِ رأیِ رسمی (`FTS_TECH_RULESET_VERSION`) دست‌نخورده می‌ماند.

اجرا:  python dev/test_structure3_engine.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import structure_engine3 as E3  # noqa: E402
from api import chart as CH  # noqa: E402
from api import structure3 as S3  # noqa: E402

RES = []


def ck(name, cond, got=""):
    RES.append((name if cond else "✗ " + name, bool(cond), "" if cond else repr(got)))


def series(closes, spread=0.004, start="2024-01-01"):
    """سریِ کندلِ قطعی از رویِ مسیرِ بست‌ها؛ high/low با `spread` عرض می‌گیرد."""
    d0 = dt.date.fromisoformat(start)
    out, prev = [], None
    for i, c in enumerate(closes):
        day = (d0 + dt.timedelta(days=i)).isoformat()
        o = prev if prev is not None else c
        out.append({"time": day, "open": o, "high": c * (1.0 + spread),
                    "low": c * (1.0 - spread), "close": c, "last": c, "volume": 1000})
        prev = c
    return out


def leg(frm, to, n):
    return [frm + (to - frm) * (i + 1) / n for i in range(n)]


# کم‌نوسان: ATR٪ ≈ عرضِ کندل (کمترِ کفِ ۳٪) ⇒ همهٔ تأییدها از کفِ ۳٪ می‌آیند
LOW = series(leg(100, 112, 40) + leg(112, 98, 35) + leg(98, 120, 45) + leg(120, 104, 30), 0.004)
# پرنوسان: ATR٪ ≈ ۱۲٪ ⇒ آستانه از ATR می‌آید و کفِ ۳٪ بی‌اثر است
HIGH = series(leg(100, 132, 30) + leg(132, 108, 30) + leg(108, 146, 34) + leg(146, 118, 26), 0.06)

_orig_series = CH._fts_analysis_series


def with_candles(candles, basis="tsetmc-adjusted"):
    CH._fts_analysis_series = lambda symbol: (candles, basis)


def no_series(*_a, **_kw):
    raise RuntimeError("منبعِ کندل در دسترس نیست (تست)")


try:
    # ── ۱) چهار حالتِ صریح ────────────────────────────────────────────────
    CH._fts_analysis_series = no_series
    r_err = S3.analyze_symbol("X")
    ck("ورودیِ خراب ⇒ status:error با پیامِ خودِ منبع",
       r_err["status"] == "error" and bool(r_err.get("message")), r_err)
    ck("حالتِ خطا هیچ پیوتی منتشر نمی‌کند", "points" not in r_err, r_err)

    with_candles([])
    r_empty = S3.analyze_symbol("X")
    ck("صفر کندل ⇒ status:empty (نه «صفر ساختار»ِ success)",
       r_empty["status"] == "empty" and r_empty["bars"] == 0, r_empty)
    ck("empty هیچ لایۀ رسم‌شدنی نمی‌سازد", "points" not in r_empty and "choch" not in r_empty, r_empty)

    with_candles(LOW[:1])
    r_one = S3.analyze_symbol("X")
    ck("یک کندل ⇒ status:insufficient", r_one["status"] == "insufficient", r_one)
    ck("insufficient هیچ لایۀ رسم‌شدنی منتشر نمی‌کند",
       "points" not in r_one and "choch" not in r_one, r_one)

    with_candles(LOW)
    ok = S3.analyze_symbol("X")
    ck("سریِ کافی ⇒ status:success", ok["status"] == "success", ok.get("status"))
    ck("مبنایِ سریِ موتورِ اول در پاسخ می‌آید (همان کندل، نه دومی)",
       ok["basis"] == "tsetmc-adjusted", ok)
    ck("تعدادِ کندلِ تحلیل == طولِ سری", ok["bars"] == len(LOW), ok["bars"])
    ck("لنگرِ `ref_close` بستِ آخرین کندلِ تحلیل است",
       abs(ok["ref_close"] - LOW[-1]["close"]) < 1e-9, ok.get("ref_close"))
    ck("پیوتِ منتشرشده غیرصفر است (کنترلِ منفی: بی‌موتور فهرست خالی می‌ماند)",
       len(ok["points"]) > 0, len(ok["points"]))

    # ── ۲) تک‌منبعِ آستانه‌ها ──────────────────────────────────────────────
    ck("بی‌رأیِ رسمی: official=False و voting=False",
       ok["official"] is False and ok["voting"] is False, ok)
    ck("هویۀ موتورِ سوم از موتورِ اول جداست", ok["engine"] == "structure3", ok["engine"])
    ck("بی‌مرجعِ بیرونی صادقاً اعلام می‌شود (تنها مانعِ مرحلۀ ۲)",
       bool(ok.get("reference_status")), ok.get("reference_status"))
    ck("منبعِ قاعده در پاسخ می‌آید: لایه درِ رأیِ رسمی FTS مشارکت نمی‌کند",
       "رأی" in (ok.get("rule_source") or ""), ok.get("rule_source"))
    ck("params دقیقاً سه پارامترِ خودِ موتور است",
       ok["params"] == {"atr_period": E3.ATR_PERIOD, "atr_mult": E3.ATR_MULT,
                        "floor_pct": E3.FLOOR_PCT}, ok["params"])
    _old_floor = E3.FLOOR_PCT
    try:
        E3.FLOOR_PCT = 7.5
        ck("کنترلِ منفی: تغییرِ موتور ⇒ `params` عوض می‌شود (عددِ second-source نیست)",
           S3.analyze_symbol("X")["params"]["floor_pct"] == 7.5)
    finally:
        E3.FLOOR_PCT = _old_floor

    # ── ۳) ضدِ repaint / بی‌دادهٔ آینده ───────────────────────────────────
    pts = ok["points"]
    ck("هر پیوت: تأیید بعد از وقوع است (confirm_idx > idx)",
       all(p["confirm_idx"] > p["idx"] for p in pts), [p for p in pts if p["confirm_idx"] <= p["idx"]][:2])
    ck("هر پیوت: زمانِ تأیید بعد از زمانِ وقوع (کِی فهمیدیم ≠ کِی رخ داد)",
       all(p["confirm_time"] > p["time"] for p in pts),
       [p for p in pts if not (p["confirm_time"] > p["time"])][:2])
    kinds = [p["kind"] for p in pts]
    ck("پیوت‌ها یک‌درمیان alternating‌اند",
       all(a != b for a, b in zip(kinds, kinds[1:])), kinds[:8])
    ck("هیچ برچسبی بی‌خارجۀ HH/HL/LH/LL نیست",
       all(p["label"] in (None, "HH", "HL", "LH", "LL") for p in pts),
       [p["label"] for p in pts if p["label"] not in (None, "HH", "HL", "LH", "LL")][:3])
    by_idx = {p["idx"]: p for p in pts}
    ck("هر CHoCH به یک پیوتِ منتشرشده ارجاع می‌دهد و سطحش را بازحسابی نمی‌کند",
       all(by_idx.get(c["idx"]) is not None and abs(by_idx[c["idx"]]["price"] - c["level"]) < 1e-9
           for c in ok["choch"]), ok["choch"][:2])
    ck("جهتِ CHoCH فقط صعودی/نزولی است",
       all(c["direction"] in ("bullish", "bearish") for c in ok["choch"]),
       [c["direction"] for c in ok["choch"]][:4])

    # پیشوند-پایداری: سریِ کوتاه‌تر فقط پیوت‌هایِ تأییدشده تا همان نقطه را می‌دهد
    full = E3.zigzag(LOW)["pivots"]
    for k in (len(LOW) - 1, len(LOW) // 2, 60, 30):
        pre = E3.zigzag(LOW[:k])["pivots"]
        ck(f"پیشوند-پایداری در k={k}: بی‌نشتِ دادهٔ آینده",
           pre == [p for p in full if p["confirm_idx"] < k],
           (len(pre), len([p for p in full if p["confirm_idx"] < k])))

    # pending هرگز رسم نمی‌شود
    zz = E3.zigzag(LOW)
    pend = zz["meta"]["pending"]
    ck("قله/درۀ بی‌برگشتِ آخر در meta.pending می‌ماند (pending:False)",
       pend is not None and pend["confirmed"] is False, pend)
    ck("pending درِ `points` منتشرشده نمی‌آید (بی‌repaint)",
       all(p["idx"] != pend["idx"] or p["confirm_idx"] != len(LOW) - 1 for p in zz["pivots"]),
       [p for p in zz["pivots"] if p["idx"] == pend["idx"]])
    # کنترلِ مثبتِ همان ادعا: یک کندلِ برگشتِ کافی اضافه شود، pending تأیید می‌شود.
    # (کفِ pending در ۱۰۳٫۵ است؛ کندلِ بعدی باید close را بالای آستانه ببرد و
    #  lowِ پایین‌تر نسازد، وگرنه خودِ extreme جابه‌جا می‌شود نه تأیید.)
    nxt = (dt.date.fromisoformat(LOW[-1]["time"]) + dt.timedelta(days=1)).isoformat()
    rev = {"time": nxt, "open": LOW[-1]["close"], "high": 110.5, "low": 105.0, "close": 110.0}
    after = E3.zigzag(LOW + [rev])
    ck("کنترلِ مثبت: با برگشتِ کافی همان extreme تأیید و منتشر می‌شود",
       any(p["idx"] == pend["idx"] for p in after["pivots"]),
       (pend["idx"], [p["idx"] for p in after["pivots"]][-3:]))
    ck("پیش ازِ برگشت، همان extreme فقط pending بود (هیچ‌وقت پیش‌دستی نمی‌کند)",
       pend["idx"] not in {p["idx"] for p in zz["pivots"]}, pend["idx"])

    # as_of: بازپخش بی‌دادهٔ آینده
    T = LOW[len(LOW) // 2]["time"]
    with_candles(LOW)
    r_asof = S3.analyze_symbol("X", as_of=T)
    ck("as_of سری را می‌بُرد (bars کمتر از کل)", r_asof["bars"] == len(LOW) // 2 + 1, r_asof["bars"])
    ck("as_of: هیچ پیوتی بعد از T وقوع ندارد",
       all(p["time"] <= T for p in r_asof["points"]), [p["time"] for p in r_asof["points"]][-3:])
    ck("as_of: هیچ تأییدی بعد از T نمی‌آید (برای رسم‌کردن هم دیرتر است)",
       all(p["confirm_time"] <= T for p in r_asof["points"]),
       [p["confirm_time"] for p in r_asof["points"]][-3:])
    ck("as_of برچسب‌دار می‌شود (پاسخِ replay هویت دارد)", r_asof["as_of"] == T, r_asof.get("as_of"))

    # ── ۴) دو شاخۀ آستانه (ATR vs کف) جدا و خوانا شمرده می‌شوند ──────────
    # معنایِ درستِ دو شمار (از خودِ `_threshold`): `atr_used` یعنی «ATRِ معتبر
    # حساب شد»، و `threshold_pct` نشان می‌دهد کدام شاخه واقعاً آستانه را ساخت
    # (max(floor, mult×ATR٪)). بی‌این تفکیک، رابطِ شواهد «بی‌ATR» را با
    # «کف‌محور» یکی می‌خواند.
    zl, zh = E3.zigzag(LOW), E3.zigzag(HIGH)
    ck("کم‌نوسان: آستانه‌ها همه رویِ کفِ ۳٪ می‌نشینند (ATR زورِ کافی ندارد)",
       len(zl["pivots"]) > 0 and all(abs(p["threshold_pct"] - E3.FLOOR_PCT) < 1e-9
                                     for p in zl["pivots"]),
       [p["threshold_pct"] for p in zl["pivots"]])
    ck("پرنوسان: ATR واقعاً آستانه را بالایِ کف می‌برد",
       any(p["threshold_pct"] > E3.FLOOR_PCT + 1e-9 and p["atr_used"] for p in zh["pivots"]),
       [(p["threshold_pct"], p["atr_used"]) for p in zh["pivots"]])
    ck("بی‌ATRِ معتبر ⇒ فقطِ کف، و این درِ meta نامبرِ جدا می‌ماند",
       zl["meta"]["confirmed_floor_only"] == sum(1 for p in zl["pivots"] if not p["atr_used"]),
       (zl["meta"], [p["atr_used"] for p in zl["pivots"]]))
    ck("مجموعِ دو شمار = پیوت‌هایِ تأییدشده (هیچ تأییدی گم نمی‌شود)",
       zh["meta"]["confirmed_atr"] + zh["meta"]["confirmed_floor_only"] == len(zh["pivots"]),
       zh["meta"])
    ck("ATRِ warm-up به‌عنوان «کندل بی‌ATR» شمرده نمی‌شود",
       zl["meta"]["atr_missing_bars"] == 0, zl["meta"])
    ck("متا همان سه پارامترِ موتور را برایِ رابط می‌برد",
       (zh["meta"]["atr_period"], zh["meta"]["atr_mult"], zh["meta"]["floor_pct"])
       == (E3.ATR_PERIOD, E3.ATR_MULT, E3.FLOOR_PCT), zh["meta"])

    # ── ۵) مرزِ سه‌موتوره: رأیِ FTS دست‌نخورده ────────────────────────────
    CH.FTS_ANALYSIS_CACHE.clear()
    rs_before = CH.FTS_TECH_RULESET_VERSION
    with_candles(LOW)
    S3.analyze_symbol("X")
    S3.analyze_symbol("X", as_of=T)
    ck("موتورِ سوم درِ کشِ تحلیلِ FTS هیچ چیزی نمی‌نویسد",
       len(CH.FTS_ANALYSIS_CACHE) == 0, list(CH.FTS_ANALYSIS_CACHE))
    # invariantِ واقعی «دست‌نخورده» است، نه عددِ خاص: مرحلۀ ۳ قواعدِ موتورِ اول را
    # عوض می‌کند (بند ۵: قاعدۀ اکیدِ پیوت) و هر بار باید کش را عوض کند؛ گاردِ
    # شمارهٔ ثابت آن bump را «شکستِ موتورِ سوم» نشان می‌داد.
    ck("نسخۀ قواعدِ رأیِ رسمی را موتورِ سوم عوض نمی‌کند (پیش/پس از دو فراخوان E3)",
       CH.FTS_TECH_RULESET_VERSION == rs_before and bool(str(rs_before).strip()),
       (rs_before, CH.FTS_TECH_RULESET_VERSION))
    ck("موتورِ سوم `structure_points`/`trend`ِ موتورِ اول را نمی‌سازد",
       "structure_points" not in ok and "trend" not in ok, sorted(ok)[:12])

    # رجیستری/ساختار: router + مسیرِ API واقعاً ثبت‌شده‌اند (اتصالِ واقعی، نه نام)
    paths = [getattr(r, "path", None) for r in S3.router.routes]
    ck("router یک مسیرِ GET دارد: /api/structure3/{symbol}",
       paths == ["/api/structure3/{symbol}"], paths)
    import api as API_MOD  # noqa: E402
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               "api", "__init__.py"), encoding="utf-8").read()
    ck("`structure3` درِ api/__init__ فهرست شده (importِ build)", "structure3" in src)
    ck("API_PKG همان ماژول را درِ بدنه import می‌کند",
       getattr(API_MOD, "api_router", None) is not None)
finally:
    CH._fts_analysis_series = _orig_series

fails = [n for n, ok_, _ in RES if not ok_]
for n, ok_, extra in RES:
    print(f"  {'PASS' if ok_ else 'FAIL'}  {n}{'  <<< ' + extra if extra else ''}")
print(f"\n{len(RES) - len(fails)}/{len(RES)} passed")
sys.exit(1 if fails else 0)
