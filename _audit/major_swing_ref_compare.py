#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/major_swing_ref_compare.py — ساختارِ روند رویِ دادهٔ خودِ منبعِ مرجع

سؤالِ این فایل (مرحلۀ ۷ دستورِ مالک): وقتی داورِ جهت فقط سقف/کفِ **ماژور** را
می‌بیند، آیا همان ساختاری را رویِ کندل‌هایِ خودِ rahavard365 می‌سازد که رویِ
کندل‌هایِ بانکِ ما می‌سازد؟

چرا این شاهدِ «ساختمانی» است نه «دیداری»:
  • ورودیِ دو طرف، دو منبعِ داده‌اند، نه دو رندرِ یکِ داده. مقایسه، *توالیِ
    Extremeهایِ ماژور* و *جهتِ اعلام‌شده* است؛ نه پیکسل.
  • تطبیقِ دیداریِ زندۀ رهاورد درِ گزارشِ دورِ قبل `NOT_OBSERVED` ماند و اینجا هم
    بدونِ دیدنِ واقعی آن وضعیت تغییر نمی‌کند — این فایل هیچ ادعایِ «چارتِ رهاورد
    همین را می‌گوید» نمی‌کند، فقط «هر دو سری را با یکِ موتورِ ثابت سنجیدیم».
  • مبنایِ قیمت: ردیف‌هایِ `type7` تعدیل‌شدۀ خودِ منبع‌اند (قراردادِ سنجشِ دورِ
    قبل: ضریبِ مرجع = type7 ÷ type0). اختلافِ سطحِ قیمتِ last/closing عمداً اینجا
    داوری نمی‌شود — خارجِ محدودهٔ این مأموریت و بازِ حل‌نشده است.

پنجرۀِ مقایسه: تقاطعِ تاریخیِ دو سری. سریِ بانک تا `max(date)` منبع برش می‌خورد
(as_ofِ واقعی، همان `_candles_upto_asof`) تا «دادۀ بیشتر» رأی را جابه‌جا نکند.

خروجی: `_audit/MAJOR-SWING-REF-COMPARE.json` + CSVِ `MATCH/MISMATCH/NOT_COMPARABLE`
اجرا: PYTHONIOENCODING=utf-8 python _audit/major_swing_ref_compare.py
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import api.chart as CH          # noqa: E402
import major_swings as MS       # noqa: E402

REF = os.path.join(ROOT, "_audit", "ra365_ref_bars.json")


def ref_candles(doc, sym, kind="D", adj="type7"):
    e = (doc.get("bars") or {}).get("%s|%s|%s" % (sym, adj, kind))
    if not e or e.get("status") != 200:
        return []
    out = []
    for b in e.get("bars") or []:
        t = str(b.get("utc") or "")[:10]
        if not t:
            continue
        try:
            o, h, l, c = (float(b[k]) for k in ("o", "h", "l", "c"))
        except (TypeError, ValueError, KeyError):
            continue
        out.append({"time": t, "open": o, "high": h, "low": l, "close": c,
                    "volume": float(b.get("v") or 0)})
    out.sort(key=lambda x: x["time"])
    return out


def read_reference_state():
    """صورتِ وضعیتِ مشاهدهٔ دیداری از سندِ بستۀِ دورِ قبل — بدونِ بازنویسیِ ادعا."""
    p = os.path.join(ROOT, "docs", "technical-indicators", "reviewed",
                     "ENGINE-1-CLOSURE-1405-07-27.md")
    if not os.path.exists(p):
        return "NO_DOC"
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    return "NOT_OBSERVED_IN_PRIOR_CLOSURE" if "NOT_OBSERVED" in txt else "UNKNOWN"


