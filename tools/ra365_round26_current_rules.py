#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 26: current adjustment rules on the frozen full-universe product.

The 2026-10-20 product snapshot carries raw candles and the event set
discovered by the pre-R18 engine. This tool applies the Round 25 rules to
that frozen event base (share-leg dedupe, combined-DPS official ratio) and
recomputes the factor chain, so the full universe can be measured with the
current *rules* even though a current full-history product snapshot does not
exist. It is not a substitute for a fresh end-to-end run; it isolates rules.

Usage:
  python tools/ra365_round26_current_rules.py --ref <ref_bars_v2> \
      --product <product_live_final_v4> --cohort <cohort.jsonl> \
      --db <market.db> --out <dir>
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TOL = 0.5
REL = 1e-6


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def norm(s):
    return str(s or "").strip().translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.environ["BORS_DB"] = a.db
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    import adjustment_engine as AE
    import api.chart as C
    C.DB_PATH = a.db
    os.makedirs(a.out, exist_ok=True)

    ref = {}
    for line in open(a.ref, encoding="utf-8"):
        d = json.loads(line)
        if d.get("type") not in ("type0", "type7") or d.get("res") != "D":
            continue
        aid = str(d.get("asset_id"))
        bar = {}
        for b in d.get("bars") or []:
            if isinstance(b, dict):
                dt = str(b.get("utc"))[:10]
                vals = (b.get("open"), b.get("high"), b.get("low"),
                        b.get("close"), b.get("volume"))
            else:
                dt = str(b[0])[:10]
                vals = (b[1], b[2], b[3], b[4], b[5])
            if dt:
                bar[dt] = tuple(fnum(x) for x in vals)
        ref.setdefault(aid, {})[d["type"]] = bar

    manifest = []
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        manifest.append((str(d.get("ra_asset_id")), d.get("symbol"),
                         d.get("basis") or "last"))
    by_sym = {str(sym): (aid, sym, basis) for aid, sym, basis in manifest}
    by_norm = {norm(sym): (aid, sym, basis) for aid, sym, basis in manifest}

    per_asset, rows, classes = [], Counter(), Counter()
    seen = set()
    for line in open(a.product, encoding="utf-8"):
        d = json.loads(line)
        hit = by_sym.get(str(d.get("symbol"))) or by_norm.get(norm(d.get("symbol")))
        if not hit:
            continue
        aid, canon, basis = hit
        if aid in seen or aid not in ref:
            continue
        seen.add(aid)
        t0, t7 = ref[aid].get("type0") or {}, ref[aid].get("type7") or {}
        candles = sorted(d.get("candles") or [], key=lambda c: str(c.get("time"))[:10])
        close = {}
        for c in candles:
            dt = str(c.get("time"))[:10]
            v = fnum(c.get("last")) if basis == "last" else fnum(c.get("closing"))
            v = v or fnum(c.get("close"))
            if dt and v:
                close[dt] = v
        events = [dict(e) for e in (d.get("adjustEvents") or []) if e.get("date")]
        sc = C._share_change_events(canon) if canon else []
        events, _dropped = C._drop_share_leg_of_observed_gap(events, sc)
        # combined DPS rule: official row matched by amount and date
        try:
            import sqlite3
            conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
            ins = conn.execute("select ins_code from instruments where l_val18=? limit 1",
                               (canon,)).fetchone()
            off = conn.execute(
                "select d_even,ratio,p_closing,p_closing_not_adjusted from"
                " price_adjust_event_rows where ins_code=?", (ins[0],)).fetchall() if ins else []
            conn.close()
        except Exception:
            off = []
        def d2i(x):
            return int(str(x).replace("-", ""))
        new_events = []
        for e in events:
            dps = e.get("dividend_per_share")
            if dps is not None and off:
                try:
                    dps = float(dps)
                except (TypeError, ValueError):
                    dps = None
            if dps is not None:
                cand = [o for o in off
                        if o[1] and o[2] and o[3]
                        and abs((o[3] - o[2]) - dps) <= max(0.5, 0.001 * dps)
                        and abs(o[0] - d2i(e.get("date"))) <= 45]
                if cand:
                    o = min(cand, key=lambda x: abs(x[0] - d2i(e.get("date"))))
                    oro = C._combined_dps_official_ratio(e.get("ratio"), o[1],
                                                         str(e.get("date"))[:10], sc)
                    if oro is not None:
                        e = dict(e, ratio=oro)
            new_events.append(e)
        dates = sorted(set(close) & set(t0) & set(t7))
        wrapped = [{"date": str(e["date"])[:10], "kind": AE.KIND_SOURCE_RATIO,
                    "ratio": float(e["ratio"])}
                   for e in new_events if fnum(e.get("ratio"))]
        fac_list, _ = AE.chain_factors(dates, wrapped)
        fac = dict(zip(dates, fac_list))
        fref = {dt: t7[dt][3] / t0[dt][3]
                for dt in dates if t0.get(dt) and t7.get(dt)
                and t0[dt][3] and t7[dt][3]}
        steps = []
        for prev, cur in zip(dates, dates[1:]):
            if prev not in fref or cur not in fref:
                continue
            sp = fac[prev] / fac[cur]
            sr = fref[prev] / fref[cur]
            ps, rs = abs(sp - 1) > 1e-7, abs(sr - 1) > 1e-7
            if not ps and not rs:
                continue
            cls = ("RATIO_DIFF" if ps and rs else "REF_ONLY" if rs else "EXTRA")
            if cls == "RATIO_DIFF" and abs(sr / sp - 1) <= 1e-4:
                continue
            steps.append((cur, cls))
            classes[cls] += 1
        adj_ok = 0
        for dt in dates:
            if dt not in fref:
                continue
            adj = close[dt] * fac[dt]
            refv = t7[dt][3]
            if abs(adj - refv) <= max(TOL, REL * abs(refv)):
                adj_ok += 1
            else:
                nxt = next((s for s in steps if s[0] > dt), None)
                rows[nxt[1] if nxt else "RAW_OR_BASIS"] += 1
        n = sum(1 for dt in dates if dt in fref)
        per_asset.append({"asset_id": aid, "symbol": canon, "rows": n,
                          "adjusted_ok_pct": round(100.0 * adj_ok / n, 4) if n else ""})
        rows["total"] += n
        rows["ok"] += adj_ok
    with open(os.path.join(a.out, "per-asset.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_asset[0]))
        w.writeheader(); w.writerows(per_asset)
    summary = {"assets": len(per_asset), "rows": rows["total"], "ok": rows["ok"],
               "adjusted_ok_pct": round(100.0 * rows["ok"] / max(1, rows["total"]), 4),
               "steps": dict(classes),
               "error_rows": {k: v for k, v in rows.items()
                              if k not in ("total", "ok")}}
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
