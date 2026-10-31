#!/usr/bin/env python
"""وکتورهایِ نام‌دارِ موتورِ FTS (B3) — خروجیِ خودِ پایتون رویِ سری‌هایِ ساختگی.

هر سری یک شاخهٔ مشخص را می‌زند (up/down/range/oneway/short/jet/choch/point/dbl).
خروجی: backend-go/internal/chart/testdata/fts_vectors.json؛ تستِ Go هر خروجی را
با همان تابع مقایسه می‌کند و گاردِ B3 تازگیِ فایل را با اجرایِ دوباره می‌سنجد.

اجرا: python tools/parity/gen_fts_vectors.py [--out PATH]
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import tempfile


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DEFAULT_OUT = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "fts_vectors.json")
BASE_DAY = _dt.date(2025, 1, 1)


def prepare(tmp):
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def row(i, o, h, l, c, v=None):
    lo = min(o, c, l)
    hi = max(o, c, h)
    vol = v if v is not None else 1000.0 + 10.0 * (i % 7)
    return {"time": (BASE_DAY + _dt.timedelta(days=i)).isoformat(),
            "open": round(o, 4), "high": round(hi, 4), "low": round(lo, 4),
            "close": round(c, 4), "volume": vol}


def wave(n, base, drift, amp, period, phase=0.0):
    out = []
    for i in range(n):
        mid = base + drift * i
        c = mid + amp * math.sin(i / period + phase)
        o = mid + amp * math.sin((i - 0.5) / period + phase)
        extra = abs(math.sin(i * 0.37)) * amp * 0.35 + 1.5
        out.append(row(i, o, max(o, c) + extra, min(o, c) - extra, c))
    return out


def series(kind):
    if kind == "up":
        return wave(140, 1000.0, 4.0, 40.0, 1.4)
    if kind == "down":
        return wave(140, 1400.0, -3.0, 35.0, 1.3, 0.7)
    if kind == "range":
        return wave(140, 1000.0, 0.0, 80.0, 2.2)
    if kind == "oneway":
        return [row(i, 1000 + 4 * i - 1, 1000 + 4 * i + 1, 1000 + 4 * i - 2,
                    1000 + 4 * i) for i in range(140)]
    if kind == "short":
        return wave(40, 1000.0, 3.0, 30.0, 1.4)
    if kind == "jet":
        out = []
        for i in range(120):
            if i < 105:
                c = 950 + 30 * math.sin(i / 1.3)
                out.append(row(i, c - 4, c + 5, c - 6, c))
            elif i < 117:
                out.append(row(i, 968, 972, 964, 970))
            elif i == 117:
                out.append(row(i, 1000, 1022, 998, 1020))
            elif i == 118:
                out.append(row(i, 1020, 1032, 1018, 1030))
            else:
                out.append(row(i, 1030, 1042, 1028, 1040))
        return out
    if kind == "choch":
        out = wave(100, 1000.0, 4.0, 40.0, 1.4)
        low = min(c["low"] for c in out[-14:])
        crash = low * 0.90
        out.append(row(100, low * 0.99, low * 1.0, crash - 5, crash))
        out.append(row(101, crash, crash + 3, crash - 4, crash - 1))
        return out
    if kind == "point":
        out = []
        for i in range(80):
            if i < 30:
                c = 1100 + 20 * math.sin(i / 2.0)
                out.append(row(i, c - 5, min(1190, c + 8), c - 9, c))
            elif i == 30:
                out.append(row(i, 1100, 1200, 1095, 1110))
            elif i < 45:
                frac = (i - 30) / 15.0
                c = 1110 - 100 * frac
                out.append(row(i, c + 2, c + 6, c - 6, c))
            elif i == 45:
                out.append(row(i, 1010, 1016, 1000, 1012))
            elif i < 60:
                frac = (i - 45) / 15.0
                c = 1012 + 170 * frac
                out.append(row(i, c - 2, min(1195, c + 8), c - 8, c))
            elif i == 60:
                out.append(row(i, 1185, 1200, 1180, 1190))
            elif i < 70:
                frac = (i - 60) / 10.0
                c = 1190 - 185 * frac
                out.append(row(i, c + 3, c + 8, c - 4, c))
            elif i == 70:
                out.append(row(i, 1008, 1012, 1000, 1006))
            elif i < 79:
                c = 1006 + 5 * (i - 70)
                out.append(row(i, c - 3, c + 6, c - 6, c))
            else:
                out.append(row(i, 1010, 1036, 1000, 1030))
        return out
    if kind == "stop":
        out = wave(140, 1000.0, 4.0, 40.0, 1.4)
        prev = out[-2]["close"]
        out[-1] = row(139, prev, prev + 2, 495, 500)
        return out
    if kind == "trail":
        out = wave(90, 1000.0, 5.0, 30.0, 1.4)
        prev = out[-1]["close"]
        for j in range(20):
            c = prev * 0.97
            out.append(row(90 + j, prev * 0.995, prev, c - 3, c))
            prev = c
        return out
    if kind == "roll":
        # رشْدِ بی‌وقفه (RSI اشباع ≥۷۰) و سپس هفت نشستِ عقبنشینیِ ملایم:
        # لایهٔ ۴ باید «چرخشِ اشباعِ خرید» را ببیند، نه واگرایی.
        out = []
        for i in range(130):
            if i < 123:
                c = 900 * (1.0075 ** i) + 6 * math.sin(i / 1.2)
                out.append(row(i, c - 5, c + 7, c - 9, c))
            else:
                c = 900 * (1.0075 ** 122) * (0.994 ** (i - 122))
                out.append(row(i, c + 6, c + 9, c - 4, c))
        return out
    if kind == "tops":
        out = []
        for i in range(150):
            if i < 95:
                c = 1050 + 28 * math.sin(i / 1.7)
                out.append(row(i, c - 4, min(c + 6, 1140), c - 8, c))
            elif i in (100, 115, 130):
                c = {100: 1200, 115: 1200, 130: 1200}[i]
                out.append(row(i, c - 8, c, c - 10, c - 2))
            elif i in (107, 122):
                c = {107: 1100, 122: 1100}[i]
                out.append(row(i, c + 6, c + 9, c, c + 4))
            elif 100 < i < 107:
                c = 1190 - 13 * (i - 100)
                out.append(row(i, c + 3, c + 7, c - 6, c))
            elif 107 < i < 115:
                c = 1108 + 12 * (i - 107)
                out.append(row(i, c - 3, c + 6, c - 7, c))
            elif 115 < i < 122:
                c = 1196 - 13 * (i - 115)
                out.append(row(i, c + 3, c + 7, c - 6, c))
            elif 122 < i < 130:
                c = 1108 + 12 * (i - 122)
                out.append(row(i, c - 3, c + 6, c - 7, c))
            elif i > 130:
                c = 1192 - 16 * (i - 130)
                out.append(row(i, c + 4, c + 8, c - 6, c - 2))
            else:
                c = 1130 + 12 * (i - 95)
                out.append(row(i, c - 4, c + 6, c - 7, c))
        return out
    if kind == "hs":
        out = []
        for i in range(150):
            if i == 100:
                out.append(row(i, 1142, 1150, 1138, 1145))
            elif i == 112:
                out.append(row(i, 1292, 1300, 1288, 1296))
            elif i == 124:
                out.append(row(i, 1152, 1160, 1148, 1156))
            elif i == 106:
                out.append(row(i, 1088, 1092, 1080, 1086))
            elif i == 118:
                out.append(row(i, 1096, 1100, 1090, 1094))
            elif i < 100:
                c = 1000 + 14 * (i / 100.0) * 10 + 20 * math.sin(i / 1.9)
                out.append(row(i, c - 4, c + 6, c - 7, c))
            elif 100 < i < 106:
                c = 1140 - 9 * (i - 100)
                out.append(row(i, c + 3, c + 7, c - 6, c))
            elif 106 < i < 112:
                c = 1090 + 34 * (i - 106)
                out.append(row(i, c - 3, c + 7, c - 7, c))
            elif 112 < i < 118:
                c = 1290 - 33 * (i - 112)
                out.append(row(i, c + 3, c + 7, c - 6, c))
            elif 118 < i < 124:
                c = 1100 + 9 * (i - 118)
                out.append(row(i, c - 3, c + 7, c - 7, c))
            elif 124 < i < 140:
                c = 1150 - 4 * (i - 124)
                out.append(row(i, c + 2, c + 6, c - 6, c))
            else:
                c = 1090 - 6 * (i - 140)
                out.append(row(i, c + 3, c + 6, c - 5, c))
        return out
    if kind == "dbl":
        out = []
        for i in range(80):
            if i < 40:
                c = 1100 + 25 * math.sin(i / 2.1)
                out.append(row(i, c - 4, min(1140, c + 8), c - 8, c))
            elif i == 40:
                out.append(row(i, 1010, 1016, 1000, 1008))
            elif i < 52:
                frac = (i - 40) / 12.0
                c = 1008 + 90 * frac
                out.append(row(i, c - 2, min(1099, c + 6), c - 5, c))
            elif i == 52:
                out.append(row(i, 1095, 1100, 1090, 1098))
            elif i < 65:
                frac = (i - 52) / 13.0
                c = 1098 - 98 * frac
                out.append(row(i, c + 2, min(1099, c + 6), c - 6, c))
            elif i == 65:
                out.append(row(i, 1008, 1012, 1000, 1010))
            else:
                c = 1010 + 10 * (i - 65)
                out.append(row(i, c - 4, min(1150, c + 8), c - 7, c))
        return out
    raise KeyError(kind)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="bors-fts-vectors-")
    prepare(tmp)
    import api.chart as ch
    import price_basis
    import trend_classify

    data = {"series": {}, "cases": {}, "status": {}}
    for kind in ("up", "down", "range", "oneway", "short", "jet", "choch",
                 "point", "dbl", "stop", "trail", "roll", "tops", "hs"):
        candles = series(kind)
        sw = ch._fts_swings(candles, k=ch._FTS_SWING_K)
        w = ch._fts_resample(candles, "W")
        m = ch._fts_resample(candles, "M")
        dbl = ch._fts_double_bottom(candles, sw)
        exit_hint = 1400.0 if kind in ("up", "stop") else None
        out = {
            "swings": sw,
            "weekly": w,
            "monthly": m,
            "trend_d": ch._fts_classify_trend(sw, series=candles),
            "trend_w": ch._fts_classify_trend(ch._fts_swings(w, k=2), series=w),
            "trend_m": ch._fts_classify_trend(ch._fts_swings(m, k=2), series=m),
            "recent": ch._fts_recent_window_trend(candles),
            "reason_d": ch._fts_trend_reason(ch._fts_classify_trend(sw, series=candles)),
            "fib": ch._fts_fib_zones(candles, sw),
            "jet": ch._fts_jet_setup(candles),
            "choch": ch._fts_choch(candles, sw),
            "point_hunt": ch._fts_point_hunt(candles, sw),
            "double_bottom": dbl["double_bottom"],
            "range_box": dbl["range_box"],
            "setups": ch._fts_setup_history(candles, sw),
            "exit": ch._fts_exit_engine(candles, entry_hint=exit_hint),
            "ma14": ch._fts_ma([c["close"] for c in candles], 14),
            "rsi14": ch._fts_rsi([c["close"] for c in candles], 14),
            "hybrid_d": trend_classify.classify_trend(sw, series=candles),
        }
        if kind == "up":
            # تساویِ حدِ ضرر: خرید رویِ همان کفِ ساختاری. max(key=...) درِ پایتون
            # نخستین بیشینه را برمی‌دارد، پس «entry» برنده است نه «swing_low».
            major_low = min(c["low"] for c in candles[:-1][-20:])
            out["exit_tie"] = ch._fts_exit_engine(
                candles, entry_hint=major_low)["l1"]["stop_basis"]
            out["exit_tie_low"] = major_low
        data["series"][kind] = candles
        data["cases"][kind] = out

        # وضعیت: همان outِ موتور + ماتریسِ ساختگی تا ترتیبِ اولویت سنجیده شود.
        base = {
            "exit_engine": out["exit"],
            "jet": out["jet"], "choch": out["choch"],
            "point_hunt": out["point_hunt"],
            "double_bottom": out["double_bottom"], "range_box": out["range_box"],
            "hourglass": {"active": None, "ma52": None},
            "fib": out["fib"],
            "trend": {"matrix": {"decision": "PERMITTED"}},
        }
        data["status"][kind + "_permitted"] = {
            "out": base, "block": ch._fts_status_block(candles, base), "series": kind}
        if kind == "jet":
            rejected = dict(base)
            rejected["trend"] = {"matrix": {"decision": "REJECT"}}
            data["status"]["jet_rejected"] = {
                "out": rejected, "block": ch._fts_status_block(candles, rejected),
                "series": kind}
        if kind == "short":
            empty = {"exit_engine": {"l1": {}, "l2": {}, "l3": {}, "l4": {}},
                     "trend": {"matrix": {"decision": "UNKNOWN"}}}
            data["status"]["short_insufficient"] = {
                "out": empty, "block": ch._fts_status_block(candles, empty),
                "series": kind}

    def synth(flags=None, decision="PERMITTED", fib=None, jet=None, ph=None,
              choch_bullish=False, dbl_active=False, box_active=False,
              hg_active=False, all_none=False):
        f = {"stop_hit": False, "ma14_exit": False, "ma14_exit_pending": False,
             "choch_break": False, "channel_break": False, "third_peak": False,
             "double_top": False, "hs_break": False, "rsi_divergence": False,
             "rsi_rollover": False}
        if flags:
            f.update(flags)
        if all_none:
            f = {k: None for k in f}
            choch_bullish = dbl_active = box_active = hg_active = None
            jet = {"active": None, "resistance": None}
            ph = {"active": None, "floor_price": None, "trigger_date": None}
        if jet is None:
            jet = {"active": False, "resistance": None}
        if ph is None:
            ph = {"active": False, "floor_price": None, "trigger_date": None}
        out = {
            "exit_engine": {
                "l1": {k: f[k] for k in ("stop_hit", "ma14_exit", "ma14_exit_pending")},
                "l2": {k: f[k] for k in ("choch_break", "channel_break")},
                "l3": {k: f[k] for k in ("third_peak", "double_top", "hs_break")},
                "l4": {k: f[k] for k in ("rsi_divergence", "rsi_rollover")},
            },
            "jet": jet, "point_hunt": ph,
            "choch": {"bullish": choch_bullish, "level": 1200.0},
            "double_bottom": {"active": dbl_active, "neckline": 1100.0},
            "range_box": {"active": box_active, "top": 1150.0},
            "hourglass": {"active": hg_active, "ma52": 900.0},
            "fib": fib,
            "trend": {"matrix": {"decision": decision}},
        }
        return out

    ref = series("range")
    cases = [
        ("prec_nosignal", synth()),
        ("prec_stop", synth(flags={"stop_hit": True})),
        ("prec_exit", synth(flags={"ma14_exit": True})),
        ("prec_warning", synth(flags={"rsi_rollover": True})),
        ("prec_veto", synth(decision="REJECT",
                            jet={"active": True, "resistance": 1234.0})),
        ("prec_trigger", synth(ph={"active": True, "floor_price": 1000.0,
                                   "trigger_date": "2025-03-03"})),
        ("prec_context", synth(fib={"zone_33_40": {"in_zone": True},
                                    "zone_618_70": {"in_zone": False}})),
        ("prec_insufficient", synth(all_none=True)),
    ]
    for name, o in cases:
        data["status"][name] = {"out": o, "block": ch._fts_status_block(ref, o),
                                "series": "range"}

    # ساعتِ شنی: هر سه field درِ پایتون داخلِ یک try خوانده می‌شوند، پس یک
    # مقدارِ بی‌اعتبار *هر سه* را رویِ پیش‌فرض می‌گذارد، نه فقط همان field.
    hg_cases = [
        {},
        {"hourglass_rsi_period": 5, "hourglass_rsi_oversold": 40.0,
         "hourglass_ma52_position": "either"},
        {"hourglass_rsi_period": None, "hourglass_rsi_oversold": 45.0},
        {"hourglass_rsi_period": "7", "hourglass_rsi_oversold": 12.0,
         "hourglass_ma52_position": "above"},
        {"hourglass_rsi_period": 200, "hourglass_rsi_oversold": 45.0},
        {"hourglass_rsi_oversold": 45.0},
    ]
    data["hourglass"] = []
    hg_path = os.path.join(tmp, "fts_thresholds.json")
    for payload in hg_cases:
        with open(hg_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        ch._FTS_HG_SETTINGS_CACHE["signature"] = None
        ch._FTS_HG_SETTINGS_CACHE["values"] = None
        data["hourglass"].append({"file": payload, "values": ch._fts_hourglass_settings()})
    if os.path.exists(hg_path):
        os.remove(hg_path)

    # مسیرِ `_fts_scaled` — ضریبِ صفر/منفی/تهی، ردیفِ بی‌`last`، `last=0`
    # (falsy ⇒ None، نه close×k)، `time`ِ بلند/کوتاه، متنِ عددی، و ردیفِ تهیِ صفر.
    # عمداً ردیفی با high/lowِ مثبت و close تهی نمی‌گذاریم: پایتون درِ
    # `max(hi, lo, None)` می‌شکند و آن را وکتور نمی‌سازیم (تفاوتِ اعلام‌شده).
    scaled_rows = [
        {"time": "2025-01-01T00:00:00", "open": 1000.6, "high": 1010.4, "low": 990.2,
         "close": 1005.9, "last": 1006.3, "volume": 100},
        {"time": "2025-01-02", "open": 1000, "high": 999, "low": 1001, "close": 1000},
        {"time": "2025-01-03", "open": 500, "high": 520, "low": 480, "close": 510,
         "closing": 505, "last": 0, "volume": 5},
        {"time": "x", "open": 1, "high": 1, "low": 1, "close": 1},
        {"time": "2025-01-04", "open": "700", "high": 710, "low": 690, "close": 705,
         "last": 707},
        {"time": "2025-01-05", "open": 0, "high": 0, "low": 0, "close": 0,
         "last": None, "volume": None},
    ]
    scaled_factors = [
        {"time": "2025-01-01", "factor": 0},
        {"time": "2025-01-02", "factor": 0.5},
        {"time": "2025-01-03", "factor": None},
        {"time": "2025-01-04", "factor": -0.5},
        "not-a-dict",
    ]
    scaled_vols = [
        {"time": "2025-01-01", "value": 250},
        {"time": "2025-01-04", "value": None},
    ]
    data["scaled"] = {
        "rows": scaled_rows,
        "factors": scaled_factors,
        "volumes": scaled_vols,
        "basis": price_basis.current(),
        "out": ch._fts_scaled(scaled_rows, scaled_factors, scaled_vols),
    }

    # اولویتِ واقعیِ پرچم‌ها وقتی هم‌زمان روشن‌اند: حدِ ضرر + وتو + تریگر + هشدار.
    tie = synth(flags={"stop_hit": True, "ma14_exit": True, "choch_break": True,
                       "third_peak": True},
                decision="REJECT",
                jet={"active": True, "resistance": 1234.0},
                ph={"active": True, "floor_price": 1000.0, "trigger_date": "2025-03-03"})
    data["status"]["prec_tie"] = {"out": tie,
                                  "block": ch._fts_status_block(ref, tie), "series": "range"}
    stop_and_veto = synth(flags={"stop_hit": True}, decision="REJECT")
    data["status"]["prec_stop_over_veto"] = {
        "out": stop_and_veto, "block": ch._fts_status_block(ref, stop_and_veto),
        "series": "range"}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote", args.out, os.path.getsize(args.out), "bytes")
    for kind, c in data["cases"].items():
        print(kind, "swings", len(c["swings"]), "exit", c["exit"]["verdict"],
              "jet", c["jet"]["active"], c["jet"]["tier"],
              "choch", c["choch"]["label"], "point", c["point_hunt"]["touches"],
              c["point_hunt"]["active"], "dbl", c["double_bottom"]["active"],
              "box", c["range_box"]["active"], "setups", len(c["setups"]),
              "fib", c["fib"] is not None,
              "trend", c["trend_d"]["trend"], c["trend_d"]["basis"])
    for name, s in data["status"].items():
        print("status", name, s["block"]["code"], "|", s["block"]["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
