"""trend_classify — طبقه‌بندِ ترکیبیِ روند، قابل‌مصرف درِ backend (P0-3).

drop-in برایِ `_fts_classify_trend`: همان امضا `(swings, series=...)` و همان
کلیدهایِ خروجی (trend/basis/hh/hl/last_high/.../times/stale_bars/window) را برمی‌گرداند
تا matrixِ دروازۀ هفتگی، `_fts_trend_reason`، جت و UI بدونِ تغییر کار کنند. واژگانِ
`trend` هم‌راستاست: خنثی→`range`، نبودِ داده→`na`. به‌علاوه کلیدهایِ ممیزیِ
`confidence/outcome/evidence/reason_codes` اضافه می‌شوند (مصرف‌کننده‌هایِ کهنه نادیده می‌گیرند).

مؤلفه‌ها: ساختارِ پیوت + حفظ/شکستِ سطح؛ شیبِ ATR-نرمال در چند پنجره؛ آرایشِ MA؛
نسبتِ کارایی. داورِ انحصاری آستانۀِ درصدیِ ثابت نیست. هیچ آستانۀِ FTS دیگری اینجا
نیامده؛ این فقط «برچسبِ روند» را می‌سازد، نه جت و نه دروازۀِ قیف.
"""
import math

SLOPE_WINDOWS = (20, 50, 120)
NEUTRAL_BAND = 0.12   # بر حسبِ امتیازِ ترکیبیِ نرمال [-1,1]، نه درصدِ قیمت
WEIGHTS = {"structure": 1.3, "slope": 1.2, "ma": 1.0, "eff": 0.9}
# کفِ تحلیل از نیازِ الگوریتم: تأییدِ ۲+۲ پیوت (≈۳۰ کندلِ روزانه) یا دو محورِ مستقل.
# عمداً ۶۰ کندلِ جت اینجا تعمیم داده نشده.
MIN_WEEKLY = 8


def _atr_pct(candles, n=14):
    if len(candles) < n + 1:
        return None
    trs = [max(candles[i]["high"] - candles[i]["low"],
               abs(candles[i]["high"] - candles[i - 1]["close"]),
               abs(candles[i]["low"] - candles[i - 1]["close"]))
           for i in range(1, len(candles))]
    atr = sum(trs[-n:]) / n
    last = candles[-1]["close"]
    return atr / last if last > 0 else None


def _slope(closes, ap):
    if not ap or ap <= 0:
        return 0.0, {}, False
    acc = wsum = 0.0
    per = {}
    for w in SLOPE_WINDOWS:
        if len(closes) <= w:
            continue
        z = ((closes[-1] - closes[-1 - w]) / closes[-1 - w] / w) / ap
        acc += math.tanh(z * 20.0) * w
        wsum += w
        per[f"slope{w}"] = round(z, 4)
    return (acc / wsum if wsum else 0.0), per, wsum > 0


def _ma(closes):
    def m(n):
        return sum(closes[-n:]) / n if len(closes) >= n else None
    m20, m50, m200, last = m(20), m(50), m(200), closes[-1]
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


def _eff(closes, n=30):
    if len(closes) <= n + 1:
        return 0.0, None, False
    net = abs(closes[-1] - closes[-1 - n])
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(len(closes) - n, len(closes)))
    er = net / path if path else 0.0
    return (er * (1 if closes[-1] >= closes[-1 - n] else -1)), round(er, 3), True


