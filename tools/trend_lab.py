"""trend_lab — طبقه‌بندِ ترکیبیِ روند (آزمایشگاهِ مستقل؛ رابطِ مصرف‌کننده دست‌نخورده).

هدفِ مالک: پوششِ کاملِ «تلاش برایِ تحلیل»، نه تحمیلِ برچسب. پس سه سرآمد:
  • classified → trend ∈ {up,down,neutral}، حتی وقتی شواهد متعارض‌اند: ترکیب می‌شوند،
    بهترینِ پشتیبانی‌شده با confidence گزارش و دلایلِ موافق/مخالف ثبت می‌شود. صرفِ
    اختلافِ ساختارِ سقف/کف مجوزِ abstain نیست.
  • insufficient_data → فقط وقتی تاریخچه/اعتبار/تأییدِ پیوت واقعاً ممکن نیست. شکست نیست.
  • «فرار به unknown با شواهدِ کافی» = شکستِ تحلیل ⇒ صفرِ آن سنجیده می‌شود.
neutral جایِ «نبودِ داده» یا «عدمِ قطعیت» را نمی‌گیرد.

داورِ انحصاری، آستانۀِ درصدیِ ثابت نیست؛ شیب با نوسانِ خودِ نماد (ATR%) نرمال می‌شود.
کفِ تحلیل از نیازِ واقعیِ الگوریتم (تأییدِ پیوت / کوچک‌ترین پنجرۀِ شیب) می‌آید، نه
تعمیرِ ۶۰ کندلِ جت. as_of برشِ واقعی می‌کند؛ مبنایِ تعدیلِ ذخیره‌شده رعایت و هیچ
دادهٔ بعد از T به تحلیلِ T نمی‌رسد. منطقِ جت و قواعدِ دروازۀِ هفتگیِ قیف به این
پروژۀِ موازی گره نمی‌خورند.

اجرا:  python tools/trend_lab.py
"""
import csv
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import chart as CH  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "market.db")
CORPUS = os.path.join(ROOT, "_audit", "FTS_TREND_CORPUS.csv")

SLOPE_WINDOWS = (20, 50, 120)   # بلندترینِ پنجره‌ای که درِ داده جا شود استفاده می‌شود
# آستانهٔ «باندِ خنثی» بر حسبِ امتیازِ ترکیبیِ نرمال است ([-1,1])، نه درصدِ قیمت.
NEUTRAL_BAND = 0.12
WEIGHTS = {"structure": 1.3, "slope": 1.2, "ma": 1.0, "eff": 0.9}


def load_candles(cur, symbol, as_of):
    """OHLCV صعودی تا as_of (برشِ واقعیِ تاریخی؛ بی‌نشتِ آینده).

    هشدار: این مسیر `price_history` خام را می‌دهد و تعدیلِ عملکردی را اعمال
    نمی‌کند؛ برایِ سنجشِ هم‌مبنا باِ production از `load_candles_fts` استفاده کن.
    این تابع فقط برایِ مواردِ آفلاین/فرضیِ نگه‌دارنده نگه داشته شده است.
    """
    cur.execute("SELECT date,open,high,low,close FROM price_history "
                "WHERE symbol=? AND date<=? ORDER BY date", (symbol, as_of))
    out = []
    for d, o, h, l, c in cur.fetchall():
        try:
            out.append({"time": str(d)[:10], "open": float(o), "high": float(h),
                        "low": float(l), "close": float(c)})
        except (TypeError, ValueError):
            continue
    return out


def load_candles_fts(symbol, as_of=None):
    """سریِ کندلِ تعدیل‌شده از همان مسیرِ production (`_fts_analysis_series`).

    سنجشِ روند باید رویِ همان داده‌ای باشد کهِ production می‌بیند (تعدیلِ عملکردی،
    لنگرِ CDN/بانکِ محلی). بی‌این، ابزارِ خامِ `price_history` شکافِ افزایشِ سرمایه
    را ریزشِ واقعی می‌شمارد و مارون را «نزولی» می‌داد در حالی کهِ production «صعودی»
    می‌گوید. برشِ as_of باِ همان `_candles_upto_asof`ِ موتور انجام می‌شود.
    بازگشت: (candles, basis)؛ candles خالی اگر هیچ منبعی نبود.
    """
    try:
        series, basis = CH._fts_analysis_series(symbol)
    except Exception:
        return [], "unavailable"
    if as_of:
        series = CH._candles_upto_asof(series, as_of)
    return series, basis


