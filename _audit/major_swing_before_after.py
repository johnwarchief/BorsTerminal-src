#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/major_swing_before_after.py — رأیِ «قبل» و «بعد» رویِ یکِ سریِ کندلِ واقعی

چرا این فایل هست: مأموریت می‌گوید «خروجی جهت روند قبل و بعد را مقایسه کن» و
«ثابت کن همان قانون تعیین جهت System 1 حفظ شده و داور دوم ساخته نشده است». پس
باید **هر دو** نسخهٔ موتور رأی بدهند، نه اینکه قاعدة قبل از رویِ متن بازنویسی شود.

«قبل» از همان کامیتِ پایه می‌آید: `git show a853cc75:api/chart.py` با یکِ تبدیلِ
یک‌خطی (only `from ._core import` → `from api._core import`) در
`_scratch/base_api_chart_a853cc75.py` بارگذاری می‌شود. بی‌این، هر مقایسه‌ای فقط
توصیفِ کدِ جدید می‌بود.

خروجی (JSON + جدول):
  • جدولِ گذارِ trend برای D/W/M (up/down/range/na × قبل→بعد)
  • شمارِ نمادهایی که مبنایشان از `pivots` به `recent-window` افتاده (هشدارِ دایرۀ
      اثر: اگر داورِ دوم ساخته شده باشد، اینجا خودش را نشان می‌دهد)
  • تصمیمِ `trend.matrix` (PERMITTED/REJECT/UNKNOWN) قبل و بعد
  • چکِ ضدِّ repaint: تکانِ ±۲٪ آخرینِ کندلِ تکمیل‌نشده در نسخهٔ بعد نباید رأیِ
      قطعی را عوض کند؛ عددِ «قبل» مبنایِ همان نقصِ سنجیده‌شده است.
  • فهرستِ تک‌تکِ اختلاف‌ها با علتِ قابل‌ردیابی (کدام پیوت ماژور شمرده نشد)