def _structure(swings):
    highs = [s for s in swings if s["kind"] == "high"]
    lows = [s for s in swings if s["kind"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return 0.0, {"structure": "کم‌پیوت"}, False
    h1, h0 = highs[-1]["price"], highs[-2]["price"]
    l1, l0 = lows[-1]["price"], lows[-2]["price"]
    hh, hl, lh, ll = h1 > h0, l1 > l0, h1 < h0, l1 < l0
    label = "HH+HL" if (hh and hl) else "LL+LH" if (ll and lh) else \
            "HH+LL" if (hh and ll) else "LH+HL" if (lh and hl) else "flat"
    v = {"HH+HL": 1.0, "LL+LH": -1.0}.get(label, 0.0)
    if label in ("HH+LL", "LH+HL"):
        struct_low = min(s["price"] for s in lows[-min(4, len(lows)):])
        struct_high = max(s["price"] for s in highs[-min(4, len(highs)):])
        if hl and l1 >= struct_low:
            v = 0.5
        elif ll and h1 <= struct_high:
            v = -0.5
    return v, {"structure": label, "last_high": round(h1, 2), "prev_high": round(h0, 2),
               "last_low": round(l1, 2), "prev_low": round(l0, 2),
               "last_high_time": highs[-1].get("time"), "prev_high_time": highs[-2].get("time"),
               "last_low_time": lows[-1].get("time"), "prev_low_time": lows[-2].get("time")}, True


def classify_trend(swings, series=None):
    """drop-in برایِ `_fts_classify_trend`. swings رویِ همان تایم‌فریمِ series."""
    candles = series or []
    closes = [c["close"] for c in candles]
    is_weekly = len(candles) < 60   # هفتگی کندلِ کمتری دارد؛ کفِ تحلیلِ هفتگی کوچک‌تر است
    sv, sevid, s_ok = _structure(swings)
    ap = _atr_pct(candles)
    lv, levid, l_ok = _slope(closes, ap)
    mv, mevid, m_ok = _ma(closes)
    ev, er, e_ok = _eff(closes)

    available = [k for k, ok in (("structure", s_ok), ("slope", l_ok), ("ma", m_ok), ("eff", e_ok)) if ok]
    sufficient = s_ok or (len([x for x in (l_ok, m_ok, e_ok) if x]) >= 2)
    base = {"hh": None, "hl": None, "basis": "hybrid", "last_high": None, "prev_high": None,
            "last_low": None, "prev_low": None, "last_high_time": None, "prev_high_time": None,
            "last_low_time": None, "prev_low_time": None, "stale_bars": None, "window": None}
    if not sufficient:
        return {**base, "trend": "na", "outcome": "insufficient_data", "confidence": 0.0,
                "score": None, "evidence": {"structure": sevid, "slope": levid, "ma": mevid, "er": er},
                "reason_codes": ["MISSING:" + ",".join(
                    k for k, ok in (("structure", s_ok), ("slope", l_ok), ("ma", m_ok), ("eff", e_ok)) if not ok)]}

    score = (WEIGHTS["structure"] * sv + WEIGHTS["slope"] * lv +
             WEIGHTS["ma"] * mv + WEIGHTS["eff"] * ev) / sum(WEIGHTS.values())
    raw = "neutral" if abs(score) < NEUTRAL_BAND else ("up" if score > 0 else "down")
    # نگاشتِ واژگانِ legacy تا matrix/UI/جت بدونِ تغییر بخوانند: neutral→range
    trend = {"up": "up", "down": "down", "neutral": "range"}[raw]

    votes = {"structure": sv, "slope": lv, "ma": mv, "eff": ev}
    pro = [k for k, v in votes.items() if (v > 0 and raw == "up") or (v < 0 and raw == "down")]
    con = [k for k, v in votes.items() if (v < 0 and raw == "up") or (v > 0 and raw == "down")]
    decisive = [1 if v > 0 else -1 for v in (sv, lv, mv) if abs(v) > 1e-9]
    agreement = (abs(sum(decisive)) / len(decisive)) if decisive else 0.0
    strength = min(1.0, abs(score) / 0.6)
    depth = min(1.0, len(candles) / (40 if is_weekly else 120))
    confidence = round(max(0.0, min(1.0, (0.5 * agreement + 0.3 * strength +
                         0.2 * (er if er is not None else 0.0)) * (0.5 + 0.5 * depth))), 3)

    return {**base, **{k: sevid.get(k) for k in
                       ("last_high", "prev_high", "last_low", "prev_low",
                        "last_high_time", "prev_high_time", "last_low_time", "prev_low_time")},
            "hh": sevid.get("structure") == "HH+HL", "hl": sevid.get("structure") in ("HH+HL", "LH+HL"),
            "trend": trend, "outcome": "classified", "confidence": confidence,
            "score": round(score, 4), "method_agreement": round(agreement, 3),
            "evidence": {"structure": sevid, "slope": levid, "ma": mevid, "er": er,
                         "votes": votes, "pro": pro, "con": con},
            "reason_codes": [f"structure={sevid.get('structure')}", f"slopeZ={levid}",
                             f"ma={mevid}", f"ER={er}", f"raw={raw}", f"score={round(score,3)}",
                             f"pro={pro}", f"con={con}", f"bars={len(candles)}"]}