def atr_pct(candles, n=14):
    if len(candles) < n + 1:
        return None
    trs = [max(candles[i]["high"] - candles[i]["low"],
               abs(candles[i]["high"] - candles[i - 1]["close"]),
               abs(candles[i]["low"] - candles[i - 1]["close"]))
           for i in range(1, len(candles))]
    atr = sum(trs[-n:]) / n
    last = candles[-1]["close"]
    return atr / last if last > 0 else None


def slope_vote(candles, ap):
    if not ap or ap <= 0:
        return 0.0, {}, False
    closes = [c["close"] for c in candles]
    per, acc, wsum = {}, 0.0, 0.0
    for w in SLOPE_WINDOWS:
        if len(closes) <= w:
            continue
        net = (closes[-1] - closes[-1 - w]) / closes[-1 - w]
        z = (net / w) / ap
        v = math.tanh(z * 20.0)
        acc += v * w
        wsum += w
        per[f"slope{w}"] = round(z, 4)
    return (acc / wsum if wsum else 0.0), per, wsum > 0


def ma_vote(candles):
    closes = [c["close"] for c in candles]
    if not closes:
        return 0.0, {"ma": "no-data"}, False
    def ma(n):
        return sum(closes[-n:]) / n if len(closes) >= n else None
    m20, m50, m200, last = ma(20), ma(50), ma(200), closes[-1]
    votes = []
    if m20 and m50:
        votes.append(1 if m20 > m50 else -1)
    if m50 and m200:
        votes.append(1 if m50 > m200 else -1)
    if m50:
        votes.append(1 if last > m50 else -1)
    if not votes:
        return 0.0, {"ma": "insufficient"}, False
    return sum(votes) / len(votes), {"ma20_gt_50": bool(m20 and m50 and m20 > m50),
                                     "ma50_gt_200": bool(m50 and m200 and m50 > m200),
                                     "px_gt_ma50": bool(m50 and last > m50)}, True


def efficiency_vote(candles, n=30):
    closes = [c["close"] for c in candles]
    if len(closes) <= n + 1:
        return 0.0, None, False
    net = abs(closes[-1] - closes[-1 - n])
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(len(closes) - n, len(closes)))
    er = net / path if path else 0.0
    direction = 1 if closes[-1] >= closes[-1 - n] else -1
    return er * direction, round(er, 3), True


def structure_vote(candles, tf):
    series = candles if tf == "D" else (CH._fts_resample(candles, "W") if len(candles) >= 4 else [])
    if len(series) < 6:
        return 0.0, {"structure": "no-series"}, False
    swings = CH._fts_swings(series, k=CH._FTS_SWING_K if tf == "D" else 2)
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return 0.0, {"structure": "کم‌پیوت (۲+۲ تأیید نشد)", "hiv": len(highs), "liv": len(lows)}, False
    h1, h0 = highs[-1]["price"], highs[-2]["price"]
    l1, l0 = lows[-1]["price"], lows[-2]["price"]
    hh, hl = h1 > h0, l1 > l0
    lh, ll = h1 < h0, l1 < l0
    label = "HH+HL" if (hh and hl) else "LL+LH" if (ll and lh) else \
            "HH+LL" if (hh and ll) else "LH+HL" if (lh and hl) else "flat"
    v = {"HH+HL": 1.0, "LL+LH": -1.0}.get(label, 0.0)
    # حفظِ سطحِ کلیدی: درِ ساختارِ مختلط، آیا HLِ ساختاری نشکسته (up) یا LHِ ساختاری نشکسته (down)
    if label in ("HH+LL", "LH+HL"):
        struct_low = min(s["price"] for s in lows[-min(4, len(lows)):])
        struct_high = max(s["price"] for s in highs[-min(4, len(highs)):])
        if hl and l1 >= struct_low:
            v = 0.5
        elif ll and h1 <= struct_high:
            v = -0.5
    return v, {"structure": label, "last_high": round(h1, 4), "prev_high": round(h0, 4),
               "last_low": round(l1, 4), "prev_low": round(l0, 4)}, True


