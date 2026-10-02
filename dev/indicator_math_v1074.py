# -*- coding: utf-8 -*-
"""dev/indicator_math_v1074.py — سه اصلاحِ عددیِ اثبات‌شده درِ ممیزیِ اندیکاتورها.

مرجعِ هر سه، همان oracleِ مستقلِ `_audit/indicator_audit/oracle.py` است (خودش با
`_audit/indicator_audit/test_oracle.py` ۳۲ سبز/۰ قرمز است: برابریِ SMA/EMA/std با
pandas 3.0.5، ثابت‌ماندنی‌هایِ سری‌هایِ تباهیده، هویتِ WMA−SMA=(n−1)/6).
داده: `_audit/indicator_audit/fixtures_ohlcv.json` = ۶ نمادِ واقعی × ۳۰۰ کندلِ آخر
از CSVهایِ منتشرشدۀ TSETMC (درِ گیت؛ پس گارد بی‌شبکه و بی‌market.dbِ کاری می‌دود).

سه چیز که با عدد ثابت شد و اینجا قفل می‌شود:
  ۱) `/api/ma` — شمارندِ `i+1` به‌جایِ عرضِ پنجره ⇒ عدد هیچ‌گاه MA نبود
     (۴۶٬۴۰۲ از ۴۶٬۴۱۴ نقطه درِ ۱۲ نماد، خطایِ نسبی ~۹۹٪).
  ۲) `_fts_rsi` — بذرِ وایلدر یکِ گامِ اضافی هم می‌خورد (تغییرِ i=period هم داخلِ
     بذر و هم به‌عنوانِ نخستینِ recursion) ⇒ warmup یکِ سطر جلو؛ بدترینِ انحرافِ
     اندازه‌گیری‌شده Δ=۱٫۸۸ رویِ پنجرۀ ۳۵ سطری، در حالی که آستانۀ واگراییِ
     لایۀ ۴ «۱٫۰ واحد» است.
  ۳) `_fts_scaled` — `last := close×k` ⇒ مبنایِ «آخرین» درِ سریِ FTS جعلی بود.
     حالا `closing` و `last` هر کدام ×k می‌شوند و `close` فقط از
     `price_basis.apply_basis` می‌آید (قراردادها دست‌نخورده).

بی‌شبکه. اجرا:  python dev/indicator_math_v1074.py
"""
import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "_audit", "indicator_audit"))

import oracle as O                                   # noqa: E402
import price_basis                                   # noqa: E402
import bors_config                                   # noqa: E402
import api.chart as CH                               # noqa: E402

PASS = FAIL = 0
RT2 = 0.005 + 1e-9        # round(...,2)
RT1 = 0.05 + 1e-9         # round(...,1)


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ✓ %s" % what)
    else:
        FAIL += 1
        print("  ✗ %s%s" % (what, ("   ← %s" % detail) if detail else ""))


def nbad(prod, ref, rt):
    """شمارِ نقاطِ واگرا (فراتر از گردکردن) + جایِ نخستینِ واگرایی + بی‌مقدارهایِ نابرابر."""
    n = min(len(prod), len(ref))
    bad = first = None
    nulls = 0
    for i in range(n):
        a, b = prod[i], ref[i]
        if a is None or b is None:
            if (a is None) != (b is None):
                nulls += 1
            continue
        if abs(float(a) - float(b)) > rt * max(1.0, abs(float(b))):
            bad = (bad or 0) + 1
            if first is None:
                first = i
    return bad or 0, first, nulls


def fixture():
    p = os.path.join(ROOT, "_audit", "indicator_audit", "fixtures_ohlcv.json")
    return json.load(open(p, encoding="utf-8"))


