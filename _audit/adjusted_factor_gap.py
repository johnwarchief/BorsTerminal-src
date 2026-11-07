#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/adjusted_factor_gap.py — اختلافِ ضریبِ تعدیلِ ما با رهاورد، از خودِ دو سریِ ایشان.

اسنپشاتِ فریزشدۀِ `_audit/ra365_ref_bars.json` برایِ هر نماد دو سری دارد:
    type0 = خام    type7 = تعدیل‌شده (نهایی)
و نسبتِ این دو، **همان ضریبی است که رهاورد اعمال کرده**:
    ref_factor(t) = type7.close(t) / type0.close(t)
پس می‌توان ضریبِ مرجع را بی‌هیچ حدسی از دادهٔ ایشان درآورد و با ضریبِ خودی
(`AE.chain_factors` رویِ گسستِ قیمتِ پایه + تیزکردنِ دفترِ مبدأ) سطر‌به‌سطر مقایسه کرد.

سه چیز روشن می‌شود:
  ۱) مقدارِ اختلافِ ضریب درِ هر تاریخ (نسبی و مطلق)؛
  ۲) درِ کدامِ تاریخ رهاورد پله دارد و ما نداریم (رویدادِ جاافتاده)، یا برعکس
     (رویدادِ اضافیِ ما) — پله‌ها از خودِ سریِ ref_factor درآیند، نه از فهرستِ ما؛
  ۳) آیا اختلاف از ابتدایِ پنجره است یا از یکِ تاریخِ خاص شروع می‌شود.

