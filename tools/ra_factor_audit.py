# -*- coding: utf-8 -*-
"""ra_factor_audit.py — reconstruct every product factor from raw events.

Usage:
  python tools/ra_factor_audit.py --product _audit/product_live_final.jsonl --out _audit/factor_audit.json
  python tools/ra_factor_audit.py --product ... --symbol فولاد --explain 2022-08-09

For each candle date t: factor(t) = ∏ ratio(event) for events with date > t, anchored
at the last candle. The tool compares that independent product with the server's
`factors` array and reports any mismatch, plus the contributing events.
"""
import argparse, json, os, sys


def audit_record(rec):
    events = []
    for e in rec.get("adjustEvents") or []:
        try:
            d = str(e.get("date"))[:10]
            r = float(e.get("ratio"))
        except (TypeError, ValueError):
            continue
        if d and r > 0:
            events.append({"date": d, "ratio": r, "source": e.get("source")})
    factors = {str(f.get("time"))[:10]: float(f.get("factor") or 1.0)
               for f in rec.get("factors") or []}
    candles = [str(c.get("time"))[:10] for c in rec.get("candles") or []]
    mismatch = []
    for t in candles:
        f = 1.0
        for e in events:
            if e["date"] > t:
                f *= e["ratio"]
        f = round(f, 10)
        if abs(f - factors.get(t, 1.0)) > 1e-8:
            mismatch.append({"date": t, "reconstructed": f, "server": factors.get(t)})
    return {"symbol": rec.get("symbol"), "candles": len(candles), "events": len(events),
            "mismatch": len(mismatch), "first_mismatches": mismatch[:5]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--symbol", default="")
    ap.add_argument("--explain", default="")
    a = ap.parse_args()
    out = []
    explain = None
    for line in open(a.product, encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("status") != "success":
            continue
        if a.symbol and rec.get("symbol") != a.symbol:
            continue
        if a.explain:
            t = a.explain
            ev = [e for e in rec.get("adjustEvents") or []
                  if str(e.get("date"))[:10] > t]
            f = 1.0
            for e in ev:
                f *= float(e.get("ratio") or 1)
            factor = {str(x.get("time"))[:10]: float(x.get("factor") or 1)
                      for x in rec.get("factors") or []}.get(t)
            explain = {"symbol": rec.get("symbol"), "date": t,
                       "contributing_events": ev, "reconstructed": round(f, 10),
                       "server": factor}
            break
        out.append(audit_record(rec))
    if explain is not None:
        print(json.dumps(explain, ensure_ascii=False, indent=1))
        return
    bad = [r for r in out if r["mismatch"]]
    summary = {"symbols": len(out), "with_mismatch": len(bad),
               "mismatch_points": sum(r["mismatch"] for r in bad), "samples": bad[:10]}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if a.out:
        json.dump({"summary": summary, "symbols": out}, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
