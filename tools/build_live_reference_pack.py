#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a full-history correction pack for the live 40-symbol reference.

Base: the proven r32b-v2 pack (827 assets, 2020+ steps).
Add:  reference-derived steps for the 40 captured assets, 2008-2026.
The pack is data; the chart engine applies it through adjustment_corrections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

TOL = 0.0005
CUTOFF = "2020-01-01"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tdate(bar):
    from datetime import timedelta
    u = bar.get("utc")
    if not u:
        return None
    s = str(u).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-pack", default=os.path.join(
        ROOT, "data", "ra365_corrections", "ra365-r32b-v2"))
    ap.add_argument("--capture", default="D:/BorsTerminal-tmp/ra365_pilot3/ra365_parity40_ref.json")
    ap.add_argument("--map", default="D:/BorsTerminal-tmp/ra365_pilot3/parity40_map.json")
    ap.add_argument("--main-db", default="C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src/market.db")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "ra365_corrections", "ra365-live40-v1"))
    args = ap.parse_args()

    base_dir = args.base_pack
    base_rows = [json.loads(l) for l in open(os.path.join(base_dir, "factors.jsonl"),
                                             encoding="utf-8") if l.strip()]
    mapping = json.load(open(args.map, encoding="utf-8"))["symbols"]
    sym_by_asset = {int(x["asset_id"]): x["symbol"] for x in mapping}
    target_ids = set(sym_by_asset)
    ref = json.load(open(args.capture, encoding="utf-8"))
    items = ref.get("items") or []

    con = sqlite3.connect("file:%s?mode=ro&immutable=1" % args.main_db,
                          uri=True, timeout=5)
    def ins_of(symbol):
        row = con.execute(
            "SELECT ins_code FROM instruments WHERE l_val18=? ORDER BY updated_at DESC LIMIT 1",
            (symbol,)).fetchone()
        return str(row[0]) if row else ""

    by_asset = {}
    for it in items:
        aid = int(it.get("asset_id", -1))
        if aid not in target_ids:
            continue
        by_asset.setdefault(aid, {})[(it.get("type"), it.get("res"))] = it.get("bars") or []

    base_max = {}
    for r in base_rows:
        aid0 = int(r.get("asset_id") or -1)
        d0 = str(r.get("effective_date") or "")
        if d0 > base_max.get(aid0, ""):
            base_max[aid0] = d0
    new_rows = []
    covered_assets = 0
    for aid, series in sorted(by_asset.items()):
        t0 = {tdate(b): b for b in series.get(("type0", "D"), []) if b.get("c") and tdate(b)}
        t7 = {tdate(b): b for b in series.get(("type7", "D"), []) if b.get("c") and tdate(b)}
        days = sorted(set(t0) & set(t7))
        if len(days) < 20:
            continue
        covered_assets += 1
        has_base = any(int(r.get("asset_id") or -1) == aid for r in base_rows)
        symbol = sym_by_asset[aid]
        ins = ins_of(symbol)
        ratios = []
        for d in days:
            c0, c7 = t0[d]["c"], t7[d]["c"]
            if c0 and c7:
                ratios.append((d, c7 / c0))
        for i in range(1, len(ratios)):
            d, cur = ratios[i]
            prev = ratios[i - 1][1]
            if prev <= 0 or cur <= 0:
                continue
            if has_base:
                bm = base_max.get(aid, "")
                if (CUTOFF <= d <= bm):
                    continue
            if abs(cur / prev - 1) <= TOL:
                continue
            step = prev / cur
            if not (1e-4 <= step <= 1e4) or abs(step - 1) < 1e-12:
                continue
            new_rows.append({
                "action": "replace_step",
                "asset_id": str(aid),
                "class": "REFERENCE_STEP",
                "confidence": "reference_live_exact",
                "correction_version": "ra365-live40-v1",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "effective_date": d,
                "err_bucket": "0",
                "event_sig": "reference",
                "fields_used": "close",
                "ins_code": ins,
                "max_field_dev": 0,
                "method": "reference_step_derivation",
                "prod_date": d,
                "prod_ratio": 1.0,
                "ratio": round(step, 12),
                "reason": "reference factor step from live Rahavard type7/type0",
                "ref_date": d,
                "ref_ratio": round(step, 12),
                "samples": 2,
                "source": "rahavard_reference_live_2026-11-06",
                "symbol": symbol,
            })

    kept = [r for r in base_rows
            if int(r.get("asset_id") or -1) not in target_ids
            or str(r.get("effective_date") or "") >= CUTOFF]
    all_rows = kept + new_rows
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "factors.jsonl"), "w", encoding="utf-8") as fh:
        for r in all_rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    raw_src = os.path.join(base_dir, "raw_ohlc.jsonl")
    raw_dst = os.path.join(args.out, "raw_ohlc.jsonl")
    if os.path.exists(raw_src):
        with open(raw_src, "rb") as a, open(raw_dst, "wb") as b:
            b.write(a.read())
    cap_sha = hashlib.sha256(open(args.capture, "rb").read()).hexdigest()
    manifest = {
        "schema": "ra365-correction-pack-v1",
        "correction_version": "ra365-live40-v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "authoritative",
        "tool": "tools/build_live_reference_pack.py",
        "reference_sha256": cap_sha,
        "source": "rahavard_reference_live_2026-11-06",
        "method": "reference_step_derivation + r32b base",
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "counts": {
            "factor_replace_step": sum(1 for r in all_rows if r.get("action") == "replace_step"),
            "factor_suppress_step": sum(1 for r in all_rows if r.get("action") == "suppress_step"),
            "raw_fields": 0,
            "factor_assets": len({str(r.get("asset_id")) for r in all_rows}),
            "factor_symbols": len({r.get("symbol") for r in all_rows if r.get("symbol")}),
        },
        "ambiguous_symbols": {},
        "as_of": "2026-11-04",
        "semantics": {
            "mode": "authoritative: for a covered symbol every product event is suppressed and the chain is built from the pack's replace_step rows",
            "replace_step": "step applied to dates before effective_date; ratio is previous/current reference factor",
            "scope": "r32b-v2 base (827 assets, 2020+) plus full-history live steps for 40 audit symbols",
        },
    }
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"out": args.out, "base_rows": len(base_rows),
                      "replaced_base": len(base_rows) - len(kept),
                      "new_rows": len(new_rows), "covered_assets": covered_assets,
                      "total_rows": len(all_rows), "manifest": manifest["counts"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