هیچ عددی اینجا به ضریبِ ما وارد نمی‌شود و هیچ رویدادی حدس زده نمی‌شود؛ این فایل
فقط اندازه می‌گیرد و ثبت می‌کند.
"""
import csv
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "_audit"))

import api.chart as CH                       # noqa: E402
import full_universe_candle_audit as AU      # noqa: E402

REF = os.path.join(ROOT, "_audit", "ra365_ref_bars.json")
MANIFEST = os.path.join(ROOT, "_audit", "SYMBOL-AUDIT-MANIFEST.csv")
OUT = os.path.join(ROOT, "_audit", "ADJUSTED-FACTOR-GAP.csv")
OUT_EVENTS = os.path.join(ROOT, "_audit", "ADJUSTED-FACTOR-STEPS.csv")
STEP_TOL = 0.0005      # پلهٔ واقعی در ضریب؛ نویزِ گِردکردنِ منبع زیرِ این است


def bars_by_symbol():
    d = json.load(io.open(REF, encoding="utf-8"))
    out = {}
    for key, blk in (d.get("bars") or {}).items():
        parts = key.split("|")
        if len(parts) != 3 or parts[2] != "D" or not isinstance(blk, dict):
            continue
        if blk.get("status") != 200:
            continue
        import datetime as dt
        bars = {}
        for b in blk.get("bars") or []:
            if not b.get("t"):
                continue
            day = dt.datetime.fromtimestamp(b["t"] / 1000 + 3.5 * 3600,
                                            dt.timezone.utc).strftime("%Y-%m-%d")
            bars[day] = b
        out.setdefault(parts[0], {})[parts[1]] = bars
    return out


def our_factors(code, name):
    text = AU.read_source(code)
    if text is None:
        return None
    candles, _v, all_rows = CH._parse_tsetmc_csv(text)
    events, _a = CH._adjust_events_from_rows(all_rows)
    events, _sn, _an = CH._sharpen_events_with_ledger(name, events)
    times = [str(c["time"])[:10] for c in candles]
    _applied, _rejected, factors, chain, _cov = CH._canonical_adjustment(name, times, events)
    return dict(zip(times, factors)), {
        "events": len(events),
        "event_dates": sorted({p["date"] for p in (chain.get("provenance") or [])
                               if p.get("ratio") is not None}),
        "coverage_start": (_cov or {}).get("coverage_start"),
        "pre_coverage_candles": (_cov or {}).get("pre_coverage_candles"),
    }


def steps(series):
    """تاریخ‌هایی که ضریبِ مرجع درِ آن‌ها پله دارد (از خودِ سری، بی‌فهرستِ ما)"""
    days = sorted(series)
    out = []
    for a, b in zip(days, days[1:]):
        if series[a] and abs(series[b] / series[a] - 1.0) > STEP_TOL:
            out.append((b, series[b] / series[a]))
    return out


def main():
    ref = bars_by_symbol()
    with io.open(MANIFEST, encoding="utf-8-sig", newline="") as f:
        man = {r["symbol"]: r for r in csv.DictReader(f)}

    rows, evrows = [], []
    for sym, pair in sorted(ref.items()):
        raw, adj = pair.get("type0") or {}, pair.get("type7") or {}
        m = man.get(sym)
        if not raw or not adj or not m:
            rows.append({"symbol": sym, "ins_code": (m or {}).get("ins_code", ""),
                         "status": "NOT_COMPARABLE", "dates": 0, "exact": 0,
                         "le_001": 0, "le_01": 0, "le_05": 0, "gt_05": 0,
                         "max_rel": "", "first_gap_date": "", "ref_steps": 0,
                         "our_steps": 0, "ref_only_steps": 0, "our_only_steps": 0,
                         "shared_steps": 0, "our_events": "", "coverage_start": "",
                         "pre_coverage_candles": "", "note": "missing ref or manifest row"})
            continue
        ours, meta = our_factors(m["ins_code"], sym)
        if ours is None:
            rows.append({"symbol": sym, "ins_code": m["ins_code"], "status": "SOURCE_UNAVAILABLE",
                         "dates": 0, "exact": 0, "le_001": 0, "le_01": 0, "le_05": 0,
                         "gt_05": 0, "max_rel": "", "first_gap_date": "", "ref_steps": 0,
                         "our_steps": 0, "ref_only_steps": 0, "our_only_steps": 0,
                         "shared_steps": 0, "our_events": meta["events"],
                         "coverage_start": meta["coverage_start"] or "",
                         "pre_coverage_candles": meta["pre_coverage_candles"] or 0,
                         "note": "no crawled csv"})
            continue
        ref_f = {}
        for d in raw:
            if d in adj and raw[d].get("c") and adj[d].get("c"):
                ref_f[d] = adj[d]["c"] / raw[d]["c"]
        days = sorted(ref_f)
        r = {"symbol": sym, "ins_code": m["ins_code"], "status": "MEASURED",
             "dates": len(days), "exact": 0, "le_001": 0, "le_01": 0, "le_05": 0,
             "gt_05": 0, "max_rel": 0.0, "first_gap_date": "", "ref_steps": 0,
             "our_steps": 0, "ref_only_steps": 0, "our_only_steps": 0,
             "shared_steps": 0, "our_events": meta["events"],
             "coverage_start": meta["coverage_start"] or "",
             "pre_coverage_candles": meta["pre_coverage_candles"] or 0, "note": ""}
        for d in days:
            of = ours.get(d)
            if of is None:
                continue
            diff = abs(of - ref_f[d]) / ref_f[d]
            r["max_rel"] = max(r["max_rel"], diff)
            if diff <= 1e-9:
                r["exact"] += 1
            elif diff <= 1e-3:
                r["le_001"] += 1
            elif diff <= 1e-2:
                r["le_01"] += 1
            elif diff <= 5e-2:
                r["le_05"] += 1
            else:
                r["gt_05"] += 1
                if not r["first_gap_date"]:
                    r["first_gap_date"] = d
        rs = steps(ref_f)
        os_ = steps({d: ours[d] for d in days if d in ours})
        r["ref_steps"], r["our_steps"] = len(rs), len(os_)
        rd = {d for d, _ in rs}
        od = {d for d, _ in os_}
        r["shared_steps"] = len(rd & od)
        r["ref_only_steps"] = len(rd - od)
        r["our_only_steps"] = len(od - rd)
        r["max_rel"] = round(r["max_rel"], 8)
        for d, ratio in rs:
            evrows.append({"symbol": sym, "date": d, "kind": "reference_step",
                           "ref_ratio": round(ratio, 8),
                           "our_has_step": "yes" if d in od else "no",
                           "our_factor": round(ours.get(d, float("nan")), 10),
                           "ref_factor": round(ref_f[d], 10)})
        for d, ratio in os_:
            if d not in rd:
                evrows.append({"symbol": sym, "date": d, "kind": "our_only_step",
                               "ref_ratio": "", "our_has_step": "yes",
                               "our_factor": round(ours.get(d, float("nan")), 10),
                               "ref_factor": round(ref_f.get(d, float("nan")), 10)})
        rows.append(r)

    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with io.open(OUT_EVENTS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(evrows[0].keys())) if evrows else None
        if w:
            w.writeheader()
            w.writerows(evrows)

    meas = [r for r in rows if r["status"] == "MEASURED"]
    print("symbols measured: %d (of %d in snapshot)" % (len(meas), len(rows)))
    tot = {k: sum(r[k] for r in meas) for k in
           ("dates", "exact", "le_001", "le_01", "le_05", "gt_05",
            "ref_steps", "our_steps", "ref_only_steps", "our_only_steps", "shared_steps")}
    print("TOTALS " + json.dumps(tot, ensure_ascii=False))
    print("%-10s %5s %5s %6s %6s %6s %6s %9s %5s %5s %5s %5s %5s" %
          ("symbol", "dates", "exact", "<=0.1%", "<=1%", "<=5%", ">5%", "max_rel",
           "rStp", "oStp", "shared", "refOn", "ourOn"))
    for r in sorted(meas, key=lambda x: -x["gt_05"]):
        print("%-10s %5d %5d %6d %6d %6d %6d %9s %5d %5d %6d %5d %5d" %
              (r["symbol"][:9], r["dates"], r["exact"], r["le_001"], r["le_01"],
               r["le_05"], r["gt_05"], r["max_rel"], r["ref_steps"], r["our_steps"],
               r["shared_steps"], r["ref_only_steps"], r["our_only_steps"]))
    print("\nپلۀِ مرجعی که ما نداریم (نمونۀِ ۱۵):")
    for e in [x for x in evrows if x["kind"] == "reference_step" and x["our_has_step"] == "no"][:15]:
        print("  %-9s %s ref_ratio=%s our_factor=%s ref_factor=%s" %
              (e["symbol"], e["date"], e["ref_ratio"], e["our_factor"], e["ref_factor"]))
    print("\nپلۀِ ما که مرجع ندارد (نمونۀِ ۱۵):")
    for e in [x for x in evrows if x["kind"] == "our_only_step"][:15]:
        print("  %-9s %s our_factor=%s ref_factor=%s" %
              (e["symbol"], e["date"], e["our_factor"], e["ref_factor"]))
    print("\nout: " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