def structure(series):
    """همان مسیری که محصول می‌رود: پیوت → درجۀبندیِ ماژور → داورِ System 1."""
    cl = CH._fts_clean_candles(series)
    sw = CH._fts_swings(cl, k=CH._FTS_SWING_K)
    majors, info = MS.select(sw, cl)
    v = CH._fts_classify_trend(majors, series=cl)
    w = CH._fts_resample(cl, "W")
    sw_w = CH._fts_swings(w, k=2)
    maj_w, info_w = MS.select(sw_w, w)
    vw = CH._fts_classify_trend(maj_w, series=w)
    last2 = {"high": [x for x in majors if x["kind"] == "high"][-2:],
             "low": [x for x in majors if x["kind"] == "low"][-2:]}
    # MATCH رویِ **تاریخِ** Extremeها سنجیده می‌شود، نه رویِ قیمتِ round شده: دو
    # منبعِ تعدیل، یکِ پیوتِ یکسان را با دو عددِ ریالیِ متفاوت می‌دهند (و اختلافِ
    # ضرایبِ تعدیل درِ این مأموریت حل‌نشده و خارجِ محدوده است). پس تاریخ = توپولوژی،
    # قیمت = اطلاعِ جدا (ستونِ price_rel_pct).
    return {"bars": len(cl), "pivots": len(sw), "majors": len(majors),
            "enough": info["enough"], "reason": info["reason"],
            "trend": v.get("trend"), "basis": v.get("basis"),
            "deciding": {k: [{"time": p.get("time"), "price": round(float(p["price"]), 2),
                              "leg_pct": p.get("leg_pct")} for p in last2[k]]
                         for k in ("high", "low")},
            "deciding_times": sorted(str(p.get("time"))[:10] for k in ("high", "low")
                                     for p in last2[k]),
            "weekly_trend": vw.get("trend"), "weekly_basis": vw.get("basis"),
            "weekly_pivots": len(sw_w), "weekly_majors": len(maj_w)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-bars", type=int, default=120)
    ap.add_argument("--csv", default=os.path.join(ROOT, "_audit", "MAJOR-SWING-REF-COMPARE.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "MAJOR-SWING-REF-COMPARE.json"))
    a = ap.parse_args()

    doc = json.load(io.open(REF, encoding="utf-8"))
    syms = sorted({k.split("|")[0] for k in doc.get("bars") or {}})
    con = sqlite3.connect(os.path.join(ROOT, "market.db"))
    rep = {"ranAt": dt.datetime.now().isoformat(timespec="seconds"),
           "reference_file": os.path.relpath(REF, ROOT),
           "reference_state_prior_closure": read_reference_state(),
           "basis_note": "ردیف‌های type7 (تعدیل‌شدۀ خودِ منبع) در برابر سریِ تعدیل‌شدۀ بانک",
           "rows": [], "counts": {}}
    for sym in syms:
        rc = ref_candles(doc, sym, "D")
        if len(rc) < a.min_bars:
            rep["rows"].append({"symbol": sym, "status": "NOT_COMPARABLE",
                                "why": "source bars < %d" % a.min_bars})
            continue
        cut = rc[-1]["time"]
        try:
            pl = CH.get_chart_db(sym)
        except Exception as ex:
            rep["rows"].append({"symbol": sym, "status": "NOT_COMPARABLE",
                                "why": "db: %s" % type(ex).__name__})
            continue
        if not pl or pl.get("status") != "success":
            rep["rows"].append({"symbol": sym, "status": "NOT_COMPARABLE", "why": "db no rows"})
            continue
        ours = CH._fts_scaled(CH._fts_clean_candles(pl.get("candles") or []),
                              pl.get("factors") or [], pl.get("volumes") or [])
        ours = [c for c in ours if str(c.get("time") or "")[:10] <= cut]
        if len(ours) < a.min_bars:
            rep["rows"].append({"symbol": sym, "status": "NOT_COMPARABLE",
                                "why": "db rows in window < %d (%d)" % (a.min_bars, len(ours))})
            continue
        sr, so = structure(rc), structure(ours)
        same_dir = sr["trend"] == so["trend"] and sr["weekly_trend"] == so["weekly_trend"]
        ts, tos = set(sr["deciding_times"]), set(so["deciding_times"])
        newest_src = [p["time"] for k in ("high", "low") for p in sr["deciding"][k][-1:]]
        newest_our = [p["time"] for k in ("high", "low") for p in so["deciding"][k][-1:]]
        same_newest = newest_src == newest_our
        overlap = len(ts & tos) / float(len(ts | tos)) if (ts | tos) else 0.0
        # سه طبقه، چون دو معنا دارند: «جهت فرق دارد» نقصِ الگوریتم است، «مجموعۀ
        # Extremeها فرق دارد ولی جهت یکی است» پیامدِ **عمقِ متفاوتِ دو سری** است
        # (منبع ۶۰۱ کندل، بانک ۳۹۰-۴۴۰ درِ همان پنجره) — نه تصمیمِ تازه.
        if not same_dir:
            status = "MISMATCH"
        elif ts == tos:
            status = "MATCH"
        elif same_newest or overlap >= 0.5:
            status = "PARTIAL_SAME_DIRECTION"
        else:
            status = "MISMATCH_STRUCTURE"
        rel = []
        for k in ("high", "low"):
            for ps, po in zip(sr["deciding"][k], so["deciding"][k]):
                if ps["time"] == po["time"] and po["price"]:
                    rel.append(abs(ps["price"] - po["price"]) / po["price"])
        row = {"symbol": sym, "status": status, "window_to": cut,
               "src_bars": sr["bars"], "our_bars": so["bars"],
               "depth_delta": sr["bars"] - so["bars"], "extreme_overlap": round(overlap, 3),
               "price_rel_pct_max": round(100.0 * max(rel), 3) if rel else None,
               "source": sr, "ours": so,
               "dir_equal": sr["trend"] == so["trend"],
               "weekly_equal": sr["weekly_trend"] == so["weekly_trend"],
               "extremes_equal": ts == tos, "newest_extremes_equal": same_newest}
        if not row["dir_equal"]:
            row["why"] = "daily %s vs %s" % (sr["trend"], so["trend"])
        elif not row["weekly_equal"]:
            row["why"] = "weekly %s vs %s" % (sr["weekly_trend"], so["weekly_trend"])
        elif not row["extremes_equal"]:
            row["why"] = ("same direction; deciding set differs (source has %d more daily "
                          "bars, overlap %.2f)" % (row["depth_delta"], overlap))
        rep["rows"].append(row)
        rep["counts"][status] = rep["counts"].get(status, 0) + 1

    rep["counts"]["symbols"] = len(rep["rows"])
    print("reference state in prior closure: %s" % rep["reference_state_prior_closure"])
    print("symbols examined: %d  counts: %s" % (len(rep["rows"]), rep["counts"]))
    print("%-9s %-22s %6s %6s %8s %8s  %s" % ("symbol", "status", "srcD", "ourD",
                                               "srcW", "ourW", "note"))
    for r in rep["rows"]:
        print("%-9s %-22s %6s %6s %8s %8s  %s" % (
            r["symbol"], r["status"],
            (r.get("source") or {}).get("trend", "—"), (r.get("ours") or {}).get("trend", "—"),
            (r.get("source") or {}).get("weekly_trend", "—"),
            (r.get("ours") or {}).get("weekly_trend", "—"),
            r.get("why", r.get("reason", ""))))
    with io.open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    with io.open(a.csv, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["symbol", "status", "window_to", "src_daily", "our_daily",
                     "src_weekly", "our_weekly", "src_bars", "our_bars", "depth_delta",
                     "extreme_overlap", "price_rel_pct_max", "src_majors", "our_majors",
                     "dir_equal", "weekly_equal", "extremes_equal", "newest_extremes_equal",
                     "why"])
        for r in rep["rows"]:
            s, o = r.get("source") or {}, r.get("ours") or {}
            wr.writerow([r["symbol"], r["status"], r.get("window_to", ""),
                         s.get("trend", ""), o.get("trend", ""),
                         s.get("weekly_trend", ""), o.get("weekly_trend", ""),
                         r.get("src_bars", ""), r.get("our_bars", ""),
                         r.get("depth_delta", ""), r.get("extreme_overlap", ""),
                         r.get("price_rel_pct_max", ""),
                         s.get("majors", ""), o.get("majors", ""),
                         r.get("dir_equal", ""), r.get("weekly_equal", ""),
                         r.get("extremes_equal", ""), r.get("newest_extremes_equal", ""),
                         r.get("why", "")])
    print("out: %s\n     %s" % (a.out, a.csv))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