def temp_ma_db(rows_by_sym):
    """بانکِ موقتِ price_history از همان fixture (last=NULL،src=published)."""
    path = os.path.join(tempfile.mkdtemp(prefix="indmath_"), "t.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
                " PRIMARY KEY (symbol, date))")
    for sym, d in rows_by_sym.items():
        for i, day in enumerate(d["time"]):
            con.execute("INSERT OR REPLACE INTO price_history VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (sym, day, d["open"][i], d["high"][i], d["low"][i], d["close"][i],
                         float(d["volume"][i] or 0), d["last"][i], d["value"][i], "published"))
    con.commit()
    con.close()
    return path


def ma_events_formula(closes, w):
    """بازنویسیِ حلقۀ api/chart.py:890-897 برایِ کنترلِ منفی (نسخۀِ معیوب)."""
    out, acc = [], 0.0
    for i, v in enumerate(closes):
        acc += v
        if i >= w:
            acc -= closes[i - w]
        out.append(round(acc / (i + 1), 2) if i >= w - 1 else None)
    return out


def rsi_double_step(closes, period):
    """بازنویسیِ نسخۀِ معیوب: بذر + یکِ گامِ RMA پیش ازِ نخستینِ خروجی."""
    g = l = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        g += max(ch, 0.0)
        l += max(-ch, 0.0)
    ag, al = g / period, l / period
    out = [None] * period
    for i in range(period, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(ch, 0.0)) / period
        al = (al * (period - 1) + max(-ch, 0.0) ) / period
        out.append(round(100.0 - 100.0 / (1.0 + ag / al), 1) if al > 0 else 100.0)
    return out


