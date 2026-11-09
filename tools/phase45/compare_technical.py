#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_technical.py — S7: SMA technical-calculation parity on identical TF/basis.

Local: the canonical adjusted series (`_fts_scaled`), resampled with the app's own
weekly (Saturday) / Jalali-month rules, and `_sma_series` — the single MA
implementation `/api/ma` serves.
Reference: Rahavard type7 (adjusted) closes, the same SMA formula applied.

Only identical formula/settings are compared: same TF, same adjusted basis, same
window. FTS rules are independent by mission rule and are not compared here.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def week_key(date_str: str) -> str:
    d = dt.date.fromisoformat(date_str[:10])
    return (d - dt.timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def month_key(date_str: str) -> str:
    import wm_calendar as WMC
    d = dt.date.fromisoformat(date_str[:10])
    jy, jm, _ = WMC.g2j(d.year, d.month, d.day)
    return f"{jy:04d}-{jm:02d}"


def closes_by_bucket(rows, keyf, value_key):
    out = {}
    for r in rows:
        out[keyf(str(r["time"])[:10])] = (r.get(value_key), str(r["time"])[:10])
    return out


def closes_by_bucket_daily(rows, value_key):
    return {str(r["time"])[:10]: (r.get(value_key), str(r["time"])[:10]) for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    args = ap.parse_args()
    args.tolerance_abs = 0.02
    args.tolerance_rel = 1e-6

    tmp = tempfile.mkdtemp(prefix="p45-tech-")
    for name in ("market.db", "user.db"):
        p = os.path.join(args.db_dir, name)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_CODAL_AUTO", "0")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    import api.chart as ch

    with open(args.symbols, encoding="utf-8-sig") as fh:
        symbols = [r["symbol"] for r in csv.DictReader(fh)]
    ref = {}
    with gzip.open(args.ref, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["adjust"] == "adjusted":
                ref.setdefault((r["symbol"], r["resolution"]), []).append(r)
    out = {"symbols": {}, "tolerance_rel": 1e-6, "tolerance_abs": 0.02,
           "note": "local values rounded to 2 decimals by _sma_series; tolerance covers input rounding"}
    for sym in symbols:
        body = ch.get_chart_db(sym)
        cands = [c for c in (body.get("candles") or []) if not c.get("live_forming")]
        scaled = ch._fts_scaled(cands, body.get("factors") or [], body.get("volumes") or [])
        scaled = [c for c in scaled if not c.get("live_forming")]
        so = {"resolutions": {}}
        for res, keyf, windows in (("D", lambda d: d[:10], (5, 20, 50, 120)),
                                   ("W", week_key, (5, 20, 52)),
                                   ("M", month_key, (5, 12))):
            local = closes_by_bucket(scaled, keyf, "close")
            ref_rows = ref.get((sym, res), [])
            rmap = {keyf(x["date"]): x["close"] for x in ref_rows}
            keys = sorted(set(local) & set(rmap))
            pairs = [(local[k][1], local[k][0], rmap[k]) for k in keys
                     if local[k][0] is not None and rmap[k] is not None]
            pairs.sort()
            loc_pairs = [(d, c) for d, c, _ in pairs]
            ref_pairs = [(d, c) for d, _, c in pairs]
            ma_local = ch._sma_series(loc_pairs, windows)
            ma_ref = ch._sma_series(ref_pairs, windows)
            st = {"common": len(pairs), "windows": {}}
            for w in windows:
                ok = bad = 0
                max_abs = 0.0
                # تفکیک «فرمول» از «ورودی»: روزی که همهٔ w closeِ پنجره با مرجع
                # یکی است، اختلافِ MA فقط می‌تواند از فرمول باشد؛ روزی که ورودی
                # متفاوت است، اختلاف به داده نسبت داده می‌شود نه به محاسبه.
                ok_same_in = bad_same_in = 0
                for i, ((d, lv), (_d2, rv)) in enumerate(
                        zip(ma_local[f"ma{w}"], ma_ref[f"ma{w}"])):
                    if lv is None or rv is None:
                        continue
                    diff = abs(float(lv) - float(rv))
                    max_abs = max(max_abs, diff)
                    same_input = all(
                        abs(float(a) - float(b)) <= max(args.tolerance_abs,
                                                        abs(float(b)) * args.tolerance_rel)
                        for _dd, a, b in pairs[max(0, i - w + 1):i + 1]
                    ) and len(pairs[max(0, i - w + 1):i + 1]) == w
                    if diff <= max(args.tolerance_abs, abs(float(rv)) * args.tolerance_rel):
                        ok += 1
                        if same_input:
                            ok_same_in += 1
                    else:
                        bad += 1
                        if same_input:
                            bad_same_in += 1
                st["windows"][str(w)] = {"ok": ok, "bad": bad, "max_abs": max_abs,
                                         "ok_same_input": ok_same_in,
                                         "bad_same_input": bad_same_in}
            so["resolutions"][res] = st
        out["symbols"][sym] = so
        print(sym, {res: {w: (v["ok"], v["bad"], round(v["max_abs"], 4))
                          for w, v in st["windows"].items()}
                    for res, st in so["resolutions"].items()}, flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    if args.md:
        lines = ["| نماد | D MA5 اوکی/بد | D MA20 | D MA50 | D MA120 | W MA5 | W MA20 | W MA52 | M MA5 | M MA12 |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for sym, so in out["symbols"].items():
            cells = []
            for res, wl in (("D", ("5", "20", "50", "120")), ("W", ("5", "20", "52")),
                            ("M", ("5", "12"))):
                st = so["resolutions"].get(res, {}).get("windows", {})
                for w in wl:
                    v = st.get(w, {})
                    cells.append(f"{v.get('ok',0)}/{v.get('bad',0)}")
            lines.append("| " + sym + " | " + " | ".join(cells) + " |")
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