def classify_one(candles, tf, as_of, symbol):
    if not candles:
        return {"symbol": symbol, "timeframe": tf, "as_of": as_of, "outcome": "insufficient_data",
                "trend": None, "confidence": 0.0, "score": None,
                "data_quality": {"bars": 0, "atr_pct": None, "evidence_available": []},
                "reason_codes": ["MISSING:no-data-at-or-before-as_of"], "evidence": {}}
    sv, sevid, s_ok = structure_vote(candles, tf)
    ap = atr_pct(candles)
    lv, levid, l_ok = slope_vote(candles, ap)
    mv, mevid, m_ok = ma_vote(candles)
    ev, er, e_ok = efficiency_vote(candles)

    available = [k for k, ok in (("structure", s_ok), ("slope", l_ok),
                                 ("ma", m_ok), ("eff", e_ok)) if ok]
    # کافی‌بودنِ شواهد از نیازِ واقعیِ الگوریتم: یا ساختارِ تأییدشده، یا دستِ‌کم
    # دو محورِ مستقلِ شیب/میانگین/کارایی. بی‌این ⇒ insufficient_data (نه neutral/unknown).
    sufficient = s_ok or (len([x for x in (l_ok, m_ok, e_ok) if x]) >= 2)
    if not sufficient:
        return {"symbol": symbol, "timeframe": tf, "as_of": as_of, "outcome": "insufficient_data",
                "trend": None, "confidence": 0.0, "score": None,
                "data_quality": {"bars": len(candles), "atr_pct": round(ap, 4) if ap else None,
                                 "evidence_available": available},
                "reason_codes": ["MISSING:" + ",".join(
                    k for k, ok in (("structure", s_ok), ("slope", l_ok), ("ma", m_ok), ("eff", e_ok)) if not ok)],
                "evidence": {"structure": sevid, "slope": levid, "ma": mevid, "er": er}}

    score = (WEIGHTS["structure"] * sv + WEIGHTS["slope"] * lv +
             WEIGHTS["ma"] * mv + WEIGHTS["eff"] * ev) / sum(WEIGHTS.values())
    trend = "neutral" if abs(score) < NEUTRAL_BAND else ("up" if score > 0 else "down")

    votes = {"structure": sv, "slope": lv, "ma": mv, "eff": ev}
    pro = [k for k, v in votes.items() if (v > 0 and trend == "up") or (v < 0 and trend == "down")]
    con = [k for k, v in votes.items() if (v < 0 and trend == "up") or (v > 0 and trend == "down")]
    decisive = [1 if v > 0 else -1 for v in (sv, lv, mv) if abs(v) > 1e-9]
    agreement = (abs(sum(decisive)) / len(decisive)) if decisive else 0.0

    strength = min(1.0, abs(score) / 0.6)
    depth = min(1.0, len(candles) / (120 if tf == "D" else 40))   # اشباعِ عمقِ داده
    conf = round(max(0.0, min(1.0, (0.5 * agreement + 0.3 * strength +
                       0.2 * (er if er is not None else 0.0)) * (0.5 + 0.5 * depth))), 3)
    codes = [f"structure={sevid.get('structure')}", f"slopeZ={levid}",
             f"ma={mevid}", f"ER={er}", f"score={round(score,3)}",
             f"pro={pro}", f"con={con}", f"agreement={round(agreement,2)}",
             f"bars={len(candles)}", f"atr%={round(ap,4) if ap else None}"]
    return {"symbol": symbol, "timeframe": tf, "as_of": as_of, "outcome": "classified",
            "trend": trend, "confidence": conf, "score": round(score, 4),
            "data_quality": {"bars": len(candles), "atr_pct": round(ap, 4) if ap else None,
                             "evidence_available": available},
            "method_agreement": round(agreement, 3), "reason_codes": codes,
            "evidence": {"structure": sevid, "slope": levid, "ma": mevid, "er": er,
                         "votes": votes, "pro": pro, "con": con}}