def main():
    fx = fixture()
    syms = sorted(fx)
    print("— ۰) fixture: %d نماد × %d کندل (بی‌شبکه)" % (len(syms), len(fx[syms[0]]["close"])))
    ck(len(syms) >= 6 and all(len(fx[s]["close"]) >= 300 for s in syms),
       "۶ نماد با ≥۳۰۰ سطر در دسترس است", str({s: len(fx[s]["close"]) for s in syms}))

    # ══════════════════════ ۱) /api/ma ══════════════════════
    print("\n— ۱) `/api/ma`: شمارند باید عرضِ پنجره باشد، نه i+1")
    db = temp_ma_db(fx)
    orig_db, orig_pb = CH.DB_PATH, bors_config.PRICE_BASIS_PATH
    CH.DB_PATH = db
    bors_config.PRICE_BASIS_PATH = os.path.join(os.path.dirname(db), "pb.json")
    try:
        for basis in ("closing", "last"):
            price_basis.set_basis(basis)
            CH.MA_CACHE.clear()
            worst = 0
            details = []
            warmups = []
            for s in syms:
                # ورودیِ endpoint همان سریِ حل‌شده توسطِ قرارداد است (last|closing)،
                # پس مرجعِ میانگین هم از همان سری ساخته می‌شود: این آزمون
                # *شمارندِ* پنجره را می‌سنجد، نه ریزالویِ مبن (که جایِ خودش سنجیده است).
                rows = [{"time": t, "close": cl, "last": ls}
                        for t, cl, ls in zip(fx[s]["time"], fx[s]["close"], fx[s]["last"])]
                price_basis.apply_basis(rows)
                closes = [float(r["close"]) for r in rows]
                res = CH.get_ma_events(s, days=len(closes))
                if res.get("status") != "ok":
                    details.append("%s:%s" % (s, res.get("message")))
                    continue
                for w in bors_config.MA_WINDOWS:
                    if w > len(closes):
                        continue
                    got = [pt[1] for pt in res["ma"]["ma%d" % w]]
                    ref = O.sma(closes, w)
                    bad, first, nulls = nbad(got, ref, RT2)
                    worst = max(worst, bad)
                    if bad or nulls:
                        details.append("%s/ma%d bad=%d first=%s nulls=%d" % (s, w, bad, first, nulls))
                    lead = 0
                    while lead < len(got) and got[lead] is None:
                        lead += 1
                    warmups.append((s, w, lead, got[w - 1] is not None))
            ck(worst == 0, "مبنایِ %s: %d نماد × %d پنجره با oracle می‌خوانند"
               % (basis, len(syms), len(bors_config.MA_WINDOWS)),
               "; ".join(details[:3]) or "max bad=%d" % worst)
            ck(all(lead == w - 1 and filled for _s, w, lead, filled in warmups),
               "مبنایِ %s: warmup دقیقاً w−1 سطرِ None و نخستینِ عدد در index w−1" % basis,
               str([x for x in warmups if x[2] != x[1] - 1 or not x[3]][:3]))
        # کنترلِ منفی: نسخۀِ معیوب باید قرمز شود (پس آزمونِ بالا پوچ نیست)
        closes = [float(x) for x in fx["فولاد"]["close"]]
        bad_old, first_old, _ = nbad(ma_events_formula(closes, 20), O.sma(closes, 20), RT2)
        ck(bad_old > len(closes) * 0.5,
           "کنترلِ منفی: شمارندِ قدیمی (i+1) همین fixture را قرمز می‌کند",
           "bad=%d/%d first=%s" % (bad_old, len(closes), first_old))
        ck(ma_events_formula(closes, 20)[36] != O.sma(closes, 20)[36],
           "کنترلِ منفی: عددِ قدیمی درِ همان سطر با مرجع فرق دارد",
           str((ma_events_formula(closes, 20)[36], O.sma(closes, 20)[36])))
    finally:
        CH.DB_PATH = orig_db
        bors_config.PRICE_BASIS_PATH = orig_pb
        CH.MA_CACHE.clear()

    # ══════════════════════ ۲) _fts_rsi ══════════════════════
    print("\n— ۲) `_fts_rsi`: بذرِ وایلدر بدونِ گامِ اضافی، warmupِ مستند")
    worst_total = 0
    detail = []
    for s in syms:
        closes = [float(x) for x in fx[s]["close"]]
        for period in (5, 7, 14):
            for win in (period + 2, 35, 60, 120, len(closes)):
                if win > len(closes) or win < period + 2:
                    continue
                x = closes[-win:] if win < len(closes) else closes
                got = CH._fts_rsi(x, period)
                ref = O.rsi(x, period, "wilder")
                bad, first, nulls = nbad(got, ref, RT1)
                worst_total += bad
                if bad or nulls:
                    detail.append("%s p=%d win=%d bad=%d first=%s nulls=%s"
                                  % (s, period, win, bad, first, nulls))
                lead = 0
                while lead < len(got) and got[lead] is None:
                    lead += 1
                if lead != period or len(got) != len(x):
                    detail.append("warmup %s p=%d win=%d lead=%d len=%d/%d"
                                  % (s, period, win, lead, len(got), len(x)))
    ck(worst_total == 0, "۶ نماد × دوره‌هایِ ۵/۷/۱۴ × پنجره‌هایِ مختلف = صفرِ واگرایی",
       "; ".join(detail[:3]))
    ck(not any("warmup" in d for d in detail),
       "warmup درِ همه‌جا دقیقاً period سطرِ None است و خروجی هم‌طولِ ورودی",
       "; ".join(d for d in detail if "warmup" in d)[:120])
    up = CH._fts_rsi([100.0 + i for i in range(40)], 14)
    dn = CH._fts_rsi([300.0 - i for i in range(40)], 14)
    ck(up[39] == 100.0, "سریِ صعودیِ خالص → ۱۰۰٫۰", str(up[39]))
    ck(dn[39] == 0.0, "سریِ نزولیِ خالص → ۰٫۰", str(dn[39]))
    ck(CH._fts_rsi([10.0, 11.0, 12.0], 14) == [None] * 3,
       "کمبودِ داده → همه None (نه صفرِ سبز)", str(CH._fts_rsi([10.0, 11.0, 12.0], 14)))
    closes = [float(x) for x in fx["فولاد"]["close"]]
    ck(CH._fts_rsi(closes, 14)[:14] == [None] * 14 and CH._fts_rsi(closes, 14)[14] is not None,
       "نخستینِ عدد دقیقاً درِ index 14 می‌نشیند", str(CH._fts_rsi(closes, 14)[13:16]))
    bad_old, first_old, _ = nbad(rsi_double_step(closes, 14), O.rsi(closes, 14, "wilder"), RT1)
    ck(bad_old > 0 and first_old == 14,
       "کنترلِ منفی: حلقۀِ معیوب (بذر + گامِ اضافی) درِ همان سطرِ نخست قرمز می‌شود",
       "bad=%d first=%s" % (bad_old, first_old))
    short = closes[-35:]
    d_old = abs(rsi_double_step(short, 14)[-1] - O.rsi(short, 14, "wilder")[-1])
    d_new = abs(CH._fts_rsi(short, 14)[-1] - O.rsi(short, 14, "wilder")[-1])
    ck(d_new <= 0.05 and d_old > d_new,
       "پنجرۀ ۳۵ سطری: اصلاح‌شده ≤۰٫۰۵ و معیوب بدتر بود (Δ_old=%.2f → Δ_new=%.2f)" % (d_old, d_new))

    # ══════════════════════ ۳) _fts_scaled ══════════════════════
    print("\n— ۳) `_fts_scaled`: last و closing دو ستونِ جدا؛ close فقط از price_basis")

    def rnd(v):
        import math
        return float(math.floor(v + 0.5)) if v >= 0 else v

    def build(sym, n=120):
        d = fx[sym]
        cd = [{"time": t, "open": o, "high": h, "low": l, "closing": cl, "close": cl,
               "last": ls, "volume": vol}
              for t, o, h, l, cl, ls, vol in zip(d["time"][-n:], d["open"][-n:], d["high"][-n:],
                                                  d["low"][-n:], d["close"][-n:], d["last"][-n:],
                                                  d["volume"][-n:])]
        return cd

    ladder_days = {}
    sym = "شپنا"
    cd = build(sym)
    # ضریبِ پلکانی: ۶۰ سطرِ اول ×۲ (رویدادِ تعدیلِ بعدی)، بقیه ×۱ — همان contractِ factor(t)
    split = 60
    fac = [{"time": c["time"], "factor": (2.0 if i < split else 1.0)} for i, c in enumerate(cd)]
    vols = [{"time": c["time"], "value": c["volume"] * 1.0} for c in cd]

    price_basis.set_basis("closing")
    sc_c = CH._fts_scaled(cd, fac, vols)
    price_basis.set_basis("last")
    CH.PATTERNS_CACHE.clear()
    sc_l = CH._fts_scaled(cd, fac, vols)
    price_basis.set_basis("closing")

    ck(len(sc_c) == len(cd) and sc_c[0]["time"] < sc_c[-1]["time"],
       "سری صعودی و هم‌طول می‌ماند", "%d/%d" % (len(sc_c), len(cd)))
    mism_closing = [i for i, (c, raw) in enumerate(zip(sc_c, cd))
                    if c["closing"] != rnd(float(raw["closing"]) * (2.0 if i < split else 1.0))]
    ck(not mism_closing, "closing = پایانیِ خام × k (لنگرِ تعدیل)",
       "سطرهایِ بد: %s" % mism_closing[:4])
    mism_last = [i for i, (c, raw) in enumerate(zip(sc_c, cd))
                 if c["last"] != (rnd(float(raw["last"]) * (2.0 if i < split else 1.0))
                                  if raw["last"] else None)]
    ck(not mism_last, "last = آخرینِ خام × k — ازِ closing بازسازی نمی‌شود",
       "سطرهایِ بد: %s" % mism_last[:4])
    n_fake = sum(1 for c in sc_c if c["last"] is not None and c["closing"] is not None
                 and c["closing"] != c["last"] and c["close"] != c["closing"])
    ck(n_fake == 0,
       "درِ مبنایِ closing هیچ سطری close‌اش از last ساخته نشده (last≠closing در %d سطر)"
       % sum(1 for a in sc_c if a["last"] != a["closing"]),
       "سطرهایِ مشکوک: %d" % n_fake)
    ck(sc_l and sc_l[-1]["close"] == sc_l[-1]["last"],
       "درِ مبنایِ last، closeِ موتور ازِ last می‌آید (resolver، نه ساختِ مصنوعی)",
       str(sc_l[-1] if sc_l else "empty"))
    diff_rows = sum(1 for a, b in zip(sc_c, sc_l) if a["close"] != b["close"])
    ck(diff_rows > 0,
       "دو مبنایِ real واقعاً دو عددِ متفاوت به موتور می‌دهند (%d سطر از %d)" % (diff_rows, len(sc_c)))
    no_last = [{"time": c["time"], "open": c["open"], "high": c["high"], "low": c["low"],
                "closing": c["closing"], "close": c["close"], "last": None,
                "volume": c["volume"]} for c in cd[:40]]
    fac_any = [{"time": c["time"], "factor": 1.0} for c in no_last]
    price_basis.set_basis("last")
    sc_none = CH._fts_scaled(no_last, fac_any, [])
    price_basis.set_basis("closing")
    ck(all(c["last"] is None for c in sc_none),
       "سریِ بی‌«آخرین» (مثلِ شاخصِ کل): last صریح None می‌ماند، نه close",
       str([c["last"] for c in sc_none[:3]]))
    ck(all(c["close"] == c["closing"] for c in sc_none),
       "و درِ همان حالت close بهِ closing برمی‌گردد (فقط با اعلامِ last_missing)",
       str([(c["close"], c["closing"]) for c in sc_none[:2]]))
    bad_vol = [i for i, (c, raw) in enumerate(zip(sc_c, cd))
               if c["volume"] != rnd(float(raw["volume"]) / (2.0 if i < split else 1.0))]
    ck(not bad_vol, "volume ÷ k (ارزشِ معامله ثابت می‌ماند) — عینِ قرینۀ فرانت",
       "سطرهایِ بد: %s" % bad_vol[:4])
    old_fake = [{"time": c["time"], "close": rnd(float(c["closing"]) * (2.0 if i < split else 1.0)),
                 "last": rnd(float(c["closing"]) * (2.0 if i < split else 1.0))}
                for i, c in enumerate(cd)]
    ck(sum(1 for c, o in zip(sc_l, old_fake) if c["last"] != o["last"]) > 0,
       "کنترلِ منفی: منطقِ قدیمی (last:=close×k) همین ورودی را با product فرق می‌داد")

    # ══════════════════════ ۴) دودِ مسیرِ FTS ══════════════════════
    print("\n— ۴) موتورِ FTS رویِ سریِ اصلاح‌شده می‌دود و عددِ ساعتِ شنی finite است")
    price_basis.set_basis("closing")
    fts = CH._fts_analyze_candles(sym, sc_c)
    hg = (fts.get("hourglass") or {})
    ck(isinstance(fts, dict) and fts.get("trend"), "تحلیلِ کامل برمی‌گردد",
       str(list(fts)[:6]))
    ck(hg.get("weekly_rsi5") is None or 0.0 <= float(hg.get("weekly_rsi5")) <= 100.0,
       "weekly_rsi5 درِ بازۀ ۰..۱۰۰ است (یا صریح None)", str(hg))
    l4 = (fts.get("exit_engine") or {}).get("l4") or {}
    ck("rsi" not in l4 or l4.get("rsi") is None or 0.0 <= float(l4["rsi"]) <= 100.0,
       "RSIِ لایۀ ۴ درِ بازۀ منطقی است", str({k: l4.get(k) for k in ("rsi", "divergence")}))

    print("\nنتیجه: %d سبز، %d قرمز" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