این فایل فقط می‌خواند: بانکِ محلی، بی‌شبکه، بی‌نوشتن رویِ هیچ چیزی جز
`_audit/MAJOR-SWING-BEFORE-AFTER.json`.
"""
import argparse
import datetime as dt
import importlib.util
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE_SHA = "a853cc75"
BASE_FILE = os.path.join(ROOT, "_scratch", "base_api_chart_%s.py" % BASE_SHA)


def load_baseline():
    """نسخۀِ کامیتِ پایهٔ api/chart.py را به‌عنوان یک ماژولِ جدا بار می‌کند."""
    if not os.path.exists(BASE_FILE):
        raise SystemExit("baseline module missing: %s — بساز با:\n"
                         "  git show %s:api/chart.py | "
                         "python -c \"import sys;print(sys.stdin.read()"
                         ".replace('from ._core import','from api._core import',1))\" "
                         "> %s" % (BASE_FILE, BASE_SHA, BASE_FILE))
    spec = importlib.util.spec_from_file_location("base_api_chart", BASE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["base_api_chart"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--min-rows", type=int, default=160)
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit",
                                                  "MAJOR-SWING-BEFORE-AFTER.json"))
    a = ap.parse_args()

    base = load_baseline()
    import api.chart as new   # noqa: E402  (نسخۀِ همین دور)

    con = sqlite3.connect(os.path.join(ROOT, "market.db"))
    all_syms = [r[0] for r in con.execute(
        "select symbol from price_history group by symbol having count(*) >= ? "
        "and max(date) >= '2026-01-01' order by count(*) desc", (a.min_rows,))]
    con.close()
    stride = max(1, len(all_syms) // max(a.limit, 1))
    syms = all_syms[::stride][:a.limit]
    print("qualifying symbols: %d; sampled %d evenly" % (len(all_syms), len(syms)))

    rep = {"ranAt": dt.datetime.now().isoformat(timespec="seconds"),
           "baseline_sha": BASE_SHA, "symbols": 0,
           "transition": {tf: {} for tf in ("D", "W", "M")},
           "basis_shift": {"pivots_to_recent_window": 0, "both_pivots": 0,
                           "new_is_na": 0},
           "matrix": {}, "diffs": [], "nudge": {"before": 0, "after": 0,
                                                "before_pairs": {}, "after_pairs": {}},
           "provisional_only_changes": 0}

    def bump(table, key):
        table[key] = table.get(key, 0) + 1

    for sym in syms:
        try:
            pl = new.get_chart_db(sym)
        except Exception:
            continue
        if not pl or pl.get("status") != "success":
            continue
        raw = pl.get("candles") or []
        if len(raw) < a.min_rows:
            continue
        try:
            series = new._fts_scaled(new._fts_clean_candles(raw),
                                     pl.get("factors") or [], pl.get("volumes") or [])
        except Exception:
            continue
        if len(series) < a.min_rows:
            continue
        rep["symbols"] += 1
        b = base._fts_analyze_candles(sym, [dict(c) for c in series])
        n = new._fts_analyze_candles(sym, [dict(c) for c in series])
        if not isinstance(b, dict) or not isinstance(n, dict):
            continue
        row = {"symbol": sym, "rows": len(series), "changes": []}
        for tf in ("D", "W", "M"):
            vb, vn = (b["trend"].get(tf) or {}), (n["trend"].get(tf) or {})
            tb, tn = vb.get("trend"), vn.get("trend")
            bb, nb = vb.get("basis"), vn.get("basis")
            if tb != tn:
                bump(rep["transition"][tf], "%s→%s" % (tb, tn))
                row["changes"].append({"tf": tf, "from": tb, "to": tn,
                                       "from_basis": bb, "to_basis": nb,
                                       "to_reason": (n["trend"]["major_swings"][tf] or {}).get("reason"),
                                       "counts": (n["trend"]["major_swings"][tf] or {}).get("counts")})
            else:
                bump(rep["transition"][tf], "%s(same)" % tb)
            if tf == "D":
                if bb == "pivots" and nb == "recent-window":
                    rep["basis_shift"]["pivots_to_recent_window"] += 1
                elif bb == "pivots" and nb == "pivots":
                    rep["basis_shift"]["both_pivots"] += 1
                if tn == "na" and tb != "na":
                    rep["basis_shift"]["new_is_na"] += 1
        # حکمِ قیف از خودِ payload خوانده می‌شود، نه از بازنویسیِ جدول: اگر یکِ
        # طرف جدول را عوض کند، مقایسه دیگر بی‌طرف نیست.
        mb = (b["trend"].get("matrix") or {}).get("decision")
        mn = (n["trend"].get("matrix") or {}).get("decision")
        bump(rep["matrix"], "%s→%s" % (mb, mn) if mb != mn else "%s(same)" % mn)
        # تفاوتِ واقعیِ حکمِ قیف مهم‌ترین ردیفِ این گزارش است
        if mb != mn:
            wms = (n["trend"]["major_swings"]["W"] or {})
            bw = [p for p in ((b.get("structure_points") or {}).get("W") or [])
                  if p["kind"] == "high"][-2:] + \
                 [p for p in ((b.get("structure_points") or {}).get("W") or [])
                  if p["kind"] == "low"][-2:]
            row["changes"].append({
                "tf": "gate", "from": mb, "to": mn,
                "to_desc": (n["trend"].get("matrix") or {}).get("desc"),
                "weekly_basis": (n["trend"]["W"] or {}).get("basis"),
                "after_extremes": [{"kind": p["kind"], "time": p["time"], "price": p["price"],
                                    "leg_pct": p["leg_pct"], "leg_atr_x": p["leg_atr_x"]}
                                   for p in (wms.get("major_swings") or [])[-4:]],
                "before_extremes": [{"kind": p["kind"], "time": p["time"], "price": p["price"],
                                     "label": p["label"]} for p in bw]})
        if row["changes"]:
            rep["diffs"].append(row)

        # ضدِّ repaint درِ معنایِ درستش: درِ یکِ as-ofِ ثابت، تکانِ درون‌جلسۀ
        # آخرینِ کندلِ تکمیل‌نشده نباید رأیِ قطعی را عوض کند. پس مرجعِ «بعد» همان
        # سریِ تکمیل‌نشده است، نه سریِ بدونِ نشانه (بی‌این تفکیک، آزمونِ کم‌کردنِ
        # یکِ کندل را با «تکان» می‌گرفت و عددِ بی‌معنا می‌داد).
        ref_n = [dict(c) for c in series]
        ref_n[-1]["live_forming"] = True
        try:
            n_ref = new._fts_analyze_candles(sym, ref_n)
            b_ref = base._fts_analyze_candles(sym, [dict(c) for c in series])
        except Exception:
            continue
        for delta, tag in ((1.02, "+2%"), (0.98, "-2%"), (1.05, "+5%"), (0.95, "-5%")):
            nudged = [dict(c) for c in series[:-1]] + [dict(series[-1])]
            nudged[-1]["live_forming"] = True
            for kk in ("close", "high", "low"):
                nudged[-1][kk] = float(series[-1][kk]) * delta
            if nudged[-1]["high"] < nudged[-1]["low"]:
                nudged[-1]["high"], nudged[-1]["low"] = nudged[-1]["low"], nudged[-1]["high"]
            plain = [dict(c) for c in nudged]        # بی‌نشانه = دیدۀ نسخۀِ پایه
            try:
                b_n = base._fts_analyze_candles(sym, plain)
                n_n = new._fts_analyze_candles(sym, nudged)
            except Exception:
                continue
            for tf in ("D", "W"):
                x = b_n["trend"][tf]["trend"]
                if x != b_ref["trend"][tf]["trend"]:
                    rep["nudge"]["before"] += 1
                    bump(rep["nudge"]["before_pairs"],
                         "%s %s %s→%s" % (tf, tag, b_ref["trend"][tf]["trend"], x))
                y = n_n["trend"][tf]["trend"]
                if y != n_ref["trend"][tf]["trend"]:
                    rep["nudge"]["after"] += 1
                    bump(rep["nudge"]["after_pairs"],
                         "%s %s %s→%s" % (tf, tag, n_ref["trend"][tf]["trend"], y))
                    rep["diffs"].append({"symbol": sym,
                                         "changes": [{"tf": "repaint",
                                                      "from": n_ref["trend"][tf]["trend"],
                                                      "to": y, "nudge": tag}]})
            g0 = (n_ref["trend"].get("matrix") or {}).get("decision")
            g1 = (n_n["trend"].get("matrix") or {}).get("decision")
            if g0 != g1:
                rep["nudge"]["after"] += 1
                bump(rep["nudge"]["after_pairs"], "gate %s %s→%s" % (tag, g0, g1))

    print("\nsymbols compared: %d" % rep["symbols"])
    for tf in ("D", "W", "M"):
        print("trend %s transitions:" % tf)
        for k, v in sorted(rep["transition"][tf].items(), key=lambda x: -x[1]):
            if "(same)" in k:
                continue
            print("   %-18s %d" % (k, v))
    print("daily basis: pivots→recent-window %d | both pivots %d | new na %d  (of %d)"
          % (rep["basis_shift"]["pivots_to_recent_window"], rep["basis_shift"]["both_pivots"],
             rep["basis_shift"]["new_is_na"], rep["symbols"]))
    print("gate decision:")
    for k, v in sorted(rep["matrix"].items(), key=lambda x: -x[1]):
        print("   %-22s %d" % (k, v))
    print("±2%% jitter of the FORMING candle — verdict changes: before %d, after %d"
          % (rep["nudge"]["before"], rep["nudge"]["after"]))
    for k, v in sorted(rep["nudge"]["after_pairs"].items(), key=lambda x: -x[1])[:10]:
        print("   AFTER %s" % k)
    print("symbols with any change: %d" % len(rep["diffs"]))
    with io.open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("out: " + a.out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
