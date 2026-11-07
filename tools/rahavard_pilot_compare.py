#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare our adjustment engine against a Rahavard type0/type7 capture.

The reference ratio type7/type0 is the cumulative corporate-action factor.
Our side is adjustment_engine.chain_factors() over the official typed ledger.
The raw-candle comparison is reported for information; the gate is factor
parity (<=0.1% error), matching the RA365 Round 32 method.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adjustment_corrections as AC  # noqa: E402
import adjustment_engine as AE  # noqa: E402
import corporate_ledger as L  # noqa: E402

TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.001


def tdate(bar: dict) -> str | None:
    u = bar.get("utc")
    try:
        if u:
            s = str(u).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(TEHRAN).date().isoformat()
        t = bar.get("t")
        if t:
            sec = t / 1000 if t > 1e11 else t
            return datetime.fromtimestamp(sec, tz=timezone.utc).astimezone(TEHRAN).date().isoformat()
    except Exception:
        return None
    return None


def series(items: list[dict], asset: int, typ: str, res: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for it in items:
        if int(it.get("asset_id", -1)) != asset or it.get("type") != typ or it.get("res") != res:
            continue
        for b in it.get("bars") or []:
            d = tdate(b)
            if d and b.get("c"):
                out[d] = b
    return out


def our_rows(conn, symbol: str) -> dict[str, tuple]:
    out = {}
    for d, o, h, l, c in conn.execute(
            "SELECT date, open, high, low, close FROM price_history WHERE symbol=?", (symbol,)):
        out[d] = (o, h, l, c)
    return out


def ins_code(conn, symbol: str) -> str | None:
    row = conn.execute(
        "SELECT ins_code FROM instruments WHERE l_val18=? ORDER BY updated_at DESC LIMIT 1",
        (symbol,)).fetchone()
    return str(row[0]) if row else None


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[int(q * (len(s) - 1))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--db", default="D:/BorsTerminal-data/market.db")
    ap.add_argument("--map", required=True, help="asset_id=symbol,asset_id=symbol")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "rebuild", "parity"))
    args = ap.parse_args()

    mapping = {}
    for part in args.map.split(","):
        k, v = part.split("=", 1)
        mapping[int(k.strip())] = v.strip()
    ref = json.load(open(args.ref, encoding="utf-8"))
    items = ref.get("items") or []
    conn = __import__("sqlite3").connect(args.db, timeout=20)
    os.makedirs(args.out, exist_ok=True)
    report = {"ref": args.ref, "at": datetime.now().isoformat(timespec="seconds"),
              "tol": TOL, "symbols": []}
    for asset, symbol in mapping.items():
        t0 = series(items, asset, "type0", "D")
        t7 = series(items, asset, "type7", "D")
        ours = our_rows(conn, symbol)
        days = sorted(set(t0) & set(t7) & set(ours))
        if len(days) < 20:
            report["symbols"].append({"symbol": symbol, "asset_id": asset,
                                      "status": "insufficient", "common_days": len(days)})
            continue
        ins = ins_code(conn, symbol)
        lev, _meta = L.build_typed_events(conn, ins) if ins else ([], {})
        lev, _suppressed, corr = AC.apply_factor_events(symbol, lev, ins)
        # The live chart path wraps pack rows as source_ratio; do the same here.
        lev = [e if e.get("kind") in AE.KNOWN_KINDS else
               {**e, "kind": AE.KIND_SOURCE_RATIO} for e in lev]
        fac, _prov = AE.chain_factors(days, lev)
        ref_fac_raw = {d: (t7[d]["c"] / t0[d]["c"] if t0[d].get("c") else None) for d in days}
        anchor = ref_fac_raw[days[-1]]
        ref_fac = {d: v / anchor for d, v in ref_fac_raw.items() if v}
        errs = [abs(fac[i] / ref_fac[d] - 1) for i, d in enumerate(days) if d in ref_fac]
        mism = [days[i] for i, d in enumerate(days)
                if d in ref_fac and abs(fac[i] / ref_fac[d] - 1) > TOL]
        raw_exact = sum(1 for d in days if abs(ours[d][3] - t0[d]["c"]) <= 1e-9)
        adj_errs = []
        for i, d in enumerate(days):
            ra = t7[d]["c"]
            oa = ours[d][3] * fac[i]
            if ra:
                adj_errs.append(abs(oa / ra - 1))
        sym = {
            "symbol": symbol, "asset_id": asset, "ins_code": ins,
            "common_days": len(days), "status": "ok",
            "factor_median_pct": round(statistics.median(errs) * 100, 5) if errs else None,
            "factor_p90_pct": round(pct(errs, 0.9) * 100, 5) if errs else None,
            "factor_max_pct": round(max(errs) * 100, 5) if errs else None,
            "within_tol_pct": round(100 * sum(1 for e in errs if e <= TOL) / len(errs), 3) if errs else None,
            "mismatch_days": mism[:20], "mismatch_count": len(mism),
            "raw_close_exact_pct": round(100 * raw_exact / len(days), 3),
            "adj_close_median_pct": round(statistics.median(adj_errs) * 100, 5) if adj_errs else None,
            "adj_close_within_tol_pct": round(100 * sum(1 for e in adj_errs if e <= TOL) / len(adj_errs), 3)
            if adj_errs else None,
        }
        report["symbols"].append(sym)
        print(f"{symbol:8s} days={len(days):4d} factor_med={sym['factor_median_pct']}% "
              f"p90={sym['factor_p90_pct']}% within={sym['within_tol_pct']}% "
              f"mismatch={len(mism)} raw_close_exact={sym['raw_close_exact_pct']}%")
    json_path = os.path.join(args.out, "parity-pilot3.json")
    csv_path = os.path.join(args.out, "parity-pilot3.csv")
    json.dump(report, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    rows = report["symbols"]
    if rows:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("wrote", json_path, csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