def main():
    args = sys.argv[1:]
    rep_mode = "--representative" in args
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()
    pairs = []
    if rep_mode:
        # نمایندهٔ طبقاتی از عرضِ عمقِ تاریخچه (کوتاه→بلند) تا همِ پوششِ تحلیل و همِ
        # سرآمدِ insufficient_data آزموده شود. یک as_ofِ فعلی + دو برشِ تاریخی.
        cur.execute("SELECT symbol, COUNT(*) n FROM price_history GROUP BY symbol")
        counts = cur.fetchall()
        counts.sort(key=lambda r: r[1])
        step = max(1, len(counts) // 40)
        picked = [counts[i][0] for i in range(0, len(counts), step)][: 48]
        for sym in picked:
            latest, _b = load_candles_fts(sym, None)
            if not latest:
                continue
            last = latest[-1]["time"]
            pts = sorted({last, latest[max(0, len(latest) - 60)]["time"],
                          latest[max(0, len(latest) - 150)]["time"]})
            for as_of in pts:
                pairs.append((sym, as_of))
    elif os.path.exists(CORPUS):
        with open(CORPUS, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                pairs.append((r["symbol"], r["as_of"]))
    else:
        print("corpus نیست؛ اول tools/fts_trend_corpus.py")
        return

    rows = []
    for sym, as_of in pairs:
        daily, _b = load_candles_fts(sym, as_of)
        weekly = CH._fts_resample(daily, "W") if len(daily) >= 4 else []
        rows.append(classify_one(daily, "D", as_of, sym))
        rows.append(classify_one(weekly, "W", as_of, sym))
    conn.close()

    from collections import Counter
    classified = [r for r in rows if r["outcome"] == "classified"]
    insufficient = [r for r in rows if r["outcome"] == "insufficient_data"]
    failures = [r for r in rows if r.get("trend") == "unknown"]
    dist = Counter(r["trend"] for r in classified)
    confs = [r["confidence"] for r in classified]
    agree = [r.get("method_agreement", 0) for r in classified]
    keyrows = {}
    for r in classified:
        keyrows.setdefault((r["symbol"], r["timeframe"]), []).append(r["trend"])
    flips = sum(1 for v in keyrows.values() if len(set(v)) > 1)

    mode = "REPRESENTATIVE (طبقاتِ عمق)" if rep_mode else "CORPUS (FTS_TREND_CORPUS.csv)"
    print(f"— {mode} —")
    print(f"تلاش برایِ تحلیل: {len(rows)}  (پوششِ تلاش = ۱۰۰٪)")
    print(f"  classified: {len(classified)} | insufficient_data: {len(insufficient)} | شکست(unknown با شواهد): {len(failures)}")
    print(f"  پوششِ تصمیم = {round(100*len(classified)/len(rows),1)}٪  (insufficient_data شکست نیست؛ فرارِ نادرست به unknown باید صفر باشد)")
    print("توزیعِ برچسب:", dict(dist))
    if confs:
        print(f"اعتماد: میانگین={round(sum(confs)/len(confs),3)}  "
              f"کم‌اعتماد(<۰٫۴)={sum(1 for c in confs if c<0.4)}  توافّقِ روش‌ها={round(sum(agree)/len(agree),3)}")
    print(f"پایداریِ زمانی (چند as_of per symbol): {flips} از {len(keyrows)} (symbol,tf) برچسب عوض کردند")

    # تفکیکِ پوشش بر حسبِ عمقِ تاریخچه ⇒ نشان می‌دهد insufficient فقط درِ کم‌عمق است
    if rep_mode:
        depthbuckets = {}
        for r in rows:
            b = r["data_quality"]["bars"]
            bucket = "<30" if b < 30 else "30-59" if b < 60 else "60-119" if b < 120 else "120+"
            depthbuckets.setdefault(bucket, Counter())[r["outcome"]] += 1
        print("پوشش بر حسبِ عمقِ کندل:")
        for bk in ["<30", "30-59", "60-119", "120+"]:
            if bk in depthbuckets:
                c = depthbuckets[bk]
                tot = sum(c.values())
                print(f"  {bk:>7}: classified={c['classified']}/{tot}  insufficient_data={c['insufficient_data']}/{tot}")
    print("⚠ پوشش ≠ صحت؛ دقتِ قطعی بدونِ مرجعِ مستقل/داوریِ مالک ادعا نمی‌شود.")

    name = "FTS_TREND_LAB_REP.csv" if rep_mode else "FTS_TREND_LAB_AUDIT.csv"
    out_csv = os.path.join(ROOT, "_audit", name)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "timeframe", "as_of", "outcome", "trend", "confidence", "score",
                    "agreement", "bars", "atr_pct", "structure", "ER", "pro", "con", "reasons"])
        for r in rows:
            ev = r.get("evidence", {})
            dq = r.get("data_quality", {})
            w.writerow([r["symbol"], r["timeframe"], r["as_of"], r["outcome"], r["trend"],
                        r["confidence"], r.get("score"), r.get("method_agreement"),
                        dq.get("bars"), dq.get("atr_pct"), ev.get("structure", {}).get("structure"),
                        ev.get("er"), "|".join(ev.get("pro", []) or []), "|".join(ev.get("con", []) or []),
                        " ; ".join(r.get("reason_codes", []))])
    print(f"ممیزیِ کامل → {out_csv}")


if __name__ == "__main__":
    main()
