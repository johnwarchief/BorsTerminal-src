#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/ra365_compare_matrix.py — ماتریسِ قابل‌اجرایِ مقایسۀِ نمودارِ روزانہ: خام و تعدیل‌شده

هرِ سطرِ این ماتریس چهارِ عددِ کنارِ هم است:
  closeِ خامِ ما | closeِ خامِ رهاورد (type0) | closeِ تعدیل‌شدهٔ ما | closeِ تعدیل‌شدهٔ رهاورد (type7)
به‌اضافۀِ ضریبِ دو طرف (`ours` از `AE.chain_factors`، `reference` از `type7 ÷ type0`) و
اختلافِ مطلق/نسبی. نمونه‌ها **تاریخ‌هایِ عادی و تاریخ‌هایِ رویدادِ تعدیل** را با هم
می‌گیرند (۳ روزِ عادیِ برگزیدہ + همۀِ روزهایِ پلۀِ ضریب درِ پنجره)، تا مقایسه فقط
رویِ «روزهایِ بی‌اثر» شلوغ نشود.

منبعِ داده: اسنپشاتِ فریزشدۀِ `_audit/ra365_ref_bars.json` (۲۹ نماد × type0/type7 × روزانہ
۶۰۱ کندل). این انتخابِ عمدی است: مقایسۀِ عددی بی‌نشستِ مرورگرِ کاربر انجام می‌شود و
هیچِ رمزِ Cookie/توکنی خوانده یا نوشته نمی‌شود. شاخۀِ زنده (نشستِ معتبر در دسترس باشد)
درِ `_audit/ra365_live.js` و `_audit/ra365_deepbars.js` هست؛ تا آن زمان وضعیتِ
مشاهدۀِ دیداریِ زنده `NOT_OBSERVED` می‌ماند و با عددِ این فایل قاطی نمی‌شود.

هیچ عددی از رهاورد به کدِ ما وارد نمی‌شود؛ این فقط می‌سنجد.
اجرا: python _audit/ra365_compare_matrix.py [--sym فولاد] [--normal 3]
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "_audit"))

import api.chart as CH                      # noqa: E402
import full_universe_candle_audit as AU     # noqa: E402

REF = os.path.join(ROOT, "_audit", "ra365_ref_bars.json")
MANIFEST = os.path.join(ROOT, "_audit", "SYMBOL-AUDIT-MANIFEST.csv")
OUT = os.path.join(ROOT, "_audit", "RA365-COMPARE-MATRIX.csv")
STEP_TOL = 5e-4


def day(ms):
    return dt.datetime.fromtimestamp(ms / 1000 + 3.5 * 3600, dt.timezone.utc).strftime("%Y-%m-%d")


def ref_bars():
    d = json.load(io.open(REF, encoding="utf-8"))
    out = {}
    for key, blk in (d.get("bars") or {}).items():
        p = key.split("|")
        if len(p) != 3 or p[2] != "D" or not isinstance(blk, dict) or blk.get("status") != 200:
            continue
        out.setdefault(p[0], {})[p[1]] = {day(b["t"]): b for b in blk.get("bars") or [] if b.get("t")}
    return out


def ours(ins_code, symbol):
    text = AU.read_source(ins_code)
    if text is None:
        return None
    cd, _v, ar = CH._parse_tsetmc_csv(text)
    ev, _a = CH._adjust_events_from_rows(ar)
    ev, _sn, _an = CH._sharpen_events_with_ledger(symbol, ev)
    times = [str(c["time"])[:10] for c in cd]
    _ap, _rj, fac, chain, _cov = CH._canonical_adjustment(symbol, times, ev)
    F = dict(zip(times, fac))
    basis = json.load(io.open(os.path.join(ROOT, "price_basis.json"), encoding="utf-8")).get("basis", "last")
    meta = PB_apply(cd)
    by = {str(c["time"])[:10]: c for c in meta}
    steps = sorted([(p["date"], p["ratio"]) for p in (chain.get("provenance") or [])
                    if p.get("ratio") is not None])
    return {"close": {d: (by[d].get("last") if basis == "last" and by[d].get("last")
                          else by[d].get("close")) for d in by},
            "raw_close": {d: by[d]["close"] for d in by},
            "factor": F, "steps": steps, "basis": basis,
            "widened": {d: by[d]["high"] for d in by}}


def PB_apply(cd):
    import price_basis as PB
    m = PB.apply_basis(cd, copy=True)
    return m["candles"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default="")
    ap.add_argument("--normal", type=int, default=3)
    ns = ap.parse_args()
    ref = ref_bars()
    man = {r["symbol"]: r for r in csv.DictReader(io.open(MANIFEST, encoding="utf-8-sig"))}

    rows = []
    for sym in sorted(ref):
        if ns.sym and ns.sym != sym:
            continue
        m = man.get(sym)
        o = ours(m["ins_code"], sym) if m else None
        if not o:
            rows.append({"symbol": sym, "date": "", "kind": "NOT_COMPARABLE",
                         "our_raw": "", "ref_raw": "", "our_adj": "", "ref_adj": "",
                         "our_factor": "", "ref_factor": "", "abs_diff": "", "rel_diff": "",
                         "note": "no crawled source for this instrument"})
            continue
        raw, adj = ref[sym].get("type0") or {}, ref[sym].get("type7") or {}
        rf = {d: adj[d]["c"] / raw[d]["c"] for d in raw if d in adj
              and raw[d].get("c") and adj[d].get("c")}
        days = sorted(rf)
        step_days = [d for d, _r in o["steps"] if d in rf]
        # تاریخ‌هایِ عادیِ برگزیدہ: پلۀِ ضریبی نداشته باشند و از انتهایِ پنجره باشند
        step_set = set(step_days)
        normal = [d for d in reversed(days) if d not in step_set][:ns.normal * 40]
        picked = set(step_days) | set(normal[:ns.normal])
        for d in sorted(picked):
            if d not in raw or d not in adj:
                continue
            our_f = o["factor"].get(d)
            our_raw_v = o["raw_close"].get(d)
            our_adj_v = our_raw_v * our_f if (our_f and our_raw_v) else None
            ref_raw_v, ref_adj_v = raw[d]["c"], adj[d]["c"]
            rel = abs(our_adj_v - ref_adj_v) / ref_adj_v if (our_adj_v and ref_adj_v) else None
            rows.append({"symbol": sym, "date": d,
                         "kind": "adjustment_step" if d in step_days else "normal",
                         "our_raw": our_raw_v, "ref_raw": ref_raw_v,
                         "our_adj": round(our_adj_v, 4) if our_adj_v else "",
                         "ref_adj": ref_adj_v,
                         "our_factor": round(our_f, 10) if our_f else "",
                         "ref_factor": round(rf[d], 10),
                         "abs_diff": round(abs(our_adj_v - ref_adj_v), 6) if our_adj_v else "",
                         "rel_diff": round(rel, 9) if rel is not None else "",
                         "note": ""})

    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    steps = [r for r in rows if r["kind"] == "adjustment_step"]
    normal = [r for r in rows if r["kind"] == "normal"]
    def band(rs):
        c = {"≤1e-9": 0, "≤0.1%": 0, "≤1%": 0, "≤5%": 0, ">5%": 0, "—": 0}
        for r in rs:
            x = r["rel_diff"]
            if x == "":
                c["—"] += 1
            elif x <= 1e-9:
                c["≤1e-9"] += 1
            elif x <= 1e-3:
                c["≤0.1%"] += 1
            elif x <= 1e-2:
                c["≤1%"] += 1
            elif x <= 5e-2:
                c["≤5%"] += 1
            else:
                c[">5%"] += 1
        return c
    print("rows: %d (steps %d, normal %d)  basis_applied=%s"
          % (len(rows), len(steps), len(normal),
             rows[0]["note"] if rows and rows[0]["kind"] == "NOT_COMPARABLE" else
             (ours(man[sorted(ref)[0]]["ins_code"], sorted(ref)[0]) or {}).get("basis")))
    print("  band(step rows) : %s" % band(steps))
    print("  band(normal rows): %s" % band(normal))
    print("\nنمونۀِ سطرهایِ پلۀِ تعدیل (۱۲):")
    for r in steps[:12]:
        print("  %-8s %s  our_adj=%-12s ref_adj=%-12s rel=%s"
              % (r["symbol"], r["date"], r["our_adj"], r["ref_adj"], r["rel_diff"]))
    print("\nنمونۀِ سطرهایِ عادی (۶):")
    for r in normal[:6]:
        print("  %-8s %s  our_raw=%-10s ref_raw=%-10s our_adj=%-12s ref_adj=%-12s rel=%s"
              % (r["symbol"], r["date"], r["our_raw"], r["ref_raw"], r["our_adj"],
                 r["ref_adj"], r["rel_diff"]))
    print("\nout: " + OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
